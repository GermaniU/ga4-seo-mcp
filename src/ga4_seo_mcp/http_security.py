"""HTTP transport hardening: DNS-rebinding protection, optional bearer token and CORS."""

from __future__ import annotations

import hmac
import sys

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
ALL_INTERFACES = {"0.0.0.0", "::", ""}


def transport_security(
    host: str, cors_origins: list[str] | None = None, extra_hosts: list[str] | None = None
) -> TransportSecuritySettings:
    allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    allowed_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    for extra in extra_hosts or []:
        # Names or IPs the operator expects clients to use: the machine's LAN address
        # when binding 0.0.0.0, for example. Anything not listed here is still rejected.
        name = f"[{extra}]" if ":" in extra else extra
        allowed_hosts += [name, f"{name}:*"]
        allowed_origins += [f"http://{name}:*", f"https://{name}:*"]
    if host not in LOOPBACK | ALL_INTERFACES:
        name = f"[{host}]" if ":" in host else host
        allowed_hosts += [name, f"{name}:*"]
        allowed_origins += [f"http://{name}:*", f"https://{name}:*"]
    allowed_origins += cors_origins or []
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


class BearerAuthMiddleware:
    """Rejects every HTTP request that lacks `Authorization: Bearer <token>`."""

    def __init__(self, app, token: str):
        self.app = app
        self._expected = f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            sent = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(sent, self._expected):
                response = PlainTextResponse(
                    "Unauthorized", status_code=401, headers={"WWW-Authenticate": "Bearer"}
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def build_http_app(
    mcp: FastMCP,
    transport: str,
    *,
    host: str,
    auth_token: str | None = None,
    cors_origins: list[str] | None = None,
    allowed_hosts: list[str] | None = None,
):
    """ASGI app for the `sse` or `streamable-http` transport with the security layers applied."""
    if host in ALL_INTERFACES and not auth_token:
        print(
            f"WARNING: listening on {host or 'all interfaces'} without MCP_AUTH_TOKEN. Anyone who "
            "can reach this port can use your Google credentials. Set MCP_AUTH_TOKEN or bind to "
            "127.0.0.1.",
            file=sys.stderr,
        )
    if host in ALL_INTERFACES and not allowed_hosts:
        print(
            f"WARNING: bound to {host or 'all interfaces'}, but only loopback is an "
            "allowed Host, so LAN clients get 421. Set MCP_ALLOWED_HOSTS to the "
            "address they use (e.g. MCP_ALLOWED_HOSTS=192.168.1.10).",
            file=sys.stderr,
        )
    mcp.settings.transport_security = transport_security(host, cors_origins, allowed_hosts)
    app = mcp.sse_app() if transport == "sse" else mcp.streamable_http_app()
    if auth_token:
        app = BearerAuthMiddleware(app, auth_token)
    if cors_origins:
        # Outermost, so preflight requests (which never carry credentials) get answered.
        app = CORSMiddleware(
            app,
            allow_origins=cors_origins,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Mcp-Session-Id",
                "Mcp-Protocol-Version",
            ],
            expose_headers=["Mcp-Session-Id"],
        )
    return app
