#!/usr/bin/env bash
# slm-agent Termux installer — designed for Samsung A52, aarch64, unrooted.
# Idempotent + resumable. Run: curl -sSL <url>/install.sh | bash
set -euo pipefail

SLM_HOME="${SLM_HOME:-$HOME/.slm}"
APP_DIR="$SLM_HOME/app"
VENV="$SLM_HOME/venv"
BIN="$SLM_HOME/bin"
MODELS="$SLM_HOME/models"
CORE="$SLM_HOME/core"
REPO_URL="${SLM_REPO_URL:-https://github.com/DXN1-termux/BUGHUNTER-AI}"
MODEL_BASE_URL="${SLM_MODEL_URL:-https://github.com/DXN1-termux/BUGHUNTER-AI/releases/download/v2.3}"

log()  { printf "\033[1;34m▸\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m⚠\033[0m %s\n" "$*" >&2; }
err()  { printf "\033[1;31m✗\033[0m %s\n" "$*" >&2; exit 1; }
ok()   { printf "\033[1;32m✓\033[0m %s\n" "$*"; }

# ---------------------------------------------------------- 1. preflight
preflight() {
  log "Preflight checks"
  [ "$(uname -o 2>/dev/null)" = "Android" ] || err "Not running on Android/Termux"
  [ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ]   || err "Termux \$PREFIX missing — install Termux from F-Droid"
  case "$(uname -m)" in aarch64|arm64) :;; *) err "Need aarch64, found $(uname -m)";; esac
  local free_mb; free_mb=$(df -m "$HOME" | awk 'NR==2{print $4}')
  [ "$free_mb" -ge 2500 ] || err "Need ≥2.5GB free in \$HOME (have ${free_mb}MB)"
  command -v curl >/dev/null || pkg install -y curl
  curl -fsS --max-time 10 https://github.com >/dev/null || err "No internet / github unreachable"
  ok "Preflight OK"
}

# ---------------------------------------------------------- 2. pkg bootstrap
pkg_bootstrap() {
  log "Updating Termux packages (may take a few minutes)"
  local tries=0
  until pkg update -y 2>/dev/null; do
    tries=$((tries+1)); [ $tries -ge 3 ] && { warn "pkg update failed 3x — run: termux-change-repo"; break; }
    sleep 2
  done
  # Split into groups so one missing pkg doesn't abort everything
  pkg install -y python python-pip git clang cmake make pkg-config || warn "core pkg group partial"
  pkg install -y rust golang openssl libjpeg-turbo file binutils   || warn "build pkg group partial"
  pkg install -y nmap tesseract termux-api tmux nano proot-utils   || warn "extras pkg group partial"
  ok "Packages installed"
}

# ---------------------------------------------------------- 3. Termux:API check (non-blocking)
termux_api_check() {
  if ! command -v termux-clipboard-get >/dev/null; then
    warn "Termux:API Android app not detected."
    warn "  Install from F-Droid: https://f-droid.org/packages/com.termux.api/"
    warn "  Clipboard/notify/screenshot tools will auto-disable until installed."
  else
    ok "Termux:API reachable"
  fi
}

# ---------------------------------------------------------- 4. storage
storage_setup() {
  if [ ! -d "$HOME/storage" ]; then
    log "Requesting Android storage permission…"
    log "A permission dialog will appear. Tap ALLOW, then press Enter."
    termux-setup-storage || true
    read -r _ || true
  fi
  ok "Storage ready"
}

# ---------------------------------------------------------- 5. dirs
dirs() {
  mkdir -p "$SLM_HOME" "$APP_DIR" "$VENV" "$BIN" "$MODELS" "$CORE" \
           "$SLM_HOME/skills" "$SLM_HOME/traces" "$SLM_HOME/proposals"
  ok "Directory tree at $SLM_HOME"
}

