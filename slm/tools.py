"""Tool registry. Every tool passes through immutable core guards."""
from __future__ import annotations
import hashlib, json, os, pathlib, subprocess, shlex, time
from dataclasses import dataclass
from typing import Callable
import httpx

from slm.core.executor_guards import (
    check_hard_blocks, check_shell, resolve_safe_path, freeze_active,
)
from slm.core.scope_enforcer import check_target

WORKDIR = pathlib.Path.cwd()
_RESULT_CACHE: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 60.0


@dataclass
class ToolSpec:
    name: str
    schema: dict
    fn: Callable[..., str]
    mutating: bool = False
    needs_scope: bool = False


TOOLS: dict[str, ToolSpec] = {}


def tool(name: str, schema: dict, *, mutating: bool = False, needs_scope: bool = False):
    def deco(fn):
        TOOLS[name] = ToolSpec(name, schema, fn, mutating, needs_scope)
        return fn
    return deco


# ----------------------------------------------------------- shell
@tool("shell",
      {"type": "object", "properties": {"cmd": {"type": "string"}},
       "required": ["cmd"]},
      mutating=True)
def shell(cmd: str, *, timeout: int = 30, cap: int = 2048) -> str:
    if not cmd or not cmd.strip():
        return "error: empty command"
    check_hard_blocks(cmd, where="shell_cmd")
    check_shell(cmd)
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True,
                           timeout=timeout, text=True, errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        if len(out) > cap:
            out = out[:cap] + f"\n…[truncated {len(out)-cap} bytes]"
        return f"exit={p.returncode}\n{out}"
    except subprocess.TimeoutExpired:
        return f"exit=timeout after {timeout}s"


# ----------------------------------------------------------- files
@tool("read_file",
      {"type": "object", "properties": {"path": {"type": "string"}},
       "required": ["path"]})
def read_file(path: str) -> str:
    if not path or not path.strip():
        return "error: empty path"
    p = resolve_safe_path(path, workdir=WORKDIR, allow_writes=False)
    if not p.exists():
        return f"error: file not found: {p}"
    if not p.is_file():
        return f"error: not a file: {p}"
    data = p.read_text(errors="replace")
    lines = data.splitlines()
    if len(data) > 8192:
        data = data[:8192] + f"\n…[truncated; {len(data)} bytes, {len(lines)} lines total]"
    return data


@tool("write_file",
      {"type": "object",
       "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
       "required": ["path", "content"]},
      mutating=True)
def write_file(path: str, content: str) -> str:
    if not path or not path.strip():
        return "error: empty path"
    if content is None:
        return "error: content cannot be None"
    check_hard_blocks(content, where="write_file")
    p = resolve_safe_path(path, workdir=WORKDIR, allow_writes=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {len(content)} bytes ({len(content.splitlines())} lines) -> {p}"


@tool("edit_file",
      {"type": "object",
       "properties": {"path": {"type": "string"},
                      "old": {"type": "string"}, "new": {"type": "string"}},
       "required": ["path", "old", "new"]},
      mutating=True)
def edit_file(path: str, old: str, new: str) -> str:
    if not path or not path.strip():
        return "error: empty path"
    if not old:
        return "error: old string cannot be empty"
    check_hard_blocks(new, where="edit_file")
    p = resolve_safe_path(path, workdir=WORKDIR, allow_writes=True)
    if not p.exists():
        return f"error: file not found: {p}"
    txt = p.read_text()
    if txt.count(old) == 0:
        return f"error: old string not found in {p} (file has {len(txt.splitlines())} lines, {len(txt)} bytes)"
    if txt.count(old) > 1:
        return f"error: old string matches {txt.count(old)} times — not unique"
    p.write_text(txt.replace(old, new, 1))
    return f"edited {p}"


@tool("delete_file",
      {"type": "object", "properties": {"path": {"type": "string"}},
       "required": ["path"]},
      mutating=True)
def delete_file(path: str) -> str:
    if not path or not path.strip():
        return "error: empty path"
    p = resolve_safe_path(path, workdir=WORKDIR, allow_writes=True)
    if not p.exists():
        return f"error: file not found: {p}"
    if p.is_dir():
        return f"error: {p} is a directory (use shell rmdir)"
    p.unlink()
    return f"deleted {p}"


@tool("list_dir",
      {"type": "object", "properties": {"path": {"type": "string"}},
       "required": ["path"]})
def list_dir(path: str) -> str:
    if not path or not path.strip():
        return "error: empty path"
    p = resolve_safe_path(path, workdir=WORKDIR, allow_writes=False)
    if not p.exists():
        return f"error: directory not found: {p}"
    if not p.is_dir():
        return f"error: not a directory: {p}"
    entries = sorted(f.name + ("/" if f.is_dir() else "") for f in p.iterdir())
    if len(entries) > 200:
        head = entries[:200]
        return "\n".join(head) + f"\n…[{len(entries) - 200} more entries truncated]"
    return "\n".join(entries)


# ----------------------------------------------------------- web
@tool("web_search",
      {"type": "object", "properties": {"query": {"type": "string"}},
       "required": ["query"]})
def web_search(query: str) -> str:
    if not query or not query.strip():
        return "error: empty search query"
    check_hard_blocks(query, where="web_search")
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return "error: duckduckgo_search not installed. Run: pip install duckduckgo_search"
    last_err = None
    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=10))
            break
        except Exception as e:
            last_err = e
            time.sleep(1.0 * (2 ** attempt))
    else:
        return f"error: web search failed after 3 attempts: {last_err}"
    lines = [f"- {r.get('title','')} — {r.get('href','')}\n  {r.get('body','')[:160]}"
             for r in results]
    out = "\n".join(lines) or "(no results)"
    check_hard_blocks(out, where="web_search_result")
    return out


