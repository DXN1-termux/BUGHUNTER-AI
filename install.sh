#!/usr/bin/env bash
# BUGHUNTER-AI installer — auto-detects platform and runs the right path.
# Usage:  bash install.sh
set -euo pipefail

BOLD="\033[1m"
CYAN="\033[1;36m"
GREEN="\033[1;32m"
RED="\033[1;31m"
RESET="\033[0m"

log()  { printf "${CYAN}▸${RESET} %s\n" "$*"; }
ok()   { printf "${GREEN}✓${RESET} %s\n" "$*"; }
err()  { printf "${RED}✗${RESET} %s\n" "$*" >&2; exit 1; }

if [ "$(uname -o 2>/dev/null)" = "Android" ]; then
    log "Detected Termux (Android) — running full mobile installer"
    exec bash "$(dirname "$0")/slm/training/install.sh"
fi

log "Detected $(uname -s) — running pip install"

if ! command -v python3 &>/dev/null; then
    err "python3 not found. Install Python 3.10+ first."
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    err "Python 3.10+ required (found $PY_VERSION)"
fi

if [ ! -d ".venv" ]; then
    log "Creating virtual environment"
    python3 -m venv .venv
fi

source .venv/bin/activate
log "Installing slm-agent"
pip install -e ".[dev]" --quiet

ok "Installed! Run: source .venv/bin/activate && slm --help"
echo
printf "${BOLD}Quick start:${RESET}\n"
echo "  slm init       # first-time config"
echo "  slm doctor     # health check"
echo "  slm            # open REPL"
