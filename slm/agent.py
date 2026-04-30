"""ReAct loop — the brain-stem of the agent.

Intelligence boosters (all config-gated in [agent]):
  - skill_rag        : inject top-3 matching user skills per run
  - plan_first       : require <plan>...</plan> on the first turn
  - few_shot         : inject 1-2 similar past successful exemplars
  - reflect          : self-critique before returning <final> (desktop+)
  - vote             : sample N rollouts per turn, pick majority tool (workstation+)
  - context_compress : summarize oldest turns when nearing n_ctx
"""
from __future__ import annotations
import json, os, pathlib, re, subprocess, time, tomllib
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterator, Optional

from slm.llm import LlamaClient
from slm.tools import dispatch, get_tool_schemas, needs_confirmation
from slm.core.executor_guards import (
    check_hard_blocks, HardBlockError, RateLimiter, freeze_active,
)
from slm.canary import (
    mint_canary, canary_instruction, check_leak, InjectionDetected,
)
from slm.refusal import (
    is_refusal, is_legitimate_refusal, inject_authorization, retry_prompt,
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
TAG_PLAN    = re.compile(r"<plan>(.*?)</plan>", re.S)
TAG_CONFIRM = re.compile(r"<confirm\s*/>", re.S)


@dataclass
class Event:
    kind: str                       # thought | plan | tool_call | tool_result | final | error
    content: str
    meta: dict = field(default_factory=dict)


def _skill_block(user_msg: str, k: int = 3) -> str:
    try:
        from slm.skills import retrieve
        hits = retrieve(user_msg, k=k)
    except Exception:
        return ""
    if not hits:
        return ""
    lines = [f"- {name}: {doc}" for name, doc in hits if doc]
    if not lines:
        return ""
    return "\n\n# Relevant skills (retrieved; call via `run_skill`):\n" + "\n".join(lines)


def _fewshot_block(user_msg: str, k: int = 2) -> str:
    try:
        from slm.session import retrieve_exemplars
        hits = retrieve_exemplars(user_msg, k=k)
    except Exception:
        return ""
    if not hits:
        return ""
    blocks = []
    for h in hits:
        blocks.append(
            f"### Past example\n"
            f"user: {h['user_msg']}\n"
            f"<plan>{h.get('plan','')}</plan>\n"
            f"<final>{h['final']}</final>"
        )
    return "\n\n# Few-shot exemplars (similar past successful sessions):\n" + "\n\n".join(blocks)


def _approx_tokens(messages: list[dict]) -> int:
    """Crude token estimate: ~4 chars/token. Good enough for compression triggers."""
    return sum(len(m.get("content", "")) for m in messages) // 4


def _compress_history(llm: LlamaClient, history: list[dict], keep_last: int = 4) -> list[dict]:
    """Collapse everything except the last `keep_last` turns into a single
    assistant summary. Called only when history is large enough that it
    matters — otherwise returned unchanged."""
    if len(history) <= keep_last + 2:
        return history
    head = history[:-keep_last]
    tail = history[-keep_last:]
    digest_prompt = (
        "Summarize the following agent session in <= 12 lines. Keep any "
        "concrete findings, file paths, URLs, and tool-results that matter "
        "for the next turn. Drop small-talk.\n\n"
        + "\n".join(f"{m['role']}: {m.get('content','')[:1200]}" for m in head)
    )
    try:
        summary = llm.complete(
            "You are a terse summarizer.",
            [{"role": "user", "content": digest_prompt}],
            temperature=0.1, max_tokens=400,
        )
    except Exception:
        return history  # compression is best-effort
    return [{"role": "user", "content": f"[summary of earlier turns]\n{summary}"}, *tail]


def _majority_call(raws: list[str]) -> Optional[str]:
    """Given N model outputs, return the one whose tool_call name appears
    most frequently. Ties broken by first occurrence."""
    names = []
    for r in raws:
        m = TAG_CALL.search(r)
        if not m:
            names.append(None)
            continue
        try:
            names.append(json.loads(m.group(1).strip()).get("name"))
        except Exception:
            names.append(None)
    if not any(names):
        return raws[0] if raws else None
    winner, _ = Counter(n for n in names if n).most_common(1)[0]
    for r, n in zip(raws, names):
        if n == winner:
            return r
    return raws[0]


class Agent:
    def __init__(self, llm: LlamaClient, system_prompt: str,
                 max_turns: int = 20, yolo: bool = False,
                 skill_rag: bool = True, plan_first: bool = True,
                 few_shot: bool = True, reflect: str = "auto",
                 vote: int = 1, context_compress: bool = True,
                 tier: str = "mobile", n_ctx: int = 1536):
        self.llm = llm
        # Inject authorization context so the base model stops nagging about
        # legitimate security work. The 4 hard-block categories are enforced
        # below this layer and cannot be bypassed regardless of prompt content.
        self.base_system = inject_authorization(system_prompt) + \
                           "\n\n# Tool schemas\n" + \
                           json.dumps(get_tool_schemas(), indent=2)
        self.max_turns = max_turns
        self.yolo = yolo
        self.skill_rag = skill_rag
        self.plan_first = plan_first
        self.few_shot = few_shot
        self.vote = max(1, int(vote)) if tier == "workstation" else 1
        self.context_compress = context_compress
        self.tier = tier
        self.n_ctx = n_ctx
        # reflect: auto = on when tier != mobile
        if reflect == "auto":
            self.reflect = (tier != "mobile")
        else:
            self.reflect = (str(reflect).lower() in ("on", "true", "1", "yes"))
        self.history: list[dict] = []

    # ------------------------------------------------------------------ plumbing
    def _build_system(self, user_msg: str) -> str:
        system = self.base_system
        if self.skill_rag:
            system += _skill_block(user_msg)
        if self.few_shot:
            system += _fewshot_block(user_msg)
        if self.plan_first:
            system += (
                "\n\n# First-turn rule\n"
                "On your FIRST assistant turn for this user prompt, emit exactly:\n"
                "  <plan>1. step\\n2. step\\n...</plan>\n"
                "  <thought>why the first step</thought>\n"
                "  <tool_call>{...}</tool_call>\n"
                "On subsequent turns, omit <plan>."
            )
        return system

    def _maybe_compress(self) -> None:
        if not self.context_compress:
            return
        # Trigger when 70% of context window is used
        if _approx_tokens(self.history) > int(self.n_ctx * 0.7):
            self.history = _compress_history(self.llm, self.history)

    def _complete(self, system: str) -> str:
        if self.vote <= 1:
            return self.llm.complete(system, self.history)
        raws = []
        for i in range(self.vote):
            try:
                raws.append(self.llm.complete(
                    system, self.history,
                    temperature=0.7 if i > 0 else 0.2))
            except Exception:
                continue
        if not raws:
            raise RuntimeError("all vote rollouts failed")
        return _majority_call(raws) or raws[0]

    def _reflect_final(self, system: str, final_text: str) -> str:
        """One critique pass. Returns a (possibly revised) final string."""
        critique_system = (
            "You are reviewing an agent's final answer. "
            "If it correctly addresses the user's request, reply with exactly "
            "<confirm/>. Otherwise, reply with a corrected <final>...</final>."
        )
        review_hist = self.history + [{
            "role": "user",
            "content": f"Candidate final answer:\n<final>{final_text}</final>\n\n"
                       f"Does this address the original user request? "
                       f"Reply <confirm/> or corrected <final>.",
        }]
        try:
            raw = self.llm.complete(critique_system, review_hist,
                                    temperature=0.1, max_tokens=400)
        except Exception:
            return final_text
        if TAG_CONFIRM.search(raw):
            return final_text
        m = TAG_FINAL.search(raw)
        return m.group(1).strip() if m else final_text

    # ------------------------------------------------------------------ main loop
    def run(self, user_msg: str) -> Iterator[Event]:
        self._retried_refusal = False
        try:
            check_hard_blocks(user_msg, where="user_prompt")
        except HardBlockError as e:
            if e.category == "quarantine":
                yield Event("final",
                            f"🔒 Device quarantine active. Repeated hard-block "
                            f"violations have triggered a cooldown. {e.match}. "
                            f"Review ~/.slm/traces/hardblock.log for the attempts "
                            f"this device made.")
            elif e.category == "non_latin_bypass":
                scripts = getattr(e, "detected_scripts", ["non-Latin"])
                yield Event("final",
                            f"This agent accepts English + European languages only "
                            f"(Latin-script + Greek + emojis). Detected: "
                            f"{', '.join(scripts)}. Please rephrase in English.")
            else:
                yield Event("final",
                            f"I can't help with that ({e.category}). This is a hard limit.")
            return

        system = self._build_system(user_msg)
        self.history.append({"role": "user", "content": user_msg})
        limiter = RateLimiter(_guardrail("max_tool_calls_per_turn", 90))
        first_turn = True
        plan_text = ""
        tools_fired = 0

        for _ in range(self.max_turns):
            if freeze_active():
                yield Event("error", "FREEZE active — agent halted.")
                return

            self._maybe_compress()

            canary = mint_canary()
            system_with_canary = system + canary_instruction(canary)
            raw = self._complete(system_with_canary)
            try:
                check_leak(raw, canary, where="model_output")
            except InjectionDetected as e:
                yield Event("error",
                            f"🚨 prompt-injection detected (canary leaked @ {e.where}). "
                            f"halting turn. see ~/.slm/canary_log.jsonl")
                return
            try:
                check_hard_blocks(raw, where="model_output")
            except HardBlockError as e:
                yield Event("final",
                            f"I can't help with that ({e.category}). This is a hard limit.")
                return

            if first_turn and (pm := TAG_PLAN.search(raw)):
                plan_text = pm.group(1).strip()
                yield Event("plan", plan_text)
            if (m := TAG_THOUGHT.search(raw)):
                yield Event("thought", m.group(1).strip())
            if (m := TAG_FINAL.search(raw)):
                final_text = m.group(1).strip()

                # Anti-nag: if the model is refusing in-scope work (not one
                # of the 4 hard-block categories), retry once with stronger
                # authorization context
                if is_refusal(final_text) and not is_legitimate_refusal(user_msg, final_text):
                    if not getattr(self, "_retried_refusal", False):
                        self._retried_refusal = True
                        yield Event("thought",
                                    "[anti-nag] model over-refused in-scope work; retrying")
                        # Drop the refusal and push a stronger re-ask
                        self.history.append({"role": "user",
                                             "content": retry_prompt(user_msg)})
                        continue
                self._retried_refusal = False

                self.history.append({"role": "assistant", "content": raw})
                if self.reflect:
                    final_text = self._reflect_final(system, final_text)
                # Record exemplar for future few-shot
                try:
                    from slm.session import record_exemplar
                    record_exemplar(user_msg, plan_text, final_text, tools_fired)
                except Exception:
                    pass
                yield Event("final", final_text)
                return

            call = TAG_CALL.search(raw)
            if not call:
                yield Event("error",
                            "model produced no tool_call or final — retrying with nudge")
                self.history.append({"role": "assistant", "content": raw})
                nudge = "Respond only with "
                if first_turn and self.plan_first:
                    nudge += "<plan>…</plan> then "
                nudge += "<thought>…</thought> then <tool_call>…</tool_call> or <final>…</final>."
                self.history.append({"role": "user", "content": nudge})
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

            if not self.yolo and needs_confirmation(name):
                yield Event("confirm", f"{name}({json.dumps(args)})",
                            meta={"name": name, "args": args})

            yield Event("tool_call", f"{name}({json.dumps(args)})",
                        meta={"name": name, "args": args})
            t0 = time.time()
            try:
                result = dispatch(name, args)
                if result is None:
                    result = "(no output)"
                check_hard_blocks(result, where="tool_result")
            except HardBlockError as e:
                self.history.append({"role": "assistant", "content": raw})
                self.history.append({"role": "user",
                                     "content": f"<tool_result>[blocked:{e.category}]</tool_result>"})
                yield Event("final",
                            f"Blocked content from tool ({e.category}); stopping.")
                return
            except (TimeoutError, subprocess.TimeoutExpired) as e:
                result = f"error: tool timed out ({e})"
            except PermissionError as e:
                result = f"error: permission denied — {e}"
            except FileNotFoundError as e:
                result = f"error: not found — {e}"
            except Exception as e:
                result = f"error: {type(e).__name__}: {e}"
            dt = time.time() - t0
            tools_fired += 1
            yield Event("tool_result", result, meta={"dt": dt, "name": name})

            self.history.append({"role": "assistant", "content": raw})
            self.history.append({"role": "user",
                                 "content": f"<tool_result>{result}</tool_result>"})
            first_turn = False
        yield Event("error", f"max_turns ({self.max_turns}) reached without <final>")

    # ------------------------------------------------------------------ autonomous goal pursuit
    def pursue(self, goal: str, max_cycles: int = 5, budget=None) -> Iterator[Event]:
        """Keep taking turns until the goal is achieved, a hard-block fires,
        max_cycles is reached, or the budget is exhausted.

        After each <final>, a critique decides whether the goal is satisfied;
        if not, the critique's next-step prompt becomes the next user_msg.

        `budget` is an optional slm.budget.Budget instance for time/tool limits.
        """
        if budget is not None and budget.ts_start == 0.0:
            budget.start()
        user_msg = goal
        for cycle in range(max_cycles):
            yield Event("thought", f"[autonomous cycle {cycle+1}/{max_cycles}] {user_msg}",
                        meta={"cycle": cycle})
            last_final = ""
            for ev in self.run(user_msg):
                yield ev
                if ev.kind == "final":
                    last_final = ev.content
                if ev.kind == "tool_call" and budget is not None:
                    budget.tick(tools=1)
                if ev.kind in ("error",):
                    return
            if budget is not None and budget.exceeded():
                yield Event("final",
                            f"[budget exhausted: {budget.reason()} — stopping with partial results]")
                return
            if not last_final:
                return
            # Goal satisfaction check
            check_system = (
                "You are judging whether a goal has been achieved. "
                "Reply with exactly <done/> if the candidate answer fully "
                "satisfies the goal, otherwise reply with "
                "<next>one concrete next sub-task</next>."
            )
            check_hist = [{
                "role": "user",
                "content": f"Goal: {goal}\n\nLatest answer:\n{last_final}",
            }]
            try:
                verdict = self.llm.complete(check_system, check_hist,
                                            temperature=0.1, max_tokens=200)
            except Exception:
                return
            if re.search(r"<done\s*/>", verdict):
                yield Event("final", f"[goal achieved after {cycle+1} cycle(s)]",
                            meta={"cycles": cycle + 1})
                return
            nxt = re.search(r"<next>(.*?)</next>", verdict, re.S)
            if not nxt:
                return
            user_msg = nxt.group(1).strip()
            # Reset history so next cycle starts fresh (keeps context small)
            self.history.clear()
        yield Event("error", f"goal not achieved within {max_cycles} cycles")
