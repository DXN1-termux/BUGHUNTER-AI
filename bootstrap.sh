#!/usr/bin/env bash
# slm-agent — one-shot extractor. Produces ./slm-agent/ with all source files.
# Usage:   bash bootstrap.sh [target-dir]
# Default target: ./slm-agent
set -euo pipefail
OUT="${1:-./slm-agent}"
mkdir -p "$OUT"
cd "$OUT"

# Files are embedded as base64 below. This avoids heredoc quoting pitfalls
# and lets us ship through any text channel (copy-paste, gist, email).

emit() {
    local path="$1" b64="$2"
    mkdir -p "$(dirname "$path")"
    printf '%s' "$b64" | base64 -d > "$path"
    echo "  ▸ $path"
}

echo "Extracting slm-agent → $OUT"

# ────────────────────────────────────────────────────────────────────
# PLACEHOLDER: the sections below must be filled in by running
#   ./pack.sh   on the workspace (script included in this file, see bottom).
# Each section will look like:
#   emit "README.md" "<base64>"
# ────────────────────────────────────────────────────────────────────

# --- BEGIN EMBEDDED FILES ---
{{EMBEDDED_FILES}}
# --- END EMBEDDED FILES ---

chmod +x install.sh training/merge_and_quant.sh 2>/dev/null || true
echo
echo "Done. Next:"
echo "  cd $OUT"
echo "  bash install.sh     # on A52 Termux"
echo "  # or: pip install -e .  (elsewhere, for editing)"
