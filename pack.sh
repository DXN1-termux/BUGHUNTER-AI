#!/usr/bin/env bash
# Pack the slm-agent tree into a single tar.gz for distribution.
# Run from inside the slm-agent/ directory on ANY machine with tar.
set -euo pipefail
cd "$(dirname "$0")"

# Fix the known workspace-path quirk: agent.py and system.md may have
# landed under slm/prompts/ when they should be at slm/agent.py and
# prompts/system.md respectively.
if [ -f slm/prompts/agent.py ] && [ ! -f slm/agent.py ]; then
    mv slm/prompts/agent.py slm/agent.py
fi
if [ -f slm/prompts/system.md ]; then
    mkdir -p prompts
    [ -f prompts/system.md ] || mv slm/prompts/system.md prompts/system.md
fi
rmdir slm/prompts 2>/dev/null || true

OUT="../slm-agent.tar.gz"
tar --exclude='__pycache__' --exclude='.git' --exclude='*.pyc' \
    -czf "$OUT" -C .. "$(basename "$PWD")"
sha256sum "$OUT"
echo "→ $OUT"
echo
echo "Ship this tarball. On the target machine:"
echo "  tar xzf slm-agent.tar.gz"
echo "  cd slm-agent"
echo "  bash install.sh     # Termux only"
