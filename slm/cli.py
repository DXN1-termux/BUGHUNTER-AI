"""Typer CLI entry point."""
from __future__ import annotations
import os, pathlib, sys, json, tomllib
import typer
from rich.console import Console

from slm.llm import LlamaClient
from slm.agent import Agent

app = typer.Typer(add_completion=False, no_args_is_help=False)
console = Console()

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))


def _version_callback(value: bool):
    if value:
        from slm import __version__
        print(f"slm-agent {__version__}")
        raise typer.Exit()


def _cfg() -> dict:
    p = SLM_HOME / "config.toml"
    if not p.exists():
        console.print("[red]No config — run `slm init` first[/red]")
        raise typer.Exit(1)
    return tomllib.loads(p.read_text())


def _system_prompt() -> str:
    p = SLM_HOME / "system.md"
    if not p.exists():
        pkg = pathlib.Path(__file__).parent.parent / "prompts" / "system.md"
        if pkg.exists():
            return pkg.read_text()
        return "You are slm, a bug-bounty agent. Use tools to help the user."
    return p.read_text()


def _resolve_tier(m: dict) -> tuple[str, dict, str]:
    """Pick model section based on m['tier']. Returns (path, section_dict, resolved_tier)."""
    tier = m.get("tier", "auto")
    if tier == "auto":
        try:
            from slm.device import detect
            tier = detect().tier
        except Exception:
            tier = "mobile"
    section = m.get(tier, {}) if isinstance(m.get(tier), dict) else {}
    path = pathlib.Path(section.get("path", m.get("primary", ""))).expanduser()
    if not path.exists():
        for alt in (m.get("primary"), m.get("fallback")):
            if alt and pathlib.Path(alt).expanduser().exists():
                path = pathlib.Path(alt).expanduser()
                break
    return str(path), section, tier


def _make_agent(yolo: bool = False) -> Agent:
    cfg = _cfg()
    m = cfg["model"]
    model_path, section, tier = _resolve_tier(m)
    n_ctx = section.get("n_ctx", m.get("n_ctx", 1536))
    llm = LlamaClient(
        model_path=model_path,
        host=cfg["server"]["host"], port=cfg["server"]["port"],
        n_ctx=n_ctx,
        n_threads=section.get("n_threads", m.get("n_threads", 6)),
        n_batch=section.get("n_batch", m.get("n_batch", 256)),
        flash_attn=section.get("flash_attn", m.get("flash_attn", True)),
    )
    a = cfg.get("agent", {})
    return Agent(
        llm, _system_prompt(), yolo=yolo,
        skill_rag=a.get("skill_rag", True),
        plan_first=a.get("plan_first", True),
        few_shot=a.get("few_shot", True),
        reflect=a.get("reflect", "auto"),
        vote=int(a.get("vote", 1)),
        context_compress=a.get("context_compress", True),
        tier=tier, n_ctx=n_ctx,
    )


# ------------------------------------------------------------- default
@app.callback(invoke_without_command=True)
def default(ctx: typer.Context,
            prompt: list[str] = typer.Argument(None),
            tui: bool = typer.Option(False, "--tui"),
            yolo: bool = typer.Option(False, "--yolo"),
            json_out: bool = typer.Option(False, "--json"),
            version: bool = typer.Option(False, "--version", callback=_version_callback,
                                         is_eager=True)):
    if ctx.invoked_subcommand is not None:
        return
    if prompt:
        _oneshot(" ".join(prompt), yolo=yolo, json_out=json_out)
        return
    if tui:
        from slm.ui_tui import run_tui
        run_tui(_make_agent(yolo))
    else:
        from slm.ui_repl import run_repl
        run_repl(_make_agent(yolo))


def _oneshot(prompt: str, *, yolo: bool, json_out: bool):
    agent = _make_agent(yolo)
    events = []
    for e in agent.run(prompt):
        events.append({"kind": e.kind, "content": e.content, "meta": e.meta})
        if not json_out and e.kind == "final":
            console.print(e.content)
    if json_out:
        print(json.dumps(events, default=str, indent=2))


# ------------------------------------------------------------- subcommands
@app.command()
def init():
    """Write default config files if missing (non-interactive)."""
    from slm import init as _init
    _init.first_run()


