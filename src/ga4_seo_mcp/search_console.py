"""Search Console tools: queries, pages, sitemaps and domain verification."""

from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

from .annotations import ENSURE, READ
from .auth import credentials
from .scopes import SITEVERIFICATION, WEBMASTERS, WEBMASTERS_READONLY


def _sc_client(write: bool = False):
    creds = credentials(WEBMASTERS if write else WEBMASTERS_READONLY)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def _siteverification_client():
    creds = credentials(SITEVERIFICATION)
    return build("siteVerification", "v1", credentials=creds, cache_discovery=False)


def _rows(resp: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [
        {
            key: r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 2),
        }
        for r in resp.get("rows", [])
    ]


def dns_txt_token(domain: str) -> str | None:
    """The TXT value that proves ownership of a domain property (asking for it changes nothing)."""
    body = {"site": {"identifier": domain, "type": "INET_DOMAIN"}, "verificationMethod": "DNS_TXT"}
    return _siteverification_client().webResource().getToken(body=body).execute().get("token")


def sc_list_sites() -> list[dict[str, Any]]:
    """List the Search Console sites you can access.

    Each entry has `siteUrl` ('sc-domain:example.com' for domain properties or a URL prefix
    like 'https://example.com/') and `permissionLevel` ('siteOwner', 'siteFullUser',
    'siteRestrictedUser' or 'siteUnverifiedUser').
    """
    return _sc_client().sites().list().execute().get("siteEntry", [])


def sc_top_queries(
    site_url: str,
    date_start: str,
    date_end: str,
    limit: int = 25,
    country: str | None = None,
) -> dict[str, Any]:
    """Top search queries with clicks, impressions, CTR (%) and average position.

    Args:
        site_url: 'sc-domain:example.com' or 'https://example.com/', exactly as in sc_list_sites.
        date_start: 'YYYY-MM-DD'.
        date_end: 'YYYY-MM-DD'. Search Console data lags 2-3 days.
        limit: rows to return (max 25000).
        country: optional ISO 3166-1 alpha-3 code to filter by, e.g. 'mex' or 'usa'.
    """
    body: dict[str, Any] = {
        "startDate": date_start,
        "endDate": date_end,
        "dimensions": ["query"],
        "rowLimit": limit,
    }
    if country:
        body["dimensionFilterGroups"] = [
            {"filters": [{"dimension": "country", "operator": "equals", "expression": country}]}
        ]
    resp = _sc_client().searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = _rows(resp, "query")
    return {
        "site_url": site_url,
        "date_range": {"start": date_start, "end": date_end},
        "row_count": len(rows),
        "rows": rows,
    }


def sc_page_performance(
    site_url: str,
    date_start: str,
    date_end: str,
    limit: int = 25,
) -> dict[str, Any]:
    """Top pages in Google Search by clicks, with impressions, CTR (%) and average position."""
    body = {
        "startDate": date_start,
        "endDate": date_end,
        "dimensions": ["page"],
        "rowLimit": limit,
    }
    resp = _sc_client().searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = _rows(resp, "page")
    return {
        "site_url": site_url,
        "date_range": {"start": date_start, "end": date_end},
        "row_count": len(rows),
        "rows": rows,
    }


def sc_query_breakdown_by_page(
    site_url: str,
    page_url: str,
    date_start: str,
    date_end: str,
    limit: int = 25,
) -> dict[str, Any]:
    """Which search queries bring traffic to one specific page.

    Useful to decide which keywords to strengthen in that page's content.
    """
    body = {
        "startDate": date_start,
        "endDate": date_end,
        "dimensions": ["query"],
        "rowLimit": limit,
        "dimensionFilterGroups": [
            {"filters": [{"dimension": "page", "operator": "equals", "expression": page_url}]}
        ],
    }
    resp = _sc_client().searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = _rows(resp, "query")
    return {"page": page_url, "row_count": len(rows), "rows": rows}


