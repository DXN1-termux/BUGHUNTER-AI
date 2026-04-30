"""Shared TF-IDF-ish token scoring used by skills & exemplar retrieval."""
from __future__ import annotations
import math, re
from collections import Counter

_TOKEN = re.compile(r"[A-Za-z0-9]{2,}")


def tokens(s: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(s or "")]


def cosine(q_counts: Counter[str], d_counts: Counter[str]) -> float:
    if not q_counts or not d_counts:
        return 0.0
    dot = sum(q_counts[t] * d_counts[t] for t in q_counts if t in d_counts)
    nq = math.sqrt(sum(v * v for v in q_counts.values()))
    nd = math.sqrt(sum(v * v for v in d_counts.values()))
    return dot / (nq * nd) if nq and nd else 0.0


def rank(query: str, docs: list[tuple[str, str]], k: int = 3) -> list[tuple[float, str, str]]:
    """docs = [(id, text), ...]; returns top-k by cosine, descending."""
    q = Counter(tokens(query))
    scored = []
    for did, text in docs:
        d = Counter(tokens(text))
        scored.append((cosine(q, d), did, text))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:k]
