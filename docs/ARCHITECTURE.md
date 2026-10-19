# Architecture

```
 MCP client (Claude Code, Cursor, VS Code, …)
        │  stdio (default)  ·  Streamable HTTP / SSE (opt-in)
        ▼
 ┌─────────────────────────── ga4-seo-mcp ────────────────────────────┐
 │ server.py        CLI (serve · auth-command · doctor), build_server │
 │ http_security.py DNS-rebinding settings · bearer token · CORS      │
 │                                                                    │
 │ build_server(toolsets, writes) ── register(mcp, writes=…) ──┐      │
 │   admin.py            GA4 Admin API (v1beta, v1alpha links) │      │
 │   bootstrap.py        bootstrap_site_measurement            │      │
 │   data.py             GA4 Data API                          │      │
 │   search_console.py   Search Console + Site Verification    │      │
 │   pagespeed.py        PageSpeed Insights v5                 │      │
 │   keywords_dataforseo.py   (optional toolset)               │      │
 │   keyword_planner.py       (optional toolset, [ads] extra)  │      │
 │   prompts.py          MCP prompts                           │      │
 │                                                             │      │
 │ scopes.py       toolsets → minimum OAuth scopes             │      │
 │ auth.py         google.auth.default(scopes=…)               │      │
 │ annotations.py  READ · CREATE · UPDATE · DELETE · ENSURE    │      │
 └─────────────────────────────────────────────────────────────┴──────┘
        │ HTTPS (gRPC for GA4 and Google Ads)
        ▼
 Google APIs · DataForSEO
```

## Registration

No module registers tools when it is imported. `build_server(toolsets, writes)` creates a `FastMCP` instance and calls `register(mcp, *, writes)` only for the enabled toolsets. Each module keeps its tool functions at module level (easy to test) and lists them in `READ_TOOLS` / `WRITE_TOOLS`; write tools are added only when `writes=True`, each with its `ToolAnnotations`.

`bootstrap_site_measurement` comes with the `admin` toolset. It is built by `make_tool(writes, gsc)`: the same plan logic always, the `apply=True` branch refusing to run unless the server has writes on, and the Search Console step skipped when the `gsc` toolset is off. It reuses the Admin and Search Console tool functions, so it calls exactly the same Google endpoints the individual tools do.

The `dataforseo` and `ads` modules are imported lazily, so `google-ads` stays an optional extra.

## Credentials and scopes

Every Google client is constructed with explicit credentials from `auth.credentials(scope)`. Reads pass the read-only scope and writes the edit scope, even when the server has writes enabled, so a service account never holds a broader token than the call needs. `scopes.required_scopes()` is the single source for which scopes a toolset combination needs; `auth-command` and `doctor` use it.

## HTTP transport

`build_http_app()` wraps the SDK's Starlette app:

1. `TransportSecuritySettings(enable_dns_rebinding_protection=True)`: only loopback hosts (plus a non-loopback `MCP_HOST`) are accepted in `Host`, and only loopback origins (plus `MCP_CORS_ORIGINS`) in `Origin`.
2. `BearerAuthMiddleware` when `MCP_AUTH_TOKEN` is set: constant-time comparison, `401` with `WWW-Authenticate: Bearer` otherwise.
3. `CORSMiddleware` outermost, only when `MCP_CORS_ORIGINS` lists origins, so browser preflights are answered without credentials.

## Tests

| File | Covers |
|---|---|
| `test_toolsets.py` | tool set per toolset/writes combination, counts, no write tool without writes |
| `test_annotations.py` | every tool annotated; reads read-only, deletes destructive, creates additive |
| `test_scopes.py` | `required_scopes()` and the printed `gcloud` command |
| `test_http_security.py` | CLI defaults, 401/200 with token, 421/403 rebinding, CORS on/off, `0.0.0.0` warning |
| `test_bootstrap.py` | plan on empty account, existing property, idempotent apply, clean failure without writes |
| `test_secrets.py` | PSI key never in errors, dev-token file must be `0600` |
| `test_cli.py` | `auth-command`, `doctor` without credentials, `--version` |
| `test_keyword*.py` | DataForSEO and Keyword Planner mapping with mocked clients |

No test calls a real Google API. `scripts/smoke_stdio.py` launches the real server over stdio and checks `initialize` + `tools/list`.
