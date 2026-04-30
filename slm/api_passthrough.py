"""External LLM passthrough — call Anthropic/OpenAI when needed.

The local model is fast and private. For very hard sub-tasks (complex reasoning,
long-context summarization), you can route a single call to a bigger model.

Credentials come from the encrypted vault. Every call:
  - uses a named provider (anthropic, openai)
  - token usage logged (not content)
  - hard blocks still fire on prompt AND response
  - canary still active on the response

Providers are scoped — you register each key with `slm vault set` and only
registered providers can be used.

Cost awareness: the call duration + token estimate is logged to ~/.slm/api_usage.jsonl
(hashes only — never raw prompts/responses).
"""
from __future__ import annotations
import hashlib, json, os, pathlib, time
import httpx

from slm.core.executor_guards import check_hard_blocks
from slm.canary import mint_canary, canary_instruction, check_leak, InjectionDetected

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
LOG = SLM_HOME / "api_usage.jsonl"

PROVIDERS = {
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "key_name": "ANTHROPIC_API_KEY",
        "models": ["claude-opus-4.7", "claude-sonnet-4.5", "claude-haiku-4"],
        "default_model": "claude-sonnet-4.5",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "key_name": "OPENAI_API_KEY",
        "models": ["gpt-5", "gpt-4o", "gpt-4-turbo"],
        "default_model": "gpt-4o",
    },
}


def _log_usage(provider: str, model: str, input_chars: int,
               output_chars: int, duration: float, status: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": time.time(),
        "provider": provider,
        "model": model,
        "input_chars": input_chars,
        "output_chars": output_chars,
        "duration_s": round(duration, 2),
        "status": status,
    }
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def call(provider: str, prompt: str, *, model: str | None = None,
         max_tokens: int = 1024, system: str = "") -> str:
    """Call an external LLM. Returns response text. Raises on failure.

    Both prompt and response pass through hard-block + canary checks.
    """
    if provider not in PROVIDERS:
        return f"error: unknown provider '{provider}'. Valid: {list(PROVIDERS)}"

    check_hard_blocks(prompt, where="api_passthrough_prompt")
    if system:
        check_hard_blocks(system, where="api_passthrough_system")

    try:
        from slm.vault import get_secret, is_unlocked
    except ImportError:
        return "error: vault module unavailable"
    if not is_unlocked():
        return "error: vault locked — run `slm vault unlock` first"

    p = PROVIDERS[provider]
    api_key = get_secret(p["key_name"])
    if not api_key:
        return f"error: no {p['key_name']} in vault — run: slm vault set {p['key_name']} <key>"

    model = model or p["default_model"]
    if model not in p["models"]:
        return f"error: model '{model}' not allowed for {provider}. Valid: {p['models']}"

    # Inject canary into system prompt for injection detection
    canary = mint_canary()
    final_system = (system or "") + canary_instruction(canary)

    t0 = time.time()
    try:
        if provider == "anthropic":
            r = httpx.post(p["url"],
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": final_system,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0)
            r.raise_for_status()
            text = r.json()["content"][0]["text"]
        elif provider == "openai":
            r = httpx.post(p["url"],
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": final_system},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=60.0)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        else:
            return f"error: provider {provider} not implemented"
    except httpx.HTTPStatusError as e:
        _log_usage(provider, model, len(prompt), 0, time.time() - t0,
                   f"http_{e.response.status_code}")
        return f"error: {provider} returned {e.response.status_code}"
    except Exception as e:
        _log_usage(provider, model, len(prompt), 0, time.time() - t0, "exception")
        return f"error: {type(e).__name__}: {e}"

    duration = time.time() - t0
    _log_usage(provider, model, len(prompt), len(text), duration, "ok")

    # Check the external response for injection + hard blocks
    try:
        check_leak(text, canary, where=f"api:{provider}")
    except InjectionDetected:
        return f"error: prompt-injection detected in {provider} response — halted"
    check_hard_blocks(text, where=f"api_passthrough_result:{provider}")

    return text
