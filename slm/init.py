"""First-run config writer."""
from __future__ import annotations
import os, pathlib, shutil, tempfile
from rich.console import Console

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
PKG_PROMPTS = pathlib.Path(__file__).parent.parent / "prompts"
console = Console()


def _atomic_write(path: pathlib.Path, content: str) -> None:
    """Write-then-rename so a partial write can never corrupt config."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def seed_skills() -> int:
    """Seed shipped example skills into ~/.slm/skills/ if missing.
    Works for editable installs (skills/ at repo root) AND wheel installs
    (skills/ shipped as package data). Returns number of files copied."""
    skills_dir = SLM_HOME / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    candidate_dirs = [
        pathlib.Path(__file__).parent.parent / "skills",   # editable install / git clone
        pathlib.Path(__file__).parent / "skills",          # wheel install
    ]
    shipped = next((d for d in candidate_dirs if d.exists() and d.is_dir()), None)
    n = 0
    if shipped:
        for src in shipped.glob("*.py"):
            dst = skills_dir / src.name
            if not dst.exists():
                try:
                    shutil.copy(src, dst)
                    n += 1
                except Exception:
                    pass
    return n


def first_run():
    SLM_HOME.mkdir(parents=True, exist_ok=True)
    models = SLM_HOME / "models"
    models.mkdir(parents=True, exist_ok=True)
    if not (SLM_HOME / "config.toml").exists():
        _atomic_write(SLM_HOME / "config.toml", f"""
# tier = "auto" picks mobile / desktop / workstation based on RAM + GPU.
# Model is bugbounty-ai (MIT). Single model, three quants, one per tier.
[model]
tier     = "auto"
name     = "bugbounty-ai-v1"
license  = "MIT"
backend  = "llama_cpp"
primary  = "{models}/bugbounty-ai-v1.IQ2_XS.gguf"
fallback = "{models}/bugbounty-ai-v1.IQ3_XXS.gguf"

[model.mobile]
path       = "{models}/bugbounty-ai-v1.IQ2_XS.gguf"
n_ctx      = 1536
n_threads  = 6
n_batch    = 256
flash_attn = true

[model.desktop]
path       = "{models}/bugbounty-ai-v1.Q4_K_M.gguf"
n_ctx      = 4096
n_threads  = 8
n_batch    = 512
flash_attn = true

[model.workstation]
path       = "{models}/bugbounty-ai-v1.Q6_K.gguf"
n_ctx      = 8192
n_threads  = 12
n_batch    = 1024
flash_attn = true

[server]
host = "127.0.0.1"
port = 8081

[ui]
mode = "repl"
yolo = false

[agent]
skill_rag        = true
plan_first       = true
few_shot         = true
reflect          = "auto"
vote             = 1
context_compress = true
autonomous       = false

[snowflake]
enabled = false
""".lstrip())
    if not (SLM_HOME / "system.md").exists():
        candidates = [
            PKG_PROMPTS / "system.md",
            pathlib.Path(__file__).parent / "prompts" / "system.md",
        ]
        src = next((c for c in candidates if c.exists()), None)
        if src:
            shutil.copy(src, SLM_HOME / "system.md")
    if not (SLM_HOME / "scope.yaml").exists():
        _atomic_write(SLM_HOME / "scope.yaml",
                      "programs: []\ndomains: []\nips: []\n")
    if not (SLM_HOME / "guardrails.toml").exists():
        _atomic_write(SLM_HOME / "guardrails.toml",
            "max_tool_calls_per_turn = 90\n"
            "shell_timeout_sec = 30\n"
            "shell_output_cap_bytes = 2048\n"
            "fetch_output_cap_bytes = 4096\n")
    skills_copied = seed_skills()
    console.print(f"[green]initialized {SLM_HOME}[/green]")
    if skills_copied:
        console.print(f"  seeded {skills_copied} example skill(s) into {SLM_HOME}/skills/")
    console.print("  Edit scope.yaml before running any network tool.")
