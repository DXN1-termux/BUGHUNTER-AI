"""Unit tests for hash-chain provenance."""
import json
import tempfile
from pathlib import Path
import pytest


@pytest.fixture
def tmp_slm_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SLM_HOME", str(tmp_path))
    import importlib
    import slm.provenance
    importlib.reload(slm.provenance)
    return tmp_path


def test_commit_creates_entry(tmp_slm_home):
    from slm.provenance import commit, _read_chain
    entry = commit(1, "example.com", "SQL injection in /api",
                   "Classic SQLi via id param", "POST /api id=1' OR 1=1--")
    assert entry["finding_id"] == 1
    assert "entry_hash" in entry
    assert "content_hash" in entry
    assert entry["prev_hash"] == "0" * 64  # genesis
    chain = _read_chain()
    assert len(chain) == 1


def test_chain_links_entries(tmp_slm_home):
    from slm.provenance import commit, _read_chain
    e1 = commit(1, "a.com", "Bug 1", "desc1", "poc1")
    e2 = commit(2, "b.com", "Bug 2", "desc2", "poc2")
    e3 = commit(3, "c.com", "Bug 3", "desc3", "poc3")
    chain = _read_chain()
    assert len(chain) == 3
    assert chain[1]["prev_hash"] == chain[0]["entry_hash"]
    assert chain[2]["prev_hash"] == chain[1]["entry_hash"]


def test_content_hash_order_independent(tmp_slm_home):
    from slm.provenance import _content_hash
    h1 = _content_hash("EXAMPLE.COM", "title", "desc", "poc")
    h2 = _content_hash("example.com", "title", "desc", "poc")
    assert h1 == h2


def test_proof_export_and_verify_roundtrip(tmp_slm_home, monkeypatch):
    from slm.provenance import commit, export_proof, verify_proof
    import slm.findings
    monkeypatch.setattr(slm.findings, "list_findings",
                        lambda: [{"id": 42, "target": "example.com"}])
    commit(42, "example.com", "SQLi", "desc", "poc")
    proof = export_proof(42)
    result = verify_proof(proof,
                          content_target="example.com",
                          content_title="SQLi",
                          content_description="desc",
                          content_poc="poc")
    assert result["valid"]
    assert result["checks"]["entry_hash_matches"]
    assert result["checks"]["content_matches"]


def test_verify_rejects_wrong_content(tmp_slm_home, monkeypatch):
    from slm.provenance import commit, export_proof, verify_proof
    import slm.findings
    monkeypatch.setattr(slm.findings, "list_findings",
                        lambda: [{"id": 1, "target": "a.com"}])
    commit(1, "a.com", "real title", "real desc", "real poc")
    proof = export_proof(1)
    result = verify_proof(proof,
                          content_target="a.com",
                          content_title="FAKE TITLE",
                          content_description="fake",
                          content_poc="fake")
    assert not result["valid"]
    assert result["checks"]["content_matches"] is False


def test_proof_missing_finding_raises(tmp_slm_home):
    from slm.provenance import export_proof
    with pytest.raises(ValueError):
        export_proof(999)
