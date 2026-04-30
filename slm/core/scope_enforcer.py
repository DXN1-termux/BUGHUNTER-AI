"""IMMUTABLE core — scope enforcement for network tools.

scope.yaml lives in $SLM_HOME/scope.yaml (user-editable).
Targets MUST be explicitly listed before any network tool fires.
"""
from __future__ import annotations
import ipaddress, os, pathlib, re, yaml
from urllib.parse import urlparse

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
_SCOPE_FILE = SLM_HOME / "scope.yaml"


class OutOfScopeError(PermissionError):
    pass


def _load() -> dict:
    if not _SCOPE_FILE.exists():
        return {"programs": [], "domains": [], "ips": []}
    with _SCOPE_FILE.open() as f:
        return yaml.safe_load(f) or {}


def _domain_matches(host: str, patterns: list[str]) -> bool:
    """Match host against scope patterns.

    Semantics:
      - bare `example.com`    → matches apex + any subdomain
      - wildcard `*.example.com` → matches subdomains only, NOT the apex
    """
    host = host.lower().strip(".")
    for pat in patterns or []:
        pat = pat.lower().strip(".")
        if pat.startswith("*."):
            base = pat[2:]
            if host != base and host.endswith("." + base):
                return True
        elif host == pat or host.endswith("." + pat):
            return True
    return False


def _parse_ip(s: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    # Strip zone id if present (e.g. fe80::1%eth0)
    s = s.split("%", 1)[0]
    try:
        return ipaddress.ip_address(s)
    except ValueError:
        return None


def _ip_matches(ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
                patterns: list[str]) -> bool:
    for pat in patterns or []:
        try:
            net = ipaddress.ip_network(pat, strict=False)
        except ValueError:
            continue
        # Only compare same-family addresses; IPv4-in-IPv6 and vice versa
        # are not accepted implicitly.
        if isinstance(ip, ipaddress.IPv4Address) and \
           isinstance(net, ipaddress.IPv4Network):
            if ip in net:
                return True
        elif isinstance(ip, ipaddress.IPv6Address) and \
             isinstance(net, ipaddress.IPv6Network):
            if ip in net:
                return True
    return False


def check_target(target: str) -> None:
    """Raise OutOfScopeError if target is not explicitly authorized.

    Accepts:
      - bare domain (example.com)
      - URL (https://api.example.com/x, http://[::1]/a)
      - IPv4 (10.0.0.1) or IPv6 (::1, fe80::1%eth0)
    """
    scope = _load()
    # Strip URL
    host = target
    if "://" in target:
        host = urlparse(target).hostname or ""
    else:
        # Strip bracketed IPv6 literal
        if host.startswith("[") and "]" in host:
            host = host[1 : host.index("]")]
        elif host.count(":") == 1:
            # "example.com:8080" → strip port; leave IPv6 (multiple colons) alone
            host = host.split(":", 1)[0]

    if not host:
        raise OutOfScopeError(f"empty target: {target!r}")

    # IP path (v4 or v6)
    ip = _parse_ip(host)
    if ip is not None:
        if _ip_matches(ip, scope.get("ips", [])):
            return
        raise OutOfScopeError(f"IP {host} not in scope.yaml::ips")

    # Domain path
    if _domain_matches(host, scope.get("domains", [])):
        return
    raise OutOfScopeError(
        f"{host} not in scope.yaml — add it to ~/.slm/scope.yaml::domains to authorize"
    )
