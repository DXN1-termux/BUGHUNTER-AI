"""Textual full-screen TUI (optional, `slm --tui`)."""
from __future__ import annotations
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Static
from textual.containers import Horizontal, Vertical
from slm.agent import Agent


class SlmApp(App):
    CSS = """
    #side  { width: 32; border: solid grey; }
    #log   { border: solid grey; }
    #input { dock: bottom; }
    """
    BINDINGS = [("ctrl+c", "quit"), ("f4", "freeze")]

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            self.log = RichLog(id="log", highlight=True, markup=True)
            self.side = Static(" ▸ tools\n ▸ skills\n ▸ scope\n ▸ traces",
                               id="side")
            yield self.log
            yield self.side
        self.input = Input(placeholder="ask or /command …", id="input")
        yield self.input
        yield Footer()

    def on_input_submitted(self, msg: Input.Submitted):
        text = msg.value.strip()
        self.input.value = ""
        if not text:
            return
        self.log.write(f"[bold]you ▸[/bold] {text}")
        for e in self.agent.run(text):
            self.log.write(f"[dim]{e.kind}[/dim] {e.content[:400]}")

    def action_freeze(self):
        import pathlib, os
        (pathlib.Path(os.environ.get("SLM_HOME",
                                     pathlib.Path.home() / ".slm")) / "FREEZE").touch()
        self.log.write("[red]FREEZE set[/red]")


def run_tui(agent: Agent):
    SlmApp(agent).run()