@app.command()
def setup():
    """Interactive install wizard — pick model, agentic features, scope."""
    from slm.setup_wizard import run_setup
    run_setup()


@app.command("install-tools")
def install_tools():
    """Install recon tools (nmap/subfinder/httpx/nuclei/ffuf/katana).

    Reads ~/.slm/TOOLS_WANTED produced by `slm setup` and dispatches to
    the platform-appropriate package manager (pkg on Termux, apt on Debian,
    brew on macOS, winget on Windows). Falls back to `go install` where
    no package exists.
    """
    wanted_path = SLM_HOME / "TOOLS_WANTED"
    if not wanted_path.exists():
        console.print("[yellow]no TOOLS_WANTED file — run `slm setup` first[/yellow]")
        raise typer.Exit(1)
    wanted = [t.strip() for t in wanted_path.read_text().splitlines() if t.strip()]
    from slm.tool_installer import install_many
    install_many(wanted)


@app.command()
def bench():
    """60s sustained tok/s benchmark; auto-selects IQ2_XS vs IQ3_XXS."""
    from slm.bench import run_bench
    run_bench()


@app.command()
def doctor():
    """Health check."""
    from slm.doctor import run_doctor
    run_doctor()


@app.command()
def pursue(goal: list[str] = typer.Argument(...),
           cycles: int = typer.Option(5, "--cycles")):
    """Autonomous mode — keep working until the goal is satisfied."""
    agent = _make_agent(yolo=False)
    goal_text = " ".join(goal)
    for e in agent.pursue(goal_text, max_cycles=cycles):
        if e.kind == "plan":
            console.print(f"[magenta][plan][/magenta] {e.content}")
        elif e.kind == "thought":
            console.print(f"[dim][thought][/dim] {e.content}")
        elif e.kind == "confirm":
            console.print(f"[yellow][confirm][/yellow] {e.content} (non-interactive mode — auto-approving)")
        elif e.kind == "tool_call":
            console.print(f"[cyan][tool][/cyan] {e.content}")
        elif e.kind == "tool_result":
            body = e.content[:500] + ("…" if len(e.content) > 500 else "")
            console.print(f"[green][result {e.meta.get('dt',0):.1f}s][/green] {body}")
        elif e.kind == "final":
            console.print(f"[bold][final][/bold] {e.content}")
        elif e.kind == "error":
            console.print(f"[red][error][/red] {e.content}")


@app.command()
def mcp():
    """Run as a Model Context Protocol server (for Claude Desktop, Cursor, etc.)."""
    from slm.mcp_server import serve
    serve()


@app.command()
def findings(
    target: str = typer.Option(None, "--target"),
    severity: str = typer.Option(None, "--severity"),
    status: str = typer.Option(None, "--status"),
    export: str = typer.Option(None, "--export", help="Path to write markdown report"),
    show_id: int = typer.Option(None, "--id", help="Export just this finding"),
):
    """View/export discovered vulnerabilities across all sessions."""
    from slm.findings import list_findings, export_markdown, stats
    from rich.table import Table

    if export:
        md = export_markdown(show_id)
        pathlib.Path(export).write_text(md)
        console.print(f"[green]wrote {export}[/green]")
        return

    rows = list_findings(target=target, severity=severity, status=status)
    if not rows:
        console.print("[yellow]no findings yet[/yellow]")
        return

    s = stats()
    console.print(f"[bold]Findings[/bold]  total={s['total']}  targets={s['targets']}")
    console.print(f"  by severity: {s['by_severity']}")
    console.print(f"  by status: {s['by_status']}\n")

    t = Table()
    for col in ("id", "sev", "target", "title", "status", "cve"):
        t.add_column(col)
    sev_color = {"critical": "red", "high": "bright_red", "medium": "yellow",
                 "low": "blue", "info": "dim"}
    for r in rows:
        color = sev_color.get(r["severity"], "white")
        t.add_row(str(r["id"]),
                  f"[{color}]{r['severity']}[/{color}]",
                  r["target"][:30], r["title"][:50],
                  r["status"], r["cve"] or "-")
    console.print(t)


