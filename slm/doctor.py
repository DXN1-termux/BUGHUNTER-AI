"""Health / diagnostic checks."""
from __future__ import annotations
import os, pathlib, shutil, sys, subprocess
from rich.console import Console

console = Console()
SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
CORE = SLM_HOME / "core"


def _chk(label: str, ok: bool, detail: str = ""):
    icon = "[green]\u2713[/green]" if ok else "[red]\u2717[/red]"
    console.print(f" {icon} {label}  {detail}")


def run_doctor():
    # Device tier
    try:
        from slm.device import detect
        dev = detect()
        _chk(f"device tier: {dev.tier}", True,
             detail=f"({dev.platform}, {dev.ram_mb} MB RAM, "
                    f"{dev.cores} cores, gpu={dev.has_gpu})")
    except Exception as e:
        _chk("device tier", False, detail=str(e))

    try:
        _is_termux = (os.uname().sysname == "Linux" and "Android" in
                      subprocess.run(["uname", "-o"], capture_output=True,
                                     text=True, timeout=5).stdout)
    except Exception:
        _is_termux = False
    _chk("Termux", _is_termux)
    _chk("aarch64", os.uname().machine in ("aarch64", "arm64"))
    free_mb = shutil.disk_usage(str(pathlib.Path.home())).free // (1024 * 1024)
    _chk(f"disk free ({free_mb} MB)", free_mb > 500)
    for b in ("llama-cli", "llama-server", "llama-bench"):
        _chk(f"bin/{b}", (SLM_HOME / "bin" / b).exists())
    for t in ("nmap", "subfinder", "httpx", "nuclei", "ffuf"):
        _chk(f"tool {t}", bool(shutil.which(t)) or (SLM_HOME / "bin" / t).exists())
    _chk("Termux:API", bool(shutil.which("termux-clipboard-get")),
         detail="install from F-Droid if missing")
    _core_files = list(CORE.rglob("*")) if CORE.exists() else []
    _chk("core chmod 444",
         bool(_core_files) and all(
             oct(p.stat().st_mode)[-3:] in ("444", "555") for p in _core_files),
         detail="" if _core_files else "core dir missing")
    _chk("FREEZE not set", not (SLM_HOME / "FREEZE").exists())
    py = subprocess.run([sys.executable, "-V"], capture_output=True, text=True).stdout.strip()
    _chk(f"python {py}", True)
    try:
        import snowflake.connector  # noqa
        _chk("snowflake-connector", True)
    except Exception:
        _chk("snowflake-connector", False, detail="optional — `slm install-snowflake`")
