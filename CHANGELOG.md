# Changelog

All notable changes to BUGHUNTER-AI are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.4.0] — 2026-06-01 | TITAN EDITION

### ✨ Added
- **TITAN Core Logic**: New `MissionOrchestrator` with recursive task decomposition and self-healing execution paths.
- **TITAN Command Center (TUI)**: High-fidelity terminal interface with real-time system monitoring (System Pulse), tool feed, and multi-tab mission control.
- **TITAN Setup Wizard**: Redesigned installation and configuration experience with full autonomy support (YOLO mode) and hardware-aligned deployment.
- **Cyberpunk Aesthetic**: Unified dark-mode theme across all interfaces with high-contrast mission status indicators.
- **Skill Synthesis**: YOLO-mode capability to generate and validate new Python tools on-the-fly.

### 🔧 Changed
- **Installation Pipeline**: Modernized `install.sh` and Termux sub-installer with optimized ARMv8.2 build flags for `llama.cpp`.
- **System Monitoring**: `slm/device.py` now provides real-time CPU and RAM utilization metrics for TUI dashboards.
- **CLI Upgrades**: Added `pursue-titan` command for high-fidelity autonomous missions.

### 🐛 Fixed
- **TUI Stability**: Resolved issues with log truncation and event handling in the `textual` application.
- **Setup Reliability**: Fixed URL validation and fallback path handling in the wizard.
- **Code Hygiene**: Performed massive cleanup of line-length and indentation violations across the entire codebase.

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
