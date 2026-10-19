"""Toolsets and the minimum OAuth scopes each one needs."""

from __future__ import annotations

import shlex

TOOLSETS = ("admin", "data", "gsc", "psi", "dataforseo", "ads")
DEFAULT_TOOLSETS = ("admin", "data", "gsc", "psi")

_AUTH = "https://www.googleapis.com/auth/"
ANALYTICS_READONLY = _AUTH + "analytics.readonly"
ANALYTICS_EDIT = _AUTH + "analytics.edit"
WEBMASTERS_READONLY = _AUTH + "webmasters.readonly"
WEBMASTERS = _AUTH + "webmasters"
SITEVERIFICATION = _AUTH + "siteverification"
ADWORDS = _AUTH + "adwords"
# gcloud refuses `application-default login --scopes=...` unless cloud-platform is in the list,
# so it is only part of the login command. API clients never request it.
CLOUD_PLATFORM = _AUTH + "cloud-platform"

_READ = {
    "admin": [ANALYTICS_READONLY],
    "data": [ANALYTICS_READONLY],
    "gsc": [WEBMASTERS_READONLY],
    "ads": [ADWORDS],
}
_WRITE = {
    "admin": [ANALYTICS_EDIT],
    "gsc": [WEBMASTERS, SITEVERIFICATION],
}
_ORDER = [
    ANALYTICS_READONLY,
    ANALYTICS_EDIT,
    WEBMASTERS_READONLY,
    WEBMASTERS,
    SITEVERIFICATION,
    ADWORDS,
]


def parse_toolsets(raw: str | None) -> tuple[str, ...]:
    """Parse a comma-separated toolset list. Empty means the defaults."""
    names = [n.strip().lower() for n in (raw or "").split(",") if n.strip()]
    if not names:
        return DEFAULT_TOOLSETS
    unknown = sorted(set(names) - set(TOOLSETS))
    if unknown:
        raise ValueError(f"unknown toolset(s): {', '.join(unknown)}. Valid: {', '.join(TOOLSETS)}")
    return tuple(dict.fromkeys(names))


def required_scopes(toolsets, writes: bool) -> list[str]:
    """Google API scopes the enabled tools request, in a stable order."""
    wanted = set()
    for name in toolsets:
        wanted.update(_READ.get(name, []))
        if writes:
            wanted.update(_WRITE.get(name, []))
    return [s for s in _ORDER if s in wanted]


def auth_command(toolsets, writes: bool, client_id_file: str | None = None) -> str:
    """The exact `gcloud` command that creates ADC with the scopes the toolsets need."""
    scopes = [CLOUD_PLATFORM, *required_scopes(toolsets, writes)]
    parts = ["gcloud", "auth", "application-default", "login"]
    if client_id_file:
        parts.append(f"--client-id-file={shlex.quote(client_id_file)}")
    parts.append("--scopes=" + ",".join(scopes))
    return " ".join(parts)
