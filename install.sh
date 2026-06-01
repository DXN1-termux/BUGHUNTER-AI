#!/usr/bin/env bash
# BUGHUNTER-AI | TITAN EDITION INSTALLER
# 2026 DXN10DAY - MAXIMUM AUTONOMY ENABLED
set -euo pipefail

# Visual Constants
BOLD="\033[1m"
CYAN="\033[1;36m"
GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
MAGENTA="\033[1;35m"
RESET="\033[0m"

log()  { printf "${CYAN}▸${RESET} %s\n" "$*"; }
info() { printf "${BOLD}${MAGENTA}TITAN${RESET} | %s\n" "$*"; }
ok()   { printf "${GREEN}✓${RESET} %s\n" "$*"; }
err()  { printf "${RED}✗${RESET} %s\n" "$*" >&2; exit 1; }

intro() {
  clear
  printf "${RED}"
  cat <<'EOF'
  ██████╗ ██╗   ██╗ ██████╗ ██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗ 
  ██╔══██╗██║   ██║██╔════╝ ██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
  ██████╔╝██║   ██║██║  ███╗███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝
  ██╔══██╗██║   ██║██║   ██║██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗
  ██████╔╝╚██████╔╝╚██████╔╝██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║
  ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
                                 TITAN EDITION v2.4
EOF
  printf "${RESET}\n"
  info "Agentic Bug-Bounty SLM | 100% Local | 100% Autonomous"
  printf "\n"
}

check_env() {
  log "Analyzing system architecture..."
  local os_type; os_type=$(uname -s)
  local machine; machine=$(uname -m)
  ok "Platform: ${os_type} (${machine})"

  if [ "${os_type}" = "Android" ] || [ -n "${PREFIX:-}" ]; then
    log "Environment: Termux (Mobile)"
    if [ ! -x "$(dirname "$0")/slm/training/install.sh" ]; then
      err "Sub-installer not found at slm/training/install.sh"
    fi
    exec bash "$(dirname "$0")/slm/training/install.sh"
  fi
}

setup_venv() {
  log "Preparing Python environment..."
  if ! command -v python3 &>/dev/null; then
    err "python3 not found. Please install Python 3.10+."
  fi

  if [ ! -d ".venv" ]; then
    log "Initializing virtual environment..."
    python3 -m venv .venv || err "Failed to create venv."
  fi

  # shellcheck disable=SC1091
  source .venv/bin/activate
  log "Updating pip and build tools..."
  pip install --quiet --upgrade pip setuptools wheel || warn "Pip update partial"
}

install_deps() {
  log "Injecting TITAN dependencies..."
  # Check for optional but recommended system tools
  for t in git curl cmake pkg-config; do
    if ! command -v "$t" &>/dev/null; then
      printf "${YELLOW}⚠ Warning: ${t} not found. Some builds may fail.${RESET}\n"
    fi
  done

  pip install --quiet -e ".[dev]" || err "Dependency injection failed."
  ok "All core systems operational."
}

finalize() {
  printf "\n"
  ok "TITAN Installation Complete."
  printf "${BOLD}${CYAN}────────────────────────────────────────────────────────────${RESET}\n"
  printf "  Run: ${GREEN}source .venv/bin/activate && slm setup${RESET}\n"
  printf "  Then: ${GREEN}slm${RESET} to launch the TITAN interface.\n"
  printf "${BOLD}${CYAN}────────────────────────────────────────────────────────────${RESET}\n"
}

main() {
  intro
  check_env
  setup_venv
  install_deps
  finalize
}

main "$@"
