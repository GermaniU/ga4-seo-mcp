"""ga4-seo-mcp: CLI entry point and server assembly."""

from __future__ import annotations

import argparse
import importlib
import os
import sys

from mcp.server.fastmcp import FastMCP

from . import __version__, admin, bootstrap, data, pagespeed, prompts, search_console
from .scopes import TOOLSETS, auth_command, parse_toolsets

INSTRUCTIONS = """\
Tools for Google Analytics 4, Search Console and PageSpeed Insights.
- Start with list_account_summaries (GA4) or sc_list_sites (Search Console) to find IDs.
- Search Console data lags 2-3 days; GA4 realtime covers the last 30 minutes.
- To set up a new site, use bootstrap_site_measurement with apply=False first, show the plan to
  the user, and only apply it after explicit confirmation.
- Tools that change configuration only exist when the server runs with --enable-writes."""

WRITE_TOOLS = frozenset(
    [fn.__name__ for fn in admin.WRITE_TOOLS] + [fn.__name__ for fn in search_console.WRITE_TOOLS]
)


def _optional_module(toolset: str):
    if toolset == "dataforseo":
        return importlib.import_module(".keywords_dataforseo", __package__)
    try:
        return importlib.import_module(".keyword_planner", __package__)
    except ImportError as exc:
        raise SystemExit(
            "The 'ads' toolset needs the google-ads package: pip install 'ga4-seo-mcp[ads]'"
        ) from exc


def build_server(toolsets, *, writes: bool) -> FastMCP:
    """A FastMCP server with only the tools of the enabled toolsets (writes only if asked)."""
    mcp = FastMCP("ga4-seo-mcp", instructions=INSTRUCTIONS)
    # FastMCP has no version argument and would report the MCP SDK version in serverInfo.
    mcp._mcp_server.version = __version__
    if "admin" in toolsets:
        admin.register(mcp, writes=writes)
        bootstrap.register(mcp, writes=writes, gsc="gsc" in toolsets)
    if "data" in toolsets:
        data.register(mcp, writes=writes)
    if "gsc" in toolsets:
        search_console.register(mcp, writes=writes)
    if "psi" in toolsets:
        pagespeed.register(mcp, writes=writes)
    for name in ("dataforseo", "ads"):
        if name in toolsets:
            _optional_module(name).register(mcp, writes=writes)
    prompts.register(mcp)
    return mcp


def _toolsets_arg(raw: str) -> tuple[str, ...]:
    try:
        return parse_toolsets(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def parse_args(argv=None) -> argparse.Namespace:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--toolsets",
        type=_toolsets_arg,
        default=argparse.SUPPRESS,
        help=f"comma-separated subset of {','.join(TOOLSETS)} "
        "(env GA4SEO_TOOLSETS, default admin,data,gsc,psi)",
    )
    common.add_argument(
        "--enable-writes",
        action="store_true",
        default=argparse.SUPPRESS,
        help="register tools that create, update, delete, submit or verify "
        "(env GA4SEO_ENABLE_WRITES=1). Off by default.",
    )

    parser = argparse.ArgumentParser(
        prog="ga4-seo-mcp",
        description="MCP server for Google Analytics 4, Search Console and PageSpeed Insights.",
        parents=[common],
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="stdio (default), streamable-http or sse (env MCP_TRANSPORT)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "127.0.0.1"),
        help="HTTP bind address (env MCP_HOST, default 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "8000")),
        help="HTTP port (env MCP_PORT, default 8000)",
    )

    sub = parser.add_subparsers(dest="command", metavar="{auth-command,doctor}")
    auth = sub.add_parser(
        "auth-command",
        parents=[common],
        help="print the gcloud login command with the minimum scopes",
    )
    auth.add_argument(
        "--client-id-file",
        help="your own OAuth client JSON (Desktop app); Google blocks Analytics and Search "
        "Console scopes on gcloud's built-in client",
    )
    sub.add_parser(
        "doctor",
        parents=[common],
        help="check credentials, token scopes and which APIs answer (read-only)",
    )

    args = parser.parse_args(argv)
    if not hasattr(args, "toolsets"):
        try:
            args.toolsets = parse_toolsets(os.environ.get("GA4SEO_TOOLSETS"))
        except ValueError as exc:
            parser.error(f"GA4SEO_TOOLSETS: {exc}")
    if not hasattr(args, "enable_writes"):
        args.enable_writes = _env_flag("GA4SEO_ENABLE_WRITES")
    return args


def main(argv=None) -> None:
    args = parse_args(argv)

    if args.command == "auth-command":
        print(auth_command(args.toolsets, args.enable_writes, args.client_id_file))
        return
    if args.command == "doctor":
        from .doctor import run_doctor

        sys.exit(run_doctor(args.toolsets, args.enable_writes))

    mcp = build_server(args.toolsets, writes=args.enable_writes)
    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return

    import uvicorn

    from .http_security import build_http_app

    cors = [o.strip() for o in os.environ.get("MCP_CORS_ORIGINS", "").split(",") if o.strip()]
    allowed_hosts = [
        h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()
    ]
    app = build_http_app(
        mcp,
        args.transport,
        host=args.host,
        auth_token=os.environ.get("MCP_AUTH_TOKEN") or None,
        cors_origins=cors,
        allowed_hosts=allowed_hosts,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