@app.command()
def replay(session: str = typer.Argument(...)):
    """Watch a past agent session play back step-by-step."""
    import time as _t
    from slm.session import replay as _replay
    events = _replay(session)
    if not events:
        console.print(f"[yellow]no events for session {session}[/yellow]")
        return
    for e in events:
        kind = e.get("kind", "")
        content = e.get("content", "")
        color = {"thought": "dim", "tool_call": "cyan", "tool_result": "green",
                 "final": "bold white", "error": "red"}.get(kind, "white")
        console.print(f"[{color}][{kind}][/{color}] {content[:200]}")
        _t.sleep(0.3)


@app.command()
def usage():
    """Show local usage stats — tokens processed, tools called, sessions run."""
    from slm.cost import format_usage
    console.print(format_usage())


@app.command("canary-log")
def canary_log():
    """Show prompt-injection attempts the canary detector has caught."""
    from slm.canary import format_log
    console.print(format_log())


@app.command()
def prove(finding_id: int = typer.Argument(...),
          out: str = typer.Option(None, "--out",
                                  help="Write proof JSON to this path"),
          witness: list[str] = typer.Option(None, "--witness",
                                            help="External witness URL (repeatable)")):
    """Export a first-finder provenance proof for a given finding."""
    from slm.provenance import export_proof
    out_path = pathlib.Path(out) if out else pathlib.Path(f"proof_{finding_id}.json")
    try:
        proof = export_proof(finding_id, out_path=out_path, witness_urls=witness)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]proof written to {out_path}[/green]")
    console.print(f"  finding_id : [cyan]{proof['finding_id']}[/cyan]")
    console.print(f"  target     : [cyan]{proof['target']}[/cyan]")
    console.print(f"  timestamp  : [cyan]{proof['timestamp_iso']}[/cyan]")
    console.print(f"  content_hash : [dim]{proof['content_hash'][:24]}...[/dim]")
    console.print(f"  entry_hash   : [dim]{proof['entry_hash'][:24]}...[/dim]")
    console.print(f"\n  Share [bold]{out_path}[/bold] with the bounty triager.")


@app.command()
def verify(proof_file: str = typer.Argument(...),
           content_file: str = typer.Option(None, "--content",
                                            help="Path to disclosed finding content (JSON with target/title/description/poc)")):
    """Verify a provenance proof (and optionally content) matches."""
    from slm.provenance import verify_proof
    proof = json.loads(pathlib.Path(proof_file).read_text())
    kwargs = {}
    if content_file:
        c = json.loads(pathlib.Path(content_file).read_text())
        kwargs = {
            "content_target": c.get("target", ""),
            "content_title": c.get("title", ""),
            "content_description": c.get("description", ""),
            "content_poc": c.get("poc", ""),
        }
    result = verify_proof(proof, **kwargs)
    color = "green" if result["valid"] else "red"
    console.print(f"[{color}]VALID = {result['valid']}[/{color}]")
    for check, val in result["checks"].items():
        icon = "✓" if val else ("✗" if val is False else "?")
        console.print(f"  {icon} {check}: {val}")


workflow_app = typer.Typer(help="Manage and run pre-built task workflows.")
app.add_typer(workflow_app, name="workflow")


@workflow_app.command("list")
def workflow_list():
    """List available workflow templates."""
    from slm.workflows import list_workflows, seed_defaults
    seed_defaults()
    wfs = list_workflows()
    if not wfs:
        console.print("[yellow]no workflows[/yellow]")
        return
    for wf in wfs:
        console.print(f"[cyan]{wf['name']}[/cyan]  {wf['description']}")
        if wf["params"]:
            console.print(f"  params: {', '.join(wf['params'])}")


@workflow_app.command("run")
def workflow_run(name: str = typer.Argument(...),
                 params: list[str] = typer.Argument(None,
                     help="key=value pairs, e.g. target=example.com")):
    """Execute a workflow by name."""
    from slm.workflows import execute
    from slm.tools import dispatch
    pdict = {}
    for p in (params or []):
        if "=" in p:
            k, v = p.split("=", 1)
            pdict[k] = v
    try:
        results = execute(name, pdict, dispatch)
    except Exception as e:
        console.print(f"[red]workflow failed: {e}[/red]")
        raise typer.Exit(1)
    for r in results:
        icon = "✓" if r["status"] == "done" else ("✗" if r["status"] == "failed" else "—")
        color = {"done": "green", "failed": "red", "skipped": "yellow"}.get(r["status"], "white")
        console.print(f"[{color}]{icon}[/{color}] {r['id']} · {r.get('title','')}")
        body = r["result"][:300] + ("…" if len(r["result"]) > 300 else "")
        console.print(f"  [dim]{body}[/dim]")


