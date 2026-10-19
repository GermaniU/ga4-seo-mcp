"""bootstrap_site_measurement: plan, and optionally apply, the GA4 + Search Console setup."""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from . import admin, search_console
from .annotations import ENSURE, READ

WRITES_REQUIRED = (
    "apply=True needs write access: restart the server with --enable-writes "
    "(or GA4SEO_ENABLE_WRITES=1). Nothing was changed."
)


class CustomDimensionSpec(BaseModel):
    parameter_name: str = Field(description="Event or user parameter, e.g. 'plan_type'.")
    display_name: str = Field(description="Letters, digits, underscores and spaces only.")
    scope: Literal["EVENT", "USER", "ITEM"] = "EVENT"


def _host(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.hostname or "").lower()


def _bare_domain(host: str) -> str:
    return host.removeprefix("www.")


def _find_property(account_id: str, domain: str, display_name: str):
    """(property, web stream) whose stream points at the domain; else a property with the name."""
    properties = admin.list_properties(account_id)
    for prop in properties:
        for stream in admin.list_data_streams(prop["property_id"]):
            web = stream.get("web")
            if web and _bare_domain(_host(web["default_uri"])) == domain:
                return prop, stream
    for prop in properties:
        if prop["display_name"] == display_name:
            return prop, None
    return None, None


def _gsc_status(domain: str) -> dict[str, Any]:
    candidates = {
        f"sc-domain:{domain}",
        f"https://{domain}/",
        f"https://www.{domain}/",
        f"http://{domain}/",
        f"http://www.{domain}/",
    }
    found = [s for s in search_console.sc_list_sites() if s.get("siteUrl") in candidates]
    domain_entry = next((s for s in found if s["siteUrl"] == f"sc-domain:{domain}"), None)
    if domain_entry and domain_entry.get("permissionLevel") != "siteUnverifiedUser":
        action = "exists"
    elif domain_entry:
        action = "verify"
    else:
        action = "create"
    return {
        "step": "search_console_domain_property",
        "action": action,
        "site_url": f"sc-domain:{domain}",
        "existing_sites": [
            {"site_url": s["siteUrl"], "permission_level": s.get("permissionLevel")} for s in found
        ],
    }


def _plan(
    site_url: str,
    account_id: str,
    property_display_name: str,
    key_events: list[str],
    custom_dimensions: list[CustomDimensionSpec],
    gsc: bool,
) -> dict[str, Any]:
    domain = _bare_domain(_host(site_url))
    if not domain:
        raise ValueError(f"site_url has no host: {site_url!r}")
    prop, stream = _find_property(account_id, domain, property_display_name)
    property_id = prop["property_id"] if prop else None

    existing_events: set[str] = set()
    existing_dims: set[str] = set()
    if property_id:
        existing_events = {k["event_name"] for k in admin.list_key_events(property_id)}
        existing_dims = {d["parameter_name"] for d in admin.list_custom_dimensions(property_id)}

    steps: list[dict[str, Any]] = [
        {
            "step": "property",
            "action": "exists" if prop else "create",
            "property_id": property_id,
            "display_name": prop["display_name"] if prop else property_display_name,
        },
        {
            "step": "web_data_stream",
            "action": "exists" if stream else "create",
            "stream_id": stream["stream_id"] if stream else None,
            "measurement_id": stream["web"]["measurement_id"] if stream else None,
            "default_uri": stream["web"]["default_uri"] if stream else f"https://{_host(site_url)}",
        },
    ]
    for name in key_events:
        steps.append(
            {
                "step": "key_event",
                "event_name": name,
                "action": "exists" if name in existing_events else "create",
            }
        )
    for spec in custom_dimensions:
        steps.append(
            {
                "step": "custom_dimension",
                "parameter_name": spec.parameter_name,
                "display_name": spec.display_name,
                "scope": spec.scope,
                "action": "exists" if spec.parameter_name in existing_dims else "create",
            }
        )
    if gsc:
        steps.append(_gsc_status(domain))
    else:
        steps.append(
            {
                "step": "search_console_domain_property",
                "action": "skipped",
                "reason": "gsc toolset disabled",
            }
        )
    return {"domain": domain, "property_id": property_id, "steps": steps}


def _next_steps(domain: str, measurement_id: str | None, txt_token: str | None) -> list[str]:
    out = []
    if measurement_id:
        out.append(f"Install the GA4 tag (gtag.js or Google Tag Manager) with {measurement_id}.")
    if txt_token:
        out.append(
            f"Add a DNS TXT record on {domain} (name '@') with value '{txt_token}', wait until "
            f"`dig TXT {domain} +short` shows it, then call sc_verify_site_dns('{domain}')."
        )
    out.append(
        f"Submit the sitemap: sc_submit_sitemap('sc-domain:{domain}', 'https://{domain}/sitemap.xml')."
    )
    out.append(f"Record a PageSpeed baseline: psi_audit('https://{domain}/').")
    return out


