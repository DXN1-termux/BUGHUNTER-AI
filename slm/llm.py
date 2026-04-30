"""HTTP client for llama-server (OpenAI-compatible endpoint).

Reliability features:
  - persistent httpx.Client (connection reuse — ~20-40 ms saved per turn)
  - auto-respawn if the server process dies mid-run
  - exponential retry on transient network errors (up to 3 attempts)
  - context-aware max_tokens: never requests more than fits in n_ctx
"""
from __future__ import annotations
import httpx, pathlib, subprocess, time, os, signal, atexit, socket


class LlamaClient:
    def __init__(self, model_path: str, host: str = "127.0.0.1", port: int = 8081,
                 n_ctx: int = 1536, n_threads: int = 6, n_batch: int = 256,
                 flash_attn: bool = True, auto_start: bool = True):
        self.host, self.port = host, port
        self.base = f"http://{host}:{port}"
        self.model_path = model_path
        self.n_ctx = n_ctx
        self._spawn_args = (n_ctx, n_threads, n_batch, flash_attn)
        self._proc: subprocess.Popen | None = None
        # persistent HTTP/1.1 keep-alive connection to the local server
        self._http = httpx.Client(
            base_url=self.base, timeout=httpx.Timeout(120.0, connect=5.0),
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
        )
        if auto_start and not self._ping():
            self._spawn(*self._spawn_args)
        atexit.register(self.close)

    # -------------------------------------------------------------- lifecycle
    def _ping(self) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=0.5):
                return True
        except OSError:
            return False

    def _server_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None and self._ping()

    def _spawn(self, n_ctx, n_threads, n_batch, flash_attn):
        bin_ = pathlib.Path(os.environ.get("SLM_HOME",
                                           pathlib.Path.home() / ".slm")) / "bin" / "llama-server"
        if not bin_.exists():
            raise RuntimeError(f"llama-server binary missing: {bin_}")
        if not pathlib.Path(self.model_path).exists():
            raise RuntimeError(f"model file missing: {self.model_path}")
        cmd = [str(bin_),
               "-m", self.model_path,
               "--host", self.host, "--port", str(self.port),
               "-c", str(n_ctx), "-t", str(n_threads), "-b", str(n_batch),
               "--mlock", "0", "--mmap", "1"]
        if flash_attn:
            cmd += ["--flash-attn"]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.PIPE,
                                      start_new_session=True)
        for _ in range(60):
            if self._ping():
                return
            if self._proc.poll() is not None:
                err = (self._proc.stderr.read().decode("utf-8", "replace")[-1000:]
                       if self._proc.stderr else "")
                raise RuntimeError(f"llama-server exited early:\n{err}")
            time.sleep(0.5)
        try:
            self._proc.terminate()
            err = (self._proc.stderr.read().decode("utf-8", "replace")[-1000:]
                   if self._proc.stderr else "")
        except Exception:
            err = ""
        raise RuntimeError(f"llama-server did not come up within 30s\n{err}")

    def stop(self):
        if self._proc and self._proc.poll() is None:
            try:
                os.killpg(self._proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                try:
                    self._proc.terminate()
                except Exception:
                    pass

    def close(self):
        try:
            self._http.close()
        except Exception:
            pass
        self.stop()

    def _ensure_up(self) -> None:
        """Respawn the server if it died between turns."""
        if self._server_alive():
            return
        # clean up the dead one before relaunching
        if self._proc is not None and self._proc.poll() is not None:
            self._proc = None
        self._spawn(*self._spawn_args)

    # -------------------------------------------------------------- completion
    def _token_budget(self, history: list[dict], max_tokens: int) -> int:
        """Clamp max_tokens so (rough) prompt + completion <= n_ctx - 128 safety.
        Crude 4-char/token estimator; good enough to avoid EOC truncation."""
        used = sum(len(m.get("content", "")) for m in history) // 4
        room = max(128, self.n_ctx - used - 128)
        return min(max_tokens, room)

    def complete(self, system: str, history: list[dict],
                 temperature: float = 0.2, max_tokens: int = 512) -> str:
        msgs = [{"role": "system", "content": system}] + history
        max_tokens = self._token_budget(msgs, max_tokens)
        payload = {"messages": msgs, "temperature": temperature,
                   "max_tokens": max_tokens}

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                self._ensure_up()
                r = self._http.post("/v1/chat/completions", json=payload)
                r.raise_for_status()
                data = r.json()
                choices = data.get("choices")
                if not choices or not isinstance(choices, list):
                    raise RuntimeError(f"malformed response: no choices in {list(data.keys())}")
                msg = choices[0].get("message") or {}
                txt = msg.get("content") or ""
                if not txt.strip():
                    if attempt < 2:
                        last_err = RuntimeError("empty response from model")
                        time.sleep(0.5 * (2 ** attempt))
                        continue
                    raise RuntimeError("model returned empty content after 3 attempts")
                break
            except (httpx.TransportError, httpx.ReadTimeout) as e:
                last_err = e
                time.sleep(0.5 * (2 ** attempt))
            except httpx.HTTPStatusError as e:
                # 5xx = server side, worth retrying; 4xx = fatal
                if 500 <= e.response.status_code < 600 and attempt < 2:
                    last_err = e
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise
        else:
            raise RuntimeError(
                f"llama-server unreachable after 3 attempts: {last_err}")

        # Truncate at first closing tag so the model can't run on past its answer
        for stop in ("</final>", "</tool_call>"):
            i = txt.find(stop)
            if i != -1:
                txt = txt[: i + len(stop)]
                break
        if "<tool_call>" in txt and "</tool_call>" not in txt:
            txt += "</tool_call>"
        if "<final>" in txt and "</final>" not in txt:
            txt += "</final>"
        return txt
