"""Discord bot runner — 24/7 authorized-server moderation.

Hooks into Discord via a bot token stored in the vault. Scope-gated: only
operates on server IDs listed in ~/.slm/discord_scope.yaml.

Example scope file:
    authorized_guilds:
      - name: my-server
        id: "123456789012345678"
        allowed_channels:          # optional; if present, only these channels
          - "987654321098765432"
        mod_mode: "reply"          # reply | delete | mute | react

    forbidden_phrases:             # immediate removal (in addition to hard blocks)
      - "discord.gg/"              # no invite links
      - "nitro giveaway"

All messages pass through the hard-block layer (CSAM etc. blocked
unconditionally). The bot never joins a new server without you adding it
to the scope file first.

Usage:
    slm vault set DISCORD_BOT_TOKEN <token>
    echo "authorized_guilds: []" > ~/.slm/discord_scope.yaml
    # edit ~/.slm/discord_scope.yaml to add your server
    slm discord start
"""
from __future__ import annotations
import asyncio, json, os, pathlib, time
from typing import Any
import yaml

from slm.core.executor_guards import check_hard_blocks, HardBlockError

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
SCOPE = SLM_HOME / "discord_scope.yaml"
LOG = SLM_HOME / "discord_audit.jsonl"


class DiscordUnauthorized(PermissionError):
    pass


def _load_scope() -> dict:
    if not SCOPE.exists():
        raise DiscordUnauthorized(
            f"{SCOPE} does not exist — create it with authorized_guilds list"
        )
    return yaml.safe_load(SCOPE.read_text()) or {}


def _authorized_guild(scope: dict, guild_id: int) -> dict | None:
    for g in scope.get("authorized_guilds", []) or []:
        if str(g.get("id")) == str(guild_id):
            return g
    return None


def _audit(event: str, meta: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.time(), "event": event, "meta": meta}
    with LOG.open("a") as f:
        f.write(json.dumps(rec, default=str) + "\n")


async def run_bot() -> None:
    try:
        import discord
    except ImportError:
        raise RuntimeError("discord.py not installed. Run: pip install 'discord.py>=2.3'")

    from slm.vault import get_secret, is_unlocked
    if not is_unlocked():
        raise RuntimeError("vault locked — run: slm vault unlock")
    token = get_secret("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN not in vault. Run: slm vault set DISCORD_BOT_TOKEN <token>")

    scope = _load_scope()
    forbidden = [p.lower() for p in scope.get("forbidden_phrases", []) or []]

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = False  # don't need member list
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        _audit("ready", {"user": str(client.user), "guilds": [g.id for g in client.guilds]})
        # Leave any guild not in scope — never act on unauthorized servers
        for g in list(client.guilds):
            if _authorized_guild(scope, g.id) is None:
                _audit("leaving_unauthorized", {"guild": g.id, "name": g.name})
                await g.leave()
        print(f"✓ Discord bot online as {client.user}")
        print(f"  authorized guilds: {[g.id for g in client.guilds]}")

    @client.event
    async def on_message(msg):
        if msg.author.bot or msg.guild is None:
            return
        g = _authorized_guild(scope, msg.guild.id)
        if g is None:
            return  # silently ignore — not in scope

        # Channel restriction
        allowed = g.get("allowed_channels")
        if allowed and str(msg.channel.id) not in [str(c) for c in allowed]:
            return

        content = msg.content or ""

        # Hard blocks: CSAM, terrorism, etc. — delete unconditionally + optional ban
        try:
            check_hard_blocks(content, where=f"discord:{msg.guild.id}:{msg.channel.id}")
        except HardBlockError as e:
            _audit("hard_block_delete", {
                "guild": msg.guild.id, "channel": msg.channel.id,
                "author": msg.author.id, "category": e.category,
            })
            try:
                await msg.delete()
                await msg.channel.send(
                    f"🛑 Message from <@{msg.author.id}> removed (policy: {e.category}).",
                    delete_after=30,
                )
            except discord.Forbidden:
                pass

            # Escalate for the 4 criminal categories: immediate ban from
            # the guild. Adult-content policy blocks only remove the
            # message. Opt-in via scope config: auto_ban_on_hard_block.
            criminal = e.category in ("csam", "terrorism", "cbrn", "mass_harm")
            if criminal and g.get("auto_ban_on_hard_block", True):
                try:
                    await msg.guild.ban(
                        msg.author,
                        reason=f"slm-agent hard-block:{e.category}",
                        delete_message_days=1,
                    )
                    _audit("auto_ban", {
                        "guild": msg.guild.id, "author": msg.author.id,
                        "category": e.category,
                    })
                except discord.Forbidden:
                    _audit("ban_forbidden", {
                        "guild": msg.guild.id, "author": msg.author.id,
                    })
                except Exception as ex:
                    _audit("ban_error", {"err": f"{type(ex).__name__}: {ex}"})
            return

        # Server-specific forbidden phrases
        lower = content.lower()
        for bad in forbidden:
            if bad in lower:
                _audit("forbidden_phrase_delete", {
                    "guild": msg.guild.id, "channel": msg.channel.id,
                    "author": msg.author.id, "phrase": bad,
                })
                try:
                    await msg.delete()
                except discord.Forbidden:
                    pass
                return

        # If mod_mode=reply, optionally route to the agent for Q&A (only when @mentioned)
        if g.get("mod_mode") == "reply" and client.user in msg.mentions:
            prompt = content.replace(f"<@{client.user.id}>", "").strip()
            if not prompt:
                return
            try:
                reply = _ask_agent(prompt)
                if reply:
                    # Also block on outbound content
                    check_hard_blocks(reply, where="discord_outbound")
                    await msg.reply(reply[:1900])
            except HardBlockError as e:
                await msg.reply(f"(policy block: {e.category})")
            except Exception as e:
                _audit("reply_error", {"err": f"{type(e).__name__}: {e}"})

    await client.start(token)


def _ask_agent(prompt: str) -> str:
    """One-shot agent call for a Discord reply."""
    try:
        from slm.cli import _make_agent
        agent = _make_agent(yolo=False)
        final = ""
        for e in agent.run(prompt):
            if e.kind == "final":
                final = e.content
        return final or "(no response)"
    except Exception as e:
        return f"(agent error: {type(e).__name__})"


def start() -> None:
    """Blocking entrypoint for `slm discord start`."""
    asyncio.run(run_bot())
