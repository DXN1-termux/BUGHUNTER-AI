# Contributing to BUGHUNTER-AI

Thanks for your interest! This project is built for the security community, by the security community.

## Quick Start

```bash
git clone https://github.com/DXN1-termux/BUGHUNTER-AI.git
cd BUGHUNTER-AI
bash install.sh          # creates .venv, installs in editable mode
source .venv/bin/activate
slm doctor               # verify setup
```

## Development Workflow

1. **Fork + branch** — create a feature branch from `main`
2. **Code** — follow existing style (ruff enforced)
3. **Test** — run `pytest` and `ruff check .`
4. **Eval** — run `python eval/run_eval.py --suite both` to verify no regressions
5. **PR** — open a pull request with a clear description

## Code Style

- Python 3.10+, type hints encouraged
- Formatted with `ruff format`, linted with `ruff check`
- No comments unless explaining *why* (not *what*)
- Keep functions short and focused

## Architecture Rules

These are **non-negotiable**:

- **Never modify `slm/core/`** — this is the immutable safety layer
- **Never weaken hard blocks** — additions welcome, removals are not
- **Never bypass scope enforcement** — all network tools must check scope
- **Never commit secrets** — no API keys, tokens, or credentials

## What We Need Help With

### Good First Issues
- Add more shell denylist patterns (obfuscation bypasses)
- Improve the TF-IDF retrieval with BM25
- Add more eval test cases to `eval/functional.jsonl`
- Port tool installer recipes to more package managers

### Bigger Projects
- Streaming token output in the REPL
- MCP (Model Context Protocol) server mode
- Browser automation skill (Playwright-based)
- Multi-model routing (use bigger model for planning, smaller for execution)

## Adding a Skill

Skills live at `~/.slm/skills/<name>.py`. To contribute a built-in skill:

1. Create `slm/skills/<name>.py`
2. Add a module docstring (used as the retrieval key)
3. Implement `def run(**kwargs) -> str`
4. Add a test case to `eval/functional.jsonl`
5. PR it

## Adding a Tool

Tools are registered in `slm/tools.py` using the `@tool` decorator:

```python
@tool("my_tool",
      {"type": "object", "properties": {...}, "required": [...]},
      mutating=True, needs_scope=False)
def my_tool(arg: str) -> str:
    ...
```

## Eval Suite

Before submitting a PR, run both eval suites:

```bash
python eval/run_eval.py --suite functional   # capability test
python eval/run_eval.py --suite redteam      # safety test (must be 100% blocked)
```

## Commit Messages

Use conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `security:` safety/guard improvement
- `eval:` new test cases
- `docs:` documentation only

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