def sc_list_sitemaps(site_url: str) -> list[dict[str, Any]]:
    """List the sitemaps submitted for a Search Console site, with errors and warnings."""
    resp = _sc_client().sitemaps().list(siteUrl=site_url).execute()
    return [
        {
            "path": s.get("path"),
            "last_submitted": s.get("lastSubmitted"),
            "last_downloaded": s.get("lastDownloaded"),
            "is_pending": s.get("isPending"),
            "is_sitemaps_index": s.get("isSitemapsIndex"),
            "type": s.get("type"),
            "errors": s.get("errors", 0),
            "warnings": s.get("warnings", 0),
        }
        for s in resp.get("sitemap", [])
    ]


def sc_submit_sitemap(site_url: str, sitemap_url: str) -> dict[str, str]:
    """Submit (or resubmit) a sitemap to Search Console.

    Args:
        site_url: 'sc-domain:example.com' or 'https://example.com/'.
        sitemap_url: absolute URL of the sitemap, e.g. 'https://example.com/sitemap.xml'.
    """
    _sc_client(write=True).sitemaps().submit(siteUrl=site_url, feedpath=sitemap_url).execute()
    return {"submitted": "true", "sitemap": sitemap_url}


def sc_add_site_and_get_verify_token(domain: str) -> dict[str, Any]:
    """Add a domain property to Search Console and return the DNS TXT record that verifies it.

    Domain properties ('sc-domain:') cover every subdomain and both http and https, but Google
    only verifies them over DNS (TXT or CNAME). Add the returned token as a TXT record on the
    zone root (name '@'), wait for it to propagate, then call sc_verify_site_dns.
    Safe to call again: an existing site is reported as 'already_exists'.

    Args:
        domain: bare domain without scheme, e.g. 'example.com'.

    Returns `add` (created / already_exists), `txt_token` and `next_steps`.
    """
    site_url = f"sc-domain:{domain}"
    out: dict[str, Any] = {"domain": domain, "site_url": site_url}
    try:
        _sc_client(write=True).sites().add(siteUrl=site_url).execute()
        out["add"] = "created"
    except HttpError as e:
        if e.status_code in (400, 409):
            out["add"] = "already_exists"
        else:
            out["add"] = f"error_{e.status_code}"
            return out

    try:
        token = dns_txt_token(domain)
        out["txt_token"] = token
        out["next_steps"] = (
            f"Add a TXT record to the DNS of {domain}: name='@' value='{token}'. "
            f"Once it resolves (dig TXT {domain} +short), call sc_verify_site_dns('{domain}')."
        )
    except HttpError as e:
        out["txt_token"] = None
        out["error"] = f"{e.status_code}: {str(e._get_reason())[:120]}"
    return out


def sc_verify_site_dns(domain: str) -> dict[str, Any]:
    """Verify ownership of a domain property whose DNS TXT record is already published.

    Run sc_add_site_and_get_verify_token first and wait until `dig TXT <domain> +short`
    shows the token.

    Args:
        domain: bare domain without scheme, e.g. 'example.com'.
    """
    try:
        r = (
            _siteverification_client()
            .webResource()
            .insert(
                verificationMethod="DNS_TXT",
                body={"site": {"identifier": domain, "type": "INET_DOMAIN"}},
            )
            .execute()
        )
        return {"domain": domain, "verified": True, "owners": r.get("owners", [])}
    except HttpError as e:
        return {
            "domain": domain,
            "verified": False,
            "error_code": e.status_code,
            "error": str(e._get_reason())[:200],
            "hint": (
                "If the error mentions the token, the TXT record has not propagated yet. "
                "Wait 30-60 seconds and retry; check with: dig TXT <domain> +short"
            ),
        }


READ_TOOLS = (
    sc_list_sites,
    sc_top_queries,
    sc_page_performance,
    sc_query_breakdown_by_page,
    sc_list_sitemaps,
)
WRITE_TOOLS = (sc_submit_sitemap, sc_add_site_and_get_verify_token, sc_verify_site_dns)


def register(mcp: FastMCP, *, writes: bool) -> None:
    for fn in READ_TOOLS:
        mcp.add_tool(fn, annotations=READ)
    if writes:
        for fn in WRITE_TOOLS:
            mcp.add_tool(fn, annotations=ENSURE)
