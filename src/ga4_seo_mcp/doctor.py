"""`ga4-seo-mcp doctor`: read-only checks of credentials, token scopes and API access."""

from __future__ import annotations

import os
import sys

import google.auth
import requests
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import Request

from .scopes import auth_command, required_scopes

TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"


def _short(exc: Exception) -> str:
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    return text[:200]


def _probe_admin(creds) -> str:
    from google.analytics.admin_v1beta import AnalyticsAdminServiceClient

    pager = AnalyticsAdminServiceClient(credentials=creds).list_account_summaries(
        request={"page_size": 50}
    )
    return f"{len(list(pager.account_summaries))} account(s) visible on the first page"


def _probe_data(creds) -> str:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient

    meta = BetaAnalyticsDataClient(credentials=creds).get_metadata(name="properties/0/metadata")
    return f"responded ({len(meta.metrics)} metrics in the schema)"


def _probe_gsc(creds) -> str:
    from googleapiclient.discovery import build

    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    return f"{len(svc.sites().list().execute().get('siteEntry', []))} site(s) visible"


def _token_scopes(creds) -> set[str] | None:
    resp = requests.get(TOKENINFO, params={"access_token": creds.token}, timeout=15)
    if not resp.ok:
        return None
    return set(resp.json().get("scope", "").split())


def run_doctor(toolsets, writes: bool, out=None) -> int:
    out = out or sys.stdout
    failures = 0

    def report(status: str, message: str) -> None:
        nonlocal failures
        failures += status == "fail"
        print(f"[{status}] {message}", file=out)

    needed = required_scopes(toolsets, writes)
    print(f"toolsets: {','.join(toolsets)}   writes: {'on' if writes else 'off'}", file=out)

    creds = None
    if needed:
        try:
            creds, _ = google.auth.default(scopes=needed)
            source = (
                "GOOGLE_APPLICATION_CREDENTIALS"
                if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
                else "Application Default Credentials"
            )
            report("ok", f"credentials found: {type(creds).__name__} via {source}")
        except DefaultCredentialsError as exc:
            report("fail", f"no Google credentials: {_short(exc)}")
            print(f"       fix: {auth_command(toolsets, writes)}", file=out)
            creds = None
        except OSError as exc:  # e.g. a mounted key file this user cannot read
            report("fail", f"cannot read the credentials file: {_short(exc)}")
            creds = None

    if creds is not None:
        try:
            creds.refresh(Request())
            report("ok", "access token refreshed")
        except Exception as exc:
            report("fail", f"cannot refresh the access token: {_short(exc)}")
            creds = None

    if creds is not None:
        granted = _token_scopes(creds)
        if granted is None:
            report("warn", "could not read the token scopes from Google's tokeninfo endpoint")
        else:
            missing = [s for s in needed if s not in granted]
            # A full `webmasters` grant also covers the read-only Search Console calls.
            implied = {
                "https://www.googleapis.com/auth/webmasters.readonly": (
                    "https://www.googleapis.com/auth/webmasters"
                ),
            }
            missing = [s for s in missing if implied.get(s) not in granted]
            if missing:
                report("fail", "token is missing scopes: " + ", ".join(missing))
                print(f"       fix: {auth_command(toolsets, writes)}", file=out)
            else:
                report("ok", f"token has the {len(needed)} scope(s) these toolsets need")

        probes = {"admin": _probe_admin, "data": _probe_data, "gsc": _probe_gsc}
        for name, probe in probes.items():
            if name not in toolsets:
                continue
            try:
                report("ok", f"{name}: {probe(creds)}")
            except Exception as exc:
                report("fail", f"{name}: {_short(exc)}")

    if "psi" in toolsets:
        key = "set" if os.environ.get("PAGESPEED_API_KEY") else "not set (small anonymous quota)"
        report("ok", f"psi: no Google login needed; PAGESPEED_API_KEY {key}")
    if "dataforseo" in toolsets:
        if os.environ.get("DATAFORSEO_LOGIN") and os.environ.get("DATAFORSEO_PASSWORD"):
            report("ok", "dataforseo: credentials present (not called, the API is paid)")
        else:
            report("fail", "dataforseo: DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD not set")
    if "ads" in toolsets:
        try:
            from . import keyword_planner

            token = (
                os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN") or keyword_planner._read_token_file()
            )
            if token:
                report("ok", "ads: developer token present (not called)")
            else:
                report("fail", "ads: no GOOGLE_ADS_DEVELOPER_TOKEN and no token file")
        except ImportError:
            report("fail", "ads: google-ads not installed: pip install 'ga4-seo-mcp[ads]'")
        except RuntimeError as exc:
            report("fail", f"ads: {exc}")

    print("all checks passed" if not failures else f"{failures} check(s) failed", file=out)
    return 1 if failures else 0
