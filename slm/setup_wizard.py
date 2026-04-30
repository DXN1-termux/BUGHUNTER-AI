"""Interactive setup wizard — `slm setup`.

Walks the user through every meaningful choice:

  - device tier (auto-detected, overridable)
  - model family + size (0.5B / 1.5B / 3B / 7B)
  - base model source (official HF repo or your own)
  - agentic features (plan-first, reflection, few-shot, vote, skill RAG,
    context compression, autonomous-goal mode)
  - initial scope (domains + IPs for authorized testing)
  - tool availability (nmap, subfinder, httpx, nuclei, ffuf)
  - Snowflake integration (optional)
  - guardrails (tool-call cap, shell timeout, output caps)

Writes:  config.toml, scope.yaml, guardrails.toml, system.md (copy),
         ~/.slm/MODEL_URL  (the user-chosen download URL, or blank)
"""
from __future__ import annotations
import os, pathlib, shutil, textwrap
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
PKG_PROMPTS = pathlib.Path(__file__).parent.parent / "prompts"
console = Console()


# ---------------------------------------------------------- model catalog
# bugbounty-ai comes in 3 sizes × 3 quants. Users pick size (capability),
# then the tier auto-picks the quant (speed/RAM fit for their device).
@dataclass
class ModelChoice:
    name: str            # internal id
    display: str         # user-facing description
    size_gb: float       # approx download
    tier: str            # which tier this quant targets
    base_size: str       # 0.5B | 1B | 2B
    default_filename: str
    tok_s_estimate: str  # rough tok/s on that tier


CATALOG = [
    # 0.5B — fastest, lightest. Recommended for phones + low-end laptops.
    ModelChoice(
        name="bugbounty-ai-v1-0.5b-mobile",
        display="bugbounty-ai 0.5B · IQ2_XS  (~300 MB)",
        size_gb=0.3, tier="mobile", base_size="0.5B",
        default_filename="bugbounty-ai-v1-0.5b.IQ2_XS.gguf",
        tok_s_estimate="22–55 tok/s"),
    ModelChoice(
        name="bugbounty-ai-v1-0.5b-desktop",
        display="bugbounty-ai 0.5B · Q4_K_M  (~450 MB)",
        size_gb=0.45, tier="desktop", base_size="0.5B",
        default_filename="bugbounty-ai-v1-0.5b.Q4_K_M.gguf",
        tok_s_estimate="60–150 tok/s"),
    ModelChoice(
        name="bugbounty-ai-v1-0.5b-workstation",
        display="bugbounty-ai 0.5B · Q6_K  (~600 MB)",
        size_gb=0.6, tier="workstation", base_size="0.5B",
        default_filename="bugbounty-ai-v1-0.5b.Q6_K.gguf",
        tok_s_estimate="150–400 tok/s"),

    # 1B — balanced. Better reasoning, still runs on modern phones.
    ModelChoice(
        name="bugbounty-ai-v1-1b-mobile",
        display="bugbounty-ai 1B · IQ2_XS  (~600 MB)",
        size_gb=0.6, tier="mobile", base_size="1B",
        default_filename="bugbounty-ai-v1-1b.IQ2_XS.gguf",
        tok_s_estimate="12–30 tok/s"),
    ModelChoice(
        name="bugbounty-ai-v1-1b-desktop",
        display="bugbounty-ai 1B · Q4_K_M  (~900 MB)",
        size_gb=0.9, tier="desktop", base_size="1B",
        default_filename="bugbounty-ai-v1-1b.Q4_K_M.gguf",
        tok_s_estimate="30–90 tok/s"),
    ModelChoice(
        name="bugbounty-ai-v1-1b-workstation",
        display="bugbounty-ai 1B · Q6_K  (~1.3 GB)",
        size_gb=1.3, tier="workstation", base_size="1B",
        default_filename="bugbounty-ai-v1-1b.Q6_K.gguf",
        tok_s_estimate="90–220 tok/s"),

    # 2B — strongest. Needs flagship phones or real hardware.
    ModelChoice(
        name="bugbounty-ai-v1-2b-mobile",
        display="bugbounty-ai 2B · IQ2_XS  (~1.1 GB)  ⚠ needs 3+ GB RAM",
        size_gb=1.1, tier="mobile", base_size="2B",
        default_filename="bugbounty-ai-v1-2b.IQ2_XS.gguf",
        tok_s_estimate="5–15 tok/s"),
    ModelChoice(
        name="bugbounty-ai-v1-2b-desktop",
        display="bugbounty-ai 2B · Q4_K_M  (~1.8 GB)",
        size_gb=1.8, tier="desktop", base_size="2B",
        default_filename="bugbounty-ai-v1-2b.Q4_K_M.gguf",
        tok_s_estimate="18–50 tok/s"),
    ModelChoice(
        name="bugbounty-ai-v1-2b-workstation",
        display="bugbounty-ai 2B · Q6_K  (~2.5 GB)",
        size_gb=2.5, tier="workstation", base_size="2B",
        default_filename="bugbounty-ai-v1-2b.Q6_K.gguf",
        tok_s_estimate="50–130 tok/s"),
]


