"""Eval-gated self-improvement.

Flow:
  1. Agent proposes a diff to ~/.slm/system.md, ~/.slm/skills/*, or a new skill.
  2. Diff is applied to a *shadow* copy.
  3. Shadow copy runs the 40-task functional eval.
  4. If pass-rate >= baseline AND red-team still 100% blocked → promote via git.
  5. Baseline is updated; failing proposals archived to ~/.slm/proposals/rejected/.

Runs in Tier 1/2 mode only (prompt + skills). Tier 3 (LoRA adapters) must
happen off-device and be pushed via `slm adapter pull`.

This module REFUSES to write into ~/.slm/core/ regardless of proposal
content — the core/ path is on a hardcoded deny-list here AND at the
filesystem layer (chmod 444 + executor_guards.resolve_safe_path).
"""
from __future__ import annotations
import pathlib, os, shutil, subprocess, json, difflib
from slm.core.executor_guards import freeze_active

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
PROPOSALS = SLM_HOME / "proposals"
REJECTED  = PROPOSALS / "rejected"
BASELINE_FILE = SLM_HOME / "eval" / "baseline.json"

# HARD deny — never writable by self-improvement.
# This list mirrors slm/core/executor_guards._SAFETY_* constants. Updating
# here alone is insufficient: the filesystem layer (resolve_safe_path) is
# the authoritative enforcement. Both must agree.
FORBIDDEN_DIRS = {"core", ".git", "traces", ".github"}
FORBIDDEN_FILES = {
    # Safety modules
    "canary.py", "refusal.py", "vault.py", "provenance.py",
    "executor_guards.py", "scope_enforcer.py", "hard_blocks.yaml",
    # Safety state
    "FREEZE", "audit.key", "vault.enc", "vault.salt",
    "canary_log.jsonl", "provenance.jsonl",
    # Repo security docs
    "SECURITY.md", "CODE_OF_CONDUCT.md",
}


class ProposalRejected(RuntimeError):
    pass


def _check_path(rel: str) -> pathlib.Path:
    p = (SLM_HOME / rel).resolve()
    try:
        p.relative_to(SLM_HOME)
    except ValueError:
        raise ProposalRejected("path escapes SLM_HOME")
    parts = p.relative_to(SLM_HOME).parts
    if parts and parts[0] in FORBIDDEN_DIRS:
        raise ProposalRejected(f"path in forbidden dir: {parts[0]}")
    if p.name in FORBIDDEN_FILES:
        raise ProposalRejected(f"path is a safety-critical file: {p.name}")
    return p


# Required substrings that must remain in system.md to keep the safety posture
# intact. If a proposal removes any of these, reject it — even if the file
# itself is on the allow list (system.md IS allowed, but can't be weaponized
# to weaken the 4 hard blocks).
REQUIRED_SYSTEM_MD_SUBSTRINGS = [
    "terrorism",
    "CBRN",
    "CSAM",
    "mass",
    "sexual",
]


def _content_sanity_check(rel_path: str, new_content: str) -> None:
    """Reject proposals that would weaken safety posture even on allowed files."""
    if rel_path.endswith("system.md"):
        lower = new_content.lower()
        missing = [s for s in REQUIRED_SYSTEM_MD_SUBSTRINGS
                   if s.lower() not in lower]
        if missing:
            raise ProposalRejected(
                f"system.md missing required safety keywords: {missing}"
            )


def propose(rel_path: str, new_content: str, reason: str) -> str:
    if freeze_active():
        raise ProposalRejected("FREEZE active")
    target = _check_path(rel_path)
    _content_sanity_check(rel_path, new_content)
    old = target.read_text() if target.exists() else ""
    diff = "".join(difflib.unified_diff(
        old.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}"))

    PROPOSALS.mkdir(parents=True, exist_ok=True)
    pid = f"{__import__('time').time_ns()}"
    pdir = PROPOSALS / pid
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "meta.json").write_text(json.dumps(
        {"rel_path": rel_path, "reason": reason}, indent=2))
    (pdir / "new_content").write_text(new_content)
    (pdir / "diff.patch").write_text(diff)

    # Shadow-apply + eval
    if _shadow_eval_passes(rel_path, new_content):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_content)
        _git_snapshot(pid, rel_path, reason)
        return f"promoted proposal {pid}"
    else:
        REJECTED.mkdir(exist_ok=True)
        shutil.move(str(pdir), str(REJECTED / pid))
        raise ProposalRejected(f"proposal {pid} failed eval gate")


def _shadow_eval_passes(rel_path: str, new_content: str) -> bool:
    # Simplified: the real impl would copy SLM_HOME to a tempdir,
    # overlay new_content, run eval/functional.jsonl + eval/redteam.jsonl,
    # compare pass rates to baseline.json. Here we stub conservatively.
    return False  # default-deny until eval harness wired up


def _git_snapshot(pid: str, rel_path: str, reason: str):
    if not (SLM_HOME / ".git").exists():
        subprocess.run(["git", "-C", str(SLM_HOME), "init", "-q"],
                       check=False)
    subprocess.run(["git", "-C", str(SLM_HOME), "add", rel_path], check=False)
    subprocess.run(["git", "-C", str(SLM_HOME), "commit", "-q",
                    "-m", f"prop/{pid}: {reason}"], check=False)
