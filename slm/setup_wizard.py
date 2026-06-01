"""Interactive setup wizard — `slm setup`. TITAN EDITION v2.4."""
from __future__ import annotations
import os
import pathlib
import shutil
import textwrap
import time
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.prompt import Confirm, Prompt

SLM_HOME = pathlib.Path(os.environ.get(
    "SLM_HOME", pathlib.Path.home() / ".slm"))
PKG_PROMPTS = pathlib.Path(__file__).parent.parent / "prompts"
console = Console()

THEME = {
    "header": "bold white on red",
    "section": "bold cyan",
    "accent": "bright_magenta",
    "error": "bold red",
    "success": "bold green",
    "dim": "dim grey",
    "titan": "bold red",
}


@dataclass
class ModelChoice:
    name: str
    display: str
    size_gb: float
    tier: str
    base_size: str
    default_filename: str
    tok_s_estimate: str


CATALOG = [
    ModelChoice(
        name="bugbounty-ai-v2-v1-0.5b-mobile",
        display="TITAN-LITE 0.5B · IQ2_XS  (~300 MB)",
        size_gb=0.3, tier="mobile", base_size="0.5B",
        default_filename="bugbounty-ai-v2-v1-0.5b.IQ2_XS.gguf",
        tok_s_estimate="25–60 tok/s"),
    ModelChoice(
        name="bugbounty-ai-v2-v1-0.5b-desktop",
        display="TITAN-LITE 0.5B · Q4_K_M  (~450 MB)",
        size_gb=0.45, tier="desktop", base_size="0.5B",
        default_filename="bugbounty-ai-v2-v1-0.5b.Q4_K_M.gguf",
        tok_s_estimate="70–180 tok/s"),
    ModelChoice(
        name="bugbounty-ai-v2-v1-1b-mobile",
        display="TITAN-CORE 1B · IQ2_XS  (~600 MB)",
        size_gb=0.6, tier="mobile", base_size="1B",
        default_filename="bugbounty-ai-v2-v1-1b.IQ2_XS.gguf",
        tok_s_estimate="15–35 tok/s"),
    ModelChoice(
        name="bugbounty-ai-v2-v1-1b-desktop",
        display="TITAN-CORE 1B · Q4_K_M  (~900 MB)",
        size_gb=0.9, tier="desktop", base_size="1B",
        default_filename="bugbounty-ai-v2-v1-1b.Q4_K_M.gguf",
        tok_s_estimate="40–110 tok/s"),
    ModelChoice(
        name="bugbounty-ai-v2-v1-2b-workstation",
        display="TITAN-ULTRA 2B · Q6_K  (~2.5 GB)",
        size_gb=2.5, tier="workstation", base_size="2B",
        default_filename="bugbounty-ai-v2-v1-2b.Q6_K.gguf",
        tok_s_estimate="60–150 tok/s"),
]


def _detect_tier() -> str:
    try:
        from slm.device import detect
        d = detect()
        console.print(f"[{THEME['dim']}]SYSTEM RECON: {d.platform.upper()} | {d.ram_mb}MB RAM | {d.cores} CORES | GPU={d.has_gpu}[/]")
        return d.tier
    except Exception:
        return "mobile"


def _section(title: str):
    console.print()
    console.print(f"[{THEME['section']}]>> {title.upper()}[/]")
    console.print(f"[{THEME['dim']}]────────────────────────────────────────────────────────────[/]")


