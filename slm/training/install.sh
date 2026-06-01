#!/usr/bin/env bash
# slm-agent TITAN Termux Installer
# Optimized for aarch64 | 2026 DXN10DAY
set -euo pipefail

# Visuals
BOLD="\033[1m"
BLUE="\033[1;34m"
GREEN="\033[1;32m"
RED="\033[1;31m"
CYAN="\033[1;36m"
YELLOW="\033[1;33m"
RESET="\033[0m"

log()  { printf "${BLUE}▸${RESET} %s\n" "$*"; }
warn() { printf "${YELLOW}⚠${RESET} %s\n" "$*" >&2; }
err()  { printf "${RED}✗${RESET} %s\n" "$*" >&2; exit 1; }
ok()   { printf "${GREEN}✓${RESET} %s\n" "$*"; }

SLM_HOME="${SLM_HOME:-$HOME/.slm}"
VENV="$SLM_HOME/venv"
BIN="$SLM_HOME/bin"
MODELS="$SLM_HOME/models"
CORE="$SLM_HOME/core"
REPO_URL="${SLM_REPO_URL:-https://github.com/DXN1-termux/BUGHUNTER-AI}"
MODEL_BASE_URL="${SLM_MODEL_URL:-https://github.com/DXN1-termux/BUGHUNTER-AI/releases/download/v2.3}"

intro() {
  clear
  printf "${RED}"
  cat <<'EOF'
  ██████╗ ██╗   ██╗ ██████╗ ██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗ 
  ██╔══██╗██║   ██║██╔════╝ ██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
  ██████╔╝██║   ██║██║  ███╗███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝
  ██╔══██╗██║   ██║██║   ██║██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗
  ██████╔╝╚██████╔╝╚██████╔╝██║  ╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║
  ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
                                 TERMUX TITAN v2.4
EOF
  printf "${RESET}\n"
  log "Initializing high-performance mobile environment..."
}

preflight() {
  log "Analyzing hardware..."
  [ "$(uname -o 2>/dev/null)" = "Android" ] || err "Non-Android platform detected."
  case "$(uname -m)" in aarch64|arm64) :;; *) err "Incompatible architecture: $(uname -m)";; esac
  
  local free_mb; free_mb=$(df -k "$HOME" | awk 'NR==2{print int($4/1024)}')
  if [ "$free_mb" -lt 2000 ]; then
    warn "Low disk space: ${free_mb}MB. 2.5GB+ recommended."
  fi
  
  command -v curl >/dev/null || pkg install -y curl
  ok "Hardware analysis complete."
}

bootstrap() {
  log "Synchronizing TITAN packages..."
  pkg update -y || warn "Standard update failed, trying fallback..."
  
  # core group
  pkg install -y python python-pip git clang cmake make pkg-config || warn "Core group partial"
  # build group
  pkg install -y rust golang openssl libjpeg-turbo file binutils || warn "Build group partial"
  # tools group
  pkg install -y nmap termux-api tmux nano proot-utils || warn "Tools group partial"
  
  if ! command -v termux-clipboard-get >/dev/null; then
    warn "Termux:API app not detected. Some features will be limited."
  fi
}

storage() {
  if [ ! -d "$HOME/storage" ]; then
    log "Requesting secure storage access..."
    termux-setup-storage || true
  fi
}

dirs() {
  log "Mapping TITAN directory structure..."
  mkdir -p "$SLM_HOME" "$VENV" "$BIN" "$MODELS" "$CORE" \
           "$SLM_HOME/skills" "$SLM_HOME/traces" "$SLM_HOME/proposals"
}

venv() {
  log "Isolating TITAN runtime..."
  [ -x "$VENV/bin/python" ] || python -m venv "$VENV"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  pip install --upgrade --no-cache-dir pip wheel setuptools >/dev/null
  echo "$("$VENV/bin/python" -V)" > "$SLM_HOME/.python-version"
}

llama_cpp() {
  if [ -x "$BIN/llama-server" ]; then return; fi
  log "Building TITAN LLM Engine (Optimized ARMv8.2)..."
  local src="$SLM_HOME/llama.cpp"
  [ -d "$src" ] || git clone --depth 1 https://github.com/ggerganov/llama.cpp "$src"
  cd "$src"
  cmake -B build -DGGML_NATIVE=ON -DGGML_LLAMAFILE=ON -DGGML_OPENMP=OFF -DGGML_CUDA=OFF -DGGML_METAL=OFF -DGGML_BLAS=OFF -DLLAMA_CURL=OFF >/dev/null
  
  local jobs=4; 
  local total_mem; total_mem=$(free -m | awk '/^Mem:/{print $2}')
  [ "$total_mem" -gt 4000 ] && jobs=8
  
  cmake --build build -j"$jobs" --target llama-server llama-bench llama-quantize
  install -m 0755 build/bin/llama-server "$BIN/llama-server"
  install -m 0755 build/bin/llama-bench  "$BIN/llama-bench"
  cd - >/dev/null
}

python_deps() {
  log "Injecting logic modules..."
  source "$VENV/bin/activate"
  pip install --no-cache-dir \
    typer rich prompt-toolkit textual httpx flask \
    beautifulsoup4 jsonschema pyyaml sqlite-utils >/dev/null
}

app_install() {
  log "Deploying BUGHUNTER-AI core..."
  local app_src="$SLM_HOME/app"
  if [ ! -d "$app_src/.git" ]; then
    git clone --depth 1 "$REPO_URL" "$app_src"
  else
    (cd "$app_src" && git pull --ff-only)
  fi
  pip install --no-cache-dir -e "$app_src" >/dev/null
  
  # Master wrapper
  cat > "$PREFIX/bin/slm" <<EOF
#!$VENV/bin/python
from slm.cli import app
if __name__ == "__main__":
    app()
EOF
  chmod +x "$PREFIX/bin/slm"
}

main() {
  intro
  preflight
  bootstrap
  storage
  dirs
  venv
  llama_cpp
  python_deps
  app_install
  
  printf "\n${GREEN}✓ TITAN Deployment Successful.${RESET}\n"
  printf "  Run: ${BOLD}slm setup${RESET}\n\n"
}

main "$@"
