"""Launch the real server over stdio, run initialize + tools/list, and print the tool count.

    python scripts/smoke_stdio.py [--expect N] [--command CMD ...] -- [server args]

Default command: `ga4-seo-mcp`. Exits 1 if --expect does not match.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def _list_tools(command: list[str], server_args: list[str]) -> list[str]:
    params = StdioServerParameters(
        command=command[0], args=[*command[1:], *server_args], env=dict(os.environ)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"initialize: {init.serverInfo.name} {init.serverInfo.version}", file=sys.stderr)
            return sorted(t.name for t in (await session.list_tools()).tools)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect", type=int)
    parser.add_argument("--command", nargs="+", default=["ga4-seo-mcp"])
    parser.add_argument("server_args", nargs="*")
    args = parser.parse_args()
    names = asyncio.run(_list_tools(args.command, args.server_args))
    print(f"tools/list: {len(names)} tools ({' '.join(args.server_args) or 'defaults'})")
    if args.expect is not None and len(names) != args.expect:
        print(f"expected {args.expect}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