# ---------------------------------------------------------- 6. venv
venv_setup() {
  log "Python venv"
  [ -x "$VENV/bin/python" ] || python -m venv "$VENV"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  pip install --upgrade --no-cache-dir pip wheel setuptools >/dev/null
  ok "Venv ready ($("$VENV/bin/python" -V))"
  echo "$("$VENV/bin/python" -V)" > "$SLM_HOME/.python-version"
}

# ---------------------------------------------------------- 7. llama.cpp build
llama_cpp_build() {
  if [ -x "$BIN/llama-server" ]; then ok "llama.cpp already built — skipping"; return; fi
  log "Building llama.cpp from source (ARM NEON + dotprod optimized)"
  local src="$SLM_HOME/llama.cpp"
  [ -d "$src" ] || git clone --depth 1 https://github.com/ggerganov/llama.cpp "$src"
  cd "$src"
  cmake -B build \
        -DGGML_NATIVE=ON \
        -DGGML_LLAMAFILE=ON \
        -DGGML_OPENMP=OFF \
        -DGGML_CUDA=OFF \
        -DGGML_METAL=OFF \
        -DGGML_BLAS=OFF \
        -DLLAMA_CURL=OFF \
        >/dev/null
  local free_mb; free_mb=$(free -m | awk '/^Mem:/{print $7}')
  local jobs=6; [ "${free_mb:-0}" -lt 3000 ] && jobs=2
  cmake --build build -j"$jobs" --target llama-cli llama-server llama-bench llama-imatrix llama-quantize
  install -m 0755 build/bin/llama-cli      "$BIN/llama-cli"
  install -m 0755 build/bin/llama-server   "$BIN/llama-server"
  install -m 0755 build/bin/llama-bench    "$BIN/llama-bench"
  cd - >/dev/null
  ok "llama.cpp built → $BIN"
}

# ---------------------------------------------------------- 8. python deps
python_deps() {
  log "Python dependencies (core)"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  pip install --no-cache-dir \
    typer rich prompt-toolkit textual httpx duckduckgo-search \
    beautifulsoup4 jsonschema pyyaml sqlite-utils >/dev/null
  ok "Core Python deps installed"

  log "Optional: llama-cpp-python (non-blocking)"
  CMAKE_ARGS="-DGGML_NATIVE=ON -DGGML_OPENMP=OFF -DGGML_LLAMAFILE=ON -DGGML_CUDA=OFF -DGGML_METAL=OFF -DGGML_BLAS=OFF" \
    FORCE_CMAKE=1 pip install --no-cache-dir llama-cpp-python 2>/dev/null \
    && ok "llama-cpp-python built" \
    || warn "llama-cpp-python skipped — will use llama-server HTTP instead (expected)"

  log "Optional: snowflake-connector-python (non-blocking)"
  export CARGO_NET_GIT_FETCH_WITH_CLI=true
  pip install --no-cache-dir 'snowflake-connector-python<4' 2>/dev/null \
    && ok "Snowflake connector installed" \
    || warn "Snowflake connector skipped — run_sql tool disabled. Fix later with: slm install-snowflake"
}

# ---------------------------------------------------------- 9. go tools (prebuilt)
gotools_fetch() {
  log "Bug-bounty Go tools"
  for tool in subfinder httpx nuclei ffuf katana; do
    if [ -x "$BIN/$tool" ]; then continue; fi
    curl -fsSL -C - -o "$BIN/$tool" "$MODEL_BASE_URL/${tool}-linux-arm64" \
      && chmod +x "$BIN/$tool" \
      && ok "  $tool" \
      || warn "  $tool download failed — skipping (install Go + build manually)"
  done
  # sqlmap is pure python
  "$VENV/bin/pip" install --no-cache-dir sqlmap >/dev/null 2>&1 || warn "sqlmap skipped"
}

