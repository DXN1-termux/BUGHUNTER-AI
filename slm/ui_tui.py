"""TITAN Command Center - High-fidelity TUI for BUGHUNTER-AI."""
from __future__ import annotations
import asyncio
import os
import pathlib
import time
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import Header, Footer, Input, Static, Log, TabbedContent, TabPane, Label, Sparkline, Digits
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive

from slm.agent import Agent
from slm.device import detect

class SystemPulse(Static):
    """Real-time system monitoring widget."""
    DEFAULT_CSS = """
    SystemPulse {
        width: 34;
        height: 100%;
        background: #0d0d0d;
        border-right: tall #222;
        padding: 1 2;
    }
    .pulse-label { color: #555; font-size: 80%; }
    .pulse-value { color: #0f0; font-weight: bold; margin-bottom: 1; }
    .pulse-crit { color: #f00; }
    #clock { color: #0af; margin-bottom: 2; }
    """

    cpu_data = reactive([])
    ram_data = reactive([])

    def on_mount(self) -> None:
        self.device = detect()
        self.set_interval(1.0, self.update_stats)

    def update_stats(self) -> None:
        stats = self.device.get_stats()
        self.cpu_data = [*self.cpu_data[-19:], stats['cpu_load']]
        self.ram_data = [*self.ram_data[-19:], (stats['ram_used_mb'] / stats['ram_total_mb']) * 100]
        
        # Build display
        now = datetime.now().strftime("%H:%M:%S")
        self.update(
            f"[bold #0af]TITAN OS[/] v2.4\n"
            f"[dim]{now}[/]\n\n"
            f"MODEL TIER: [#f0f]{self.device.tier.upper()}[/]\n"
            f"CORES: {self.device.cores}\n\n"
            f"CPU LOAD\n"
            f"[#0f0]{stats['cpu_load']:.1f}%[/]\n\n"
            f"RAM USAGE\n"
            f"[#0f0]{stats['ram_used_mb']} / {stats['ram_total_mb']} MB[/]\n\n"
            f"STATUS: [bold #0f0]OPERATIONAL[/]"
        )

