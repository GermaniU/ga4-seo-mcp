"""
Tools del MCP para Google PageSpeed Insights API + CrUX (Chrome UX Report).

Cubre: scores Lighthouse, field data CrUX (Core Web Vitals de usuarios reales).
Sin auth: la API es pública pero rate-limited; API key opcional vía env
`PAGESPEED_API_KEY` para evitar throttling.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from .mcp_app import mcp


PSI_BASE = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
TIMEOUT = 120  # PSI tarda 30-90s, sobre todo en mobile + accessibility


def _api_key_param() -> dict[str, str]:
    key = os.environ.get("PAGESPEED_API_KEY")
    return {"key": key} if key else {}


@mcp.tool()
def psi_audit(
    url: str,
    strategy: str = "mobile",
    categories: list[str] | None = None,
) -> dict[str, Any]:
    """
    Audit PageSpeed Insights (Lighthouse + CrUX) sobre una URL pública.

    Args:
        url: URL absoluta a auditar (debe ser pública, sin auth gate).
        strategy: 'mobile' (default) o 'desktop'.
        categories: subset de
            ['performance','accessibility','best-practices','seo','pwa']
            (default todas excepto pwa).

    Devuelve scores 0-100 + Core Web Vitals (LCP/INP/CLS/FCP/TTFB) en
    formato Lighthouse lab + field (CrUX) si la URL tiene datos suficientes.
    """
    cats = categories or ["performance", "accessibility", "best-practices", "seo"]
    params = {
        "url": url,
        "strategy": strategy,
        **_api_key_param(),
    }
    # PSI espera categorías repetidas en query string
    query_str = "&".join([f"{k}={v}" for k, v in params.items()] + [f"category={c}" for c in cats])
    resp = requests.get(f"{PSI_BASE}?{query_str}", timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    # Extraer lo que vale la pena, no el JSON enorme
    lh = data.get("lighthouseResult", {})
    categories_result = lh.get("categories", {})
    audits = lh.get("audits", {})

    scores = {
        c: int((categories_result.get(c, {}).get("score") or 0) * 100)
        for c in cats
        if c in categories_result
    }

    # Core Web Vitals lab
    web_vitals_lab = {}
    for metric_id, audit_key in [
        ("LCP", "largest-contentful-paint"),
        ("FCP", "first-contentful-paint"),
        ("CLS", "cumulative-layout-shift"),
        ("TBT", "total-blocking-time"),
        ("SI", "speed-index"),
        ("INP", "interaction-to-next-paint"),
        ("TTFB", "server-response-time"),
    ]:
        a = audits.get(audit_key, {})
        if a:
            web_vitals_lab[metric_id] = {
                "value": a.get("numericValue"),
                "display_value": a.get("displayValue"),
                "score": int((a.get("score") or 0) * 100) if a.get("score") is not None else None,
            }

    # Field data (CrUX — datos reales de Chrome)
    crux_loading = data.get("loadingExperience", {})
    crux_origin = data.get("originLoadingExperience", {})

    def _crux_summary(le: dict) -> dict:
        out = {"overall_category": le.get("overall_category")}
        metrics = le.get("metrics", {})
        for m in ["LARGEST_CONTENTFUL_PAINT_MS", "INTERACTION_TO_NEXT_PAINT", "CUMULATIVE_LAYOUT_SHIFT_SCORE", "FIRST_CONTENTFUL_PAINT_MS", "EXPERIMENTAL_TIME_TO_FIRST_BYTE"]:
            if m in metrics:
                out[m] = {
                    "percentile": metrics[m].get("percentile"),
                    "category": metrics[m].get("category"),
                }
        return out

    return {
        "url": data.get("id"),
        "strategy": strategy,
        "fetch_time": lh.get("fetchTime"),
        "scores": scores,
        "web_vitals_lab": web_vitals_lab,
        "crux_url": _crux_summary(crux_loading) if crux_loading else None,
        "crux_origin": _crux_summary(crux_origin) if crux_origin else None,
        "lighthouse_version": lh.get("lighthouseVersion"),
    }


@mcp.tool()
def psi_field_data_only(url: str, strategy: str = "mobile") -> dict[str, Any]:
    """
    Solo CrUX field data (Chrome UX real users), saltando Lighthouse lab.
    Rápido (~1-2s). Útil para tendencia de CWV en producción.

    Devuelve `overall_category` ('FAST'/'AVERAGE'/'SLOW') + percentiles 75 para
    LCP, INP, CLS, FCP, TTFB.
    """
    result = psi_audit(url=url, strategy=strategy, categories=["performance"])
    return {
        "url": result["url"],
        "strategy": strategy,
        "crux_url": result.get("crux_url"),
        "crux_origin": result.get("crux_origin"),
    }
