"""Rich + prompt-toolkit REPL."""
from __future__ import annotations
import pathlib, os
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from slm.agent import Agent

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
console = Console()


def _ask_confirm() -> bool:
    try:
        ans = input("  proceed? [Y/n] ").strip().lower()
        return ans in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _slash(cmd: str, agent: Agent) -> bool:
    if cmd in ("/exit", "/quit"):
        return False
    if cmd == "/clear":
        agent.history.clear()
        console.print("[dim]history cleared[/dim]")
    elif cmd == "/tools":
        from slm.tools import TOOLS
        for t in TOOLS.values():
            console.print(f" [cyan]{t.name}[/cyan]  mutating={t.mutating} scope={t.needs_scope}")
    elif cmd == "/freeze":
        (SLM_HOME / "FREEZE").touch()
        console.print("[red]FREEZE set — all tools halted[/red]")
    elif cmd == "/unfreeze":
        (SLM_HOME / "FREEZE").unlink(missing_ok=True)
        console.print("[green]FREEZE cleared[/green]")
    elif cmd.startswith("/scope"):
        console.print((SLM_HOME / "scope.yaml").read_text())
    else:
        console.print(f"[yellow]unknown: {cmd}[/yellow]")
    return True


def run_repl(agent: Agent):
    hist = FileHistory(str(SLM_HOME / "history"))
    session = PromptSession(history=hist)
    console.print(Panel.fit(
        "slm-agent  —  type /help, /tools, /scope, /freeze, /exit",
        style="bold blue"))
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
                console.print(Panel(e.content, title="plan", style="magenta"))
            elif e.kind == "thought":
                console.print(Panel(e.content, title="thought", style="dim"))
            elif e.kind == "confirm":
                console.print(Panel(e.content,
                                    title=f"confirm {e.meta.get('name','')}?",
                                    style="yellow"))
                ans = _ask_confirm()
                if not ans:
                    console.print("[yellow]denied by user[/yellow]")
                    break
            elif e.kind == "tool_call":
                console.print(Panel(e.content, title=f"tool: {e.meta.get('name','')}",
                                    style="cyan"))
            elif e.kind == "tool_result":
                body = e.content if len(e.content) < 1500 else e.content[:1500] + "…"
                console.print(Panel(body,
                                    title=f"result ({e.meta.get('dt',0):.1f}s)",
                                    style="green"))
            elif e.kind == "final":
                console.print(Panel(Text(e.content), title="final", style="bold white"))
            elif e.kind == "error":
                console.print(f"[red]error:[/red] {e.content}")
