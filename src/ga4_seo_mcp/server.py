"""
Servidor MCP para Google Marketing Stack (Analytics + Search Console + PageSpeed).

Entry point: importa todos los módulos de tools para que se registren contra la
instancia FastMCP compartida en `mcp_app.py`, luego corre `mcp.run()` por stdio.

Auth:
- GA Admin/Data + Search Console + Google Ads: Application Default Credentials.
  Scopes requeridos: analytics.edit + analytics.readonly + webmasters + siteverification + cloud-platform + adwords.
  Setup: bash scripts/auth-v2.sh
- PageSpeed: API pública. Opcional env PAGESPEED_API_KEY para mayor cuota.
- DataForSEO: HTTP Basic Auth vía env vars DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD.
- Google Ads (Keyword Planner): ADC + env var GOOGLE_ADS_DEVELOPER_TOKEN
  obligatoria (opcional GOOGLE_ADS_LOGIN_CUSTOMER_ID si es cuenta MCC).
  Ver docstring de keyword_planner.py para el detalle de qué está validado.
"""

from __future__ import annotations

# Importar módulos: el side-effect es que cada @mcp.tool() se registre
# en la instancia compartida `mcp` de mcp_app.
import argparse
import os

from . import admin       # noqa: F401  Admin API (config GA4)
from . import data        # noqa: F401  Data API (lectura métricas GA4)
from . import search_console  # noqa: F401  Search Console (SEO queries, pages)
from . import pagespeed   # noqa: F401  PageSpeed Insights + CrUX
from . import keywords_dataforseo  # noqa: F401  DataForSEO keyword research
from . import keyword_planner  # noqa: F401  Google Ads Keyword Planner
from . import prompts     # noqa: F401  MCP Prompts (plantillas predefinidas)

from .mcp_app import mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="GA Admin MCP Server (Google Marketing Stack)")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="Transport type: stdio (default), sse, or streamable-http",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "0.0.0.0"),
        help="Host interface for SSE/HTTP transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "8772")),
        help="Port for SSE/HTTP transport (default: 8772)",
    )
    args, _ = parser.parse_known_args()

    if args.transport in ("sse", "streamable-http"):
        mcp.settings.host = args.host
        mcp.settings.port = args.port

        # FastMCP no agrega CORS por default: un cliente MCP corriendo en un
        # browser (ej. webui de llama.cpp) hace fetch/EventSource cross-origin
        # y sin Access-Control-Allow-Origin en la respuesta real (no solo en el
        # preflight OPTIONS) el browser descarta la respuesta como fallo de red.
        import uvicorn
        from starlette.middleware.cors import CORSMiddleware

        raw_app = mcp.sse_app() if args.transport == "sse" else mcp.streamable_http_app()
        app = CORSMiddleware(
            raw_app,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        return

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()

