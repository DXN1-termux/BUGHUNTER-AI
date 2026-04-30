#!/usr/bin/env bash
# One-shot downloader. URLs valid 7 days from 2026-04-27 18:00 UTC.
# On A52 Termux:  pkg install curl && bash grab.sh
set -e
mkdir -p slm-agent/{slm/core,slm/prompts,training,eval}
cd slm-agent

B="https://sfc-eu-ds1-44-customer-stage.s3.eu-central-1.amazonaws.com/vxkm1000-s/stages/3e1c5447-de1f-41e5-a2b6-893bbd7fa51d"
Q="X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAQ2ZNK5J5RAFFJYUX%2F20260427%2Feu-central-1%2Fs3%2Faws4_request&X-Amz-Date=20260427T180009Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host"

get() { curl -fsSL -o "$1" "$B/$1?$Q&X-Amz-Signature=$2"; echo "  ▸ $1"; }

get README.md                       09d63aaf3ac9081aac1689dd9f8ca60f322c78286aabb74281785f4eb0b1d641
get bootstrap.sh                    1534074abb6ddb6d64a80a605aff3033a2ff3f53bb7b7d879069e54580526812
get install.sh                      ba22e427701b9008718d6a1448313ccfa40daca6be34b9bc868dabc53e86c301
get pack.sh                         b32c2619d72e00bfcb0a6be24af5fb40e6eb1d4a63ba63baf883f6f857adb992
get pyproject.toml                  eed5176dc115739906280e4ab0f0c415c4979783fb181d210e6f9a50f4763f96
get slm-agent-bundle.py             a6f6b99f9b835a07a98e505177567f3922f5f6a23c3a7ff8ea95669dd3235acd

get eval/functional.jsonl           2cdad6df4406f8eac9b2645ae6dd49a3cd35551df924c9e76ace5615266c7865
get eval/redteam.jsonl              6a7584fa725e3de9dfde334958daf11ee928dfb258be8b3b207c227e89d29863
get eval/run_eval.py                3c0cfce6d6d8b7cfb9288942c116d9f46902e1c5022bde7709b38eb18155b4e7

get slm/__init__.py                 12cddebf5a467c8d7c52b06ef34c91491e3f17878abd53009bb0432f8aea5979
get slm/bench.py                    5c2590f7e8a314fcf51500b1ea7c0892743ae0c7eb877b017a07ff9393360662
get slm/cli.py                      8ac58e99a93546ffaa7206a3015f6d694e732471702ddaf6c408d01aaa867213
get slm/doctor.py                   2693c2eba7eeef04ad3bb90946d32c925f864855adbbe332e09da91f6db343f3
get slm/init.py                     01d8469a5f1d31839f108ed02f6b5669053ec36d0946e9a69e742cb8efe99687
get slm/llm.py                      e3ca87562acf795f98cc3529554568de5478947e840e69b4b79f6f59b64e8f28
get slm/reflection.py               a50f66a41aedff559c18a067f5981269a3c3af43f9d01f54133f501cd6551746
get slm/session.py                  113a0d0cac05d7e66c97f7ca0b4a98cf69f4db39923cdc8539886677143e0d58
get slm/skills.py                   c8cedb010e0338b5349145631231f7d1452b0a2cea6b306d9e9a23f52f6ddae6
get slm/tools.py                    b32d26f6e414536db723223e392da7919fb89cfeaa04d187b1388027536b56e1
get slm/ui_repl.py                  b40941a110a86f43938becdcd29d0c5f33f7c4ad84fabb6b65d407257e1023ef
get slm/ui_tui.py                   f24bd3a74cfdf78581599556ce50134ccb4acb7aea1a9b4e406888be161e1453

get slm/core/__init__.py            77e9c2c40244438f9ca03df9807104a5cb9d73864685ad32336ce2873f2e9254
get slm/core/executor_guards.py     85cc423521a41668b60baa9c673ee087d2cc9d2634a7313fbcaaf8603b1cdd07
get slm/core/hard_blocks.yaml       b14a1c95b1ffcdcf32252a504c5c4f9044b794f3822a488ab4ccac62e3647b89
get slm/core/scope_enforcer.py      3b8f9d1444d99f3bb8d50d5bd7519b2b3e50589122f7e6978a94bc1e92eab18d

get slm/prompts/agent.py            7edb8b009eb84367452294c5295c28654833bdf4cd541ac65aac5e0e5b77f705
get slm/prompts/system.md           dc29723943023086163c1fdb873202600a1e5ed598e0a2feb353f005eb59cf54

get training/generate_sft.sql       89dffd664691ceedc9d44e7e0552016d70e963ddf36dca5ae554e9c43a092e4d
get training/imatrix_corpus.md      f7746a474514645de2526961c4c1d5cd834aa015dd04931eed8a40207ae21c43
get training/merge_and_quant.sh     28a6ab111ff0c125dd5668d49e65b25e88e49d5bbe16e131b39d2d299d2a39ca
get training/train_lora.py          883f3684d0b861a47025e439e812c131c42aafdea9d87485fcdcb6d2515919a2

# Fix the two misplaced files (workspace quirk)
mv slm/prompts/agent.py slm/agent.py
mkdir -p ../slm-agent/prompts; mv slm/prompts/system.md prompts/system.md
rmdir slm/prompts 2>/dev/null || true

chmod +x install.sh pack.sh training/merge_and_quant.sh

echo
echo "✓ slm-agent/ ready. Next:  cd slm-agent && bash install.sh"
