#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  BUGHUNTER-AI v2.3 · zip + S3 upload helper
#  © 2026 DXN10DAY
# ═══════════════════════════════════════════════════════════════════════════
#
# Produces a timestamped zip of the whole repo and (optionally) uploads it
# to your S3 bucket with a 7-day presigned URL.
#
# Usage:
#
#   # Just zip:
#   bash release_zip.sh
#
#   # Zip + upload + presign:
#   export AWS_S3_BUCKET=my-bucket-name
#   export AWS_REGION=eu-central-1
#   bash release_zip.sh --upload
#
# Prerequisites:
#   • zip (apt/pkg install zip)
#   • aws CLI (optional; only for --upload)
#   • aws configured: `aws configure` OR env vars AWS_ACCESS_KEY_ID +
#     AWS_SECRET_ACCESS_KEY
#
# What it excludes:
#   __pycache__, *.pyc, .venv, .git, models/, traces/, vault.enc, audit.key,
#   canary_log.jsonl, quarantine.flag, findings.db, usage.db, queue.db,
#   cve_cache, wordlists, FREEZE, any .env / credentials.json
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── config ────────────────────────────────────────────────────────────────
VERSION="${VERSION:-2.3.0}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${OUT_DIR:-./dist}"
ZIP_NAME="bughunter-ai-v${VERSION}-${STAMP}.zip"
ZIP_PATH="${OUT_DIR}/${ZIP_NAME}"

UPLOAD=0
for arg in "$@"; do
    case "$arg" in
        --upload) UPLOAD=1 ;;
        -h|--help)
            sed -n '/^# Usage:/,/^# =====/p' "$0"
            exit 0
            ;;
    esac
done

# ─── sanity ────────────────────────────────────────────────────────────────
if ! command -v zip >/dev/null; then
    echo "error: zip not installed. Install it first:" >&2
    echo "  Termux :  pkg install zip" >&2
    echo "  Debian :  sudo apt install zip" >&2
    echo "  macOS  :  (already installed)" >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# Basic repo check
if [ ! -f "README.md" ] || [ ! -d "slm" ]; then
    echo "error: run this from the BUGHUNTER-AI repo root." >&2
    exit 1
fi

mkdir -p "$OUT_DIR"

# ─── build zip ─────────────────────────────────────────────────────────────
printf "\033[1;36m▸\033[0m zipping %s\n" "$ZIP_NAME"

# Explicit excludes — never ship runtime state or secrets by accident
zip -qr "$ZIP_PATH" . \
    -x '__pycache__/*' \
    -x '*/__pycache__/*' \
    -x '*.pyc' -x '*.pyo' \
    -x '.venv/*' -x 'venv/*' \
    -x '.git/*' -x '.github/secrets/*' \
    -x 'dist/*' -x 'build/*' -x '*.egg-info/*' \
    -x 'models/*' -x '*.gguf' -x '*.imatrix' \
    -x 'traces/*' -x 'traces.db' -x 'findings.db' -x 'usage.db' \
    -x 'queue.db' -x 'tasks.db' -x 'cost.db' \
    -x 'vault.enc' -x 'vault.salt' -x 'audit.key' \
    -x 'canary_log.jsonl' -x 'quarantine.flag' \
    -x 'FREEZE' -x 'MODEL_URL' -x 'TOOLS_WANTED' \
    -x 'cve_cache/*' -x 'wordlists/*' -x 'skills/*/__pycache__/*' \
    -x 'proposals/*' \
    -x '.env' -x '.env.*' -x 'credentials.json' -x '*.key' -x '*.pem' \
    -x '.DS_Store' -x 'Thumbs.db'

SIZE=$(ls -lh "$ZIP_PATH" | awk '{print $5}')
SHA256=$(sha256sum "$ZIP_PATH" | awk '{print $1}')

printf "\033[1;32m✓\033[0m zipped \033[1m%s\033[0m (%s)\n" "$ZIP_NAME" "$SIZE"
printf "  \033[2msha256\033[0m: %s\n" "$SHA256"
printf "  \033[2mpath\033[0m:   %s\n" "$ZIP_PATH"

# Write manifest alongside the zip
cat > "${ZIP_PATH}.manifest.txt" <<EOF
BUGHUNTER-AI v${VERSION}
Generated: ${STAMP}
File:      ${ZIP_NAME}
Size:      ${SIZE}
SHA-256:   ${SHA256}
Source:    $(git rev-parse HEAD 2>/dev/null || echo "not a git repo")
License:   MIT + PPL-1.0 + UAAC-1.1
Copyright: © 2026 DXN10DAY
EOF

# ─── upload (optional) ─────────────────────────────────────────────────────
if [ "$UPLOAD" -eq 0 ]; then
    echo
    echo "done. To also upload to S3 + get a presigned URL:"
    echo "  export AWS_S3_BUCKET=your-bucket"
    echo "  export AWS_REGION=eu-central-1"
    echo "  bash $(basename "$0") --upload"
    exit 0
fi

if ! command -v aws >/dev/null; then
    echo "error: aws CLI not installed." >&2
    echo "  Termux:  pkg install python && pip install awscli" >&2
    echo "  Debian:  sudo apt install awscli" >&2
    echo "  macOS:   brew install awscli" >&2
    exit 1
fi

: "${AWS_S3_BUCKET:?AWS_S3_BUCKET env var not set}"
: "${AWS_REGION:=eu-central-1}"

KEY="bughunter-ai/releases/v${VERSION}/${ZIP_NAME}"

printf "\n\033[1;36m▸\033[0m uploading to s3://%s/%s\n" "$AWS_S3_BUCKET" "$KEY"

aws s3 cp "$ZIP_PATH" "s3://${AWS_S3_BUCKET}/${KEY}" \
    --region "$AWS_REGION" \
    --metadata "sha256=${SHA256},version=${VERSION},copyright=DXN10DAY-2026" \
    --no-progress

printf "\033[1;32m✓\033[0m uploaded\n\n"

# 7-day presigned URL
URL=$(aws s3 presign "s3://${AWS_S3_BUCKET}/${KEY}" \
        --region "$AWS_REGION" \
        --expires-in 604800)

echo "═══════════════════════════════════════════════════════════════════════"
echo " 📦 SHAREABLE URL (valid 7 days):"
echo "═══════════════════════════════════════════════════════════════════════"
echo "$URL"
echo "═══════════════════════════════════════════════════════════════════════"
echo
echo "Verify on the receiving end with:"
echo "  curl -fL -O '<url>'"
echo "  echo '${SHA256}  ${ZIP_NAME}' | sha256sum -c"
echo

# Save URL to a file too
echo "$URL" > "${ZIP_PATH}.presigned_url.txt"
echo "url also saved to: ${ZIP_PATH}.presigned_url.txt"