@tool("fetch_url",
      {"type": "object", "properties": {"url": {"type": "string"}},
       "required": ["url"]},
      needs_scope=True)
def fetch_url(url: str) -> str:
    if not url or not url.strip():
        return "error: empty URL"
    check_target(url)
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "error: beautifulsoup4 not installed. Run: pip install beautifulsoup4"
    try:
        r = httpx.get(url, timeout=httpx.Timeout(20.0, connect=5.0),
                      follow_redirects=True, headers={"User-Agent": "slm-agent/2.3"})
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        cap = 4096
        if len(text) > cap:
            text = text[:cap] + f"\n…[truncated; {len(r.text)} bytes total, {len(r.text.splitlines())} lines]"
        check_hard_blocks(text, where="fetch_url_result")
        return f"status={r.status_code} content_type={r.headers.get('content-type','')}\n{text}"
    except httpx.TimeoutException:
        return f"error: request timed out (20s) for {url}"
    except httpx.ConnectError as e:
        return f"error: connection failed for {url}: {e}"
    except Exception as e:
        return f"error: {type(e).__name__}: {e}"


# ----------------------------------------------------------- snowflake
@tool("run_sql",
      {"type": "object", "properties": {"query": {"type": "string"}},
       "required": ["query"]},
      mutating=True)
def run_sql(query: str) -> str:
    if not query or not query.strip():
        return "error: empty SQL query"
    try:
        import snowflake.connector as sc
    except ImportError:
        return "error: snowflake-connector-python not installed. Run: slm install-snowflake"
    check_hard_blocks(query, where="run_sql")
    cfg = _load_sf_cfg()
    if not cfg:
        return "error: snowflake not configured. Edit ~/.slm/config.toml"
    try:
        with sc.connect(**cfg, network_timeout=30) as cx, cx.cursor() as cur:
            cur.execute(query, timeout=60)
            rows = cur.fetchmany(100)
            cols = [c[0] for c in cur.description] if cur.description else []
            total_rows = cur.rowcount or len(rows)
        result = json.dumps({"columns": cols, "rows": rows, "total_rows": total_rows},
                            default=str, indent=2)
        if len(result) > 4096:
            result = result[:4096] + f"\n\u2026[truncated; {total_rows} rows total]"
        return result
    except Exception as e:
        return f"error: SQL execution failed: {type(e).__name__}: {e}"


def _load_sf_cfg() -> dict | None:
    import tomllib
    p = pathlib.Path(os.environ.get("SLM_HOME",
                                    pathlib.Path.home() / ".slm")) / "config.toml"
    if not p.exists():
        return None
    data = tomllib.loads(p.read_text()).get("snowflake", {})
    return data if data.get("enabled") else None


# ----------------------------------------------------------- findings
@tool("report_finding",
      {"type": "object",
       "properties": {
           "target":      {"type": "string"},
           "title":       {"type": "string"},
           "severity":    {"type": "string",
                           "enum": ["critical", "high", "medium", "low", "info"]},
           "category":    {"type": "string"},
           "cve":         {"type": "string"},
           "url":         {"type": "string"},
           "description": {"type": "string"},
           "poc":         {"type": "string"},
       },
       "required": ["target", "title", "severity"]},
      mutating=True)
def report_finding(target: str, title: str, severity: str,
                   category: str = "other", cve: str = "", url: str = "",
                   description: str = "", poc: str = "") -> str:
    """Persist a discovered vulnerability so it survives the session."""
    if not target or not title:
        return "error: target and title required"
    check_hard_blocks(title + " " + description, where="report_finding")
    try:
        from slm.findings import add_finding
    except Exception as e:
        return f"error: findings store unavailable: {e}"
    fid = add_finding(target=target, title=title, severity=severity,
                      category=category, cve=cve, url=url,
                      description=description, poc=poc, session="agent")
    return f"finding #{fid} saved: [{severity.upper()}] {title} on {target}"


