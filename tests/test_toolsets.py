from __future__ import annotations

import pytest

from ga4_seo_mcp.scopes import DEFAULT_TOOLSETS, parse_toolsets
from ga4_seo_mcp.server import WRITE_TOOLS, build_server

ADMIN_READ = {
    "list_account_summaries",
    "list_properties",
    "get_property",
    "list_data_streams",
    "get_data_stream",
    "list_key_events",
    "list_custom_dimensions",
    "list_google_ads_links",
    "bootstrap_site_measurement",
}
ADMIN_WRITE = {
    "create_property",
    "update_property",
    "delete_property",
    "create_web_data_stream",
    "update_web_data_stream",
    "delete_data_stream",
    "create_key_event",
    "create_custom_dimension",
    "create_google_ads_link",
    "delete_google_ads_link",
}
DATA = {
    "run_report",
    "run_realtime_report",
    "top_pages",
    "events_summary",
    "traffic_sources",
    "conversions_summary",
    "web_vitals_summary",
    "audit_portfolio",
}
GSC_READ = {
    "sc_list_sites",
    "sc_top_queries",
    "sc_page_performance",
    "sc_query_breakdown_by_page",
    "sc_list_sitemaps",
}
GSC_WRITE = {"sc_submit_sitemap", "sc_add_site_and_get_verify_token", "sc_verify_site_dns"}
PSI = {"psi_audit", "psi_field_data_only"}
DATAFORSEO = {"kw_ideas", "kw_volume"}
ADS = {"kw_ideas_gads", "kw_volume_gads"}


def test_default_toolsets():
    assert DEFAULT_TOOLSETS == ("admin", "data", "gsc", "psi")
    assert parse_toolsets(None) == DEFAULT_TOOLSETS
    assert parse_toolsets("") == DEFAULT_TOOLSETS


def test_parse_toolsets_normalizes_and_dedupes():
    assert parse_toolsets(" GSC, psi,gsc ") == ("gsc", "psi")


def test_parse_toolsets_rejects_unknown():
    with pytest.raises(ValueError, match="unknown toolset"):
        parse_toolsets("admin,ga3")


def test_write_tools_constant_matches_expected():
    assert WRITE_TOOLS == ADMIN_WRITE | GSC_WRITE


@pytest.mark.parametrize(
    ("toolsets", "writes", "expected"),
    [
        (DEFAULT_TOOLSETS, False, ADMIN_READ | DATA | GSC_READ | PSI),
        (DEFAULT_TOOLSETS, True, ADMIN_READ | ADMIN_WRITE | DATA | GSC_READ | GSC_WRITE | PSI),
        (("data",), False, DATA),
        (("data",), True, DATA),
        (("psi",), False, PSI),
        (("gsc",), True, GSC_READ | GSC_WRITE),
        (("dataforseo",), False, DATAFORSEO),
        (("ads",), False, ADS),
    ],
)
async def test_registered_tools_per_combination(tool_names, toolsets, writes, expected):
    assert await tool_names(toolsets, writes) == expected


async def test_counts(tool_names):
    assert len(await tool_names(DEFAULT_TOOLSETS)) == 24
    assert len(await tool_names(DEFAULT_TOOLSETS, writes=True)) == 37
    assert len(await tool_names(("data",))) == 8
    all_toolsets = ("admin", "data", "gsc", "psi", "dataforseo", "ads")
    assert len(await tool_names(all_toolsets, writes=True)) == 41


@pytest.mark.parametrize(
    "toolsets", [DEFAULT_TOOLSETS, ("admin", "data", "gsc", "psi", "dataforseo", "ads")]
)
async def test_no_write_tool_without_enable_writes(tool_names, toolsets):
    assert not (await tool_names(toolsets, writes=False)) & WRITE_TOOLS


async def test_prompts_registered():
    mcp = build_server(DEFAULT_TOOLSETS, writes=False)
    names = {p.name for p in await mcp.list_prompts()}
    assert names == {
        "audit_ga4_setup",
        "seo_360_audit",
        "portfolio_performance_digest",
        "launch_site_measurement",
    }


async def test_server_reports_its_own_version():
    from ga4_seo_mcp import __version__

    mcp = build_server(("psi",), writes=False)
    assert mcp._mcp_server.version == __version__