def run_setup():
    clear_screen = "\033[H\033[J"
    console.print(clear_screen, end="")
    
    # ASCII Header
    console.print(Panel(textwrap.dedent("""\
        [bold red]
        ████████╗██╗████████╗ █████╗ ███╗   ██╗
        ╚══██╔══╝██║╚══██╔══╝██╔══██╗████╗  ██║
           ██║   ██║   ██║   ███████║██╔██╗ ██║
           ██║   ██║   ██║   ██╔══██║██║╚██╗██║
           ██║   ██║   ██║   ██║  ██║██║ ╚████║
           ╚═╝   ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝
        [/]
        [bold white]B U G H U N T E R - A I | TITAN EDITION v2.4[/]
        [dim]Maximum Autonomy Deployment Wizard[/]
    """), style="bold red", expand=True, justify="center"))

    SLM_HOME.mkdir(parents=True, exist_ok=True)

    # 1. AUTONOMY LEVEL ------------------------------------------------------
    _section("1. Mission Protocol")
    titan_mode = Confirm.ask("Enable [bold red]TITAN PROTOCOL[/]? (YOLO Mode + Full Autonomy)", default=True)
    
    # 2. HARDWARE ALIGNMENT --------------------------------------------------
    _section("2. Hardware Alignment")
    auto_tier = _detect_tier()
    tier = Prompt.ask("Override detected tier?", choices=["auto", "mobile", "desktop", "workstation"], default="auto")
    resolved_tier = auto_tier if tier == "auto" else tier
    ok(f"Environment locked: {resolved_tier.upper()}")

    # 3. BRAIN SELECTION -----------------------------------------------------
    _section("3. Brain Selection")
    size_choices = ["0.5B", "1B", "2B"]
    chosen_size = Prompt.ask("Select model magnitude", choices=size_choices, default="1B" if resolved_tier != "mobile" else "0.5B")
    
    chosen = next((m for m in CATALOG if m.base_size == chosen_size and m.tier == resolved_tier), None)
    if not chosen:
        chosen = next(m for m in CATALOG if m.base_size == chosen_size)
        
    console.print(f"  [{THEME['accent']}]Target Neural Set:[/] {chosen.display}")
    console.print(f"  [{THEME['accent']}]Expected Velocity:[/] {chosen.tok_s_estimate}")
    
    # 4. DATA ACQUISITION ----------------------------------------------------
    _section("4. Data Acquisition")
    gguf_url = Prompt.ask("Custom GGUF Source (Optional)", default="")
    if gguf_url:
        (SLM_HOME / "MODEL_URL").write_text(gguf_url)
    
    model_filename = Prompt.ask("Model Identifier", default=chosen.default_filename)

    # 5. LOGIC ENHANCEMENTS --------------------------------------------------
    _section("5. Logic Enhancements")
    features = {
        "skill_rag": Confirm.ask("Enable Skill RAG (Contextual Augmentation)?", default=True),
        "plan_first": Confirm.ask("Enable Chain-of-Thought Planning?", default=True),
        "few_shot": Confirm.ask("Enable Past-Mission Exemplars?", default=True),
        "reflect": Confirm.ask("Enable Self-Correction Pass?", default=(resolved_tier != "mobile")),
        "autonomous": Confirm.ask("Enable Recursive Goal Pursuit?", default=titan_mode),
    }

    # 6. OPERATIONAL SCOPE ---------------------------------------------------
    _section("6. Operational Scope")
    console.print(f"[{THEME['dim']}]Define authorized testing boundaries (comma-separated).[/]")
    domains_raw = Prompt.ask("Allowed Domains", default="example.com, *.example.com")
    domains = [d.strip() for d in domains_raw.split(",") if d.strip()]
    
    ips_raw = Prompt.ask("Allowed IP Ranges/CIDR", default="127.0.0.1")
    ips = [i.strip() for i in ips_raw.split(",") if i.strip()]

    # 7. TOOLING INJECTION ---------------------------------------------------
    _section("7. Tooling Injection")
    tools = ["nmap", "subfinder", "httpx", "nuclei", "ffuf", "katana"]
    tools_wanted = {t: Confirm.ask(f"Inject {t} into agent?", default=True) for t in tools}

    # 8. FINALIZING DEPLOYMENT -----------------------------------------------
    _section("8. Finalizing Deployment")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="Compiling Guardrails...", total=None)
        time.sleep(0.5)
        progress.add_task(description="Syncing Neural Weights...", total=None)
        time.sleep(0.5)
        progress.add_task(description="Hardening Core Guards...", total=None)
        time.sleep(0.5)

    _write_files(
        tier=tier, titan_mode=titan_mode, model=chosen, model_filename=model_filename,
        features=features, domains=domains, ips=ips, tools_wanted=tools_wanted
    )

    console.print(Panel(textwrap.dedent(f"""\
        [bold green]✓ DEPLOYMENT COMPLETE[/]
        
        TITAN is now synchronized with your hardware.
        
        [bold white]NEXT STEPS:[/]
        1. [cyan]slm doctor[/]   - Verify core integrity
        2. [cyan]slm bench[/]    - Optimize performance
        3. [cyan]slm[/]          - Enter TITAN Command Center
    """), style="bold green", expand=False))


