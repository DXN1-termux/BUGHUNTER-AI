# Changelog

All notable changes to BUGHUNTER-AI are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.3.1] — 2026-06-01

### ✨ Added
- **bugbounty-ai-v2 framework**: Complete migration from `v1` to `v2`.
- **Tri-Model Lineup**: Fine-tuned 0.5B, 1.5B, and 3B parameter models for device-specific performance tiers.
- **Expanded Sandbox**: Enabled read/edit access to full Termux home directory (`/data/data/com.termux/files/home/`) with critical sub-paths (`.ssh`, `.config/gh`, `.env`, `.git`) explicitly denied.

### 🔧 Changed
- **Codebase Rewiring**: Systematic scan-and-replace updating all references from `bugbounty-ai` / `v1` to `bugbounty-ai-v2`.
- **System Prompt**: Reconfigured `slm/prompts/system.md` to reflect a professional, technical security research persona.
- **Training Pipeline**: Updated `train_lora.py` and infrastructure for tri-model support and custom dataset ingestion.
- **Project Version**: Updated to v2.3.1 across `pyproject.toml` and documentation.

### 🐛 Fixed
- Resolved dependency resolution issues during Termux installation (`primp` build failure).
- Hardened path enforcement in `executor_guards.py` to support expanded filesystem sandbox.


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
