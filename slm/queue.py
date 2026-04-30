"""Task queue — schedule goals for later / background execution.

Use case: "Queue recon for these 10 domains, come back in 2 hours."

    slm queue add "recon acme.test and find bugs"
    slm queue add "recon beta.test and find bugs"
    slm queue list
    slm worker    # process the queue in the foreground

The worker pops one task, runs it via `agent.pursue()`, logs the trace and
any findings into findings.db / traces.db, then moves to the next. Crashes
are survivable — an interrupted task resumes on the next worker start.
"""
from __future__ import annotations
import os, pathlib, time
from dataclasses import dataclass
import sqlite_utils

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
DB = SLM_HOME / "queue.db"


def _db():
    d = sqlite_utils.Database(DB)
    if "tasks" not in d.table_names():
        d["tasks"].create({
            "id": int, "ts_added": float, "ts_started": float, "ts_done": float,
            "goal": str, "status": str, "cycles": int,
            "result": str, "error": str,
        }, pk="id")
        d["tasks"].create_index(["status"], if_not_exists=True)
    return d


def add(goal: str, cycles: int = 5) -> int:
    return _db()["tasks"].insert({
        "ts_added": time.time(),
        "ts_started": 0.0,
        "ts_done": 0.0,
        "goal": goal[:500],
        "status": "pending",
        "cycles": cycles,
        "result": "",
        "error": "",
    }).last_pk


def list_all(status: str | None = None, limit: int = 50) -> list[dict]:
    q = "SELECT * FROM tasks"
    if status:
        q += " WHERE status = ?"
        rows = list(_db().query(q + f" ORDER BY ts_added DESC LIMIT {int(limit)}", [status]))
    else:
        rows = list(_db().query(q + f" ORDER BY ts_added DESC LIMIT {int(limit)}"))
    return rows


def take_next() -> dict | None:
    d = _db()
    rows = list(d.query("SELECT * FROM tasks WHERE status = 'pending' "
                        "ORDER BY ts_added ASC LIMIT 1"))
    if not rows:
        return None
    task = rows[0]
    d["tasks"].update(task["id"], {"status": "running", "ts_started": time.time()})
    return task


def mark_done(task_id: int, result: str) -> None:
    _db()["tasks"].update(task_id, {
        "status": "done",
        "ts_done": time.time(),
        "result": result[:4000],
    })


def mark_failed(task_id: int, error: str) -> None:
    _db()["tasks"].update(task_id, {
        "status": "failed",
        "ts_done": time.time(),
        "error": error[:1000],
    })


def remove(task_id: int) -> None:
    _db()["tasks"].delete(task_id)


def clear_done() -> int:
    d = _db()
    before = d["tasks"].count
    d.conn.execute("DELETE FROM tasks WHERE status IN ('done', 'failed')")
    return before - d["tasks"].count
