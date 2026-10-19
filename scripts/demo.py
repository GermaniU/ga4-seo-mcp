"""Recordable demo: a real MCP client talks to ga4-seo-mcp over stdio.

1. psi_audit on a public site.
2. bootstrap_site_measurement(apply=False) planning a site that is not set up yet.

Source of docs/assets/demo.gif. Read-only: the server runs without --enable-writes.
The GA4 account ID is redacted on screen, and the planned site is example.com, so nothing
from the account that runs the demo is shown.

    PAGESPEED_API_KEY=... uv run python scripts/demo.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PUBLIC_URL = "https://www.python.org/"
NEW_SITE = "https://example.com"

BOLD, DIM, GREEN, CYAN, YELLOW, RESET = (
    "\033[1m",
    "\033[2m",
    "\033[32m",
    "\033[36m",
    "\033[33m",
    "\033[0m",
)


THIN_SPACES = {"\u202f": " ", "\u00a0": " ", "\u2009": " ", "\u2007": " "}


def say(text: str = "", pause: float = 0.6) -> None:
    # PageSpeed formatea sus displayValue con espacios angostos (U+202F/NBSP); la
    # fuente del GIF no tiene ese glifo y lo dibuja como un cuadro roto.
    for bad, good in THIN_SPACES.items():
        text = text.replace(bad, good)
    print(text, flush=True)
    time.sleep(pause)


def call_line(name: str, args: str) -> None:
    say(f"{CYAN}> {name}{RESET}({args})", 0.3)


def payload(result):
    if result.isError:
        raise SystemExit(f"tool error: {result.content[0].text}")
    data = result.structuredContent
    if data is not None:
        return data.get("result", data)
    return json.loads(result.content[0].text)


async def main() -> None:
    # Primera línea ya en pantalla: si no, el primer cuadro del GIF sale vacío y
    # LinkedIn lo puede usar como miniatura.
    say(f"{DIM}$ python scripts/demo.py   ·   MCP over stdio, read-only{RESET}", 0.8)
    say()

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "ga4_seo_mcp.server"], env=dict(os.environ)
    )
    with open(os.devnull, "w") as quiet:
        async with stdio_client(params, errlog=quiet) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                tools = (await session.list_tools()).tools
                say(
                    f"{BOLD}{init.serverInfo.name} {init.serverInfo.version}{RESET}  "
                    f"{DIM}{len(tools)} tools, read-only (no --enable-writes){RESET}",
                    1.0,
                )
                say()

                call_line("psi_audit", f"url={PUBLIC_URL!r}, strategy='mobile'")
                psi = payload(
                    await session.call_tool("psi_audit", {"url": PUBLIC_URL, "strategy": "mobile"})
                )
                scores = "  ".join(f"{k} {GREEN}{v}{RESET}" for k, v in psi["scores"].items())
                say(f"  {scores}")
                lab = psi["web_vitals_lab"]
                say(
                    "  lab  "
                    + "  ".join(
                        f"{m} {lab[m]['display_value']}" for m in ("LCP", "CLS", "TBT") if m in lab
                    )
                )
                crux = (psi.get("crux_origin") or {}).get("overall_category")
                say(f"  CrUX origin (real users): {YELLOW}{crux or 'no data'}{RESET}", 1.2)
                say()

                summaries = payload(await session.call_tool("list_account_summaries", {}))
                account_id = summaries[0]["account_id"]
                call_line(
                    "bootstrap_site_measurement",
                    f"site_url={NEW_SITE!r}, key_events=[…], apply=False",
                )
                plan = payload(
                    await session.call_tool(
                        "bootstrap_site_measurement",
                        {
                            "site_url": NEW_SITE,
                            "account_id": account_id,
                            "property_display_name": "Example Site",
                            "time_zone": "America/Mexico_City",
                            "currency_code": "USD",
                            "key_events": ["generate_lead"],
                            "custom_dimensions": [
                                {"parameter_name": "plan_type", "display_name": "Plan type"}
                            ],
                        },
                    )
                )
                for step in plan["steps"]:
                    detail = step.get("event_name") or step.get("parameter_name") or ""
                    color = GREEN if step["action"] == "exists" else YELLOW
                    say(f"  {step['step']:<32} {detail:<14} {color}{step['action']}{RESET}", 0.35)
                # Dos líneas cortas en vez de una que se parte a media palabra con
                # el ancho de terminal del GIF.
                say(f"  {DIM}Plan only, nothing was changed.{RESET}", 0.5)
                say(f"  {DIM}Apply it with --enable-writes.{RESET}", 2.5)


if __name__ == "__main__":
    asyncio.run(main())
