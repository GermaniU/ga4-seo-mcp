"""
MCP Prompts nativos para el Google Marketing Stack (ga4-seo-mcp).

Registra plantillas de prompt ejecutables (@mcp.prompt()) que guían al modelo de lenguaje
en flujos complejos de auditoría y análisis de GA4, Search Console y PageSpeed.
"""

from __future__ import annotations

from .mcp_app import mcp


@mcp.prompt()
def audit_ga4_setup(property_id: str) -> str:
    """
    Prompt plantilla para auditar la instrumentación completa de una propiedad GA4.

    Guía al asistente a revisar Data Streams, Key Events, Custom Dimensions y Google Ads Links.
    """
    return f"""Por favor realiza una auditoría completa de la instrumentación de la propiedad GA4 '{property_id}':

1. **Propiedad y Data Streams**:
   - Usa `get_property` para obtener los detalles de la propiedad.
   - Usa `list_data_streams` para verificar los streams de datos Web y App configurados.

2. **Key Events y Conversiones**:
   - Usa `list_key_events` para obtener las conversiones declaradas.
   - Usa `events_summary` (Data API) para comparar cuáles son los eventos reales disparados en los últimos 7 días y detectar gaps de medición.

3. **Custom Dimensions y Métricas**:
   - Usa `list_custom_dimensions` para revisar qué dimensiones personalizadas (event/user scoped) están activas.

4. **Vinculación con Google Ads**:
   - Usa `list_google_ads_links` para comprobar si existe integración activa con Google Ads.

5. **Entregable**:
   - Genera un reporte estructurado en Markdown con un Score de Salud (1-10) de la instrumentación y recomendaciones concretas para corregir faltantes.
"""


@mcp.prompt()
def seo_360_audit(site_url: str, property_id: str) -> str:
    """
    Prompt plantilla para auditoría 360° de SEO orgánico y rendimiento Web (Search Console + GA4 + PageSpeed).
    """
    return f"""Por favor realiza una auditoría 360° de SEO y Performance para el sitio '{site_url}' (Propiedad GA4: '{property_id}'):

1. **Rendimiento Orgánico (Search Console)**:
   - Usa `search_console_top_queries` para obtener las top 25 búsquedas de los últimos 28 días con clics, impresiones, CTR y posición.
   - Usa `search_console_top_pages` para identificar las landing pages principales.

2. **Comportamiento en Sitio (GA4 Data API)**:
   - Usa `top_pages` y `traffic_sources` en GA4 para analizar usuarios activos, tiempo de sesión y bounce rate de esas páginas.

3. **Velocidad y Experiencia de Usuario (PageSpeed Insights + CrUX)**:
   - Usa `run_pagespeed` para auditar la velocidad en Mobile y Desktop.
   - Usa `get_crux_data` si hay datos de campo disponibles.

4. **Síntesis**:
   - Muestra una tabla comparativa de Oportunidades SEO (páginas con alto volumen de impresiones pero bajo CTR o bounce rate alto).
   - Entrega los 3 accionables más urgentes de optimización.
"""


@mcp.prompt()
def portfolio_performance_digest(property_ids: str) -> str:
    """
    Prompt plantilla para generar un reporte digest consolidado de un portafolio de sitios.

    Args:
        property_ids: Cadena de IDs de propiedades GA4 separados por coma (ej. '123456789,987654321').
    """
    pids = [p.strip() for p in property_ids.split(",") if p.strip()]
    pids_repr = ", ".join([f"'{p}'" for p in pids])

    return f"""Por favor genera un Digest Consolidado del Portafolio para las propiedades GA4: [{pids_repr}]:

1. Usa la herramienta `audit_portfolio` enviando la lista de propiedades para los últimos 7 días.
2. Presenta un cuadro comparativo del portafolio mostrando:
   - Sesiones totales por propiedad.
   - Usuarios activos.
   - Conversiones registradas.
   - Bounce Rate promedio.
3. Destaca la propiedad con mejor rendimiento y la que presente mayor caída o requerimiento de atención.
"""
