"""LoRA SFT on Qwen2.5-Coder-0.5B-Instruct using trl. Off-device.

Requirements (on your laptop / cloud GPU box, NOT on A52):
    pip install torch transformers peft trl datasets accelerate bitsandbytes

Expected: single 24 GB GPU, ~2–4 h for 3 epochs over 5 k traces.
Output: merged HF model at ./out/slm-agent-merged
"""
from __future__ import annotations
import json, pathlib, argparse, os
import torch
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig


def _best_attn() -> str:
    """Return flash_attention_2 only if installed and a CUDA GPU is available."""
    try:
        import flash_attn  # noqa: F401
        if torch.cuda.is_available():
            return "flash_attention_2"
    except Exception:
        pass
    return "sdpa"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="0.5B", choices=["0.5B", "1B", "2B"],
                    help="Base model size: 0.5B (fastest), 1B (balanced), 2B (strongest)")
    ap.add_argument("--base", default=None,
                    help="Override HF base model ID (otherwise derived from --size)")
    ap.add_argument("--data", default="./sft.jsonl")
    ap.add_argument("--out",  default="./out")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=None,
                    help="per-device batch size (auto-scaled by --size if omitted)")
    ap.add_argument("--lora-r", type=int, default=None,
                    help="LoRA rank (auto-scaled by --size if omitted)")
    args = ap.parse_args()

    # Base model selection by size
    SIZE_TO_BASE = {
        "0.5B": "Qwen/Qwen2.5-Coder-0.5B-Instruct",
        "1B":   "Qwen/Qwen2.5-Coder-1.5B-Instruct",
        "2B":   "Qwen/Qwen2.5-Coder-3B-Instruct",
    }
    base = args.base or SIZE_TO_BASE[args.size]

    # Auto-scale training hyperparams based on size (24GB GPU assumed)
    if args.batch_size is None:
        args.batch_size = {"0.5B": 4, "1B": 2, "2B": 1}[args.size]
    if args.lora_r is None:
        args.lora_r = {"0.5B": 16, "1B": 32, "2B": 64}[args.size]
    grad_accum = {"0.5B": 4, "1B": 8, "2B": 16}[args.size]

    print(f"Training bugbounty-ai {args.size} from {base}")
    print(f"  batch_size={args.batch_size} · lora_r={args.lora_r} · grad_accum={grad_accum}")

    tok = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base, torch_dtype=torch.bfloat16,
        attn_implementation=_best_attn(), trust_remote_code=True,
    )

    ds = load_dataset("json", data_files=args.data, split="train")

    def fmt(ex):
        return {"text": tok.apply_chat_template(ex["messages"], tokenize=False)}
    ds = ds.map(fmt, remove_columns=ds.column_names)

    lora = LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_r * 2, lora_dropout=0.05, bias="none",
        target_modules=["q_proj","k_proj","v_proj","o_proj",
                        "gate_proj","up_proj","down_proj"],
        task_type="CAUSAL_LM",
    )

    cfg = SFTConfig(
        output_dir=f"{args.out}/checkpoints-{args.size}",
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        bf16=True, logging_steps=10, save_steps=500,
        max_seq_length=4096, packing=True,
        report_to="none",
    )

    # trl >=0.12 deprecated `tokenizer=` in favor of `processing_class=`.
    try:
        trainer = SFTTrainer(model=model, args=cfg, train_dataset=ds,
                             processing_class=tok, peft_config=lora)
    except TypeError:
        trainer = SFTTrainer(model=model, args=cfg, train_dataset=ds,
                             tokenizer=tok, peft_config=lora)
    trainer.train()

    # Merge + save for gguf conversion
    merged = trainer.model.merge_and_unload()
    out_dir = f"{args.out}/slm-agent-{args.size}-merged"
    merged.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    print(f"merged {args.size} model → {out_dir}")


if __name__ == "__main__":
    main()
