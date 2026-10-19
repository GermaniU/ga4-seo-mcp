# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] — 2026-10-19

### Fixed
- Both READMEs now use absolute repository URLs for every link and image. PyPI renders the project description outside the repository, so relative paths (`docs/assets/demo.gif`, `LICENSE`, `docs/TOOLS.md`…) resolved against `pypi.org` and returned 404 — the demo GIF showed as a broken image. Images load from `raw.githubusercontent.com`; prose links point to `blob/main`, which works on GitHub too. No code changes.

## [0.1.0] — 2026-10-19

First public version, derived from an internal prototype with a clean history.

### Security
- **Read-only by default.** Tools that create, update, delete, submit or verify are only registered with `--enable-writes` / `GA4SEO_ENABLE_WRITES=1`.
- MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) on every tool.
- Minimum OAuth scopes per toolset; every Google client requests only the scope of its call.
- HTTP transport: `127.0.0.1` by default, DNS-rebinding protection on, CORS off unless `MCP_CORS_ORIGINS`, optional `MCP_AUTH_TOKEN` bearer check (401), warning when listening on all interfaces without a token.
- The PageSpeed API key can no longer leak through HTTP error messages; the Google Ads developer token file must be `chmod 600`.

### Added
- Toolsets: `--toolsets` / `GA4SEO_TOOLSETS` (`admin,data,gsc,psi,dataforseo,ads`, default `admin,data,gsc,psi`).
- `bootstrap_site_measurement`: read-only plan of a site's GA4 + Search Console setup, and an idempotent `apply=True` mode behind `--enable-writes` that returns the measurement ID and the DNS TXT token.
- `launch_site_measurement` prompt: plan → confirmation → apply → DNS verification → sitemap → PageSpeed baseline.
- CLI: `ga4-seo-mcp auth-command` (prints the `gcloud` login with the minimum scopes) and `ga4-seo-mcp doctor` (read-only checks of credentials, token scopes and API access), `--version`.
- Service accounts via `GOOGLE_APPLICATION_CREDENTIALS`.
- Docker image (non-root, stdio entrypoint), `server.json` for the MCP Registry (PyPI + OCI), CI (ruff, pytest on 3.11/3.12, wheel install, stdio and Docker smoke tests, gitleaks) and a tag-triggered release workflow.
- `docs/TOOLS.md` generated from the live registry, `docs/AUTH.md`, `docs/ARCHITECTURE.md`, `README.es.md`.
- GA4 Admin API tools (accounts, properties, data streams, key events, custom dimensions, Google Ads links).
- GA4 Data API tools (flexible reports, realtime, top pages, events, traffic sources, conversions, portfolio audit).
- Search Console tools (top queries, page performance, sitemaps, domain verification over DNS TXT).
- PageSpeed Insights tools (Lighthouse lab data and CrUX field data).
- Optional keyword research toolsets: DataForSEO and Google Ads Keyword Planner (`[ads]` extra).

### Changed (from the internal prototype)
- Tool descriptions and prompts rewritten in English; prompts reference the real tool names.
- `create_property` requires `time_zone` and `currency_code` instead of defaulting to Mexico/MXN.
- PageSpeed requests encode the audited URL properly (URLs with query strings used to break).
- The HTTP default port is `8000`.

[Unreleased]: https://github.com/GermaniU/ga4-seo-mcp/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/GermaniU/ga4-seo-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/GermaniU/ga4-seo-mcp/releases/tag/v0.1.0
