#!/usr/bin/env bash
# Convert merged HF checkpoint → GGUF, calibrate imatrix on bug-bounty corpus,
# quantize to IQ2_XS (primary) + Q4_K_M + Q6_K (one quant per tier).
#
# Run on the same laptop/cloud box where train_lora.py ran.
# Requires a local llama.cpp checkout built with llama-imatrix + llama-quantize.
#
# Usage:
#   SIZE=0.5B bash merge_and_quant.sh
#   SIZE=1B   bash merge_and_quant.sh
#   SIZE=2B   bash merge_and_quant.sh
set -euo pipefail

SIZE="${SIZE:-0.5B}"
MERGED="${1:-./out/slm-agent-${SIZE}-merged}"
LCPP="${LCPP:-$HOME/src/llama.cpp}"
OUT="${OUT:-./out}"
CORPUS="${CORPUS:-./imatrix_corpus.txt}"   # see imatrix_corpus.md

require() {
    [ -e "$1" ] || { echo "missing: $1" >&2; exit 2; }
}
require "$MERGED"
require "$LCPP/convert_hf_to_gguf.py"
require "$LCPP/build/bin/llama-imatrix"
require "$LCPP/build/bin/llama-quantize"
require "$CORPUS"

mkdir -p "$OUT"
BASE="slm-agent-v1-${SIZE,,}"

# 1) HF → fp16 GGUF
python "$LCPP/convert_hf_to_gguf.py" "$MERGED" \
    --outfile "$OUT/${BASE}.fp16.gguf" \
    --outtype f16

# 2) imatrix calibration on bug-bounty corpus
"$LCPP/build/bin/llama-imatrix" \
    -m "$OUT/${BASE}.fp16.gguf" \
    -f "$CORPUS" \
    -o "$OUT/${BASE}.imatrix" \
    --chunks 300 -t 8

# 3) quantize with imatrix → IQ2_XS (mobile) + Q4_K_M (desktop) + Q6_K (workstation)
for Q in IQ2_XS Q4_K_M Q6_K; do
    "$LCPP/build/bin/llama-quantize" \
        --imatrix "$OUT/${BASE}.imatrix" \
        "$OUT/${BASE}.fp16.gguf" \
        "$OUT/${BASE}.${Q}.gguf" \
        "$Q"
    (cd "$OUT" && sha256sum "${BASE}.${Q}.gguf" > "${BASE}.${Q}.gguf.sha256")
done

echo "-------------------------------------------------------------"
echo " ${SIZE} quants produced:"
echo "   $OUT/${BASE}.IQ2_XS.gguf   (mobile)"
echo "   $OUT/${BASE}.Q4_K_M.gguf   (desktop)"
echo "   $OUT/${BASE}.Q6_K.gguf     (workstation)"
echo ""
echo " Upload all 3 quants + sha256 files to:"
echo "   https://github.com/DXN1-termux/BUGHUNTER-AI/releases/tag/v2.3"
echo "-------------------------------------------------------------"
