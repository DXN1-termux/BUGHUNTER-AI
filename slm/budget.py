"""Budget enforcement — time / token / tool-call caps for long-running goals.

Primary use case: autonomous mode. "Recon this domain overnight" shouldn't
run for 48 hours. You set a budget, the agent respects it, and exits
gracefully with whatever it has when the budget is spent.

Budget fields (any can be None = unlimited):
    max_tokens      : sum of input + output tokens across the whole run
    max_seconds     : wall-clock time
    max_tools       : total tool invocations
    max_findings    : stop after this many vulns saved

Usage:
    b = Budget(max_seconds=3600, max_tools=100)
    b.start()
    ...
    b.tick(tokens=42, tools=1)
    if b.exceeded():
        reason = b.reason()    # "max_seconds" or "max_tools" etc.
        break
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Budget:
    max_tokens: Optional[int] = None
    max_seconds: Optional[float] = None
    max_tools: Optional[int] = None
    max_findings: Optional[int] = None

    tokens_used: int = 0
    tools_used: int = 0
    findings_added: int = 0
    ts_start: float = 0.0

    def start(self) -> None:
        self.ts_start = time.time()

    def tick(self, tokens: int = 0, tools: int = 0, findings: int = 0) -> None:
        self.tokens_used += tokens
        self.tools_used += tools
        self.findings_added += findings

    def elapsed(self) -> float:
        return time.time() - self.ts_start if self.ts_start > 0 else 0.0

    def exceeded(self) -> bool:
        return self.reason() is not None

    def reason(self) -> Optional[str]:
        if self.max_tokens is not None and self.tokens_used >= self.max_tokens:
            return "max_tokens"
        if self.max_seconds is not None and self.elapsed() >= self.max_seconds:
            return "max_seconds"
        if self.max_tools is not None and self.tools_used >= self.max_tools:
            return "max_tools"
        if self.max_findings is not None and self.findings_added >= self.max_findings:
            return "max_findings"
        return None

    def remaining(self) -> dict:
        return {
            "tokens": None if self.max_tokens is None else self.max_tokens - self.tokens_used,
            "seconds": None if self.max_seconds is None else round(self.max_seconds - self.elapsed(), 1),
            "tools": None if self.max_tools is None else self.max_tools - self.tools_used,
            "findings": None if self.max_findings is None else self.max_findings - self.findings_added,
        }

    def format(self) -> str:
        r = self.remaining()
        parts = []
        for k, v in r.items():
            if v is not None:
                parts.append(f"{k}={v}")
        return "budget remaining: " + (" ".join(parts) if parts else "unlimited")
