"""Regenerate docs/TOOLS.md from the real tool registry.

uv run python scripts/gen_tools_doc.py          # write docs/TOOLS.md
uv run python scripts/gen_tools_doc.py --check  # exit 1 if it is out of date
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

from ga4_seo_mcp.scopes import TOOLSETS, required_scopes
from ga4_seo_mcp.server import WRITE_TOOLS, build_server

OUT = Path(__file__).resolve().parent.parent / "docs" / "TOOLS.md"


def _kind(tool) -> str:
    if tool.name == "bootstrap_site_measurement":
        return "read (plan); write with `apply=True`"
    a = tool.annotations
    if a.readOnlyHint:
        return "read"
    if a.destructiveHint:
        return "write, destructive"
    return "write"


def _summary(description: str) -> str:
    return inspect.cleandoc(description).split("\n\n")[0].replace("\n", " ")


async def _render() -> str:
    lines = [
        "# Tools",
        "",
        "Generated from the live registry by `scripts/gen_tools_doc.py`; do not edit by hand.",
        "",
        "Write tools only exist when the server starts with `--enable-writes`.",
        "`bootstrap_site_measurement` is always registered with the `admin` toolset; its",
        "`apply=True` mode needs `--enable-writes`.",
        "",
    ]
    seen: set[str] = set()
    for toolset in TOOLSETS:
        tools = [t for t in await build_server((toolset,), writes=True).list_tools()]
        tools = [t for t in tools if t.name not in seen]
        seen.update(t.name for t in tools)
        reads = len([t for t in tools if t.name not in WRITE_TOOLS])
        scopes = required_scopes((toolset,), writes=False)
        write_scopes = [s for s in required_scopes((toolset,), writes=True) if s not in scopes]
        lines += [
            f"## `{toolset}` ({reads} read, {len(tools) - reads} write)",
            "",
            "Scopes: " + (", ".join(f"`{s.rsplit('/', 1)[-1]}`" for s in scopes) or "none"),
        ]
        if write_scopes:
            lines[-1] += " · with writes: " + ", ".join(
                f"`{s.rsplit('/', 1)[-1]}`" for s in write_scopes
            )
        lines += ["", "| Tool | Kind | Description |", "|---|---|---|"]
        for t in tools:
            lines.append(f"| `{t.name}` | {_kind(t)} | {_summary(t.description)} |")
        lines.append("")
    prompts = await build_server((), writes=False).list_prompts()
    lines += ["## Prompts", "", "| Prompt | Arguments | Description |", "|---|---|---|"]
    for p in prompts:
        args = ", ".join(f"`{a.name}`" for a in p.arguments or [])
        lines.append(f"| `{p.name}` | {args} | {_summary(p.description)} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    text = asyncio.run(_render())
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != text:
            print("docs/TOOLS.md is out of date: run scripts/gen_tools_doc.py", file=sys.stderr)
            return 1
        return 0
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
