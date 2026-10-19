"""MCP server for Google Analytics 4, Search Console and PageSpeed Insights."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ga4-seo-mcp")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0"
