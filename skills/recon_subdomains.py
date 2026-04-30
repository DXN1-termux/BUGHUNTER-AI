"""Subdomain enumeration and live-host probing.

Enumerates subdomains of a target domain using subfinder, then probes for
live HTTP(S) hosts with httpx. Returns a sorted list of live URLs.
"""
from __future__ import annotations


def run(domain: str, **kwargs) -> str:
    from slm.tools import dispatch
    subs_raw = dispatch("subfinder", {"target": domain})
    if subs_raw.startswith("error"):
        return subs_raw

    subdomains = [s.strip() for s in subs_raw.splitlines() if s.strip()]
    if not subdomains:
        return f"No subdomains found for {domain}"

    live = []
    for sub in subdomains:
        result = dispatch("httpx", {"target": sub})
        if result and not result.startswith("error"):
            for line in result.splitlines():
                if line.strip():
                    live.append(line.strip())

    if not live:
        return f"Found {len(subdomains)} subdomains but none responded to HTTP probing"

    live.sort()
    return (
        f"Live hosts for {domain} ({len(live)}/{len(subdomains)} responding):\n"
        + "\n".join(f"  {h}" for h in live)
    )
