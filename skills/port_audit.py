"""Port scan a target and identify interesting services.

Runs an nmap TCP connect scan on common ports, parses the output, and
highlights potentially vulnerable services (outdated versions, known-weak
ports like 21/FTP, 23/Telnet, 3389/RDP exposed).
"""
from __future__ import annotations


INTERESTING_PORTS = {
    21: "FTP (check anonymous login)",
    22: "SSH (check version for CVEs)",
    23: "Telnet (cleartext — high risk)",
    25: "SMTP (check open relay)",
    53: "DNS (check zone transfer)",
    80: "HTTP",
    110: "POP3 (cleartext)",
    135: "MSRPC",
    139: "NetBIOS",
    443: "HTTPS",
    445: "SMB (check EternalBlue, signing)",
    1433: "MSSQL",
    1521: "Oracle",
    3306: "MySQL",
    3389: "RDP (check BlueKeep)",
    5432: "PostgreSQL",
    5900: "VNC (check auth bypass)",
    6379: "Redis (check unauth access)",
    8080: "HTTP-alt",
    8443: "HTTPS-alt",
    9200: "Elasticsearch",
    27017: "MongoDB (check unauth)",
}


def run(target: str, ports: str = "21,22,23,25,53,80,110,135,139,443,445,1433,3306,3389,5432,5900,6379,8080,8443,9200,27017", **kwargs) -> str:
    from slm.tools import dispatch
    result = dispatch("nmap", {"target": target, "extra": f"-p {ports}"})
    if result.startswith("error"):
        return result

    findings = []
    for line in result.splitlines():
        if "/tcp" in line and "open" in line:
            parts = line.split()
            port_num = int(parts[0].split("/")[0])
            service = " ".join(parts[2:]) if len(parts) > 2 else "unknown"
            note = INTERESTING_PORTS.get(port_num, "")
            flag = " ⚠️" if port_num in (21, 23, 445, 3389, 5900, 6379, 27017) else ""
            findings.append(f"  {parts[0]:12} {parts[1]:8} {service:20} {note}{flag}")

    if not findings:
        return f"No open ports found on {target} (scanned: {ports})"

    return (
        f"Open ports on {target}:\n"
        + "\n".join(findings)
        + f"\n\n{len(findings)} open port(s). Investigate flagged services first."
    )
