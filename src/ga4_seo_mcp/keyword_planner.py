"""Google Ads Keyword Planner tools (needs the `ads` extra and a developer token).

Complements DataForSEO rather than replacing it: Google Ads is free and gives Google's own
competition and top-of-page bid data, but for accounts without active spend it reports
`avg_monthly_searches` in buckets (10, 30, 50, 70, 170, 210, ...), like the Keyword Planner UI.
DataForSEO gives exact volumes for long-tail queries.

Auth: Application Default Credentials with the `adwords` scope, plus a developer token from
GOOGLE_ADS_DEVELOPER_TOKEN or ~/.config/ga4-seo-mcp/dev-token (must be chmod 600).
GOOGLE_ADS_LOGIN_CUSTOMER_ID is only needed when operating through a manager (MCC) account.
"""

from __future__ import annotations

import itertools
import os
import stat
from typing import Any

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from mcp.server.fastmcp import FastMCP

from .annotations import READ

DEFAULT_LOCATION_ID_MX = "2484"
DEFAULT_LANGUAGE_ID_ES = "1003"

# page_size controls each page, not the total, so `limit` is also enforced client-side.
_MAX_PAGE_SIZE = 1000

TOKEN_FILE = os.path.expanduser("~/.config/ga4-seo-mcp/dev-token")


def _read_token_file() -> str | None:
    """Developer token from TOKEN_FILE, refusing files other users can read."""
    try:
        mode = os.stat(TOKEN_FILE).st_mode
    except OSError:
        return None
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise RuntimeError(f"{TOKEN_FILE} is readable by other users; run: chmod 600 {TOKEN_FILE}")
    with open(TOKEN_FILE, encoding="utf-8") as fh:
        return fh.read().strip() or None


def _client() -> GoogleAdsClient:
    """GoogleAdsClient over ADC. Fails before any network call if the token is missing."""
    developer_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN") or _read_token_file()
    if not developer_token:
        raise RuntimeError(
            "Missing Google Ads developer token: set GOOGLE_ADS_DEVELOPER_TOKEN or write it to "
            f"{TOKEN_FILE} (chmod 600). See "
            "https://developers.google.com/google-ads/api/docs/get-started/dev-token"
        )
    config: dict[str, Any] = {
        "developer_token": developer_token,
        "use_proto_plus": True,
        "use_application_default_credentials": True,
    }
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
    if login_customer_id:
        config["login_customer_id"] = login_customer_id.replace("-", "").strip()
    return GoogleAdsClient.load_from_dict(config)


def _run(fn: Any, *, request: Any) -> Any:
    """Call an RPC, turning GoogleAdsException into a readable RuntimeError."""
    try:
        return fn(request=request)
    except GoogleAdsException as ex:
        details = "; ".join(f"{err.message} ({err.error_code})" for err in ex.failure.errors)
        raise RuntimeError(f"Google Ads API error: {details or ex}") from ex


def _historical_metrics_to_dict(text: str, metrics: Any | None) -> dict[str, Any]:
    """Flatten KeywordPlanHistoricalMetrics; bids come in micros and are converted to units."""
    if metrics is None:
        return {
            "keyword": text,
            "avg_monthly_searches": None,
            "competition": None,
            "competition_index": None,
            "low_top_of_page_bid": None,
            "high_top_of_page_bid": None,
        }
    return {
        "keyword": text,
        "avg_monthly_searches": metrics.avg_monthly_searches,
        "competition": metrics.competition.name,
        "competition_index": metrics.competition_index,
        "low_top_of_page_bid": metrics.low_top_of_page_bid_micros / 1_000_000,
        "high_top_of_page_bid": metrics.high_top_of_page_bid_micros / 1_000_000,
    }


def kw_ideas_gads(
    customer_id: str,
    keywords: list[str],
    location_id: str = DEFAULT_LOCATION_ID_MX,
    language_id: str = DEFAULT_LANGUAGE_ID_ES,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Discover keyword ideas from seed keywords with Google Ads Keyword Planner.

    Free, but without active ad spend the volume comes in buckets; use kw_ideas (DataForSEO)
    when you need exact long-tail volumes.

    Args:
        customer_id: Google Ads customer ID (10 digits, dashes allowed). The account does not
            need campaigns or spend.
        keywords: seed keywords, e.g. ['coffee shop', 'espresso machine'].
        location_id: geo target constant ID (default '2484', Mexico; '2840' is United States).
        language_id: language constant ID (default '1003', Spanish; '1000' is English).
        limit: maximum results (default 50).

    Returns keyword, avg_monthly_searches, competition, competition_index and the low/high
    top-of-page bids in the account currency.
    """
    client = _client()
    google_ads_service = client.get_service("GoogleAdsService")
    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id.replace("-", "").strip()
    request.language = google_ads_service.language_constant_path(language_id)
    request.geo_target_constants.append(google_ads_service.geo_target_constant_path(location_id))
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    request.keyword_seed.keywords.extend(keywords)
    request.page_size = min(limit, _MAX_PAGE_SIZE)

    response = _run(keyword_plan_idea_service.generate_keyword_ideas, request=request)
    return [
        _historical_metrics_to_dict(idea.text, idea.keyword_idea_metrics)
        for idea in itertools.islice(response, limit)
    ]


def kw_volume_gads(
    customer_id: str,
    keywords: list[str],
    location_id: str = DEFAULT_LOCATION_ID_MX,
    language_id: str = DEFAULT_LANGUAGE_ID_ES,
) -> list[dict[str, Any]]:
    """Historical metrics from Google Ads Keyword Planner for queries you already know.

    Same caveat as kw_ideas_gads: bucketed volume without active spend; use kw_volume
    (DataForSEO) for exact numbers.

    Args:
        customer_id: Google Ads customer ID (10 digits, dashes allowed).
        keywords: exact queries.
        location_id: geo target constant ID (default '2484', Mexico).
        language_id: language constant ID (default '1003', Spanish).
    """
    client = _client()
    google_ads_service = client.get_service("GoogleAdsService")
    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordHistoricalMetricsRequest")
    request.customer_id = customer_id.replace("-", "").strip()
    request.keywords.extend(keywords)
    request.language = google_ads_service.language_constant_path(language_id)
    request.geo_target_constants.append(google_ads_service.geo_target_constant_path(location_id))
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

    response = _run(keyword_plan_idea_service.generate_keyword_historical_metrics, request=request)
    return [
        _historical_metrics_to_dict(result.text, result.keyword_metrics)
        for result in response.results
    ]


def register(mcp: FastMCP, *, writes: bool) -> None:
    for fn in (kw_ideas_gads, kw_volume_gads):
        mcp.add_tool(fn, annotations=READ)