queue_app = typer.Typer(help="Background task queue for autonomous runs.")
app.add_typer(queue_app, name="queue")


@queue_app.command("add")
def queue_add(goal: list[str] = typer.Argument(...),
              cycles: int = typer.Option(5, "--cycles")):
    """Queue a goal for later execution."""
    from slm.queue import add
    qid = add(" ".join(goal), cycles=cycles)
    console.print(f"[green]queued #{qid}[/green]")


@queue_app.command("list")
def queue_list(status: str = typer.Option(None, "--status")):
    """Show queued/running/done/failed tasks."""
    from slm.queue import list_all
    from rich.table import Table
    rows = list_all(status=status)
    if not rows:
        console.print("[yellow]queue empty[/yellow]")
        return
    t = Table()
    for col in ("id", "status", "goal", "cycles"):
        t.add_column(col)
    colors = {"pending": "yellow", "running": "cyan",
              "done": "green", "failed": "red"}
    for r in rows:
        c = colors.get(r["status"], "white")
        t.add_row(str(r["id"]), f"[{c}]{r['status']}[/{c}]",
                  r["goal"][:60], str(r["cycles"]))
    console.print(t)


@queue_app.command("clear")
def queue_clear():
    """Remove done/failed tasks from the queue."""
    from slm.queue import clear_done
    n = clear_done()
    console.print(f"[green]removed {n} completed task(s)[/green]")


@app.command()
def worker(once: bool = typer.Option(False, "--once",
                                     help="Run one task then exit"),
           max_seconds: int = typer.Option(None, "--max-seconds",
                                           help="Overall budget in seconds"),
           max_tools: int = typer.Option(None, "--max-tools",
                                         help="Overall tool-call budget")):
    """Process the task queue. Use --once for a single-shot, or run
    continuously until the queue is empty."""
    from slm.queue import take_next, mark_done, mark_failed
    from slm.budget import Budget
    budget = Budget(max_seconds=max_seconds, max_tools=max_tools)
    budget.start()
    while True:
        if budget.exceeded():
            console.print(f"[yellow]budget exhausted ({budget.reason()})[/yellow]")
            break
        task = take_next()
        if not task:
            console.print("[dim]queue empty[/dim]")
            break
        console.print(f"[cyan]▶ #{task['id']}[/cyan] {task['goal']}")
        try:
            agent = _make_agent(yolo=False)
            final = ""
            ntools = 0
            for e in agent.pursue(task["goal"], max_cycles=task["cycles"]):
                if e.kind == "tool_call":
                    ntools += 1
                    budget.tick(tools=1)
                if e.kind == "final":
                    final = e.content
                if budget.exceeded():
                    break
            mark_done(task["id"], final or "(no final)")
            console.print(f"[green]✓ #{task['id']}[/green] {final[:120]}")
        except Exception as e:
            mark_failed(task["id"], f"{type(e).__name__}: {e}")
            console.print(f"[red]✗ #{task['id']}: {e}[/red]")
        if once:
            break


vault_app = typer.Typer(help="Encrypted credential vault for Discord tokens, API keys, etc.")
app.add_typer(vault_app, name="vault")


def _prompt_pass(prompt_text: str = "passphrase: ") -> str:
    try:
        import getpass
        return getpass.getpass(prompt_text)
    except Exception:
        return input(prompt_text)


@vault_app.command("unlock")
def vault_unlock():
    """Unlock the vault for the current session (auto-locks after 15 min idle)."""
    from slm.vault import unlock, VaultWrongPassphrase
    p = _prompt_pass()
    try:
        unlock(p)
        console.print("[green]vault unlocked[/green]")
    except VaultWrongPassphrase:
        console.print("[red]wrong passphrase[/red]")
        raise typer.Exit(1)


@vault_app.command("lock")
def vault_lock():
    """Wipe the in-memory key."""
    from slm.vault import lock
    lock()
    console.print("[green]vault locked[/green]")


