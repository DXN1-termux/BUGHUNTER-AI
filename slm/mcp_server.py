"""MCP (Model Context Protocol) server mode.

Exposes BUGHUNTER-AI's tool catalog over stdio so Claude Desktop, Cursor,
and any other MCP client can use it as a tool provider. This means you can
ask Claude "recon example.com" and it'll call through to slm-agent running
on your machine with all its safety guards intact.

Usage (in Claude Desktop's mcp.json):
    {
      "mcpServers": {
        "slm-agent": {
          "command": "slm",
          "args": ["mcp"]
        }
      }
    }

Then in Claude: "Use slm-agent to enumerate subdomains of example.com."

Every call still goes through the immutable safety layer:
  - hard blocks fire on the prompt + result
  - scope enforcement gates all network tools
  - shell denylist catches destructive commands
  - FREEZE switch halts everything
"""
from __future__ import annotations
import json, sys
from typing import Any

from slm.tools import TOOLS, dispatch, get_tool_schemas
from slm.core.executor_guards import check_hard_blocks, HardBlockError, freeze_active


MCP_VERSION = "2024-11-05"


def _send(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _ok(rid: Any, result: dict) -> None:
    _send({"jsonrpc": "2.0", "id": rid, "result": result})


def _err(rid: Any, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}})


def _tool_list() -> list[dict]:
    out = []
    for spec in TOOLS.values():
        out.append({
            "name": spec.name,
            "description": (spec.fn.__doc__ or spec.name).strip().split("\n")[0],
            "inputSchema": spec.schema,
        })
    return out


def _handle(req: dict) -> None:
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        _ok(rid, {
            "protocolVersion": MCP_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "slm-agent", "version": "2.3.0"},
        })
    elif method == "tools/list":
        _ok(rid, {"tools": _tool_list()})
    elif method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {}) or {}
        if freeze_active():
            _err(rid, -32001, "FREEZE active — all tools halted")
            return
        try:
            check_hard_blocks(json.dumps({"name": name, "args": args}), where="mcp_call")
            result = dispatch(name, args)
            check_hard_blocks(result, where="mcp_result")
            _ok(rid, {"content": [{"type": "text", "text": result}]})
        except HardBlockError as e:
            _err(rid, -32002, f"hard-block:{e.category}")
        except Exception as e:
            _err(rid, -32000, f"{type(e).__name__}: {e}")
    elif method == "ping":
        _ok(rid, {})
    elif method.startswith("notifications/"):
        return  # fire-and-forget
    else:
        _err(rid, -32601, f"method not found: {method}")


def serve() -> None:
    """Blocking stdio loop — one JSON-RPC message per line."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            _handle(req)
        except Exception as e:
            _err(req.get("id"), -32603, f"internal: {e}")


if __name__ == "__main__":
    serve()