def _size_options() -> list[tuple[str, str, str]]:
    """Returns (size_id, display, recommendation) tuples."""
    return [
        ("0.5B",
         "bugbounty-ai 0.5B — fastest, lightest (300 MB–600 MB)",
         "recommended for: phones, older laptops, Pi, fast iteration"),
        ("1B",
         "bugbounty-ai 1B — balanced (600 MB–1.3 GB)",
         "recommended for: flagship phones, modern laptops · better multi-step reasoning"),
        ("2B",
         "bugbounty-ai 2B — strongest (1.1 GB–2.5 GB)",
         "recommended for: workstations / top-tier phones · best accuracy on complex bugs"),
    ]


# ---------------------------------------------------------- prompt helpers
def _ask(prompt: str, default: str = "") -> str:
    shown = f"{prompt} [{default}]: " if default else f"{prompt}: "
    try:
        ans = input(shown).strip()
    except EOFError:
        return default
    return ans or default


def _ask_bool(prompt: str, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    ans = _ask(f"{prompt} ({d})", "Y" if default else "N").lower()
    return ans.startswith("y")


def _ask_choice(prompt: str, options: list[str], default_idx: int = 0) -> int:
    table = Table(show_header=False, box=None)
    for i, opt in enumerate(options):
        marker = "[cyan]*[/cyan]" if i == default_idx else " "
        table.add_row(f"  {marker} [{i}]", opt)
    console.print(table)
    while True:
        raw = _ask(prompt, str(default_idx))
        try:
            idx = int(raw)
            if 0 <= idx < len(options):
                return idx
        except ValueError:
            pass
        console.print("[red]pick a number from the list[/red]")


# ---------------------------------------------------------- sections
def _section(title: str) -> None:
    console.print()
    console.print(Panel.fit(f"[bold]{title}[/bold]", style="blue"))


def _detect_tier() -> str:
    try:
        from slm.device import detect
        d = detect()
        console.print(f"[dim]detected: {d.platform}, {d.ram_mb} MB RAM, "
                      f"{d.cores} cores, gpu={d.has_gpu} → tier [bold]{d.tier}[/bold][/dim]")
        return d.tier
    except Exception:
        return "mobile"


# ---------------------------------------------------------- wizard
def run_setup():
    console.print(Panel(
        "[bold]slm-agent setup[/bold]\n"
        "Interactive configuration. You can re-run this any time.\n"
        "All choices can be edited later in ~/.slm/config.toml.",
        style="magenta"))

    SLM_HOME.mkdir(parents=True, exist_ok=True)

    # 1. DEVICE TIER -----------------------------------------------------------
    _section("1. device tier")
    auto = _detect_tier()
    tier_options = ["auto-detect (recommended)", "mobile (phone / low-end)",
                    "desktop (laptop / pc)", "workstation (gpu / 24+ GB RAM)"]
    default_idx = 0
    pick = _ask_choice("choose tier", tier_options, default_idx)
    tier = ["auto", "mobile", "desktop", "workstation"][pick]
    resolved_tier = auto if tier == "auto" else tier

    # 2. MODEL ----------------------------------------------------------------
    _section("2. model size")
    console.print("[bold]bugbounty-ai[/bold] (MIT) — choose capability vs. speed.\n")

    sizes = _size_options()
    size_display = []
    default_size_idx = 0
    for i, (sid, disp, rec) in enumerate(sizes):
        # Smart default based on tier
        if resolved_tier == "workstation" and sid == "2B":
            default_size_idx = i
        elif resolved_tier == "desktop" and sid == "1B":
            default_size_idx = i
        elif resolved_tier == "mobile" and sid == "0.5B":
            default_size_idx = i
        size_display.append(f"{disp}\n      [dim]{rec}[/dim]")

    size_pick = _ask_choice("choose model size", size_display, default_size_idx)
    chosen_size = sizes[size_pick][0]

    _section("3. model quant")
    console.print(f"For [cyan]{chosen_size}[/cyan] on tier [cyan]{resolved_tier}[/cyan]:\n")

    chosen = next((m for m in CATALOG
                   if m.base_size == chosen_size and m.tier == resolved_tier), None)
    if chosen is None:
        chosen = next(m for m in CATALOG if m.base_size == chosen_size)
    console.print(f"  selected: [cyan]{chosen.display}[/cyan]")
    console.print(f"  estimated speed: [green]{chosen.tok_s_estimate}[/green]")
    console.print(f"  disk space needed: [yellow]~{chosen.size_gb:.1f} GB[/yellow]\n")

    gguf_url = _ask(
        "GGUF download URL (leave blank to place the file manually later)",
        default="")
    (SLM_HOME / "MODEL_URL").write_text(gguf_url)
    model_filename = _ask("filename for the GGUF",
                          default=chosen.default_filename)

    # 4. AGENTIC FEATURES ------------------------------------------------------
    _section("4. agentic features")
    console.print(
        "These make the small model behave more like a big one — "
        "at the cost of tokens and latency.\n")
    skill_rag   = _ask_bool("enable skill RAG (inject relevant skills per turn)", True)
    plan_first  = _ask_bool("require <plan> on first turn (plan-then-execute)", True)
    few_shot    = _ask_bool("few-shot from past successful sessions", True)
    context_cp  = _ask_bool("context compression when near n_ctx", True)
    if resolved_tier == "mobile":
        reflect = "off"
        vote = 1
        console.print("[dim]reflection disabled on mobile (too slow).[/dim]")
        console.print("[dim]vote-of-N disabled on mobile.[/dim]")
    else:
        reflect_on = _ask_bool("self-reflection before <final> answers", True)
        reflect = "on" if reflect_on else "off"
        if resolved_tier == "workstation":
            vote_on = _ask_bool("vote-of-3 (sample 3 rollouts, pick majority)", False)
            vote = 3 if vote_on else 1
        else:
            vote = 1

    autonomous = _ask_bool(
        "autonomous-goal mode (agent keeps working until the goal is done "
        "or it hits a checkpoint)", False)

    max_tool_calls = _ask("max tool calls per turn", default="90")
    shell_timeout  = _ask("shell command timeout (seconds)", default="30")

    # 5. SCOPE -----------------------------------------------------------------
    _section("5. authorized scope")
    console.print(
        "Scope gates every network tool. Nothing fires against a target "
        "not listed here.\n")
    domains: list[str] = []
    while True:
        d = _ask("add a domain (blank to stop; use *.example.com for wildcard)", "")
        if not d:
            break
        domains.append(d)
    ips: list[str] = []
    while True:
        ip = _ask("add an IP or CIDR (blank to stop)", "")
        if not ip:
            break
        ips.append(ip)
    programs = []
    prog = _ask("bug-bounty program name (optional, free-form)", "")
    if prog:
        programs.append(prog)

    # 6. TOOLS ----------------------------------------------------------------
    _section("6. recon tooling")
    tools_wanted = {}
    for t in ("nmap", "subfinder", "httpx", "nuclei", "ffuf", "katana"):
        tools_wanted[t] = _ask_bool(f"will you use {t}?", True)

    # 7. SNOWFLAKE ------------------------------------------------------------
    _section("6. snowflake integration (optional)")
    snow = _ask_bool("enable Snowflake run_sql tool?", False)
    snow_account = snow_user = snow_role = snow_wh = ""
    if snow:
        snow_account = _ask("account identifier (e.g. acme-xy12345)", "")
        snow_user    = _ask("user", os.environ.get("USER", ""))
        snow_role    = _ask("role", "PUBLIC")
        snow_wh      = _ask("warehouse", "COMPUTE_WH")

    # 8. WRITE FILES ----------------------------------------------------------
    _section("8. writing config")
    _write_files(
        tier=tier, model=chosen, model_filename=model_filename,
        skill_rag=skill_rag, plan_first=plan_first, few_shot=few_shot,
        reflect=reflect, vote=vote, context_compress=context_cp,
        autonomous=autonomous, max_tool_calls=max_tool_calls,
        shell_timeout=shell_timeout, domains=domains, ips=ips,
        programs=programs, tools_wanted=tools_wanted, snow=snow,
        snow_account=snow_account, snow_user=snow_user,
        snow_role=snow_role, snow_wh=snow_wh,
    )

    console.print()
    console.print(Panel(
        f"[green]setup complete[/green]\n\n"
        f"Next steps:\n"
        f"  1. place your model at  ~/.slm/models/{model_filename}\n"
        f"     (or re-run setup and paste a download URL)\n"
        f"  2. [cyan]slm doctor[/cyan]   — health check\n"
        f"  3. [cyan]slm bench[/cyan]    — sustained tok/s\n"
        f"  4. [cyan]slm[/cyan]          — open REPL",
        style="green"))


def _fallback_filename(model: ModelChoice) -> str:
    """Fallback to same-size model at next-lower tier (speed/RAM safety net)."""
    tier_order = ["mobile", "desktop", "workstation"]
    idx = tier_order.index(model.tier) if model.tier in tier_order else 0
    fallback_tier = tier_order[max(0, idx - 1)]
    fallback_model = next(
        (m for m in CATALOG if m.tier == fallback_tier and m.base_size == model.base_size),
        model,
    )
    return fallback_model.default_filename


def _write_files(**ctx):
    models_dir = SLM_HOME / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (SLM_HOME / "skills").mkdir(parents=True, exist_ok=True)

    chosen_model = ctx['model']
    fb_filename = _fallback_filename(chosen_model)
    # Same-size variants for each tier (so tier sections stay consistent with chosen size)
    mobile_model = next(
        (m for m in CATALOG if m.tier == "mobile" and m.base_size == chosen_model.base_size),
        chosen_model)
    desktop_model = next(
        (m for m in CATALOG if m.tier == "desktop" and m.base_size == chosen_model.base_size),
        chosen_model)
    workstation_model = next(
        (m for m in CATALOG if m.tier == "workstation" and m.base_size == chosen_model.base_size),
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
        "domains:\n"  + _yaml_list(ctx["domains"]) +
        "ips:\n"      + _yaml_list(ctx["ips"])
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
            pathlib.Path(__file__).parent / "prompts" / "system.md",  # wheel (slm/prompts)
        ]
        src = next((c for c in candidates if c.exists()), None)
        if src:
            shutil.copy(src, sys_md)

    # Seed example skills (shared helper with `slm init`)
    try:
        from slm.init import seed_skills
        n = seed_skills()
        if n:
            console.print(f"[dim]  seeded {n} example skill(s) into {SLM_HOME}/skills/[/dim]")
    except Exception:
        pass

    # tool install hints
    want = [t for t, v in ctx["tools_wanted"].items() if v]
    if want:
        (SLM_HOME / "TOOLS_WANTED").write_text("\n".join(want) + "\n")
        console.print(f"[dim]recon tools you opted into: "
                      f"{', '.join(want)} — install via `slm install-tools`[/dim]")

    console.print(f"[green]  wrote[/green]  {SLM_HOME/'config.toml'}")
    console.print(f"[green]  wrote[/green]  {SLM_HOME/'scope.yaml'}")
    console.print(f"[green]  wrote[/green]  {SLM_HOME/'guardrails.toml'}")
