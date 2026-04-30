"""ReAct loop — the brain-stem of the agent."""
from __future__ import annotations
import json, os, pathlib, re, time, tomllib
from dataclasses import dataclass, field
from typing import Iterator

from slm.llm import LlamaClient
from slm.tools import dispatch, get_tool_schemas
from slm.core.executor_guards import (
    check_hard_blocks, HardBlockError, RateLimiter, freeze_active,
)

_SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))


def _guardrail(key: str, default: int) -> int:
    p = _SLM_HOME / "guardrails.toml"
    if not p.exists():
        return default
    try:
        val = tomllib.loads(p.read_text()).get(key, default)
        return int(val)
    except Exception:
        return default

TAG_THOUGHT = re.compile(r"<thought>(.*?)</thought>", re.S)
TAG_CALL    = re.compile(r"<tool_call>(.*?)</tool_call>", re.S)
TAG_FINAL   = re.compile(r"<final>(.*?)</final>", re.S)


@dataclass
class Event:
    kind: str                       # thought | tool_call | tool_result | final | error
    content: str
    meta: dict = field(default_factory=dict)


class Agent:
    def __init__(self, llm: LlamaClient, system_prompt: str,
                 max_turns: int = 20, yolo: bool = False):
        self.llm = llm
        self.system = system_prompt + "\n\n# Tool schemas\n" + \
                      json.dumps(get_tool_schemas(), indent=2)
        self.max_turns = max_turns
        self.yolo = yolo
        self.history: list[dict] = []

    def run(self, user_msg: str) -> Iterator[Event]:
        try:
            check_hard_blocks(user_msg, where="user_prompt")
        except HardBlockError as e:
            yield Event("final",
                        f"I can't help with that ({e.category}). This is a hard limit.")
            return

        self.history.append({"role": "user", "content": user_msg})
        limiter = RateLimiter(_guardrail("max_tool_calls_per_turn", 90))

        for _ in range(self.max_turns):
            if freeze_active():
                yield Event("error", "FREEZE active — agent halted.")
                return

            raw = self.llm.complete(self.system, self.history)
            try:
                check_hard_blocks(raw, where="model_output")
            except HardBlockError as e:
                yield Event("final",
                            f"I can't help with that ({e.category}). This is a hard limit.")
                return

            if (m := TAG_THOUGHT.search(raw)):
                yield Event("thought", m.group(1).strip())
            if (m := TAG_FINAL.search(raw)):
                self.history.append({"role": "assistant", "content": raw})
                yield Event("final", m.group(1).strip())
                return

            call = TAG_CALL.search(raw)
            if not call:
                yield Event("error",
                            "model produced no tool_call or final — retrying with nudge")
                self.history.append({"role": "assistant", "content": raw})
                self.history.append({"role": "user",
                                     "content": "Respond only with <thought>…</thought> then <tool_call>…</tool_call> or <final>…</final>."})
                continue

            try:
                payload = json.loads(call.group(1).strip())
                name = payload["name"]
                args = payload.get("args", {})
            except Exception as e:
                yield Event("error", f"malformed tool_call: {e}")
                self.history.append({"role": "assistant", "content": raw})
                self.history.append({"role": "user",
                                     "content": f"Your last tool_call was not valid JSON: {e}. Retry."})
                continue

            sig = name + json.dumps(args, sort_keys=True)
            try:
                limiter.tick(sig)
            except RuntimeError as e:
                yield Event("error", str(e))
                return

            yield Event("tool_call", f"{name}({json.dumps(args)})",
                        meta={"name": name, "args": args})
            t0 = time.time()
            try:
                result = dispatch(name, args)
                check_hard_blocks(result, where="tool_result")
            except HardBlockError as e:
                self.history.append({"role": "assistant", "content": raw})
                self.history.append({"role": "user",
                                     "content": f"<tool_result>[blocked:{e.category}]</tool_result>"})
                yield Event("final",
                            f"Blocked content from tool ({e.category}); stopping.")
                return
            except Exception as e:
                result = f"error: {e}"
            dt = time.time() - t0
            yield Event("tool_result", result, meta={"dt": dt})

            self.history.append({"role": "assistant", "content": raw})
            self.history.append({"role": "user",
                                 "content": f"<tool_result>{result}</tool_result>"})
        yield Event("error", f"max_turns ({self.max_turns}) reached without <final>")
