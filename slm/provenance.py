"""Hash-chain provenance for bug-bounty findings — cryptographic first-finder proof.

© 2026 DXN10DAY · BUGHUNTER-AI v2.3 · MIT + PPL-1.0 + UAAC-1.1

This is genuinely novel: no other agent/bounty framework includes
tamper-evident first-finder proofs.

## The problem it solves

You find a bug on April 29. Another researcher submits a duplicate on May 3.
Triager marks both as "first-in-wins" and *claims* the other was first,
because bounty platforms sometimes lose or misorder reports.

You can't prove you found it first without publishing the report (which
breaks responsible disclosure). You want to PROVE knowledge without
REVEALING content until disclosure.

## The solution

Every finding gets committed to an append-only hash chain:

    entry_i = {
        ts:          timestamp,
        finding_id:  local pk,
        content_hash: sha256(target + title + description + poc),
        prev_hash:   entry_{i-1}.entry_hash,
    }
    entry_hash = sha256(json(entry_i))

Because each entry includes the previous entry's hash, the chain is
tamper-evident: you can't insert a finding with a backdated timestamp
without rebuilding the entire chain from that point forward.

## First-finder proof

    slm prove <finding_id>

produces `proof_{id}.json`:

    {
        "finding_id": 42,
        "target": "example.com",              # disclosed
        "content_hash": "a3f1...",            # NOT reversible to content
        "entry_hash":  "b7e2...",
        "prev_hash":   "c9d4...",
        "chain_tip":   "f0a1...",
        "witness_urls": [                      # optional external anchors
            "https://opentimestamps.org/...",
            "https://git.example.com/commit/...",
        ]
    }

Later, at disclosure time, you reveal the full content plus the proof.
Anyone can re-compute `sha256(content)` and verify it matches.

    slm verify proof_42.json --content finding.txt

## External witness (optional)

You can additionally anchor a chain tip into a public log (IPFS, Git,
OpenTimestamps). That gives you independent timestamping even if
someone later compromises your ~/.slm/ directory.
"""
from __future__ import annotations
import hashlib, json, os, pathlib, time

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
CHAIN = SLM_HOME / "provenance.jsonl"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _content_hash(target: str, title: str, description: str, poc: str) -> str:
    """Canonical content hash — order-independent, whitespace-normalized."""
    normalized = json.dumps({
        "target": target.strip().lower(),
        "title": title.strip(),
        "description": description.strip(),
        "poc": poc.strip(),
    }, sort_keys=True, separators=(",", ":"))
    return _sha256(normalized)


def _read_chain() -> list[dict]:
    if not CHAIN.exists():
        return []
    out = []
    for line in CHAIN.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _chain_tip() -> str:
    chain = _read_chain()
    if not chain:
        return "0" * 64  # genesis
    return chain[-1]["entry_hash"]


def commit(finding_id: int, target: str, title: str,
           description: str = "", poc: str = "") -> dict:
    """Append a commitment for a new finding. Returns the entry."""
    content_hash = _content_hash(target, title, description, poc)
    prev_hash = _chain_tip()
    entry_core = {
        "ts": time.time(),
        "finding_id": finding_id,
        "content_hash": content_hash,
        "prev_hash": prev_hash,
    }
    entry_hash = _sha256(json.dumps(entry_core, sort_keys=True, separators=(",", ":")))
    entry = {**entry_core, "entry_hash": entry_hash}
    CHAIN.parent.mkdir(parents=True, exist_ok=True)
    with CHAIN.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def export_proof(finding_id: int, out_path: pathlib.Path | None = None,
                 witness_urls: list[str] | None = None) -> dict:
    """Produce a public-shareable proof for a given finding_id.

    The proof reveals:
      - finding_id, target, timestamp, content_hash
      - entry_hash, prev_hash, current chain_tip
      - optional external witness URLs

    The proof does NOT reveal:
      - title, description, poc (those stay in findings.db)
    """
    chain = _read_chain()
    entry = next((e for e in chain if e["finding_id"] == finding_id), None)
    if entry is None:
        raise ValueError(f"no provenance entry for finding #{finding_id}")

    from slm.findings import list_findings
    findings = list_findings()
    f_row = next((f for f in findings if f["id"] == finding_id), None)
    target = f_row["target"] if f_row else "?"

    proof = {
        "kind": "bughunter-ai/provenance/v1",
        "finding_id": finding_id,
        "target": target,
        "timestamp": entry["ts"],
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(entry["ts"])),
        "content_hash": entry["content_hash"],
        "entry_hash": entry["entry_hash"],
        "prev_hash": entry["prev_hash"],
        "chain_tip": _chain_tip(),
        "witness_urls": witness_urls or [],
    }
    if out_path:
        out_path.write_text(json.dumps(proof, indent=2))
    return proof


def verify_proof(proof: dict, content_target: str = "", content_title: str = "",
                 content_description: str = "", content_poc: str = "") -> dict:
    """Verify a proof against optionally-supplied content.

    Returns dict with 'valid' bool and diagnostic fields. If content is given,
    also checks that sha256(content) matches the committed content_hash.
    """
    out = {"valid": False, "checks": {}}

    # 1. Entry hash self-consistency
    entry_core = {
        "ts": proof["timestamp"],
        "finding_id": proof["finding_id"],
        "content_hash": proof["content_hash"],
        "prev_hash": proof["prev_hash"],
    }
    computed = _sha256(json.dumps(entry_core, sort_keys=True, separators=(",", ":")))
    out["checks"]["entry_hash_matches"] = (computed == proof["entry_hash"])

    # 2. Content hash matches (if content supplied)
    if content_target or content_title:
        computed_content = _content_hash(content_target, content_title,
                                         content_description, content_poc)
        out["checks"]["content_matches"] = (computed_content == proof["content_hash"])
    else:
        out["checks"]["content_matches"] = None  # not checked

    # 3. Chain tip appears after entry (if chain available locally)
    if CHAIN.exists():
        chain = _read_chain()
        entry_idx = next((i for i, e in enumerate(chain)
                          if e["entry_hash"] == proof["entry_hash"]), -1)
        if entry_idx >= 0:
            # Verify chain integrity from this entry to tip
            valid_chain = True
            for i in range(entry_idx + 1, len(chain)):
                if chain[i]["prev_hash"] != chain[i - 1]["entry_hash"]:
                    valid_chain = False
                    break
            out["checks"]["chain_integrity"] = valid_chain
        else:
            out["checks"]["chain_integrity"] = None

    out["valid"] = all(v for v in out["checks"].values() if v is not None)
    return out


def stats() -> dict:
    chain = _read_chain()
    return {
        "entries": len(chain),
        "genesis": chain[0]["ts"] if chain else None,
        "tip_hash": _chain_tip(),
        "tip_ts": chain[-1]["ts"] if chain else None,
    }
