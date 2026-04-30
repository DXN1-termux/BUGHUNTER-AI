"""Wordlist manager — auto-fetch common bug-bounty wordlists on demand.

Downloads from the official SecLists repo into ~/.slm/wordlists/.
Caches locally so repeat calls are instant. Names are stable across
machines so skills can reference `wordlist('common')` and get the same
list everywhere.
"""
from __future__ import annotations
import os, pathlib
import httpx

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
WORDLISTS = SLM_HOME / "wordlists"

RAW = "https://raw.githubusercontent.com/danielmiessler/SecLists/master"

CATALOG = {
    "common":           f"{RAW}/Discovery/Web-Content/common.txt",
    "big":              f"{RAW}/Discovery/Web-Content/big.txt",
    "raft-small-words": f"{RAW}/Discovery/Web-Content/raft-small-words.txt",
    "api-endpoints":    f"{RAW}/Discovery/Web-Content/api/api-endpoints.txt",
    "subdomains-top1m": f"{RAW}/Discovery/DNS/subdomains-top1million-5000.txt",
    "nginx-default":    f"{RAW}/Discovery/Web-Content/CMS/nginx.txt",
    "admin-panels":     f"{RAW}/Discovery/Web-Content/AdminPanels.fuzz.txt",
    "passwords-top1k":  f"{RAW}/Passwords/Common-Credentials/10-million-password-list-top-1000.txt",
    "xss-payloads":     f"{RAW}/Fuzzing/XSS/XSS-Jhaddix.txt",
    "sqli-payloads":    f"{RAW}/Fuzzing/SQLi/Generic-SQLi.txt",
    "lfi-payloads":     f"{RAW}/Fuzzing/LFI/LFI-Jhaddix.txt",
    "user-agents":      f"{RAW}/Fuzzing/User-Agents/UserAgents.fuzz.txt",
}


def run(name: str = "common", force: bool = False, **kwargs) -> str:
    """Download a wordlist by name. Returns the local path."""
    if name == "list":
        return "Available wordlists:\n" + "\n".join(
            f"  {n:20}  {u.rsplit('/', 1)[-1]}" for n, u in CATALOG.items()
        )
    if name not in CATALOG:
        return f"error: unknown wordlist '{name}'. Try 'list' for the catalog."

    WORDLISTS.mkdir(parents=True, exist_ok=True)
    out = WORDLISTS / f"{name}.txt"
    if out.exists() and not force:
        size = out.stat().st_size
        lines = sum(1 for _ in out.open())
        return f"cached at {out} ({size:,} bytes, {lines:,} lines)"

    url = CATALOG[name]
    try:
        r = httpx.get(url, timeout=60, follow_redirects=True)
        r.raise_for_status()
        out.write_bytes(r.content)
        lines = sum(1 for _ in out.open())
        return f"downloaded {out} ({len(r.content):,} bytes, {lines:,} lines)"
    except Exception as e:
        return f"error: download failed: {type(e).__name__}: {e}"
