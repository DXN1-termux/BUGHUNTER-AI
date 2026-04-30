# Changelog

All notable changes to BUGHUNTER-AI are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.3.0] — 2026-04-29

### 🔒 Security
- **CSAM hard block hardened to 0% bypass rate**
  - Tier 1: 5 hardcoded Python regex patterns that fire even if `hard_blocks.yaml` is tampered with
  - Tier 2: Expanded YAML patterns from 2 → 9 rules (terminology, euphemisms, codewords, contextual, age-explicit, AI-generation requests)
  - Unicode normalization (NFKC) + leetspeak folding + separator stripping defeats `cs4m`, `ｃｓａｍ`, `c.s.a.m`, `l0l1c0n`, and zero-width obfuscation
  - Path/filename scanning via `resolve_safe_path`
  - 8 new unit tests + 10 new red-team eval cases covering every known bypass vector
- Shell injection via unsanitized `extra` param in bug-bounty tool wrappers (`nmap`, `nuclei`, `ffuf`, etc.) — now double-quoted via `shlex.split` + `shlex.quote`
- Stale `slm/prompts/core/` directory with weaker safety checks replaced with `raise ImportError` stubs
- YAML load failures no longer disable protection (hardcoded layer still fires)

### ✨ Added
- **Confirmation prompts for mutating tools** in non-yolo mode — REPL asks `proceed? [Y/n]` before destructive operations
- **Tool result caching** — 60s TTL cache for non-mutating, non-scope tools
- **Session persistence** — `save_history()` / `restore_history()` for crash recovery
- **Retry with backoff** for `web_search` (3 attempts, exponential)
- **Lazy imports** for optional deps (`duckduckgo_search`, `beautifulsoup4`) with helpful error messages
- **Structured truncation metadata** — tool results now report byte count, line count, total rows when truncated
- **Input validation** for every tool (empty strings, None values, file existence checks)
- **`slm --version`** flag
- **3 example skills** shipped by default: `recon_subdomains`, `vuln_scan`, `port_audit`
- **`tests/` directory** with 25+ unit tests (safety, scope, tools)
- **Expanded eval suite**: functional 10 → 30, red-team 10 → 30 cases
- **GitHub Actions CI** (lint + test + safety verification)
- **Issue & PR templates**, `CONTRIBUTING.md`, `SECURITY.md`
- **Dockerfile** for containerized deployment
- **One-liner install** via `curl | bash`
- **Animated SVG demo** in README (Tokyo Night themed)
- **24-hour WhatsApp support** channel

### 🔧 Changed
- `fetch_url` timeout: 15s → 20s with 5s connect timeout + content-type header
- `run_sql`: 60s query timeout + 30s network timeout
- `bench.py` now reads `n_threads` from per-tier config (was hardcoded `-t 6`)
- `setup_wizard.py` fallback now resolves to next-lower-tier quant (was same as primary)
- LLM client handles malformed JSON, missing choices, empty responses with retry
- Agent loop gives typed errors (`TimeoutError`, `PermissionError`, `FileNotFoundError`) to the model

### 🐛 Fixed
- `doctor.py` Termux check crashing on non-Linux (`uname -o` fails on macOS/Windows)
- `eval/run_eval.py` redundant `parent.parent / "eval"` path resolution
- `_resolve_tier()` in `cli.py` calling `detect()` twice
- `_system_prompt()` crashing with `FileNotFoundError` if `~/.slm/system.md` missing
- `pursue` command ignoring `confirm` events
- `install.sh` referencing placeholder `EXAMPLE` URLs → now points to real GitHub repo
- `list_dir` and `delete_file` missing input validation

## [0.1.0] — 2026-04-27

### Initial Release
- Agentic bug-bounty SLM with ReAct loop
- 3-tier auto-detection (mobile/desktop/workstation)
- Immutable core safety layer with hard blocks + scope enforcement
- Tools: shell, file ops, web search, fetch URL, SQL, 6 recon tools
- Skill RAG with TF-IDF retrieval
- LoRA SFT training pipeline with Snowflake AI_COMPLETE
- imatrix calibration for IQ2_XS / IQ3_XXS quants
- Textual TUI + rich REPL
- Termux (Android) native support

[unreleased]: https://github.com/DXN1-termux/BUGHUNTER-AI/compare/v2.3.0...HEAD
[2.3.0]: https://github.com/DXN1-termux/BUGHUNTER-AI/compare/v0.1.0...v2.3.0
[0.1.0]: https://github.com/DXN1-termux/BUGHUNTER-AI/releases/tag/v0.1.0
