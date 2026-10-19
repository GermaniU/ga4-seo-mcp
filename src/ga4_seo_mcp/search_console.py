"""
Tools del MCP para Google Search Console API.

Cubre: queries SEO, page performance, indexing status, sitemaps.
Requiere scope ADC: webmasters.readonly (o webmasters)
API: searchconsole.googleapis.com
"""

from __future__ import annotations

from typing import Any

import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .mcp_app import mcp


def _sc_client(write: bool = False):
    """Cliente Search Console v1 vía discovery, autenticado con ADC.

    Args:
        write: si True, pide scope `webmasters` (no readonly) para add/delete sites,
               submit sitemaps, etc. Default readonly (más seguro).
    """
    scope = (
        "https://www.googleapis.com/auth/webmasters"
        if write
        else "https://www.googleapis.com/auth/webmasters.readonly"
    )
    credentials, _ = google.auth.default(scopes=[scope])
    return build("searchconsole", "v1", credentials=credentials, cache_discovery=False)


def _siteverification_client():
    """Cliente Site Verification API — para auto-verify via GA."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/siteverification"]
    )
    return build("siteVerification", "v1", credentials=credentials, cache_discovery=False)


@mcp.tool()
def sc_list_sites() -> list[dict[str, Any]]:
    """
    Lista sites verificados en Search Console accesibles al usuario.

    Devuelve cada uno con su `siteUrl` (formato 'sc-domain:dominio.com' o URL)
    y `permissionLevel` ('siteOwner', 'siteFullUser', 'siteRestrictedUser').
    """
    svc = _sc_client()
    resp = svc.sites().list().execute()
    return resp.get("siteEntry", [])


@mcp.tool()
def sc_top_queries(
    site_url: str,
    date_start: str,
    date_end: str,
    limit: int = 25,
    country: str | None = None,
) -> dict[str, Any]:
    """
    Top queries de búsqueda con clicks, impressions, CTR, position media.

    Args:
        site_url: 'https://example.com/' o 'sc-domain:example.com'
        date_start: 'YYYY-MM-DD'
        date_end: 'YYYY-MM-DD'
        limit: filas (max 25000)
        country: opcional, código ISO-3 (ej. 'mex', 'usa') para filtrar.
    """
    svc = _sc_client()
    body: dict[str, Any] = {
        "startDate": date_start,
        "endDate": date_end,
        "dimensions": ["query"],
        "rowLimit": limit,
        "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
    }
    if country:
        body["dimensionFilterGroups"] = [
            {"filters": [{"dimension": "country", "operator": "equals", "expression": country}]}
        ]
    resp = svc.searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = [
        {
            "query": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 2),
        }
        for r in resp.get("rows", [])
    ]
    return {
        "site_url": site_url,
        "date_range": {"start": date_start, "end": date_end},
        "row_count": len(rows),
        "rows": rows,
    }


@mcp.tool()
def sc_page_performance(
    site_url: str,
    date_start: str,
    date_end: str,
    limit: int = 25,
) -> dict[str, Any]:
    """Top páginas SEO ordenadas por clicks. Métricas: clicks, impressions, CTR, position."""
    svc = _sc_client()
    body = {
        "startDate": date_start,
        "endDate": date_end,
        "dimensions": ["page"],
        "rowLimit": limit,
        "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
    }
    resp = svc.searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = [
        {
            "page": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 2),
        }
        for r in resp.get("rows", [])
    ]
    return {
        "site_url": site_url,
        "date_range": {"start": date_start, "end": date_end},
        "row_count": len(rows),
        "rows": rows,
    }


@mcp.tool()
def sc_query_breakdown_by_page(
    site_url: str,
    page_url: str,
    date_start: str,
    date_end: str,
    limit: int = 25,
) -> dict[str, Any]:
    """
    Para una URL específica, qué queries la traen — útil para optimizar
    contenido (saber qué keywords trabajar más en una página dada).
    """
    svc = _sc_client()
    body = {
        "startDate": date_start,
        "endDate": date_end,
        "dimensions": ["query"],
        "rowLimit": limit,
        "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
        "dimensionFilterGroups": [
            {"filters": [{"dimension": "page", "operator": "equals", "expression": page_url}]}
        ],
    }
    resp = svc.searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = [
        {
            "query": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 2),
        }
        for r in resp.get("rows", [])
    ]
    return {"page": page_url, "row_count": len(rows), "rows": rows}


@mcp.tool()
def sc_list_sitemaps(site_url: str) -> list[dict[str, Any]]:
    """Lista sitemaps registrados en Search Console para el site."""
    svc = _sc_client()
    resp = svc.sitemaps().list(siteUrl=site_url).execute()
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


@mcp.tool()
def sc_submit_sitemap(site_url: str, sitemap_url: str) -> dict[str, str]:
    """
    Envía/notifica un sitemap a Google Search Console.

    Args:
        site_url: 'https://example.com/' o 'sc-domain:example.com'
        sitemap_url: URL absoluta del sitemap (ej. 'https://example.com/sitemap.xml')

    Necesita scope `webmasters` (no readonly).
    """
    svc = _sc_client(write=True)
    svc.sitemaps().submit(siteUrl=site_url, feedpath=sitemap_url).execute()
    return {"submitted": "true", "sitemap": sitemap_url}


@mcp.tool()
def sc_add_site_and_get_verify_token(domain: str) -> dict[str, Any]:
    """
    Registra un site (domain-property) en Search Console y devuelve el token
    DNS_TXT necesario para verificar ownership.

    **Limitación importante**: para domain-properties (`sc-domain:`), Google
    Site Verification API **solo acepta `DNS_TXT` o `DNS_CNAME`** como
    método. ANALYTICS y FILE/META solo funcionan para URL-prefix properties
    (`https://dominio.com/`). Como domain-property es mejor (cubre www +
    sin-www + http + https), usamos ese tipo y aceptamos que la verificación
    requiere agregar un TXT record en DNS.

    El TXT record debe estar en el zone root (name = `@`), tipo TXT,
    contenido = el token devuelto (incluyendo el prefijo `google-site-
    verification=`). TTL 120s es suficiente.

    Una vez agregado el TXT y propagado (~30s), llamar `sc_verify_site_dns`
    para completar.

    Args:
        domain: dominio sin scheme (ej. 'example.com').

    Returns dict con `add` (status), `txt_token` (el valor a poner como
    TXT record), `next_steps` (qué hacer manualmente o vía CF API).
    """
    site_url = f"sc-domain:{domain}"
    out: dict[str, Any] = {"domain": domain, "site_url": site_url}

    # 1) Add site (idempotente)
    sc = _sc_client(write=True)
    try:
        sc.sites().add(siteUrl=site_url).execute()
        out["add"] = "created"
    except HttpError as e:
        if e.status_code in (409, 400):
            out["add"] = "already_exists"
        else:
            out["add"] = f"error_{e.status_code}"
            return out

    # 2) Obtener token DNS_TXT
    sv = _siteverification_client()
    try:
        tok = sv.webResource().getToken(body={
            "site": {"identifier": domain, "type": "INET_DOMAIN"},
            "verificationMethod": "DNS_TXT",
        }).execute()
        out["txt_token"] = tok.get("token")
        out["next_steps"] = (
            f"Agregar TXT record en DNS de {domain}: name='@' content='{tok.get('token')}' ttl=120. "
            f"Luego llamar sc_verify_site_dns('{domain}')."
        )
    except HttpError as e:
        out["txt_token"] = None
        out["error"] = f"{e.status_code}: {str(e._get_reason())[:120]}"

    return out


@mcp.tool()
def sc_verify_site_dns(domain: str) -> dict[str, Any]:
    """
    Completa la verificación DNS_TXT de un domain-property previamente
    registrado con `sc_add_site_and_get_verify_token`.

    Pre-requisito: el TXT record ya está propagado en DNS público del
    dominio. Validable con `dig TXT <domain> +short`.

    Args:
        domain: dominio sin scheme (ej. 'example.com').

    Returns dict con resultado de la verificación.
    """
    sv = _siteverification_client()
    try:
        r = sv.webResource().insert(
            verificationMethod="DNS_TXT",
            body={"site": {"identifier": domain, "type": "INET_DOMAIN"}},
        ).execute()
        return {"domain": domain, "verified": True, "owners": r.get("owners", [])}
    except HttpError as e:
        err = str(e._get_reason())
        return {
            "domain": domain,
            "verified": False,
            "error_code": e.status_code,
            "error": err[:200],
            "hint": (
                "Si dice 'tokenVerifyError': el TXT no se propagó. Esperar 30-60s y reintentar. "
                "Validar con: dig TXT <domain> +short"
            ),
        }
