"""DataForSEO keyword research tools (Labs API + Keywords Data API).

Exact search volumes, including long-tail queries that Google Ads only reports in buckets.
Credentials come from DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD and are never logged or echoed.
"""

from __future__ import annotations

import os
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

from .annotations import READ

DATAFORSEO_BASE = "https://api.dataforseo.com"
TIMEOUT = 30


def _auth() -> tuple[str, str]:
    login = os.environ.get("DATAFORSEO_LOGIN")
    password = os.environ.get("DATAFORSEO_PASSWORD")
    if not login or not password:
        raise RuntimeError("DATAFORSEO_LOGIN/DATAFORSEO_PASSWORD are not set")
    return (login, password)


def _post(path: str, payload: list[dict[str, Any]]) -> dict[str, Any]:
    """Authenticated POST. Raises with the API's own status message (20000 means OK)."""
    resp = requests.post(f"{DATAFORSEO_BASE}{path}", json=payload, auth=_auth(), timeout=TIMEOUT)
    if not resp.ok:
        raise RuntimeError(f"DataForSEO HTTP {resp.status_code}: {resp.reason}")
    data = resp.json()

    if data.get("status_code") != 20000:
        raise RuntimeError(
            f"DataForSEO error {data.get('status_code')}: {data.get('status_message')}"
        )
    tasks = data.get("tasks") or []
    if not tasks:
        raise RuntimeError("DataForSEO returned no tasks")
    task = tasks[0]
    if task.get("status_code") != 20000:
        raise RuntimeError(
            f"DataForSEO task error {task.get('status_code')}: {task.get('status_message')}"
        )
    return task


def kw_ideas(
    keywords: list[str],
    location_name: str = "Mexico",
    language_code: str = "es",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Discover long-tail keyword ideas related to one or more seed keywords (DataForSEO Labs).

    Ideas are related to the seeds but do not necessarily contain them. Paid API: each call
    spends DataForSEO credit.

    Args:
        keywords: seed keywords, e.g. ['coffee shop', 'espresso machine'].
        location_name: DataForSEO location name (default 'Mexico').
        language_code: ISO language code (default 'es').
        limit: maximum results (default 50, API maximum 1000).

    Returns keyword, search_volume, competition, competition_level and cpc per idea.
    """
    payload = [
        {
            "keywords": keywords,
            "location_name": location_name,
            "language_code": language_code,
            "limit": limit,
        }
    ]
    task = _post("/v3/dataforseo_labs/google/keyword_ideas/live", payload)
    results = task.get("result") or []
    if not results or not results[0]:
        return []
    out = []
    for item in results[0].get("items") or []:
        # Volume, competition and CPC live under keyword_info, not at the item top level.
        info = item.get("keyword_info") or {}
        out.append(
            {
                "keyword": item.get("keyword"),
                "search_volume": info.get("search_volume"),
                "competition": info.get("competition"),
                "competition_level": info.get("competition_level"),
                "cpc": info.get("cpc"),
            }
        )
    return out


def kw_volume(
    keywords: list[str],
    location_name: str = "Mexico",
    language_code: str = "es",
) -> list[dict[str, Any]]:
    """Exact monthly search volume and CPC for queries you already know (DataForSEO).

    Typical use: enrich the queries returned by sc_top_queries. Does not discover new
    keywords. Paid API.

    Args:
        keywords: exact queries (max 1000, 80 characters each).
        location_name: DataForSEO location name (default 'Mexico').
        language_code: ISO language code (default 'es').

    Returns keyword, search_volume, cpc, competition and monthly_searches per query.
    """
    payload = [
        {
            "keywords": keywords,
            "location_name": location_name,
            "language_code": language_code,
        }
    ]
    task = _post("/v3/keywords_data/google_ads/search_volume/live", payload)
    # Unlike keyword_ideas, `result` is already the list of items here.
    out = []
    for r in task.get("result") or []:
        if not r:
            continue
        out.append(
            {
                "keyword": r.get("keyword"),
                "search_volume": r.get("search_volume"),
                "cpc": r.get("cpc"),
                "competition": r.get("competition"),
                "monthly_searches": r.get("monthly_searches"),
            }
        )
    return out


def register(mcp: FastMCP, *, writes: bool) -> None:
    for fn in (kw_ideas, kw_volume):
        mcp.add_tool(fn, annotations=READ)
