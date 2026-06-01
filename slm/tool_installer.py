"""Best-effort installer for recon tools across platforms."""
from __future__ import annotations
import platform
import shutil
import subprocess
import os
import sys
from rich.console import Console

console = Console()

# Theme consistent with setup wizard
THEME = {
    "accent": "cyan",
    "ok": "green",
    "err": "red",
    "warn": "yellow",
    "dim": "dim",
}


def _which(b: str) -> bool:
    return bool(shutil.which(b))


def _run(cmd: list[str]) -> bool:
    console.print(f"[{THEME['dim']}]$ {' '.join(cmd)}[/]")
    try:
        # Use shell=True only on Windows for winget/choco, otherwise False
        r = subprocess.run(
            cmd,
            check=False,
            shell=(sys.platform == "win32"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        return r.returncode == 0
    except FileNotFoundError:
        return False


def _detect_pm() -> str:
    if sys.platform == "win32":
        if _which("winget"):
            return "winget"
        if _which("choco"):
            return "choco"
        return "windows_manual"
    if sys.platform == "darwin":
        if _which("brew"):
            return "brew"
    if os.environ.get("PREFIX", "").endswith("com.termux/files/usr"):
        return "pkg"
    if _which("apt-get"):
        return "apt"
    if _which("pacman"):
        return "pacman"
    if _which("dnf"):
        return "dnf"
    return "unknown"


def _check_go() -> bool:
    if _which("go"):
        return True
    console.print(f"[{THEME['warn']}]  Go not found; 'go install' will fail.[/]")
    return False


def _install_one(tool: str, pm: str) -> bool:
    if _which(tool):
        console.print(f"[{THEME['ok']}]  ✅ {tool} already installed[/]")
        return True
    
    # Pre-check for Go
    if tool in ["subfinder", "httpx", "nuclei", "ffuf", "katana"] and not _check_go():
        return False

    cmd_map = {
        "pkg": {
            "nmap": ["pkg", "install", "-y", "nmap"],
            "subfinder": [
                "go",
                "install",
                "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
            ],
            "httpx": ["go", "install", "github.com/projectdiscovery/httpx/cmd/httpx@latest"],
            "nuclei": [
                "go",
                "install",
                "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
            ],
            "ffuf": ["go", "install", "github.com/ffuf/ffuf/v2@latest"],
            "katana": [
                "go",
                "install",
                "github.com/projectdiscovery/katana/cmd/katana@latest",
            ],
        },
        "apt": {
            "nmap": ["sudo", "apt-get", "install", "-y", "nmap"],
            "ffuf": ["sudo", "apt-get", "install", "-y", "ffuf"],
            "subfinder": [
                "go",
                "install",
                "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
            ],
            "httpx": ["go", "install", "github.com/projectdiscovery/httpx/cmd/httpx@latest"],
            "nuclei": [
                "go",
                "install",
                "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
            ],
            "katana": [
                "go",
                "install",
                "github.com/projectdiscovery/katana/cmd/katana@latest",
            ],
        },
        "brew": {
            "nmap": ["brew", "install", "nmap"],
            "subfinder": ["brew", "install", "subfinder"],
            "httpx": ["brew", "install", "httpx"],
            "nuclei": ["brew", "install", "nuclei"],
            "ffuf": ["brew", "install", "ffuf"],
            "katana": ["brew", "install", "katana"],
        },
        "winget": {
            "nmap": ["winget", "install", "--id", "Insecure.Nmap"],
            "ffuf": ["winget", "install", "--id", "ffuf.ffuf"],
        },
        "choco": {
            "nmap": ["choco", "install", "nmap", "-y"],
            "ffuf": ["choco", "install", "ffuf", "-y"],
        }
    }
    
    cmd = cmd_map.get(pm, {}).get(tool)
    if not cmd:
        console.print(f"[{THEME['warn']}]  No recipe for {tool} on {pm}[/]")
        return False
        
    console.print(f"[{THEME['accent']}]  Installing {tool}...[/]")
    ok = _run(cmd)
    if ok:
        console.print(f"[{THEME['ok']}]  ✅ {tool} installed[/]")
    else:
        console.print(f"[{THEME['err']}]  ❌ {tool} failed to install[/]")
    return ok


def install_many(tools: list[str]) -> None:
    pm = _detect_pm()
    console.print(f"[{THEME['accent']}]Package manager detected:[/] {pm}")
    if pm == "unknown" or pm == "windows_manual":
        console.print(f"[{THEME['err']}]Manual installation required for this platform.[/]")
        return
    failures = []
    for t in tools:
        if not _install_one(t, pm):
            failures.append(t)
    if failures:
        console.print(f"[{THEME['warn']}]Failed to install: {', '.join(failures)}[/]")
    else:
        console.print(f"[{THEME['ok']}]All requested tools installed[/]")
