"""SQLite session + trace log + successful-exemplar store."""
from __future__ import annotations
import os, pathlib, json, time
import sqlite_utils

from slm.retrieval import rank

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
DB = SLM_HOME / "traces.db"

# Cap trace log growth on mobile; keep the newest N rows.
MAX_EVENTS = 50_000
MAX_EXEMPLARS = 2_000


def _db():
    d = sqlite_utils.Database(DB)
    if "events" not in d.table_names():
        d["events"].create({
            "id": int, "session": str, "ts": float,
            "kind": str, "content": str, "meta": str,
        }, pk="id")
        d["events"].create_index(["session", "ts"], if_not_exists=True)
    if "exemplars" not in d.table_names():
        d["exemplars"].create({
            "id": int, "ts": float,
            "user_msg": str, "plan": str, "final": str, "ntools": int,
        }, pk="id")
        d["exemplars"].create_index(["ts"], if_not_exists=True)
    return d


def _rotate(table: str, keep: int) -> None:
    """Delete oldest rows if the table exceeds `keep`."""
    try:
        d = _db()
        n = d[table].count
        if n > keep:
            d.conn.execute(
                f"DELETE FROM {table} WHERE id IN ("
                f"  SELECT id FROM {table} ORDER BY id ASC LIMIT ?)",
                (n - keep,),
            )
    except Exception:
        pass


def log(session: str, kind: str, content: str, meta: dict):
    # Redact any vault-stored secrets from the content before persistence
    try:
        from slm.vault import redact
        content = redact(content)
    except Exception:
        pass
    _db()["events"].insert({
        "session": session, "ts": time.time(),
        "kind": kind, "content": content[:16384],
        "meta": json.dumps(meta, default=str)[:4096],
    })
    # amortized rotation: every ~200 inserts is plenty
    if int(time.time()) % 23 == 0:
        _rotate("events", MAX_EVENTS)


def replay(session: str) -> list[dict]:
    return list(_db()["events"].rows_where("session = ?", [session]))


# ----------------------------------------------------------- exemplars
def record_exemplar(user_msg: str, plan: str, final: str, ntools: int) -> None:
    """Persist a successful (user, plan, final) tuple for future few-shot."""
    if not user_msg or not final:
        return
    _db()["exemplars"].insert({
        "ts": time.time(),
        "user_msg": user_msg[:2000],
        "plan": (plan or "")[:2000],
        "final": final[:4000],
        "ntools": int(ntools),
    })
    _rotate("exemplars", MAX_EXEMPLARS)


def retrieve_exemplars(user_msg: str, k: int = 2, min_score: float = 0.15) -> list[dict]:
    """Return up to k past successful exemplars most similar to user_msg."""
    try:
        rows = list(_db()["exemplars"].rows)
    except Exception:
        return []
    if not rows:
        return []
    docs = [(str(r["id"]), r["user_msg"]) for r in rows]
    by_id = {str(r["id"]): r for r in rows}
    picks = rank(user_msg, docs, k=k)
    return [by_id[did] for score, did, _ in picks if score >= min_score]


def save_history(session: str, history: list[dict]) -> None:
    d = _db()
    if "history_snapshots" not in d.table_names():
        d["history_snapshots"].create({
            "id": int, "session": str, "ts": float, "data": str,
        }, pk="id")
    d["history_snapshots"].insert({
        "session": session,
        "ts": time.time(),
        "data": json.dumps(history, default=str)[:65536],
    })


def restore_history(session: str) -> list[dict] | None:
    d = _db()
    if "history_snapshots" not in d.table_names():
        return None
    rows = list(d["history_snapshots"].rows_where(
        "session = ? ORDER BY ts DESC LIMIT 1", [session]))
    if not rows:
        return None
    try:
        return json.loads(rows[0]["data"])
    except Exception:
        return None
