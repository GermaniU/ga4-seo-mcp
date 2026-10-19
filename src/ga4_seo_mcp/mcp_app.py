"""Instancia FastMCP compartida. Los módulos de tools la importan para registrar."""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# Server pensado para servir en toda la LAN (--host 0.0.0.0 default). La
# protección anti-DNS-rebinding del SDK solo permite Host: localhost/127.0.0.1
# por defecto y rechaza con 421 cualquier cliente que conecte por la IP LAN.
mcp = FastMCP(
    "ga4-seo-mcp",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
