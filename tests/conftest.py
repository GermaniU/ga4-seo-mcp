from __future__ import annotations

import pytest

from ga4_seo_mcp.server import build_server


@pytest.fixture
def tool_names():
    async def _names(toolsets, writes=False):
        mcp = build_server(toolsets, writes=writes)
        return {t.name for t in await mcp.list_tools()}

    return _names
