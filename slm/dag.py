"""Task DAG planner — decompose a goal into dependency-ordered subtasks.

Turns "recon acme.test, find bugs, write report" into:

    t1: subfinder acme.test
    t2: httpx live probe       (depends: t1)
    t3: nuclei scan            (depends: t2)
    t4: draft report           (depends: t3)

Each task has: id, title, cmd_hint, deps, status (pending/running/done/failed),
result. Persisted to ~/.slm/tasks.db so long runs survive crashes.

The planner asks the model once at the start to produce the DAG as JSON,
then the executor loop walks it in topological order, firing tasks whose
deps are all satisfied.
"""
from __future__ import annotations
import json, os, pathlib, re, time
from dataclasses import dataclass, field
from typing import Optional
import sqlite_utils

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
DB = SLM_HOME / "tasks.db"

PLAN_PROMPT = """Decompose the user's goal into a directed acyclic graph (DAG) of concrete subtasks.

Return STRICT JSON only, no prose:

{
  "goal": "<original goal, verbatim>",
  "tasks": [
    {"id": "t1", "title": "<short action>", "hint": "<which tool or skill>", "deps": []},
    {"id": "t2", "title": "<short action>", "hint": "<which tool or skill>", "deps": ["t1"]},
    ...
  ]
}

Rules:
- 2-8 tasks. More is usually too granular.
- Each task title starts with a verb.
- deps list references earlier task ids only (acyclic).
- hint names a tool (shell/subfinder/httpx/...) or skill (recon_subdomains/...).
- If the goal is a single action, produce one task.
"""


@dataclass
class Task:
    id: str
    title: str
    hint: str
    deps: list[str]
    status: str = "pending"  # pending | running | done | failed | skipped
    result: str = ""
    ts_start: float = 0.0
    ts_end: float = 0.0


def _db():
    d = sqlite_utils.Database(DB)
    if "plans" not in d.table_names():
        d["plans"].create({
            "id": int, "ts": float, "goal": str, "tasks_json": str,
            "status": str,
        }, pk="id")
    return d


def request_plan(llm, system: str, goal: str) -> dict:
    """Ask the model to produce a DAG for the given goal. Returns parsed dict."""
    raw = llm.complete(
        system + "\n\n" + PLAN_PROMPT,
        [{"role": "user", "content": f"Goal: {goal}"}],
        temperature=0.1, max_tokens=800,
    )
    # Extract JSON (tolerate code fences or prose)
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise ValueError(f"could not find JSON in plan response:\n{raw[:400]}")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"plan JSON invalid: {e}")
    if "tasks" not in data or not isinstance(data["tasks"], list):
        raise ValueError("plan missing 'tasks' list")
    return data


def save_plan(goal: str, tasks: list[Task]) -> int:
    rec = {
        "ts": time.time(),
        "goal": goal[:500],
        "tasks_json": json.dumps([t.__dict__ for t in tasks]),
        "status": "running",
    }
    return _db()["plans"].insert(rec).last_pk


def update_plan(plan_id: int, tasks: list[Task], status: str = "running"):
    _db()["plans"].update(plan_id, {
        "tasks_json": json.dumps([t.__dict__ for t in tasks]),
        "status": status,
    })


def load_plan(plan_id: int) -> tuple[str, list[Task]] | None:
    rows = list(_db()["plans"].rows_where("id = ?", [plan_id]))
    if not rows:
        return None
    r = rows[0]
    tasks = [Task(**t) for t in json.loads(r["tasks_json"])]
    return r["goal"], tasks


def _ready(tasks: list[Task]) -> list[Task]:
    """Tasks whose deps are all done."""
    done_ids = {t.id for t in tasks if t.status == "done"}
    failed_ids = {t.id for t in tasks if t.status == "failed"}
    out = []
    for t in tasks:
        if t.status != "pending":
            continue
        if any(d in failed_ids for d in t.deps):
            t.status = "skipped"
            continue
        if all(d in done_ids for d in t.deps):
            out.append(t)
    return out


def next_runnable(tasks: list[Task]) -> Optional[Task]:
    r = _ready(tasks)
    return r[0] if r else None


def is_complete(tasks: list[Task]) -> bool:
    return all(t.status in ("done", "failed", "skipped") for t in tasks)


def summary(tasks: list[Task]) -> str:
    lines = []
    icons = {"pending": "⏳", "running": "▶️", "done": "✓", "failed": "✗", "skipped": "—"}
    for t in tasks:
        ic = icons.get(t.status, "?")
        deps = ("  [deps: " + ",".join(t.deps) + "]") if t.deps else ""
        lines.append(f"  {ic} {t.id}  {t.title}{deps}")
    return "\n".join(lines)
