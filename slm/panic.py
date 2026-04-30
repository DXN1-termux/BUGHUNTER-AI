"""Panic / secure shred — wipe all ~/.slm/ state.

One command, zero questions, no recovery. Used when you need to ensure
NO trace of your session history, findings, vault, or canary log exists
on disk.

Two modes:
  soft : delete files with rm-equivalent (fast, recoverable by forensic tools)
  hard : overwrite with random bytes before delete (slow, best-effort secure)

Neither is a substitute for full-disk encryption. But if an adversary
has physical access and your disk is plaintext, hard shred helps.
"""
from __future__ import annotations
import os, pathlib, secrets, shutil

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))


def _random_overwrite(path: pathlib.Path, passes: int = 3) -> None:
    """Overwrite file contents with random bytes. Not a DoD-grade wipe but
    defeats casual recovery on rotational disks. On SSDs with wear-leveling
    this is best-effort only."""
    try:
        size = path.stat().st_size
    except OSError:
        return
    try:
        with path.open("r+b") as f:
            for _ in range(passes):
                f.seek(0)
                f.write(secrets.token_bytes(size))
                f.flush()
                os.fsync(f.fileno())
    except OSError:
        pass


def shred(hard: bool = False) -> dict:
    """Wipe ~/.slm/. Returns a summary dict."""
    if not SLM_HOME.exists():
        return {"deleted": 0, "message": f"{SLM_HOME} does not exist"}

    file_count = 0
    overwrite_count = 0

    # Walk + overwrite files first (if hard)
    if hard:
        for root, _, files in os.walk(SLM_HOME):
            for name in files:
                p = pathlib.Path(root) / name
                _random_overwrite(p)
                overwrite_count += 1

    # Count files before delete
    for root, _, files in os.walk(SLM_HOME):
        file_count += len(files)

    shutil.rmtree(SLM_HOME, ignore_errors=True)

    return {
        "deleted": file_count,
        "overwritten": overwrite_count,
        "path": str(SLM_HOME),
        "mode": "hard" if hard else "soft",
    }
