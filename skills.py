"""Skill library with embedding retrieval (local, lightweight).

Skills are .py files at ~/.slm/skills/<name>.py with a module-level
callable `run(**kwargs) -> str` and a top-of-file docstring used as the
retrieval key. No external embedding model needed on A52; we use a tiny
TF-IDF fallback (see slm.retrieval).
"""
from __future__ import annotations
import pathlib, os, importlib.util

from slm.retrieval import rank

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
SKILLS = SLM_HOME / "skills"


def list_skills() -> list[tuple[str, str]]:
    SKILLS.mkdir(parents=True, exist_ok=True)
    out = []
    for p in SKILLS.glob("*.py"):
        out.append((p.stem, _extract_docstring(p.read_text())))
    return out


def _extract_docstring(src: str) -> str:
    """Extract the module docstring (single- or multi-line)."""
    lines = src.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        return ""
    s = lines[i].lstrip()
    for q in ('"""', "'''"):
        if s.startswith(q):
            body = s[3:]
            if q in body:
                return body.split(q, 1)[0].strip()
            buf = [body]
            for j in range(i + 1, len(lines)):
                if q in lines[j]:
                    buf.append(lines[j].split(q, 1)[0])
                    return " ".join(x.strip() for x in buf if x.strip())
                buf.append(lines[j])
            return " ".join(x.strip() for x in buf if x.strip())
    return ""


def retrieve(query: str, k: int = 3) -> list[tuple[str, str]]:
    skills = list_skills()
    if not skills:
        return []
    docs = [(name, doc) for name, doc in skills if doc]
    if not docs:
        return []
    picks = rank(query, docs, k=k)
    return [(did, text) for score, did, text in picks if score > 0]


def run_skill(name: str, **kwargs) -> str:
    p = SKILLS / f"{name}.py"
    if not p.exists():
        return f"error: skill '{name}' not found"
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "run"):
        return f"error: skill '{name}' has no run()"
    return str(mod.run(**kwargs))
