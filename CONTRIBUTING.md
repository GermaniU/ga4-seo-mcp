# Contributing to ga4-seo-mcp

Thanks for your interest! This document explains how the project is built and how to contribute. Read it before sending a PR.

---

## Philosophy

> **Small, well-made software that is easy to maintain.**

`ga4-seo-mcp` does one thing: give an AI agent safe, scoped access to the measurement stack of a website (GA4, Search Console, PageSpeed, and optional keyword research). Speculative features do not get in. Every line has to justify its maintenance.

---

## Disciplines

### Clean code
- Clear names in English. If a function needs a comment to explain *what* it does, rename it first.
- Short functions with one responsibility.
- No dead code. If it is commented out or unused, delete it.

### Toolsets and safety are the architecture
- Each Google surface lives in its own module under `src/ga4_seo_mcp/` and exposes `register(mcp, *, writes: bool)`. Modules never register tools as an import side effect.
- **Every tool that changes state must be registered only when `writes=True`.** `tests/test_toolsets.py` fails if a write tool shows up in read-only mode.
- Every tool declares MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`). `tests/test_annotations.py` enforces it.
- New Google API scopes go through `ga4_seo_mcp.scopes.required_scopes()`; never request a scope directly in a tool.

### KISS · YAGNI
- If there is only one implementation, there is no interface.
- Do not add error handling for cases that cannot happen. Validate at the edges (user input, external APIs).

### Tests first
- Logic with rules → write the test before the code.
- Tests never call real Google APIs. Mock the client factory (`_client()`, `_sc_client()`, …) with `monkeypatch`.

### Comments
- By default, do not write comments. Explain the **why** (a decision, a non-obvious constraint, an API quirk), never the *what*.

---

## Conventions

- Code, docstrings, tool descriptions, commits, PRs and issues: **English**. Issues in Spanish are welcome too.
- Tool descriptions are read by the user's LLM: say what the tool does, what it returns, and any precondition, in plain English.
- [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. Imperative mood, first line ≤ 72 characters, body explains the **why**.
- **1 PR = 1 purpose.** The PR body answers: what changes, why, and how you tested it.
- Never commit real property IDs, account IDs, customer IDs, domains you manage or credentials. Examples use `properties/123456789`, `example.com` and `my-gcp-project`.

---

## Development setup

```bash
git clone https://github.com/GermaniU/ga4-seo-mcp.git
cd ga4-seo-mcp
uv sync --all-extras

uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Adding a tool

1. Add the function to the module of its Google surface and register it inside that module's `register()`, under `if writes:` if it changes anything.
2. Pass explicit annotations (`READ`, `WRITE`, `DESTRUCTIVE`, … from `ga4_seo_mcp.annotations`).
3. Add tests with a mocked client, and update the expected counts in `tests/test_toolsets.py`.
4. Update `docs/TOOLS.md` (`uv run python scripts/gen_tools_doc.py`), the toolset table in both READMEs, and `CHANGELOG.md` under `[Unreleased]`.

---

## Code of conduct

Be professional, in any language. Criticize code, not people.
