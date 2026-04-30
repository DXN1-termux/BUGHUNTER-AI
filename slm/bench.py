"""60-second sustained tok/s benchmark; selects IQ2_XS vs IQ3_XXS."""
from __future__ import annotations
import pathlib, os, subprocess, tomllib, time, re
from rich.console import Console


def _rewrite_primary(text: str, new_path: str) -> str:
    """Rewrite the [model] primary = "..." line tolerant of whitespace."""
    return re.sub(
        r'(?m)^(\s*primary\s*=\s*)"[^"]*"',
        lambda m: f'{m.group(1)}"{new_path}"',
        text,
        count=1,
    )

SLM_HOME = pathlib.Path(os.environ.get("SLM_HOME", pathlib.Path.home() / ".slm"))
TARGET_TOKS = 20.0
console = Console()


def _bench_one(model: str, n_threads: int = 6) -> float:
    bin_ = SLM_HOME / "bin" / "llama-bench"
    if not bin_.exists():
        console.print(f"[red]llama-bench missing — reinstall[/red]")
        return 0.0
    try:
        out = subprocess.check_output(
            [str(bin_), "-m", model, "-p", "0", "-n", "200", "-t", str(n_threads)],
            text=True, stderr=subprocess.STDOUT, timeout=180,
        )
    except subprocess.CalledProcessError as e:
        console.print(f"[red]bench failed:[/red]\n{e.output[-500:]}")
        return 0.0
    # parse "tg   200 ...   XX.XX ± YY.YY"
    m = re.search(r"tg\s+\d+\s+\S+\s+\S+\s+([\d.]+)\s*±", out)
    return float(m.group(1)) if m else 0.0


def run_bench():
    cfg_path = SLM_HOME / "config.toml"
    cfg = tomllib.loads(cfg_path.read_text())
    primary = cfg["model"]["primary"]
    fallback = cfg["model"].get("fallback")
    from slm.device import detect
    tier = detect().tier
    n_threads = cfg.get("model", {}).get(tier, {}).get("n_threads", 6)
    console.print(f"[cyan]primary[/cyan]  {primary}")
    tps_p = _bench_one(primary, n_threads=n_threads)
    console.print(f"  → {tps_p:.1f} tok/s")
    chosen = primary
    if tps_p < TARGET_TOKS and fallback:
        console.print(f"[yellow]below target ({TARGET_TOKS} tok/s) — trying fallback[/yellow]")
        tps_f = _bench_one(fallback, n_threads=n_threads)
        console.print(f"  → {tps_f:.1f} tok/s")
        if tps_f > tps_p:
            chosen = fallback
    # rewrite config with chosen
    if chosen != primary:
        original = cfg_path.read_text()
        new = _rewrite_primary(original, chosen)
        if new == original:
            console.print(f"[yellow]could not rewrite primary in {cfg_path}[/yellow]")
        else:
            cfg_path.write_text(new)
            console.print(f"[green]selected {chosen}[/green]")
    else:
        console.print(f"[green]keeping {chosen}[/green]")
