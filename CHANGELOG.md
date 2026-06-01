# Changelog

All notable changes to BUGHUNTER-AI are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.4.0] — 2026-06-01

### ✨ Added
- **Setup Wizard Upgrade**: Improved device detection, input validation (URLs), and advanced configuration options (memory limit, log level).
- **Interface Refinement**: Modernized TUI CSS theme and improved Setup Wizard UI with `rich` for better readability.

### 🔧 Changed
- **Safety Architecture**: Hardened CSAM detection by moving from fragile regex YAML to native, deterministically compiled Python pattern sets.
- **Project Structure**: Created `slm/core/hard_blocks_data.py` for centralized, robust pattern management.

### 🐛 Fixed
- **Codebase Sanity**: Fixed syntax corruption (`—`, `©`, `·`) and resolved pervasive linting/formatting issues (PEP8 compliance).
- **Exception Stability**: Fixed `HardBlockError` exception hierarchy issues causing test failures.
- **Refusal Detection**: Fixed regex patterns in `slm/refusal.py` to correctly identify agent refusals.
- **Test Suite**: Stabilized tests by refactoring `tests/test_safety.py` and adding quarantine-bypass test fixtures.

----------
----------
----------

## [2.3.1] — 2026-06-01


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
