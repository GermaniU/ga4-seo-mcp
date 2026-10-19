# Security

This document explains what `ga4-seo-mcp` protects, what it does **not** protect, and how to report a vulnerability.

*Resumen en español: reporta las vulnerabilidades en privado desde la pestaña **Security → Report a vulnerability** del repositorio. No abras issues públicos para problemas de seguridad.*

---

## Threat model

`ga4-seo-mcp` is a **single-user** MCP server. It acts on Google Analytics 4, Search Console and (optionally) Google Ads **with your own Google credentials**. Anyone who can call its tools can do whatever those credentials allow, within the toolsets you enabled. Security is therefore about two things: who can reach the server, and which tools exist at all.

### What it protects

| Risk | Mitigation |
|---|---|
| An LLM (or a prompt injection) changes or deletes your GA4/Search Console configuration | **Read-only by default.** Tools that create, update, delete, submit or verify anything are not even registered unless you start the server with `--enable-writes` (or `GA4SEO_ENABLE_WRITES=1`). Every tool carries MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`) so clients can ask before running writes. |
| The OAuth token grants more than you need | `ga4-seo-mcp auth-command` prints a `gcloud` login with the **minimum scopes** for the toolsets you enable. Read-only use only asks for `analytics.readonly` and `webmasters.readonly`. |
| Another machine on your network uses your Google credentials through the HTTP transport | HTTP listens on `127.0.0.1` by default. Binding to a non-loopback address without `MCP_AUTH_TOKEN` prints a warning. |
| A web page you visit calls the local HTTP endpoint (CSRF / DNS rebinding) | **DNS-rebinding protection is on** (only the configured host is accepted in the `Host` header) and **CORS is off** unless you list exact origins in `MCP_CORS_ORIGINS`. |
| Someone without the token calls the HTTP endpoint | Set `MCP_AUTH_TOKEN`: every HTTP request must send `Authorization: Bearer <token>` or gets `401`. |
| API secrets leak into logs or tool errors | DataForSEO credentials and the Google Ads developer token are read only from environment variables or from a file with `0600` permissions. They are never logged or returned in error messages. |
| The container compromises the host | The Docker image runs as an unprivileged user. |

### What it does NOT protect

- **Other processes of your own user.** Any program on your machine can launch the stdio server or call the loopback endpoint.
- **Internet exposure.** Do not publish the HTTP port to the internet. If you must reach it remotely, put a reverse proxy with TLS and authentication in front and set `MCP_AUTH_TOKEN`.
- **What your Google account can already do.** With `--enable-writes`, the tools can change everything your account (or service account) has edit access to. Use a service account with access only to the properties you want to manage.
- **Data returned by the APIs.** Report rows, page titles and query strings are third-party content. Treat them as untrusted input (prompt injection), like any other text from the web.
- **`MCP_CORS_ORIGINS=*`.** Technically possible, but it lets any website you visit use your credentials. **Do not use it.**

---

## Recommended configuration

| Setting | Recommendation |
|---|---|
| Transport | `stdio` (default). Use HTTP only when several clients must share one server. |
| `MCP_HOST` | `127.0.0.1` (default). In Docker publish with `-p 127.0.0.1:8000:8000`. |
| `MCP_AUTH_TOKEN` | Always set it when using HTTP outside a single-user laptop. |
| `MCP_CORS_ORIGINS` | Empty (default). Only list exact origins for a browser-based client you control. |
| `--enable-writes` | Off (default). Turn it on only for the session where you actually set up a site. |
| Credentials | A service account with Viewer access on the properties for read-only use. |

---

## Reporting a vulnerability

**Do not open a public issue.** Use GitHub private reporting: open the repository's **Security** tab, choose **Report a vulnerability**, and include:

- steps to reproduce;
- the impact (what data is exposed or what an attacker can do);
- the affected version or commit.

You can write in English or Spanish.
