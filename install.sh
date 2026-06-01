#!/usr/bin/env bash
# BUGHUNTER-AI installer — auto-detects platform and runs the right path.
# Usage:  bash install.sh
set -euo pipefail

BOLD="\033[1m"
CYAN="\033[1;36m"
GREEN="\033[1;32m"
RED="\033[1;31m"
RESET="\033[0m"

# UI helpers for a modern, clean installation
log()  { printf "\033[1;36m🔵 %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m✅ %s\033[0m\n" "$*"; }
err()  { printf "\033[1;31m❌ %s\033[0m\n" "$*" >&2; exit 1; }

if [ "$(uname -o 2>/dev/null)" = "Android" ]; then
    log "Detected Termux (Android) — initializing mobile setup"
    exec bash "$(dirname "$0")/slm/training/install.sh"
fi

log "Detected $(uname -s) — preparing environment"

if ! command -v python3 &>/dev/null; then
    err "python3 not found."
fi

if [ ! -d ".venv" ]; then
    log "Creating virtual environment..."
    python3 -m venv .venv >/dev/null 2>&1
fi

source .venv/bin/activate
log "Installing dependencies..."
pip install --quiet -e ".[dev]" >/dev/null 2>&1

ok "Installed! Run: source .venv/bin/activate && slm"