class SlmApp(App):
    TITLE = "BUGHUNTER-AI | TITAN COMMAND CENTER"
    BINDINGS = [
        Binding("ctrl+c", "quit", "Shutdown", show=True, priority=True),
        Binding("f1", "help", "Help", show=True),
        Binding("f4", "freeze", "Emergency Freeze", show=True),
        Binding("ctrl+l", "clear_logs", "Clear Logs", show=True),
    ]

    CSS = """
    Screen {
        background: #0a0a0a;
        color: #eee;
    }
    #main-layout {
        height: 100%;
    }
    #chat-log {
        background: #111;
        border: solid #222;
        height: 1fr;
    }
    #tool-log {
        background: #0a0a0a;
        color: #0c0;
        border: solid #222;
    }
    #input-container {
        height: auto;
        dock: bottom;
        padding: 1;
        background: #111;
        border-top: tall #333;
    }
    Input {
        background: #1a1a1a;
        border: solid #444;
        color: #fff;
    }
    Input:focus {
        border: double #0af;
    }
    .role-user { color: #0f0; font-weight: bold; }
    .role-agent { color: #0af; font-weight: bold; }
    .event-thought { color: #666; italic: True; }
    .event-plan { color: #f0f; bold: True; }
    .event-tool { color: #0cc; }
    .event-error { color: #f00; reverse: True; }
    """

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            yield SystemPulse()
            with TabbedContent():
                with TabPane("CORE CHAT", id="tab-chat"):
                    self.chat_log = Log(id="chat-log", highlight=True)
                    yield self.chat_log
                with TabPane("TOOL FEED", id="tab-tools"):
                    self.tool_log = Log(id="tool-log")
                    yield self.tool_log
                with TabPane("PROWLER STATS", id="tab-prowler"):
                    self.prowler_stats = Static("Initializing Prowler Subsystem...", id="prowler-view")
                    yield self.prowler_stats
                with TabPane("OPERATIONAL SCOPE", id="tab-scope"):
                    yield Static("Authorized domains and IPs defined in scope.yaml", id="scope-view")
        
        with Vertical(id="input-container"):
            self.input = Input(placeholder="COMMAND: Enter mission goal or query...")
            yield self.input
        yield Footer()

    def on_mount(self) -> None:
        self.chat_log.write("[bold #f00]TITAN KERNEL BOOTED.[/]")
        self.chat_log.write("[dim]All safety protocols engaged. Awaiting instruction...[/]")
        self.input.focus()
        
        # Start Prowler monitoring interval
        from slm.core.prowler import ProwlerEngine
        self.prowler_engine = ProwlerEngine()
        self.set_interval(5.0, self.update_prowler_ui)

    def update_prowler_ui(self) -> None:
        stats = self.prowler_engine.get_stats()
        self.prowler_stats.update(
            f"[bold #f00]TITAN PROWLER LIVE[/]\n\n"
            f"TOTAL ASSETS: [bold #0f0]{stats['total_assets']}[/]\n"
            f"VULNERABILITIES: [bold #ff0]{stats['total_vulns']}[/]\n"
            f"CRITICAL FAULTS: [bold #f00]{stats['critical_vulns']}[/]\n\n"
            f"Last Scan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        self.input.value = ""
        if not text:
            return

        if text.startswith("/"):
            self.handle_command(text)
            return

        self.chat_log.write(f"\n[role-user]USER ▸[/role-user] {text}")
        
        # Run agent in a separate thread to avoid blocking TUI
        asyncio.create_task(self.run_agent_mission(text))

    async def run_agent_mission(self, goal: str):
        try:
            # We wrap the synchronous generator in an async wrapper
            loop = asyncio.get_event_loop()
            
            def run_sync():
                return list(self.agent.run(goal))
            
            # Since Agent.run is a generator, we iterate manually
            for e in self.agent.run(goal):
                await self.post_event_to_ui(e)
                # Small sleep to allow UI to breathe
                await asyncio.sleep(0.01)
                
        except Exception as err:
            self.chat_log.write(f"[event-error]CRITICAL FAULT: {err}[/event-error]")

    async def post_event_to_ui(self, e):
        if e.kind == "thought":
            self.chat_log.write(f"[event-thought]THOUGHT:[/event-thought] {e.content}")
        elif e.kind == "plan":
            self.chat_log.write(f"[event-plan]MISSION PLAN:[/event-plan]\n{e.content}")
        elif e.kind == "tool_call":
            self.chat_log.write(f"[event-tool]EXECUTING:[/event-tool] {e.content}")
            self.tool_log.write(f"[{datetime.now().strftime('%H:%M:%S')}] CALL: {e.content}")
        elif e.kind == "tool_result":
            self.tool_log.write(f"[{datetime.now().strftime('%H:%M:%S')}] RESULT: {str(e.content)[:500]}")
        elif e.kind == "final":
            self.chat_log.write(f"\n[role-agent]TITAN ▸[/role-agent] {e.content}")
        elif e.kind == "error":
            self.chat_log.write(f"[event-error]ERROR:[/event-error] {e.content}")

    def handle_command(self, cmd: str):
        if cmd == "/clear":
            self.chat_log.clear()
            self.tool_log.clear()
        elif cmd == "/freeze":
            self.action_freeze()
        else:
            self.chat_log.write(f"[dim]Unknown command: {cmd}[/dim]")

    def action_freeze(self):
        slm_home = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
        (slm_home / "FREEZE").touch()
        self.chat_log.write("[bold red]🚨 EMERGENCY FREEZE ACTIVATED. ALL TOOLS HALTED.[/]")

    def action_clear_logs(self):
        self.chat_log.clear()
        self.tool_log.clear()

def run_tui(agent: Agent):
    app = SlmApp(agent)
    app.run()
