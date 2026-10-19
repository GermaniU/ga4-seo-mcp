## What changes and why?

<!-- Conventional Commit title (feat:/fix:/refactor:/test:/docs:/chore:), first line ≤ 72 chars.
     Explain the WHY; the diff already shows the what. -->

## How did you test it?

<!-- Exact commands. Never paste real property/account IDs or tokens. -->

---

## Checklist

- [ ] Tests for all new logic (Google clients mocked, no real API calls)
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run pytest` passes
- [ ] New write tools are registered only with `writes=True` and carry annotations
- [ ] `docs/TOOLS.md` regenerated (`uv run python scripts/gen_tools_doc.py`) and both READMEs updated
- [ ] `CHANGELOG.md` entry under `[Unreleased]`
