"""Local CVE lookup — fetches and caches NVD entries by CVE ID.

Falls back to CIRCL CVE Search if NVD is rate-limited. Cache is in
~/.slm/cve_cache/ so repeated lookups are instant and work offline
once seen.
"""
from __future__ import annotations
import json, os, pathlib, re
import httpx

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
CACHE = SLM_HOME / "cve_cache"

CVE_RE = re.compile(r"CVE-\d{4}-\d{1,7}", re.I)


def _fmt(data: dict) -> str:
    cve_id = data.get("id") or data.get("cveMetadata", {}).get("cveId", "?")
    descs = (data.get("descriptions") or
             data.get("containers", {}).get("cna", {}).get("descriptions") or [])
    desc = next((d.get("value", "") for d in descs if d.get("lang") == "en"), "")
    metrics = data.get("metrics") or {}
    cvss = "?"
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        if metrics.get(key):
            m = metrics[key][0].get("cvssData", {})
            cvss = f"{m.get('baseScore','?')} ({m.get('baseSeverity','?')})"
            break
    refs = data.get("references", [])[:5]
    ref_lines = "\n".join(f"  - {r.get('url','')}" for r in refs)
    return (
        f"📋 {cve_id}\n"
        f"   CVSS: {cvss}\n"
        f"\n"
        f"   {desc[:600]}\n"
        f"\n"
        f"   References:\n{ref_lines}"
    )


def run(cve: str, **kwargs) -> str:
    """Look up a CVE by ID (e.g. 'CVE-2024-23897'). Caches locally."""
    if not cve or not CVE_RE.match(cve.strip()):
        return f"error: '{cve}' doesn't look like a CVE ID (expected CVE-YYYY-NNNN)"
    cve = cve.strip().upper()

    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{cve}.json"
    if cached.exists():
        data = json.loads(cached.read_text())
        return _fmt(data) + "\n   [cached]"

    # Try NVD first
    try:
        r = httpx.get(
            f"https://services.nvd.nist.gov/rest/json/cves/2.0",
            params={"cveId": cve}, timeout=15,
            headers={"User-Agent": "slm-agent/2.3"},
        )
        if r.status_code == 200:
            vulns = r.json().get("vulnerabilities", [])
            if vulns:
                cve_data = vulns[0].get("cve", {})
                cached.write_text(json.dumps(cve_data))
                return _fmt(cve_data)
    except Exception:
        pass

    # Fallback: CIRCL
    try:
        r = httpx.get(f"https://cve.circl.lu/api/cve/{cve}", timeout=15)
        if r.status_code == 200 and r.json():
            data = r.json()
            cached.write_text(json.dumps(data))
            return _fmt(data)
    except Exception as e:
        return f"error: NVD + CIRCL both failed: {type(e).__name__}: {e}"

    return f"error: {cve} not found in NVD or CIRCL"
