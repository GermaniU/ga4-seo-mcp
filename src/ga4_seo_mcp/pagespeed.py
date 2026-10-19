"""PageSpeed Insights tools: Lighthouse lab scores and CrUX field data."""

from __future__ import annotations

import os
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

from .annotations import READ

PSI_BASE = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
TIMEOUT = 120  # a mobile run with every category often takes 30-90 s

_LAB_AUDITS = [
    ("LCP", "largest-contentful-paint"),
    ("FCP", "first-contentful-paint"),
    ("CLS", "cumulative-layout-shift"),
    ("TBT", "total-blocking-time"),
    ("SI", "speed-index"),
    ("INP", "interaction-to-next-paint"),
    ("TTFB", "server-response-time"),
]
_CRUX_METRICS = [
    "LARGEST_CONTENTFUL_PAINT_MS",
    "INTERACTION_TO_NEXT_PAINT",
    "CUMULATIVE_LAYOUT_SHIFT_SCORE",
    "FIRST_CONTENTFUL_PAINT_MS",
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE",
]


def _fetch(url: str, strategy: str, categories: list[str]) -> dict[str, Any]:
    params: list[tuple[str, str]] = [("url", url), ("strategy", strategy)]
    params += [("category", c) for c in categories]
    key = os.environ.get("PAGESPEED_API_KEY")
    if key:
        params.append(("key", key))
    resp = requests.get(PSI_BASE, params=params, timeout=TIMEOUT)
    if not resp.ok:
        # Build the message from the API body: requests' own error embeds the URL, API key included.
        try:
            message = resp.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            message = resp.reason
        raise RuntimeError(f"PageSpeed Insights error {resp.status_code}: {message}")
    return resp.json()


def _crux_summary(le: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"overall_category": le.get("overall_category")}
    metrics = le.get("metrics", {})
    for m in _CRUX_METRICS:
        if m in metrics:
            out[m] = {
                "percentile": metrics[m].get("percentile"),
                "category": metrics[m].get("category"),
            }
    return out


def psi_audit(
    url: str,
    strategy: str = "mobile",
    categories: list[str] | None = None,
) -> dict[str, Any]:
    """Run a PageSpeed Insights audit (Lighthouse lab test + CrUX field data) on a public URL.

    Takes 30-90 seconds. Without PAGESPEED_API_KEY the anonymous quota is small and Google
    may answer 429; set the key for regular use.

    Args:
        url: absolute public URL, e.g. 'https://example.com/'.
        strategy: 'mobile' (default) or 'desktop'.
        categories: subset of ['performance', 'accessibility', 'best-practices', 'seo'].
            Default: all four.

    Returns 0-100 category scores, lab Core Web Vitals (LCP, FCP, CLS, TBT, SI, TTFB) and,
    when Chrome has enough real-user traffic, CrUX p75 field data for the URL and its origin.
    """
    cats = categories or ["performance", "accessibility", "best-practices", "seo"]
    data = _fetch(url, strategy, cats)
    lh = data.get("lighthouseResult", {})
    categories_result = lh.get("categories", {})
    audits = lh.get("audits", {})

    scores = {
        c: int((categories_result[c].get("score") or 0) * 100)
        for c in cats
        if c in categories_result
    }
    web_vitals_lab = {}
    for metric_id, audit_key in _LAB_AUDITS:
        a = audits.get(audit_key)
        if a:
            web_vitals_lab[metric_id] = {
                "value": a.get("numericValue"),
                "display_value": a.get("displayValue"),
                "score": int(a["score"] * 100) if a.get("score") is not None else None,
            }

    crux_url = data.get("loadingExperience")
    crux_origin = data.get("originLoadingExperience")
    return {
        "url": data.get("id"),
        "strategy": strategy,
        "fetch_time": lh.get("fetchTime"),
        "scores": scores,
        "web_vitals_lab": web_vitals_lab,
        "crux_url": _crux_summary(crux_url) if crux_url else None,
        "crux_origin": _crux_summary(crux_origin) if crux_origin else None,
        "lighthouse_version": lh.get("lighthouseVersion"),
    }


def psi_field_data_only(url: str, strategy: str = "mobile") -> dict[str, Any]:
    """Only the CrUX field data (real Chrome users, p75 over 28 days) for a URL and its origin.

    PageSpeed Insights still runs a performance-only Lighthouse pass, so expect 15-40 seconds.
    `overall_category` is FAST, AVERAGE or SLOW; it is null when the page has too little traffic.
    """
    result = psi_audit(url=url, strategy=strategy, categories=["performance"])
    return {
        "url": result["url"],
        "strategy": strategy,
        "crux_url": result["crux_url"],
        "crux_origin": result["crux_origin"],
    }


def register(mcp: FastMCP, *, writes: bool) -> None:
    for fn in (psi_audit, psi_field_data_only):
        mcp.add_tool(fn, annotations=READ)
