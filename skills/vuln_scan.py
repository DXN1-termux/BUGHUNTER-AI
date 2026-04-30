"""Run nuclei vulnerability templates against a target and format results.

Executes nuclei with default templates against a target URL, parses the
output into a structured vulnerability report grouped by severity.
"""
from __future__ import annotations


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def run(target: str, templates: str = "", **kwargs) -> str:
    from slm.tools import dispatch

    extra = f"-t {templates}" if templates else ""
    result = dispatch("nuclei", {"target": target, "extra": extra})
    if result.startswith("error"):
        return result

    vulns = {"critical": [], "high": [], "medium": [], "low": [], "info": []}

    for line in result.splitlines():
        if not line.strip():
            continue
        severity = "info"
        for sev in SEVERITY_ORDER:
            if f"[{sev}]" in line.lower():
                severity = sev
                break
        vulns[severity].append(line.strip())

    total = sum(len(v) for v in vulns.values())
    if total == 0:
        return f"Nuclei scan complete: no findings against {target}"

    report = [f"Nuclei scan results for {target} — {total} finding(s)\n"]
    for sev in ("critical", "high", "medium", "low", "info"):
        if vulns[sev]:
            header = f"{'🔴' if sev == 'critical' else '🟠' if sev == 'high' else '🟡' if sev == 'medium' else '🔵' if sev == 'low' else '⚪'} {sev.upper()} ({len(vulns[sev])})"
            report.append(header)
            for v in vulns[sev][:10]:
                report.append(f"  {v}")
            if len(vulns[sev]) > 10:
                report.append(f"  ... and {len(vulns[sev]) - 10} more")
            report.append("")

    crit_high = len(vulns["critical"]) + len(vulns["high"])
    if crit_high > 0:
        report.append(f"⚠️  {crit_high} critical/high findings — investigate immediately")

    return "\n".join(report)
