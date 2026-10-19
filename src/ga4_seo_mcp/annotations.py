"""MCP tool annotations shared by every module."""

from mcp.types import ToolAnnotations

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
# Adds a new resource; calling it twice creates two (or fails on a duplicate).
CREATE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
)
# Overwrites existing values: the previous ones are lost.
UPDATE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True
)
DELETE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True
)
# Changes state but repeating it is harmless (submit a sitemap, verify a domain).
ENSURE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True
)
