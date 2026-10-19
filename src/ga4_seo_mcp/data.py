"""
Tools del MCP para Google Analytics Data API (lectura de métricas GA4).

Cubre: reportes flexibles, top pages, eventos, real-time, fuentes de tráfico.
Requiere scope ADC: analytics.readonly (o analytics.edit que lo incluye).
API: analyticsdata.googleapis.com
"""

from __future__ import annotations

from typing import Any

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    OrderBy,
    RunRealtimeReportRequest,
    RunReportRequest,
)

from .mcp_app import mcp


def _data_client() -> BetaAnalyticsDataClient:
    return BetaAnalyticsDataClient()


def _norm_property(property_id: str) -> str:
    return property_id if property_id.startswith("properties/") else f"properties/{property_id}"


def _row_to_dict(row, dim_names: list[str], met_names: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, name in enumerate(dim_names):
        out[name] = row.dimension_values[i].value
    for i, name in enumerate(met_names):
        val = row.metric_values[i].value
        # Try numeric coercion
        try:
            out[name] = float(val) if "." in val else int(val)
        except (ValueError, AttributeError):
            out[name] = val
    return out


@mcp.tool()
def run_report(
    property_id: str,
    metrics: list[str],
    dimensions: list[str] | None = None,
    date_start: str = "7daysAgo",
    date_end: str = "today",
    limit: int = 25,
    order_by_metric: str | None = None,
    order_desc: bool = True,
) -> dict[str, Any]:
    """
    Corre un reporte de GA4 flexible.

    Args:
        property_id: id numérico o 'properties/...'
        metrics: lista de métricas (ej. ['sessions','activeUsers','conversions']).
            Catálogo: https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema#metrics
        dimensions: opcional (ej. ['date','sessionSource','pagePath']).
            Catálogo: https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema#dimensions
        date_start: 'YYYY-MM-DD', 'today', 'yesterday', '7daysAgo', '30daysAgo'…
        date_end: igual que date_start.
        limit: filas máximas (default 25).
        order_by_metric: ordenar por esta métrica (ej. 'sessions').
        order_desc: descendente si True.

    Returns dict con `dimensions`, `metrics`, `rows` (lista) y `row_count`.
    """
    client = _data_client()
    dim_names = dimensions or []
    req = RunReportRequest(
        property=_norm_property(property_id),
        dimensions=[Dimension(name=d) for d in dim_names],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=date_start, end_date=date_end)],
        limit=limit,
    )
    if order_by_metric:
        req.order_bys = [OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order_by_metric), desc=order_desc)]
    resp = client.run_report(request=req)
    rows = [_row_to_dict(r, dim_names, metrics) for r in resp.rows]
    return {
        "property_id": property_id,
        "dimensions": dim_names,
        "metrics": metrics,
        "date_range": {"start": date_start, "end": date_end},
        "row_count": resp.row_count,
        "rows": rows,
    }


