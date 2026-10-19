"""
Tools del MCP para DataForSEO — keyword research (Labs API + Keywords Data API).

Cubre: descubrimiento de keywords long-tail a partir de seeds (`kw_ideas`) y
enriquecimiento de volumen/CPC para queries ya conocidas (`kw_volume`), ej. las
que trae `sc_top_queries` de Search Console.

Auth: HTTP Basic Auth con credenciales de cuenta DataForSEO, vía env vars
`DATAFORSEO_LOGIN` y `DATAFORSEO_PASSWORD`. Sin Application Default Credentials.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from .mcp_app import mcp


DATAFORSEO_BASE = "https://api.dataforseo.com"
TIMEOUT = 30


def _auth() -> tuple[str, str]:
    login = os.environ.get("DATAFORSEO_LOGIN")
    password = os.environ.get("DATAFORSEO_PASSWORD")
    if not login or not password:
        raise RuntimeError(
            "Faltan DATAFORSEO_LOGIN/DATAFORSEO_PASSWORD en el entorno"
        )
    return (login, password)


def _post(path: str, payload: list[dict[str, Any]]) -> dict[str, Any]:
    """POST autenticado a DataForSEO. Valida `status_code` top-level y de la
    primera task (20000 = OK); si alguno falla, levanta RuntimeError con el
    `status_message` que devuelve la API en vez de un stacktrace opaco.
    """
    resp = requests.post(
        f"{DATAFORSEO_BASE}{path}",
        json=payload,
        auth=_auth(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("status_code") != 20000:
        raise RuntimeError(
            f"DataForSEO error {data.get('status_code')}: {data.get('status_message')}"
        )

    tasks = data.get("tasks") or []
    if not tasks:
        raise RuntimeError("DataForSEO no devolvió tasks en la respuesta")

    task = tasks[0]
    if task.get("status_code") != 20000:
        raise RuntimeError(
            f"DataForSEO task error {task.get('status_code')}: {task.get('status_message')}"
        )

    return task


@mcp.tool()
def kw_ideas(
    keywords: list[str],
    location_name: str = "Mexico",
    language_code: str = "es",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Descubrimiento de keywords long-tail a partir de una o varias seeds.

    Usa DataForSEO Labs `keyword_ideas` (Live) — devuelve keywords
    relacionadas a las seeds (no necesariamente las contienen), con volumen,
    competencia y CPC. Útil para encontrar long-tail que todavía no rankea.

    Args:
        keywords: seeds de búsqueda (ej. ['restaurante cdmx', 'comida a domicilio']).
        location_name: nombre de ubicación DataForSEO (default 'Mexico').
        language_code: código de idioma ISO (default 'es').
        limit: máximo de resultados a devolver (default 50, tope API 1000).

    Devuelve lista de dicts normalizados (no el envelope crudo de DataForSEO):
    keyword, search_volume, competition, competition_level, cpc.
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

    items = results[0].get("items") or []
    out = []
    for item in items:
        # search_volume/competition/cpc viven anidados en `keyword_info`, NO
        # a nivel top del item — confirmado en la doc oficial de DataForSEO.
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


@mcp.tool()
def kw_volume(
    keywords: list[str],
    location_name: str = "Mexico",
    language_code: str = "es",
) -> list[dict[str, Any]]:
    """
    Enriquece con volumen/CPC un set de queries ya conocidas — ej. las que
    trae `sc_top_queries` de Search Console.

    Usa DataForSEO Keywords Data `google_ads/search_volume` (Live) — a
    diferencia de `kw_ideas`, no descubre keywords nuevas: solo devuelve
    métricas para exactamente las queries pasadas.

    Args:
        keywords: queries exactas a consultar (max 1000, 80 chars c/u).
        location_name: nombre de ubicación DataForSEO (default 'Mexico').
        language_code: código de idioma ISO (default 'es').

    Devuelve lista de dicts: keyword, search_volume, cpc, competition,
    monthly_searches.
    """
    payload = [
        {
            "keywords": keywords,
            "location_name": location_name,
            "language_code": language_code,
        }
    ]
    task = _post("/v3/keywords_data/google_ads/search_volume/live", payload)

    # A diferencia de keyword_ideas, acá `result` YA es la lista de items
    # (sin envelope `items[]` intermedio) — confirmado en la doc oficial.
    results = task.get("result") or []
    out = []
    for r in results:
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
