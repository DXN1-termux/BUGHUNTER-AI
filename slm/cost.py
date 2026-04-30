"""Local usage stats.

Tracks tokens processed, sessions run, and tools invoked on your device.
No cost — this all runs free on your own hardware. The "would have cost X
on cloud" line at the bottom is just a fun comparison for context, not a
feature you need to use.

Everything local, everything free, always.
"""
from __future__ import annotations
import json, os, pathlib, time
import sqlite_utils

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
DB = SLM_HOME / "usage.db"

# Purely comparative — what the same tokens would cost on cloud (Apr 2026).
# Shown as a footer line, not the main metric.
CLOUD_PRICES = {
    "gpt-4o":            (0.005, 0.015),
    "claude-sonnet-4.5": (0.003, 0.015),
}


def _db():
    d = sqlite_utils.Database(DB)
    if "sessions" not in d.table_names():
        d["sessions"].create({
            "id": int, "ts": float, "session": str,
            "input_tokens": int, "output_tokens": int,
            "ntools": int, "duration_s": float,
        }, pk="id")
    return d


def track(session: str, input_tokens: int, output_tokens: int,
          ntools: int, duration_s: float) -> None:
    _db()["sessions"].insert({
        "ts": time.time(), "session": session,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "ntools": int(ntools),
        "duration_s": float(duration_s),
    })


def usage_stats() -> dict:
    rows = list(_db()["sessions"].rows)
    total_in = sum(r["input_tokens"] for r in rows)
    total_out = sum(r["output_tokens"] for r in rows)
    total_tools = sum(r["ntools"] for r in rows)
    total_time = sum(r["duration_s"] for r in rows)
    avg_tok_s = (total_out / total_time) if total_time > 0 else 0.0
    # Rolling-average of last 10 sessions for "recent" rate
    recent = sorted(rows, key=lambda r: r["ts"])[-10:]
    recent_out = sum(r["output_tokens"] for r in recent)
    recent_time = sum(r["duration_s"] for r in recent)
    recent_tok_s = (recent_out / recent_time) if recent_time > 0 else 0.0
    # Peak session tok/s
    peak_tok_s = max(
        (r["output_tokens"] / r["duration_s"]
         for r in rows if r["duration_s"] > 0),
        default=0.0,
    )
    cloud_equiv = {}
    for model, (pin, pout) in CLOUD_PRICES.items():
        cloud_equiv[model] = round((total_in / 1000) * pin + (total_out / 1000) * pout, 2)
    return {
        "sessions": len(rows),
        "input_tokens": total_in,
        "output_tokens": total_out,
        "tools_called": total_tools,
        "compute_seconds": total_time,
        "avg_tok_s": round(avg_tok_s, 1),
        "recent_tok_s": round(recent_tok_s, 1),
        "peak_tok_s": round(peak_tok_s, 1),
        "cloud_equivalent_usd": cloud_equiv,
    }


def format_usage() -> str:
    s = usage_stats()
    if s["sessions"] == 0:
        return "No sessions yet — run `slm` to start tracking usage."
    lines = [
        "📊 Local usage stats",
        "",
        f"   sessions run       : {s['sessions']:,}",
        f"   tokens processed   : {s['input_tokens']:,} in / {s['output_tokens']:,} out",
        f"   tools called       : {s['tools_called']:,}",
        f"   compute time       : {s['compute_seconds']:.1f}s",
        "",
        f"   ⚡ avg tok/s        : {s['avg_tok_s']}",
        f"   ⚡ recent tok/s     : {s['recent_tok_s']}  (last 10 sessions)",
        f"   ⚡ peak tok/s       : {s['peak_tok_s']}",
        "",
        f"   cost to you        : $0.00 (100% local, always)",
        "",
        "   for reference only — same tokens on cloud would've been:",
    ]
    for model, cost in s["cloud_equivalent_usd"].items():
        lines.append(f"     {model:20}  ~${cost:.2f}")
    return "\n".join(lines)