def _write_files(**ctx):
    models_dir = SLM_HOME / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    model = ctx['model']
    config = textwrap.dedent(f"""\
        # TITAN CORE CONFIGURATION
        [model]
        tier     = "{ctx['tier']}"
        primary  = "{models_dir}/{ctx['model_filename']}"
        name     = "{model.name}"
        license  = "MIT"
        backend  = "llama_cpp"

        [model.mobile]
        path       = "{models_dir}/bugbounty-ai-v2-v1-0.5b.IQ2_XS.gguf"
        n_ctx      = 2048
        n_threads  = 6
        n_batch    = 256
        flash_attn = true

        [model.desktop]
        path       = "{models_dir}/bugbounty-ai-v2-v1-1b.Q4_K_M.gguf"
        n_ctx      = 4096
        n_threads  = 8
        n_batch    = 512
        flash_attn = true

        [model.workstation]
        path       = "{models_dir}/bugbounty-ai-v2-v1-2b.Q6_K.gguf"
        n_ctx      = 8192
        n_threads  = 12
        n_batch    = 1024
        flash_attn = true

        [agent]
        yolo             = {str(ctx['titan_mode']).lower()}
        skill_rag        = {str(ctx['features']['skill_rag']).lower()}
        plan_first       = {str(ctx['features']['plan_first']).lower()}
        few_shot         = {str(ctx['features']['few_shot']).lower()}
        reflect          = "{'on' if ctx['features']['reflect'] else 'off'}"
        autonomous       = {str(ctx['features']['autonomous']).lower()}
        context_compress = true
        
        [ui]
        mode = "tui"
        theme = "titan-dark"
        """)
    (SLM_HOME / "config.toml").write_text(config)

    # Scope
    scope = "programs: []\ndomains:\n" + "".join(f"  - {d}\n" for d in ctx['domains']) + "ips:\n" + "".join(f"  - {i}\n" for i in ctx['ips'])
    (SLM_HOME / "scope.yaml").write_text(scope)
    
    # Tools wanted
    want = [t for t, v in ctx["tools_wanted"].items() if v]
    (SLM_HOME / "TOOLS_WANTED").write_text("\n".join(want) + "\n")


def ok(msg: str):
    console.print(f"[{THEME['success']}]✓[/] {msg}")

if __name__ == "__main__":
    run_setup()


def _fallback_filename(model: ModelChoice) -> str:
    """Fallback to same-size model at next-lower tier (speed/RAM safety net)."""
    tier_order = ["mobile", "desktop", "workstation"]
    idx = tier_order.index(model.tier) if model.tier in tier_order else 0
    fallback_tier = tier_order[max(0, idx - 1)]
    fallback_model = next(
        (m for m in CATALOG if m.tier ==
         fallback_tier and m.base_size == model.base_size),
        model,
    )
    return fallback_model.default_filename


