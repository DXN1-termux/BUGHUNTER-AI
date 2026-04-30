"""Best-effort installer for recon tools across platforms."""
from __future__ import annotations
import platform, shutil, subprocess, os
from rich.console import Console

console = Console()


def _which(b: str) -> bool:
    return bool(shutil.which(b))


def _run(cmd: list[str]) -> bool:
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    try:
        r = subprocess.run(cmd, check=False)
        return r.returncode == 0
    except FileNotFoundError:
        return False


def _detect_pm() -> str:
    # Order matters: prefer native package manager
    if os.environ.get("PREFIX", "").endswith("com.termux/files/usr"):
        return "pkg"
    if _which("apt-get"):
        return "apt"
    if _which("brew"):
        return "brew"
    if _which("pacman"):
        return "pacman"
    if _which("dnf"):
        return "dnf"
    if _which("winget"):
        return "winget"
    return "unknown"


def _install_one(tool: str, pm: str) -> bool:
    if _which(tool):
        console.print(f"[green]  ✓ {tool} already installed[/green]")
        return True
    cmd_map = {
        "pkg": {
            "nmap":      ["pkg", "install", "-y", "nmap"],
            "subfinder": ["go", "install", "-v",
                          "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"],
            "httpx":     ["go", "install", "-v",
                          "github.com/projectdiscovery/httpx/cmd/httpx@latest"],
            "nuclei":    ["go", "install", "-v",
                          "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"],
            "ffuf":      ["go", "install", "-v",
                          "github.com/ffuf/ffuf/v2@latest"],
            "katana":    ["go", "install",
                          "github.com/projectdiscovery/katana/cmd/katana@latest"],
        },
        "apt": {
            "nmap":      ["sudo", "apt-get", "install", "-y", "nmap"],
            "subfinder": ["go", "install", "-v",
                          "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"],
            "httpx":     ["go", "install", "-v",
                          "github.com/projectdiscovery/httpx/cmd/httpx@latest"],
            "nuclei":    ["go", "install", "-v",
                          "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"],
            "ffuf":      ["sudo", "apt-get", "install", "-y", "ffuf"],
            "katana":    ["go", "install",
                          "github.com/projectdiscovery/katana/cmd/katana@latest"],
        },
        "brew": {
            "nmap":      ["brew", "install", "nmap"],
            "subfinder": ["brew", "install", "subfinder"],
            "httpx":     ["brew", "install", "httpx"],
            "nuclei":    ["brew", "install", "nuclei"],
            "ffuf":      ["brew", "install", "ffuf"],
            "katana":    ["brew", "install", "katana"],
        },
        "pacman": {
            "nmap":      ["sudo", "pacman", "-S", "--noconfirm", "nmap"],
            "ffuf":      ["sudo", "pacman", "-S", "--noconfirm", "ffuf"],
        },
        "dnf": {
            "nmap":      ["sudo", "dnf", "install", "-y", "nmap"],
        },
        "winget": {
            "nmap":      ["winget", "install", "--id", "Insecure.Nmap"],
        },
    }
    cmd = cmd_map.get(pm, {}).get(tool)
    if not cmd:
        console.print(f"[yellow]  no install recipe for {tool} on {pm}; "
                      f"try `go install` manually[/yellow]")
        return False
    ok = _run(cmd)
    console.print(f"  {'[green]✓[/green]' if ok else '[red]✗[/red]'} {tool}")
    return ok


def install_many(tools: list[str]) -> None:
    pm = _detect_pm()
    console.print(f"[cyan]package manager:[/cyan] {pm}")
    if pm == "unknown":
        console.print("[red]no supported package manager found; install tools manually[/red]")
        return
    failures = []
    for t in tools:
        if not _install_one(t, pm):
            failures.append(t)
    if failures:
        console.print(f"[yellow]failed: {', '.join(failures)}[/yellow]")
    else:
        console.print("[green]all requested tools installed[/green]")