@vault_app.command("set")
def vault_set(name: str = typer.Argument(...),
              value: str = typer.Argument(None,
                  help="If omitted, reads stdin securely (recommended)")):
    """Store a secret. Leave value blank and paste it when prompted for safety."""
    from slm.vault import set_secret, VaultLocked
    if value is None:
        value = _prompt_pass(f"value for {name} (hidden): ")
    if not value:
        console.print("[red]empty value rejected[/red]")
        raise typer.Exit(1)
    try:
        set_secret(name, value)
    except VaultLocked:
        console.print("[red]vault locked — run `slm vault unlock` first[/red]")
        raise typer.Exit(1)
    console.print(f"[green]stored {name}[/green]")


@vault_app.command("list")
def vault_list():
    """List secret names (never the raw values)."""
    from slm.vault import list_secrets, VaultLocked
    try:
        rows = list_secrets()
    except VaultLocked:
        console.print("[red]vault locked[/red]")
        raise typer.Exit(1)
    if not rows:
        console.print("[yellow]empty vault[/yellow]")
        return
    from rich.table import Table
    t = Table()
    for col in ("name", "length", "preview"):
        t.add_column(col)
    for r in rows:
        t.add_row(r["name"], str(r["length"]), r["preview"])
    console.print(t)


@vault_app.command("delete")
def vault_delete(name: str = typer.Argument(...)):
    """Remove a secret."""
    from slm.vault import delete_secret, VaultLocked
    try:
        ok = delete_secret(name)
    except VaultLocked:
        console.print("[red]vault locked[/red]")
        raise typer.Exit(1)
    if ok:
        console.print(f"[green]deleted {name}[/green]")
    else:
        console.print(f"[yellow]no such secret: {name}[/yellow]")


discord_app = typer.Typer(help="Discord bot runner (scope-gated 24/7 moderation).")
app.add_typer(discord_app, name="discord")


@discord_app.command("start")
def discord_start():
    """Start the Discord bot. Requires vault unlocked + DISCORD_BOT_TOKEN set +
    discord_scope.yaml with authorized guilds."""
    from slm.discord_bot import start
    try:
        start()
    except Exception as e:
        console.print(f"[red]discord error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def ask_cloud(provider: str = typer.Argument(..., help="anthropic | openai"),
              prompt: list[str] = typer.Argument(...),
              model: str = typer.Option(None, "--model"),
              max_tokens: int = typer.Option(1024, "--max-tokens")):
    """Forward a single prompt to an external LLM (using vault credentials)."""
    from slm.api_passthrough import call
    result = call(provider, " ".join(prompt), model=model, max_tokens=max_tokens)
    console.print(result)


@app.command()
def panic(hard: bool = typer.Option(False, "--hard",
                                    help="Overwrite files with random bytes before delete")):
    """🚨 Wipe ALL ~/.slm/ state (vault, findings, traces, canary log, everything).

    No confirmation — hit this only when you mean it. Pair with --hard for
    random-overwrite passes before deletion.
    """
    from slm.panic import shred
    result = shred(hard=hard)
    console.print(f"[red]shredded {result['deleted']} file(s)[/red] "
                  f"({result['mode']} mode)")
    if result.get("overwritten"):
        console.print(f"  overwrote {result['overwritten']} file(s) with random bytes")


@app.command()
def uninstall(purge: bool = typer.Option(False, "--purge")):
    """Remove ~/.slm/ after confirmation."""
    if not typer.confirm(f"Remove {SLM_HOME} entirely?"):
        raise typer.Exit()
    import shutil
    shutil.rmtree(SLM_HOME, ignore_errors=True)
    prefix_bin = pathlib.Path(os.environ.get("PREFIX", "/usr/local")) / "bin" / "slm"
    prefix_bin.unlink(missing_ok=True)
    console.print("[green]uninstalled[/green]")


@app.command("install-snowflake")
def install_snowflake():
    """Build the Snowflake connector (rust toolchain required)."""
    os.environ["CARGO_NET_GIT_FETCH_WITH_CLI"] = "true"
    os.execv(sys.executable, [sys.executable, "-m", "pip", "install",
                              "--no-cache-dir", "snowflake-connector-python<4"])


if __name__ == "__main__":
    app()
