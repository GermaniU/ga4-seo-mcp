from __future__ import annotations

import pytest

from ga4_seo_mcp.scopes import TOOLSETS
from ga4_seo_mcp.server import WRITE_TOOLS, build_server


async def _tools(writes):
    return await build_server(TOOLSETS, writes=writes).list_tools()


@pytest.mark.parametrize("writes", [False, True])
async def test_every_tool_is_annotated_and_open_world(writes):
    for tool in await _tools(writes):
        a = tool.annotations
        assert a is not None, tool.name
        assert a.openWorldHint is True, tool.name
        assert a.readOnlyHint is not None, tool.name


async def test_read_tools_are_read_only():
    for tool in await _tools(writes=False):
        assert tool.annotations.readOnlyHint is True, tool.name


async def test_write_tools_are_not_read_only():
    tools = {t.name: t.annotations for t in await _tools(writes=True)}
    for name in WRITE_TOOLS:
        assert tools[name].readOnlyHint is False, name
        assert tools[name].destructiveHint is not None, name
        assert tools[name].idempotentHint is not None, name


async def test_delete_tools_are_destructive():
    tools = {t.name: t.annotations for t in await _tools(writes=True)}
    deletes = [n for n in tools if n.startswith("delete_")]
    assert len(deletes) == 3
    for name in deletes:
        assert tools[name].destructiveHint is True, name


async def test_create_tools_are_additive():
    tools = {t.name: t.annotations for t in await _tools(writes=True)}
    for name in [n for n in tools if n.startswith("create_")]:
        assert tools[name].destructiveHint is False, name
        assert tools[name].idempotentHint is False, name


async def test_bootstrap_is_read_only_without_writes():
    ro = {t.name: t.annotations for t in await _tools(writes=False)}
    rw = {t.name: t.annotations for t in await _tools(writes=True)}
    assert ro["bootstrap_site_measurement"].readOnlyHint is True
    assert rw["bootstrap_site_measurement"].readOnlyHint is False
    assert rw["bootstrap_site_measurement"].destructiveHint is False
    assert rw["bootstrap_site_measurement"].idempotentHint is True


async def test_tool_descriptions_are_english_and_present():
    for tool in await _tools(writes=True):
        assert tool.description and len(tool.description) > 20, tool.name
        for word in (" para ", " una ", " del ", " Lista ", " ej. "):
            assert word not in tool.description, (tool.name, word)