def _apply(plan: dict[str, Any], *, account_id, display_name, time_zone, currency_code) -> dict:
    domain = plan["domain"]
    steps = plan["steps"]
    property_id = plan["property_id"]
    measurement_id = None
    txt_token = None
    blocked = False

    for step in steps:
        if step["action"] in ("exists", "skipped"):
            step["result"] = "skipped"
            if step["step"] == "web_data_stream":
                measurement_id = step["measurement_id"]
            continue
        if blocked and step["step"] != "search_console_domain_property":
            step["result"] = "not_run: the property or its web stream could not be created"
            continue
        try:
            if step["step"] == "property":
                created = admin.create_property(account_id, display_name, time_zone, currency_code)
                property_id = step["property_id"] = created["property_id"]
            elif step["step"] == "web_data_stream":
                created = admin.create_web_data_stream(
                    property_id, display_name, step["default_uri"]
                )
                step["stream_id"] = created["stream_id"]
                measurement_id = step["measurement_id"] = created["web"]["measurement_id"]
            elif step["step"] == "key_event":
                admin.create_key_event(property_id, step["event_name"])
            elif step["step"] == "custom_dimension":
                admin.create_custom_dimension(
                    property_id, step["parameter_name"], step["display_name"], step["scope"]
                )
            elif step["action"] == "verify":
                # Already added but unverified: only the TXT token is missing.
                txt_token = step["txt_token"] = search_console.dns_txt_token(domain)
                step["result"] = "token_fetched"
                continue
            elif step["step"] == "search_console_domain_property":
                added = search_console.sc_add_site_and_get_verify_token(domain)
                txt_token = step["txt_token"] = added.get("txt_token")
                if added.get("error") or str(added.get("add", "")).startswith("error"):
                    raise RuntimeError(added.get("error") or added["add"])
            step["result"] = "created"
        except Exception as exc:  # report every failed step instead of aborting the run
            step["result"] = f"error: {exc}"
            if step["step"] in ("property", "web_data_stream"):
                blocked = True

    return {
        "applied": True,
        "domain": domain,
        "property_id": property_id,
        "measurement_id": measurement_id,
        "dns_txt_token": txt_token,
        "steps": steps,
        "next_steps": _next_steps(domain, measurement_id, txt_token),
    }


def make_tool(*, writes: bool, gsc: bool):
    def bootstrap_site_measurement(
        site_url: str,
        account_id: str,
        property_display_name: str,
        time_zone: str,
        currency_code: str,
        key_events: list[str] | None = None,
        custom_dimensions: list[CustomDimensionSpec] | None = None,
        apply: bool = False,
    ) -> dict[str, Any]:
        """Plan, and optionally apply, the full measurement setup of a website.

        With apply=False (default) nothing is changed: it detects what already exists for the
        site (GA4 property and web stream matched by the site's domain, key events, custom
        dimensions, Search Console domain property) and returns the steps that would run.
        Show this plan to the user and get explicit confirmation before calling apply=True.

        With apply=True (requires the server to run with --enable-writes) it creates only the
        missing pieces, skipping what exists, so it is safe to re-run. It returns a step-by-step
        report with the GA4 measurement ID (G-...) and the DNS TXT token for Search Console.
        DNS verification and sitemap submission stay manual follow-up steps
        (sc_verify_site_dns, sc_submit_sitemap) because the TXT record must be published first.

        Args:
            site_url: the site, e.g. 'https://example.com'.
            account_id: GA4 account that owns (or will own) the property; see
                list_account_summaries.
            property_display_name: name for a new property; also used to find an existing one.
            time_zone: IANA time zone for a new property, e.g. 'America/Mexico_City'.
            currency_code: ISO 4217 currency for a new property, e.g. 'USD'.
            key_events: event names to mark as key events, e.g. ['generate_lead'].
            custom_dimensions: parameters to register as custom dimensions.
            apply: False = plan only (default); True = execute the plan.
        """
        if apply and not writes:
            raise PermissionError(WRITES_REQUIRED)
        plan = _plan(
            site_url,
            account_id,
            property_display_name,
            key_events or [],
            custom_dimensions or [],
            gsc,
        )
        if not apply:
            return {
                "applied": False,
                "site_url": site_url,
                **plan,
                "writes_enabled": writes,
                "note": (
                    "Plan only, nothing was changed. Confirm with the user, then call again "
                    "with apply=True."
                    if writes
                    else "Plan only, nothing was changed. Applying it requires restarting the "
                    "server with --enable-writes."
                ),
            }
        return _apply(
            plan,
            account_id=account_id,
            display_name=property_display_name,
            time_zone=time_zone,
            currency_code=currency_code,
        )

    return bootstrap_site_measurement


def register(mcp: FastMCP, *, writes: bool, gsc: bool) -> None:
    mcp.add_tool(make_tool(writes=writes, gsc=gsc), annotations=ENSURE if writes else READ)
