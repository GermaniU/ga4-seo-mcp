from __future__ import annotations

from ga4_seo_mcp.scopes import (
    ADWORDS,
    ANALYTICS_EDIT,
    ANALYTICS_READONLY,
    CLOUD_PLATFORM,
    SITEVERIFICATION,
    WEBMASTERS,
    WEBMASTERS_READONLY,
    auth_command,
    required_scopes,
)


def test_read_only_default_scopes():
    assert required_scopes(("admin", "data", "gsc", "psi"), writes=False) == [
        ANALYTICS_READONLY,
        WEBMASTERS_READONLY,
    ]


def test_write_scopes():
    assert required_scopes(("admin", "data", "gsc", "psi"), writes=True) == [
        ANALYTICS_READONLY,
        ANALYTICS_EDIT,
        WEBMASTERS_READONLY,
        WEBMASTERS,
        SITEVERIFICATION,
    ]


def test_data_only_needs_analytics_readonly():
    assert required_scopes(("data",), writes=True) == [ANALYTICS_READONLY]


def test_psi_and_dataforseo_need_no_google_scope():
    assert required_scopes(("psi", "dataforseo"), writes=True) == []


def test_ads_adds_adwords():
    assert required_scopes(("ads",), writes=False) == [ADWORDS]


def test_cloud_platform_never_requested_by_clients():
    every = ("admin", "data", "gsc", "psi", "dataforseo", "ads")
    assert CLOUD_PLATFORM not in required_scopes(every, writes=True)


def test_auth_command_read_only():
    cmd = auth_command(("admin", "data", "gsc", "psi"), writes=False)
    assert cmd.startswith("gcloud auth application-default login ")
    scopes = cmd.split("--scopes=")[1].split()[0].split(",")
    assert scopes == [CLOUD_PLATFORM, ANALYTICS_READONLY, WEBMASTERS_READONLY]
    assert "--client-id-file" not in cmd


def test_auth_command_with_client_file():
    cmd = auth_command(("gsc",), writes=True, client_id_file="oauth-client.json")
    assert "--client-id-file=oauth-client.json" in cmd
    assert SITEVERIFICATION in cmd