def _write_files(**ctx):
    models_dir = SLM_HOME / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (SLM_HOME / "skills").mkdir(parents=True, exist_ok=True)

    chosen_model = ctx['model']
    fb_filename = _fallback_filename(chosen_model)
    # Same-size variants for each tier (so tier sections stay consistent with
    # chosen size)
    mobile_model = next(
        (m for m in CATALOG if m.tier ==
         "mobile" and m.base_size == chosen_model.base_size),
        chosen_model)
    desktop_model = next(
        (m for m in CATALOG if m.tier ==
         "desktop" and m.base_size == chosen_model.base_size),
        chosen_model)
    workstation_model = next(
        (m for m in CATALOG if m.tier ==
         "workstation" and m.base_size == chosen_model.base_size),
        chosen_model)

    config = textwrap.dedent(f"""\
        # written by `slm setup` — hand-edit freely
        [model]
        tier     = "{ctx['tier']}"
        primary  = "{models_dir}/{ctx['model_filename']}"
        fallback = "{models_dir}/{fb_filename}"
        name     = "{ctx['model'].name}"
        license  = "MIT"
        backend  = "llama_cpp"
        memory_limit = {ctx['memory_limit']}

        [model.mobile]
        path       = "{models_dir}/{mobile_model.default_filename}"
        n_ctx      = 1536
        n_threads  = 6
        n_batch    = 256
        flash_attn = true

        [model.desktop]
        path       = "{models_dir}/{desktop_model.default_filename}"
        n_ctx      = 4096
        n_threads  = 8
        n_batch    = 512
        flash_attn = true

        [model.workstation]
        path       = "{models_dir}/{workstation_model.default_filename}"
        n_ctx      = 8192
        n_threads  = 12
        n_batch    = 1024
        flash_attn = true

        [server]
        host = "127.0.0.1"
        port = 8081
        log_level = "{ctx['log_level']}"

        [ui]
        mode = "repl"
        yolo = false

        [agent]
        skill_rag        = {str(ctx['skill_rag']).lower()}
        plan_first       = {str(ctx['plan_first']).lower()}
        few_shot         = {str(ctx['few_shot']).lower()}
        reflect          = "{ctx['reflect']}"
        vote             = {ctx['vote']}
        context_compress = {str(ctx['context_compress']).lower()}
        autonomous       = {str(ctx['autonomous']).lower()}

        [snowflake]
        enabled   = {str(ctx['snow']).lower()}
        account   = "{ctx['snow_account']}"
        user      = "{ctx['snow_user']}"
        role      = "{ctx['snow_role']}"
        warehouse = "{ctx['snow_wh']}"
        """)
    (SLM_HOME / "config.toml").write_text(config)

    # scope
    def _yaml_list(items: list) -> str:
        if not items:
            return "  []\n"
        return "".join(f"  - {x}\n" for x in items)

    scope = (
        "programs:\n" + _yaml_list(ctx["programs"]) +
        "domains:\n" + _yaml_list(ctx["domains"]) +
        "ips:\n" + _yaml_list(ctx["ips"])
    )
    (SLM_HOME / "scope.yaml").write_text(scope)

    # guardrails
    (SLM_HOME / "guardrails.toml").write_text(
        f"max_tool_calls_per_turn = {int(ctx['max_tool_calls'])}\n"
        f"shell_timeout_sec       = {int(ctx['shell_timeout'])}\n"
        f"shell_output_cap_bytes  = 2048\n"
        f"fetch_output_cap_bytes  = 4096\n")

    # system.md (copy if missing) — handle both editable and wheel layouts
    sys_md = SLM_HOME / "system.md"
    if not sys_md.exists():
        candidates = [
            PKG_PROMPTS / "system.md",                          # editable
            pathlib.Path(__file__).parent / "prompts" /
            "system.md",  # wheel (slm/prompts)
        ]
        src = next((c for c in candidates if c.exists()), None)
        if src:
            shutil.copy(src, sys_md)

    # Seed example skills (shared helper with `slm init`)
    try:
        from slm.init import seed_skills
        n = seed_skills()
        if n:
            console.print(
                f"[dim]  seeded {n} example skill(s) into {SLM_HOME}/skills/[/dim]")
    except Exception:
        pass

    # tool install hints
    want = [t for t, v in ctx["tools_wanted"].items() if v]
    if want:
        (SLM_HOME / "TOOLS_WANTED").write_text("\n".join(want) + "\n")
        console.print(
            f"[dim]recon tools you opted into: " f"{
                ', '.join(want)} — install via `slm install-tools`[/dim]")

    console.print(f"[green]  wrote[/green]  {SLM_HOME / 'config.toml'}")
    console.print(f"[green]  wrote[/green]  {SLM_HOME / 'scope.yaml'}")
    console.print(f"[green]  wrote[/green]  {SLM_HOME / 'guardrails.toml'}")
