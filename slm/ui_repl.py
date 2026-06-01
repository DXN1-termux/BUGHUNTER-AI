"""Rich + prompt-toolkit REPL."""
from __future__ import annotations
import pathlib
import os
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from slm.agent import Agent

SLM_HOME = pathlib.Path(os.environ.get(
    "SLM_HOME", pathlib.Path.home() / ".slm"))
console = Console()

THEME = {
    "accent": "cyan",
    "section": "bold blue",
    "thought": "dim",
    "tool": "cyan",
    "result": "green",
    "final": "bold white",
    "error": "red",
}


def _ask_confirm(session: PromptSession) -> bool:
    try:
        ans = session.prompt("  [?] Proceed? [Y/n]: ").strip().lower()
        return ans in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _slash(cmd: str, agent: Agent) -> bool:
    if cmd in ("/exit", "/quit"):
        return False
    if cmd == "/clear":
        agent.history.clear()
        console.print(f"[{THEME['accent']}]history cleared[/]")
    elif cmd == "/tools":
        from slm.tools import TOOLS
        for t in TOOLS.values():
            console.print(
                f" [{THEME['accent']}]{t.name}[/]  mutating={t.mutating} scope={t.needs_scope}")
    elif cmd == "/freeze":
        (SLM_HOME / "FREEZE").touch()
        console.print(f"[{THEME['error']}]FREEZE set — all tools halted[/]")
    elif cmd == "/unfreeze":
        (SLM_HOME / "FREEZE").unlink(missing_ok=True)
        console.print(f"[{THEME['ok']}]FREEZE cleared[/]")
    elif cmd.startswith("/scope"):
        console.print((SLM_HOME / "scope.yaml").read_text())
    else:
        console.print(f"[{THEME['error']}]unknown: {cmd}[/]")
    return True


def run_repl(agent: Agent):
    hist = FileHistory(str(SLM_HOME / "history"))
    session = PromptSession(history=hist)
    console.print(Panel(
        "slm-agent  —  type /help, /tools, /scope, /freeze, /exit",
        style=THEME['section']))
    
    while True:
        try:
            line = session.prompt("you ▸ ")
        except (EOFError, KeyboardInterrupt):
            break
        if not line.strip():
            continue
        if line.startswith("/"):
            if not _slash(line.strip(), agent):
                break
            continue
            
        for e in agent.run(line):
            if e.kind == "plan":
                console.print(Panel(e.content, title="PLAN", style="magenta"))
            elif e.kind == "thought":
                console.print(Panel(e.content, title="THOUGHT", style=THEME['thought']))
            elif e.kind == "confirm":
                console.print(Panel(e.content,
                                    title=f"CONFIRM {e.meta.get('name', '')}?",
                                    style="yellow"))
                if not _ask_confirm(session):
                    console.print(f"[{THEME['error']}]denied by user[/]")
                    break
            elif e.kind == "tool_call":
                console.print(
                    Panel(
                        e.content,
                        title=f"CALL: {e.meta.get('name', '')}",
                        style=THEME['tool']))
            elif e.kind == "tool_result":
                body = e.content if len(e.content) < 1500 else e.content[:1500] + "…"
                console.print(
                    Panel(
                        body,
                        title=f"RESULT ({e.meta.get('dt', 0):.1f}s)",
                        style=THEME['result']))
            elif e.kind == "final":
                console.print(
                    Panel(Text(e.content), title="FINAL", style=THEME['final']))
            elif e.kind == "error":
                console.print(f"[{THEME['error']}]error:[/] {e.content}")