# ----------------------------------------------------------- notify
@tool("notify",
      {"type": "object",
       "properties": {"message": {"type": "string"},
                      "title":   {"type": "string"}},
       "required": ["message"]},
      mutating=True)
def notify(message: str, title: str = "slm-agent") -> str:
    """Send a webhook notification if configured in ~/.slm/config.toml::[notify]."""
    if not message:
        return "error: empty message"
    check_hard_blocks(message, where="notify")
    import tomllib
    cfg_path = pathlib.Path(os.environ.get("SLM_HOME",
                                           pathlib.Path.home() / ".slm")) / "config.toml"
    if not cfg_path.exists():
        return "error: no config.toml"
    nc = tomllib.loads(cfg_path.read_text()).get("notify", {})
    webhook = nc.get("webhook_url", "")
    kind = nc.get("kind", "discord")
    if not webhook:
        return "error: [notify].webhook_url not set"
    try:
        if kind == "discord":
            payload = {"content": f"**{title}**\n{message[:1800]}"}
        elif kind == "slack":
            payload = {"text": f"*{title}*\n{message[:1800]}"}
        elif kind == "telegram":
            chat_id = nc.get("chat_id", "")
            payload = {"chat_id": chat_id,
                       "text": f"{title}\n{message[:1800]}"}
        else:
            payload = {"title": title, "message": message[:1800]}
        r = httpx.post(webhook, json=payload, timeout=10.0)
        r.raise_for_status()
        return f"notified via {kind} (status {r.status_code})"
    except Exception as e:
        return f"error: notify failed: {type(e).__name__}: {e}"


@tool("ask_cloud",
      {"type": "object",
       "properties": {
           "provider":   {"type": "string", "enum": ["anthropic", "openai"]},
           "prompt":     {"type": "string"},
           "model":      {"type": "string"},
           "max_tokens": {"type": "integer"},
       },
       "required": ["provider", "prompt"]})
def ask_cloud(provider: str, prompt: str,
              model: str = None, max_tokens: int = 1024) -> str:
    """Route a single query to a cloud model (Opus, GPT-4o, etc.) when the
    local model needs a stronger brain. Credentials come from the vault."""
    from slm.api_passthrough import call
    return call(provider, prompt, model=model, max_tokens=max_tokens)


# ----------------------------------------------------------- bug bounty wrappers
for _name, _cmd in [
    ("nmap",      "nmap -sT -Pn -T3"),
    ("subfinder", "subfinder -silent -d"),
    ("httpx",     "httpx -silent -u"),
    ("nuclei",    "nuclei -silent -u"),
    ("ffuf",      "ffuf -u"),
    ("katana",    "katana -silent -u"),
]:
    def _make(name, base):
        @tool(name,
              {"type": "object", "properties": {"target": {"type": "string"},
                                                "extra":  {"type": "string"}},
               "required": ["target"]},
              mutating=True, needs_scope=True)
        def _fn(target: str, extra: str = ""):
            check_target(target)
            safe_extra = " ".join(shlex.quote(tok) for tok in shlex.split(extra)) if extra else ""
            return shell(f"{base} {shlex.quote(target)} {safe_extra}", timeout=120, cap=4096)
        _fn.__name__ = name
        return _fn
    _make(_name, _cmd)


def get_tool_schemas() -> list[dict]:
    return [{"name": t.name, "parameters": t.schema} for t in TOOLS.values()]


def needs_confirmation(name: str) -> bool:
    if name not in TOOLS:
        return False
    return TOOLS[name].mutating


def _cache_key(name: str, args: dict) -> str:
    raw = name + json.dumps(args, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def dispatch(name: str, args: dict) -> str:
    if freeze_active():
        return "error: FREEZE active \u2014 all tools halted. Remove ~/.slm/FREEZE to resume."
    if name not in TOOLS:
        return f"error: unknown tool '{name}'. Available: {', '.join(TOOLS.keys())}"
    spec = TOOLS[name]
    if not spec.mutating and not spec.needs_scope:
        key = _cache_key(name, args)
        if key in _RESULT_CACHE:
            ts, result = _RESULT_CACHE[key]
            if time.time() - ts < _CACHE_TTL:
                return result
    result = spec.fn(**args)
    if not spec.mutating and not spec.needs_scope:
        _RESULT_CACHE[_cache_key(name, args)] = (time.time(), result)
    return result
