"""Workflow templates — reusable YAML-defined task chains.

Users ship workflows in ~/.slm/workflows/<name>.yaml and invoke them with:

    slm run-workflow recon example.com

Workflow format:

    name: recon
    description: "Subdomain enum → live probe → vuln scan → summarize"
    params:
      target: {required: true}
    tasks:
      - id: t1
        title: "Enumerate subdomains"
        tool: subfinder
        args: {target: "{{target}}"}
      - id: t2
        title: "Probe live hosts"
        tool: httpx
        args: {target: "{{t1.result}}"}    # reference prior task result
        deps: [t1]
      - id: t3
        title: "Scan for CVEs"
        tool: nuclei
        args: {target: "{{t2.result}}"}
        deps: [t2]

Workflows = deterministic task chains (no LLM needed per step). Agent mode
(pursue) = LLM-driven planning. Having both lets users pick determinism
when they want it, autonomy when they don't.
"""
from __future__ import annotations
import os, pathlib, re
from typing import Any
import yaml

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
WORKFLOWS = SLM_HOME / "workflows"

_SUBST = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def list_workflows() -> list[dict]:
    if not WORKFLOWS.exists():
        return []
    out = []
    for p in WORKFLOWS.glob("*.yaml"):
        try:
            data = yaml.safe_load(p.read_text()) or {}
            out.append({
                "name": data.get("name", p.stem),
                "description": data.get("description", ""),
                "params": list((data.get("params") or {}).keys()),
                "path": str(p),
            })
        except Exception:
            continue
    return out


def load_workflow(name: str) -> dict:
    p = WORKFLOWS / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"workflow '{name}' not found at {p}")
    return yaml.safe_load(p.read_text())


def _substitute(value: Any, context: dict) -> Any:
    """Replace {{param}} and {{taskid.result}} references in strings/dicts/lists."""
    if isinstance(value, str):
        def repl(m):
            key = m.group(1)
            if "." in key:
                tid, attr = key.split(".", 1)
                return str(context.get(tid, {}).get(attr, ""))
            return str(context.get(key, ""))
        return _SUBST.sub(repl, value)
    if isinstance(value, dict):
        return {k: _substitute(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, context) for v in value]
    return value


def execute(name: str, params: dict, dispatch_fn) -> list[dict]:
    """Execute a workflow. Returns list of task results.

    dispatch_fn: callable(tool_name, args_dict) -> str  (use slm.tools.dispatch)
    """
    wf = load_workflow(name)
    tasks = wf.get("tasks", [])
    context = dict(params)
    results = []

    # Validate required params
    for pname, meta in (wf.get("params") or {}).items():
        if meta.get("required") and pname not in params:
            raise ValueError(f"missing required param: {pname}")

    # Execute in order (YAML order is the canonical order; deps give structure)
    for task in tasks:
        tid = task["id"]
        deps = task.get("deps", [])
        if any(context.get(d, {}).get("status") == "failed" for d in deps):
            results.append({"id": tid, "status": "skipped", "reason": "upstream failed"})
            context[tid] = {"status": "skipped", "result": ""}
            continue

        args = _substitute(task.get("args", {}), context)
        tool = task["tool"]
        try:
            result = dispatch_fn(tool, args)
            status = "failed" if (isinstance(result, str) and result.startswith("error")) else "done"
        except Exception as e:
            result = f"error: {type(e).__name__}: {e}"
            status = "failed"
        record = {"id": tid, "title": task.get("title", ""), "status": status, "result": result}
        results.append(record)
        context[tid] = record

    return results


# ---------------------------------------------------------- shipped defaults
DEFAULT_WORKFLOWS = {
    "recon": """\
name: recon
description: Subdomain enum → live probe → vuln scan
params:
  target: {required: true}
tasks:
  - id: t1
    title: "Enumerate subdomains"
    tool: subfinder
    args: {target: "{{target}}"}
  - id: t2
    title: "Probe live hosts"
    tool: httpx
    args: {target: "{{target}}"}
    deps: [t1]
  - id: t3
    title: "Scan with nuclei"
    tool: nuclei
    args: {target: "{{target}}"}
    deps: [t2]
""",
    "port_audit": """\
name: port_audit
description: Common-port TCP scan + service enum
params:
  target: {required: true}
tasks:
  - id: t1
    title: "Scan common ports"
    tool: nmap
    args: {target: "{{target}}", extra: "-p 21,22,80,443,3306,5432,6379,8080,9200"}
""",
    "web_fuzz": """\
name: web_fuzz
description: Directory fuzzing with a common wordlist
params:
  target: {required: true}
tasks:
  - id: t1
    title: "Fuzz paths"
    tool: ffuf
    args: {target: "{{target}}", extra: "-w ~/.slm/wordlists/common.txt -mc 200,301,302,403"}
""",
}


def seed_defaults() -> int:
    """Write the shipped workflow templates to ~/.slm/workflows/ if missing."""
    WORKFLOWS.mkdir(parents=True, exist_ok=True)
    n = 0
    for name, content in DEFAULT_WORKFLOWS.items():
        p = WORKFLOWS / f"{name}.yaml"
        if not p.exists():
            p.write_text(content)
            n += 1
    return n