@mcp.tool()
def run_realtime_report(
    property_id: str,
    metrics: list[str] | None = None,
    dimensions: list[str] | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """
    Real-time report (últimos 30 minutos). Útil para VALIDAR que un evento
    nuevo dispara en producción tras un deploy.

    Args:
        metrics: default ['activeUsers']. También 'eventCount'.
        dimensions: default ['eventName']. Útiles: 'unifiedScreenName', 'country', 'deviceCategory'.
    """
    client = _data_client()
    dim_names = dimensions or ["eventName"]
    met_names = metrics or ["activeUsers"]
    req = RunRealtimeReportRequest(
        property=_norm_property(property_id),
        dimensions=[Dimension(name=d) for d in dim_names],
        metrics=[Metric(name=m) for m in met_names],
        limit=limit,
    )
    resp = client.run_realtime_report(request=req)
    rows = [_row_to_dict(r, dim_names, met_names) for r in resp.rows]
    return {
        "property_id": property_id,
        "row_count": resp.row_count,
        "rows": rows,
    }


@mcp.tool()
def top_pages(
    property_id: str,
    date_start: str = "7daysAgo",
    date_end: str = "today",
    limit: int = 20,
) -> dict[str, Any]:
    """
    Top URLs por sesiones con métricas SEO/UX comunes.

    Devuelve por cada pagePath: sessions, activeUsers, bounceRate, averageSessionDuration.
    """
    return run_report(
        property_id=property_id,
        dimensions=["pagePath", "pageTitle"],
        metrics=["sessions", "activeUsers", "bounceRate", "averageSessionDuration"],
        date_start=date_start,
        date_end=date_end,
        limit=limit,
        order_by_metric="sessions",
        order_desc=True,
    )


@mcp.tool()
def events_summary(
    property_id: str,
    date_start: str = "7daysAgo",
    date_end: str = "today",
    limit: int = 50,
) -> dict[str, Any]:
    """
    Conteo de eventos disparados. Útil para auditar QUÉ se está midiendo
    y detectar gap entre key events declarados y eventos reales.
    """
    return run_report(
        property_id=property_id,
        dimensions=["eventName"],
        metrics=["eventCount", "eventCountPerUser"],
        date_start=date_start,
        date_end=date_end,
        limit=limit,
        order_by_metric="eventCount",
        order_desc=True,
    )


@mcp.tool()
def traffic_sources(
    property_id: str,
    date_start: str = "7daysAgo",
    date_end: str = "today",
    limit: int = 20,
) -> dict[str, Any]:
    """Top fuentes de tráfico (source/medium) con conversions."""
    return run_report(
        property_id=property_id,
        dimensions=["sessionSource", "sessionMedium"],
        metrics=["sessions", "activeUsers", "conversions"],
        date_start=date_start,
        date_end=date_end,
        limit=limit,
        order_by_metric="sessions",
        order_desc=True,
    )


@mcp.tool()
def conversions_summary(
    property_id: str,
    date_start: str = "7daysAgo",
    date_end: str = "today",
) -> dict[str, Any]:
    """Conversions por event_name. Resumen de Key Events activos."""
    return run_report(
        property_id=property_id,
        dimensions=["eventName"],
        metrics=["conversions", "totalUsers"],
        date_start=date_start,
        date_end=date_end,
        limit=25,
        order_by_metric="conversions",
        order_desc=True,
    )


@mcp.tool()
def web_vitals_summary(
    property_id: str,
    date_start: str = "7daysAgo",
    date_end: str = "today",
) -> dict[str, Any]:
    """
    Breakdown de Core Web Vitals capturados por nuestro WebVitalsReporter.
    Requiere: custom dimensions `web_vital_metric` + `web_vital_rating`
    declaradas en la propiedad.
    """
    return run_report(
        property_id=property_id,
        dimensions=["customEvent:web_vital_metric", "customEvent:web_vital_rating"],
        metrics=["eventCount"],
        date_start=date_start,
        date_end=date_end,
        limit=50,
        order_by_metric="eventCount",
        order_desc=True,
    )


@mcp.tool()
def audit_portfolio(
    property_ids: list[str],
    date_start: str = "7daysAgo",
    date_end: str = "today",
) -> dict[str, Any]:
    """
    Auditoría consolidada de un portafolio de propiedades GA4.

    Ejecuta consultas resumidas (sessions, activeUsers, conversions, bounceRate)
    para cada propiedad provista y consolida los resultados en un solo reporte.

    Args:
        property_ids: Lista de IDs numéricos o 'properties/...' (ej. ['123456789', '987654321']).
        date_start: Rango de fecha inicio (default: '7daysAgo').
        date_end: Rango de fecha fin (default: 'today').

    Returns:
        Dict con métricas agregadas por propiedad y errores (si alguna fallara).
    """
    summary_results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for pid in property_ids:
        try:
            report = run_report(
                property_id=pid,
                dimensions=[],
                metrics=["sessions", "activeUsers", "conversions", "bounceRate", "averageSessionDuration"],
                date_start=date_start,
                date_end=date_end,
                limit=1,
            )
            rows = report.get("rows", [])
            metrics_summary = rows[0] if rows else {
                "sessions": 0, "activeUsers": 0, "conversions": 0, "bounceRate": 0.0, "averageSessionDuration": 0.0
            }
            summary_results.append({
                "property_id": pid,
                "metrics": metrics_summary,
            })
        except Exception as exc:
            errors.append({
                "property_id": pid,
                "error": str(exc),
            })

    return {
        "portfolio_count": len(property_ids),
        "date_range": {"start": date_start, "end": date_end},
        "successful_audits": summary_results,
        "failed_audits": errors,
    }

