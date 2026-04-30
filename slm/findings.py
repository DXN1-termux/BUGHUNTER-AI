"""Persistent findings store — remembers every vulnerability the agent discovers.

Survives sessions, can be queried, and feeds back into few-shot retrieval.
Every finding is tagged with target, severity, category, CVE (if known),
PoC, and the exact session that produced it (for audit).

Public API:
    add_finding(target, title, severity, category, ...)
    list_findings(target=None, severity=None, status=None) -> list[Finding]
    mark_status(finding_id, status)   # open | triaged | reported | fixed | dup | invalid
    export_markdown(finding_id=None) -> str
"""
from __future__ import annotations
import json, os, pathlib, time
from dataclasses import dataclass, asdict
from typing import Optional
import sqlite_utils

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
DB = SLM_HOME / "findings.db"

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
STATUSES = ("open", "triaged", "reported", "fixed", "dup", "invalid")


@dataclass
class Finding:
    id: int
    ts: float
    target: str
    title: str
    severity: str
    category: str
    cve: str
    url: str
    description: str
    poc: str
    session: str
    status: str


def _db():
    d = sqlite_utils.Database(DB)
    if "findings" not in d.table_names():
        d["findings"].create({
            "id": int, "ts": float, "target": str, "title": str,
            "severity": str, "category": str, "cve": str, "url": str,
            "description": str, "poc": str, "session": str, "status": str,
        }, pk="id")
        d["findings"].create_index(["target"], if_not_exists=True)
        d["findings"].create_index(["severity"], if_not_exists=True)
        d["findings"].create_index(["status"], if_not_exists=True)
    return d


def add_finding(target: str, title: str, severity: str = "medium",
                category: str = "other", cve: str = "", url: str = "",
                description: str = "", poc: str = "",
                session: str = "manual") -> int:
    if severity not in SEVERITY_ORDER:
        severity = "medium"
    rec = {
        "ts": time.time(),
        "target": target, "title": title[:200],
        "severity": severity, "category": category,
        "cve": cve, "url": url[:500],
        "description": description[:4000], "poc": poc[:4000],
        "session": session, "status": "open",
    }
    result = _db()["findings"].insert(rec)
    fid = result.last_pk
    # Anchor in append-only hash-chain for first-finder proof
    try:
        from slm.provenance import commit
        commit(fid, target, title, description, poc)
    except Exception:
        pass
    return fid


def list_findings(*, target: Optional[str] = None,
                  severity: Optional[str] = None,
                  status: Optional[str] = None,
                  limit: int = 100) -> list[dict]:
    where = []
    params = []
    if target:
        where.append("target = ?")
        params.append(target)
    if severity:
        where.append("severity = ?")
        params.append(severity)
    if status:
        where.append("status = ?")
        params.append(status)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    q = f"SELECT * FROM findings{clause} ORDER BY ts DESC LIMIT {int(limit)}"
    return list(_db().query(q, params))


def mark_status(finding_id: int, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    _db()["findings"].update(finding_id, {"status": status})


def export_markdown(finding_id: Optional[int] = None) -> str:
    """Render findings as HackerOne-style markdown report."""
    if finding_id is not None:
        rows = list(_db()["findings"].rows_where("id = ?", [finding_id]))
    else:
        rows = sorted(_db()["findings"].rows,
                      key=lambda r: (SEVERITY_ORDER.get(r["severity"], 9), -r["ts"]))
    if not rows:
        return "*(no findings)*"

    out = ["# Bug-Bounty Findings Report", ""]
    for r in rows:
        sev_badge = {
            "critical": "🔴 CRITICAL", "high": "🟠 HIGH",
            "medium": "🟡 MEDIUM", "low": "🔵 LOW", "info": "⚪ INFO",
        }.get(r["severity"], r["severity"].upper())
        out.append(f"## [{sev_badge}] {r['title']}")
        out.append(f"- **Target:** {r['target']}")
        if r["url"]:
            out.append(f"- **URL:** {r['url']}")
        if r["cve"]:
            out.append(f"- **CVE:** `{r['cve']}`")
        out.append(f"- **Category:** {r['category']}")
        out.append(f"- **Status:** {r['status']}")
        out.append(f"- **Discovered:** {time.strftime('%Y-%m-%d', time.localtime(r['ts']))}")
        if r["description"]:
            out.append("\n### Description")
            out.append(r["description"])
        if r["poc"]:
            out.append("\n### Proof of Concept")
            out.append("```\n" + r["poc"] + "\n```")
        out.append("\n---\n")
    return "\n".join(out)


def stats() -> dict:
    """Dashboard numbers for `slm findings` output."""
    rows = list(_db()["findings"].rows)
    by_sev = {}
    by_status = {}
    targets = set()
    for r in rows:
        by_sev[r["severity"]] = by_sev.get(r["severity"], 0) + 1
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        targets.add(r["target"])
    return {
        "total": len(rows),
        "targets": len(targets),
        "by_severity": by_sev,
        "by_status": by_status,
    }