# ---------------------------------------------------------- 10. model fetch
model_fetch() {
  log "Downloading model weights (resumable)"
  for q in IQ2_XS IQ3_XXS; do
    local f="$MODELS/slm-agent-v1.${q}.gguf"
    if [ -f "$f" ] && sha256sum -c "$MODELS/${q}.sha256" >/dev/null 2>&1; then
      ok "  $q already present + verified"; continue
    fi
    curl -fL -C - -o "$f"                    "$MODEL_BASE_URL/slm-agent-v1.${q}.gguf"
    curl -fL     -o "$MODELS/${q}.sha256"    "$MODEL_BASE_URL/slm-agent-v1.${q}.gguf.sha256"
    (cd "$MODELS" && sha256sum -c "${q}.sha256") || err "$q checksum failed — retry install"
    ok "  $q verified"
  done
}

# ---------------------------------------------------------- 11. app install
app_install() {
  log "Installing slm app"
  if [ ! -d "$APP_DIR/.git" ]; then
    git clone --depth 1 "$REPO_URL" "$APP_DIR"
  else
    (cd "$APP_DIR" && git pull --ff-only) || warn "git pull skipped"
  fi
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  pip install --no-cache-dir -e "$APP_DIR" >/dev/null
  # absolute-path shebang wrapper so new shells work without venv activation
  cat > "$PREFIX/bin/slm" <<EOF
#!$VENV/bin/python
from slm.cli import app
if __name__ == "__main__":
    app()
EOF
  chmod +x "$PREFIX/bin/slm"
  ok "slm installed — $(command -v slm)"
}

# ---------------------------------------------------------- 12. immutable core
core_lock() {
  log "Locking immutable core (chmod 444)"
  cp -nr "$APP_DIR/slm/core/"* "$CORE/"
  chmod -R 444 "$CORE"
  find "$CORE" -type d -exec chmod 555 {} \;
  ok "Core locked"
}

# ---------------------------------------------------------- 13. first-run wizard
first_run() {
  [ -f "$SLM_HOME/config.toml" ] && { ok "Config already exists"; return; }
  log "First-run config"
  cat > "$SLM_HOME/config.toml" <<EOF
[model]
primary  = "$MODELS/slm-agent-v1.IQ2_XS.gguf"
fallback = "$MODELS/slm-agent-v1.IQ3_XXS.gguf"
n_ctx      = 1536
n_threads  = 6
n_batch    = 256
flash_attn = true

[server]
host = "127.0.0.1"
port = 8081

[ui]
mode = "repl"       # repl | tui
yolo = false

[snowflake]
enabled = false
EOF
  cp "$APP_DIR/prompts/system.md" "$SLM_HOME/system.md"
  cat > "$SLM_HOME/scope.yaml" <<EOF
# Authorized targets. Network tools refuse anything NOT listed.
programs: []
domains:  []
ips:      []
EOF
  cat > "$SLM_HOME/guardrails.toml" <<EOF
max_tool_calls_per_turn = 20
shell_timeout_sec = 30
shell_output_cap_bytes = 2048
fetch_output_cap_bytes = 4096
network_allowlist = []
EOF
  ok "Defaults written to $SLM_HOME — edit scope.yaml before using network tools"
}

# ---------------------------------------------------------- 14. bench + smoke
bench_and_smoke() {
  log "Benchmarking (60s sustained) — this picks IQ2_XS vs IQ3_XXS"
  slm bench || warn "bench failed — run later: slm bench"
  log "Smoke test"
  slm "say hello in five words" || warn "smoke test failed — run: slm doctor"
}

# ---------------------------------------------------------- run
main() {
  preflight
  pkg_bootstrap
  termux_api_check
  storage_setup
  dirs
  venv_setup
  llama_cpp_build
  python_deps
  gotools_fetch
  model_fetch
  app_install
  core_lock
  first_run
  bench_and_smoke
  cat <<EOF

\033[1;32m╭─────────────────────────────────────────────╮
│  slm-agent installed.                       │
│                                             │
│  Edit scope:   nano ~/.slm/scope.yaml       │
│  Start REPL:   slm                          │
│  Full TUI:     slm --tui                    │
│  One-shot:     slm "recon example.com"      │
│  Health:       slm doctor                   │
│  Uninstall:    slm uninstall                │
╰─────────────────────────────────────────────╯\033[0m

EOF
}
main "$@"
