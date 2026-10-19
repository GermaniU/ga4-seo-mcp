"""GA4 Data API tools: reports, realtime, top pages, events, traffic sources."""

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
from mcp.server.fastmcp import FastMCP

from .annotations import READ
from .auth import credentials
from .scopes import ANALYTICS_READONLY


def _data_client() -> BetaAnalyticsDataClient:
    return BetaAnalyticsDataClient(credentials=credentials(ANALYTICS_READONLY))


def _norm_property(property_id: str) -> str:
    return property_id if property_id.startswith("properties/") else f"properties/{property_id}"


def _row_to_dict(row, dim_names: list[str], met_names: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, name in enumerate(dim_names):
        out[name] = row.dimension_values[i].value
    for i, name in enumerate(met_names):
        val = row.metric_values[i].value
        try:
            out[name] = float(val) if "." in val else int(val)
        except (ValueError, AttributeError):
            out[name] = val
    return out


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
    """Run a flexible GA4 report.

    Args:
        property_id: numeric ID or 'properties/123456789'.
        metrics: e.g. ['sessions', 'activeUsers', 'keyEvents']. Catalog:
            https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema#metrics
        dimensions: optional, e.g. ['date', 'sessionSource', 'pagePath']. Catalog:
            https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema#dimensions
        date_start: 'YYYY-MM-DD', 'today', 'yesterday' or 'NdaysAgo' (e.g. '28daysAgo').
        date_end: same formats as date_start.
        limit: maximum rows (default 25).
        order_by_metric: sort by this metric, e.g. 'sessions'.
        order_desc: sort descending (default True).

    Returns the dimension and metric names, the date range, row_count and the rows.
    """
    dim_names = dimensions or []
    req = RunReportRequest(
        property=_norm_property(property_id),
        dimensions=[Dimension(name=d) for d in dim_names],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=date_start, end_date=date_end)],
        limit=limit,
    )
    if order_by_metric:
        req.order_bys = [
            OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order_by_metric), desc=order_desc)
        ]
    resp = _data_client().run_report(request=req)
    return {
        "property_id": property_id,
        "dimensions": dim_names,
        "metrics": metrics,
        "date_range": {"start": date_start, "end": date_end},
        "row_count": resp.row_count,
        "rows": [_row_to_dict(r, dim_names, metrics) for r in resp.rows],
    }


def run_realtime_report(
    property_id: str,
    metrics: list[str] | None = None,
    dimensions: list[str] | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Realtime report for the last 30 minutes.

    Useful to confirm that a new event fires in production right after a deploy.

    Args:
        metrics: default ['activeUsers']; 'eventCount' also works.
        dimensions: default ['eventName']; also 'unifiedScreenName', 'country', 'deviceCategory'.
    """
    dim_names = dimensions or ["eventName"]
    met_names = metrics or ["activeUsers"]
    req = RunRealtimeReportRequest(
        property=_norm_property(property_id),
        dimensions=[Dimension(name=d) for d in dim_names],
        metrics=[Metric(name=m) for m in met_names],
        limit=limit,
    )
    resp = _data_client().run_realtime_report(request=req)
    return {
        "property_id": property_id,
        "row_count": resp.row_count,
        "rows": [_row_to_dict(r, dim_names, met_names) for r in resp.rows],
    }


def top_pages(
    property_id: str,
    date_start: str = "7daysAgo",
    date_end: str = "today",
    limit: int = 20,
) -> dict[str, Any]:
    """Top pages by sessions, with active users, bounce rate and average session duration."""
    return run_report(
        property_id=property_id,
        dimensions=["pagePath", "pageTitle"],
        metrics=["sessions", "activeUsers", "bounceRate", "averageSessionDuration"],
        date_start=date_start,
        date_end=date_end,
        limit=limit,
        order_by_metric="sessions",
    )


def events_summary(
    property_id: str,
    date_start: str = "7daysAgo",
    date_end: str = "today",
    limit: int = 50,
) -> dict[str, Any]:
    """Count of every event that fired, to audit what is actually being measured.

    Compare it with list_key_events to find key events that never fire.
    """
    return run_report(
        property_id=property_id,
        dimensions=["eventName"],
        metrics=["eventCount", "eventCountPerUser"],
        date_start=date_start,
        date_end=date_end,
        limit=limit,
        order_by_metric="eventCount",
    )


def traffic_sources(
    property_id: str,
    date_start: str = "7daysAgo",
    date_end: str = "today",
    limit: int = 20,
) -> dict[str, Any]:
    """Top traffic sources (source / medium) with sessions, active users and conversions."""
    return run_report(
        property_id=property_id,
        dimensions=["sessionSource", "sessionMedium"],
        metrics=["sessions", "activeUsers", "conversions"],
        date_start=date_start,
        date_end=date_end,
        limit=limit,
        order_by_metric="sessions",
    )


def conversions_summary(
    property_id: str,
    date_start: str = "7daysAgo",
    date_end: str = "today",
) -> dict[str, Any]:
    """Conversions and total users per event name: a summary of the active key events."""
    return run_report(
        property_id=property_id,
        dimensions=["eventName"],
        metrics=["conversions", "totalUsers"],
        date_start=date_start,
        date_end=date_end,
        limit=25,
        order_by_metric="conversions",
    )


def web_vitals_summary(
    property_id: str,
    date_start: str = "7daysAgo",
    date_end: str = "today",
) -> dict[str, Any]:
    """Core Web Vitals reported by your own site as GA4 events.

    Requires the site to send web-vitals events with the parameters `web_vital_metric` and
    `web_vital_rating`, both registered as event-scoped custom dimensions.
    For Google's field data use psi_field_data_only instead.
    """
    return run_report(
        property_id=property_id,
        dimensions=["customEvent:web_vital_metric", "customEvent:web_vital_rating"],
        metrics=["eventCount"],
        date_start=date_start,
        date_end=date_end,
        limit=50,
        order_by_metric="eventCount",
    )


def audit_portfolio(
    property_ids: list[str],
    date_start: str = "7daysAgo",
    date_end: str = "today",
) -> dict[str, Any]:
    """Summary metrics for several GA4 properties in one call.

    Returns sessions, active users, conversions, bounce rate and average session duration per
    property, plus the properties that failed and why.

    Args:
        property_ids: e.g. ['123456789', '987654321'].
    """
    ok: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    empty = {
        "sessions": 0,
        "activeUsers": 0,
        "conversions": 0,
        "bounceRate": 0.0,
        "averageSessionDuration": 0.0,
    }
    for pid in property_ids:
        try:
            report = run_report(
                property_id=pid,
                metrics=list(empty),
                date_start=date_start,
                date_end=date_end,
                limit=1,
            )
            rows = report.get("rows", [])
            ok.append({"property_id": pid, "metrics": rows[0] if rows else dict(empty)})
        except Exception as exc:
            failed.append({"property_id": pid, "error": str(exc)})
    return {
        "portfolio_count": len(property_ids),
        "date_range": {"start": date_start, "end": date_end},
        "successful_audits": ok,
        "failed_audits": failed,
    }


TOOLS = (
    run_report,
    run_realtime_report,
    top_pages,
    events_summary,
    traffic_sources,
    conversions_summary,
    web_vitals_summary,
    audit_portfolio,
)


def register(mcp: FastMCP, *, writes: bool) -> None:
    for fn in TOOLS:
        mcp.add_tool(fn, annotations=READ)
