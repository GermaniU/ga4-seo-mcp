"""bootstrap_site_measurement against in-memory fakes of the Admin and Search Console clients."""

from __future__ import annotations

import pytest
from google.analytics.admin_v1beta.types import (
    CustomDimension,
    DataStream,
    KeyEvent,
    Property,
)
from mcp.server.fastmcp.exceptions import ToolError

from ga4_seo_mcp import admin, bootstrap, search_console
from ga4_seo_mcp.server import build_server

ACCOUNT = "123456789"
SITE = "https://www.example.com"


class _Exec:
    def __init__(self, value=None, on_execute=None):
        self._value = value
        self._on_execute = on_execute

    def execute(self):
        if self._on_execute:
            self._on_execute()
        return self._value


class FakeGoogle:
    """GA4 Admin + Search Console + Site Verification state, recording every call."""

    def __init__(self):
        self.properties: list[Property] = []
        self.streams: dict[str, list[DataStream]] = {}
        self.key_events: dict[str, list[KeyEvent]] = {}
        self.dimensions: dict[str, list[CustomDimension]] = {}
        self.site_entries: list[dict] = []
        self.calls: list[str] = []
        self.writes: list[str] = []

    # --- GA4 Admin (v1beta client surface) ---
    def list_properties(self, request):
        self.calls.append("list_properties")
        return list(self.properties)

    def list_data_streams(self, parent):
        self.calls.append("list_data_streams")
        return list(self.streams.get(parent, []))

    def list_key_events(self, parent):
        self.calls.append("list_key_events")
        return list(self.key_events.get(parent, []))

    def list_custom_dimensions(self, parent):
        self.calls.append("list_custom_dimensions")
        return list(self.dimensions.get(parent, []))

    def create_property(self, property):
        self.writes.append("create_property")
        property.name = f"properties/{555000 + len(self.properties)}"
        self.properties.append(property)
        return property

    def create_data_stream(self, parent, data_stream):
        self.writes.append("create_data_stream")
        data_stream.name = f"{parent}/dataStreams/777"
        data_stream.web_stream_data.measurement_id = "G-TEST123"
        self.streams.setdefault(parent, []).append(data_stream)
        return data_stream

    def create_key_event(self, parent, key_event):
        self.writes.append(f"create_key_event:{key_event.event_name}")
        key_event.name = f"{parent}/keyEvents/1"
        self.key_events.setdefault(parent, []).append(key_event)
        return key_event

    def create_custom_dimension(self, parent, custom_dimension):
        self.writes.append(f"create_custom_dimension:{custom_dimension.parameter_name}")
        custom_dimension.name = f"{parent}/customDimensions/1"
        self.dimensions.setdefault(parent, []).append(custom_dimension)
        return custom_dimension

    # --- Search Console + Site Verification (discovery client surface) ---
    def _sites(self):
        fake = self

        class Sites:
            def list(self):
                fake.calls.append("sc_sites_list")
                return _Exec({"siteEntry": list(fake.site_entries)})

            def add(self, siteUrl):
                def _add():
                    fake.writes.append(f"sc_add:{siteUrl}")
                    fake.site_entries.append(
                        {"siteUrl": siteUrl, "permissionLevel": "siteUnverifiedUser"}
                    )

                return _Exec({}, _add)

        return Sites()

    def sites(self):
        return self._sites()

    def webResource(self):
        fake = self

        class WebResource:
            def getToken(self, body):
                fake.calls.append("sv_get_token")
                return _Exec({"token": "google-site-verification=abc"})

        return WebResource()


@pytest.fixture
def google(monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(admin, "_client", lambda write=False: fake)
    monkeypatch.setattr(search_console, "_sc_client", lambda write=False: fake)
    monkeypatch.setattr(search_console, "_siteverification_client", lambda: fake)
    return fake


def _existing_site(fake: FakeGoogle):
    prop = Property(
        name="properties/123456789", parent=f"accounts/{ACCOUNT}", display_name="Example"
    )
    stream = DataStream(
        name="properties/123456789/dataStreams/42",
        type_=DataStream.DataStreamType.WEB_DATA_STREAM,
        web_stream_data=DataStream.WebStreamData(
            default_uri="https://example.com", measurement_id="G-EXISTING"
        ),
    )
    fake.properties.append(prop)
    fake.streams["properties/123456789"] = [stream]
    fake.key_events["properties/123456789"] = [KeyEvent(event_name="generate_lead")]
    fake.site_entries.append({"siteUrl": "sc-domain:example.com", "permissionLevel": "siteOwner"})


ARGS = dict(
    site_url=SITE,
    account_id=ACCOUNT,
    property_display_name="Example",
    time_zone="America/Mexico_City",
    currency_code="USD",
    key_events=["generate_lead", "sign_up"],
    custom_dimensions=[
        bootstrap.CustomDimensionSpec(parameter_name="plan_type", display_name="Plan type")
    ],
)


def _actions(result):
    return [(s["step"], s["action"]) for s in result["steps"]]


def test_plan_on_empty_account_creates_everything(google):
    tool = bootstrap.make_tool(writes=False, gsc=True)
    result = tool(**ARGS)
    assert result["applied"] is False
    assert result["domain"] == "example.com"
    assert _actions(result) == [
        ("property", "create"),
        ("web_data_stream", "create"),
        ("key_event", "create"),
        ("key_event", "create"),
        ("custom_dimension", "create"),
        ("search_console_domain_property", "create"),
    ]
    assert google.writes == []
    assert "--enable-writes" in result["note"]


def test_plan_distinguishes_dimensions_with_same_name_and_different_scope(google):
    # Si ya existe plan_type como USER y se pide como EVENT, hay que crearla.
    prop = Property(
        name="properties/123456789", parent=f"accounts/{ACCOUNT}", display_name="Example"
    )
    google.properties.append(prop)
    google.dimensions.setdefault("properties/123456789", []).append(
        CustomDimension(
            parameter_name="plan_type", display_name="Plan type", scope="USER"
        )
    )

    result = bootstrap.make_tool(writes=False, gsc=False)(
        **{
            **ARGS,
            "custom_dimensions": [
                bootstrap.CustomDimensionSpec(
                    parameter_name="plan_type", display_name="Plan type"
                )
            ],
        }
    )
    steps = {s["step"]: s for s in result["steps"]}
    assert steps["custom_dimension"]["scope"] == "EVENT"
    assert steps["custom_dimension"]["action"] == "create"

    # Una vez creada con ese scope, el plan la reconoce como existente.
    google.dimensions["properties/123456789"].append(
        CustomDimension(parameter_name="plan_type", display_name="Plan type", scope="EVENT")
    )
    again = bootstrap.make_tool(writes=False, gsc=False)(
        **{
            **ARGS,
            "custom_dimensions": [
                bootstrap.CustomDimensionSpec(
                    parameter_name="plan_type", display_name="Plan type"
                )
            ],
        }
    )
    again_steps = {s["step"]: s for s in again["steps"]}
    assert again_steps["custom_dimension"]["action"] == "exists"


def test_plan_detects_existing_property_by_stream_domain(google):
    _existing_site(google)
    result = bootstrap.make_tool(writes=False, gsc=True)(**{**ARGS, "property_display_name": "New"})
    assert result["property_id"] == "123456789"
    steps = {(s["step"], s.get("event_name")): s for s in result["steps"]}
    assert steps[("property", None)]["action"] == "exists"
    assert steps[("web_data_stream", None)]["measurement_id"] == "G-EXISTING"
    assert steps[("key_event", "generate_lead")]["action"] == "exists"
    assert steps[("key_event", "sign_up")]["action"] == "create"
    assert steps[("search_console_domain_property", None)]["action"] == "exists"
    assert google.writes == []


def test_plan_without_gsc_toolset_skips_search_console(google):
    result = bootstrap.make_tool(writes=False, gsc=False)(**ARGS)
    assert result["steps"][-1]["action"] == "skipped"
    assert "sc_sites_list" not in google.calls


def test_apply_without_writes_fails_before_any_call(google):
    tool = bootstrap.make_tool(writes=False, gsc=True)
    with pytest.raises(PermissionError, match="--enable-writes"):
        tool(**ARGS, apply=True)
    assert google.calls == [] and google.writes == []


async def test_apply_without_writes_is_a_tool_error_over_mcp(google):
    mcp = build_server(("admin", "gsc"), writes=False)
    with pytest.raises(ToolError, match="--enable-writes"):
        await mcp.call_tool(
            "bootstrap_site_measurement",
            {**ARGS, "custom_dimensions": [], "apply": True},
        )
    assert google.writes == []


def test_apply_creates_missing_pieces_and_returns_ids(google):
    result = bootstrap.make_tool(writes=True, gsc=True)(**ARGS, apply=True)
    assert result["applied"] is True
    assert result["measurement_id"] == "G-TEST123"
    assert result["dns_txt_token"] == "google-site-verification=abc"
    assert all(s["result"] == "created" for s in result["steps"])
    assert google.writes == [
        "create_property",
        "create_data_stream",
        "create_key_event:generate_lead",
        "create_key_event:sign_up",
        "create_custom_dimension:plan_type",
        "sc_add:sc-domain:example.com",
    ]
    assert any("sc_verify_site_dns" in s for s in result["next_steps"])


def test_apply_is_idempotent(google):
    tool = bootstrap.make_tool(writes=True, gsc=True)
    tool(**ARGS, apply=True)
    first = list(google.writes)
    again = tool(**ARGS, apply=True)
    # Only the still-unverified Search Console site asks for its token again; nothing is created.
    assert google.writes == first
    assert {
        s["step"]: s["result"]
        for s in again["steps"]
        if s["step"] != "search_console_domain_property"
    } == {
        "property": "skipped",
        "web_data_stream": "skipped",
        "key_event": "skipped",
        "custom_dimension": "skipped",
    }
    assert again["measurement_id"] == "G-TEST123"
    assert again["steps"][-1]["result"] == "token_fetched"
    assert again["dns_txt_token"] == "google-site-verification=abc"


def test_apply_on_existing_site_only_adds_the_missing_key_event(google):
    _existing_site(google)
    result = bootstrap.make_tool(writes=True, gsc=True)(
        **{**ARGS, "custom_dimensions": []}, apply=True
    )
    assert google.writes == ["create_key_event:sign_up"]
    assert result["measurement_id"] == "G-EXISTING"
    assert result["dns_txt_token"] is None


def test_failed_property_creation_blocks_dependent_steps(google, monkeypatch):
    def boom(property):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(google, "create_property", boom)
    result = bootstrap.make_tool(writes=True, gsc=False)(**ARGS, apply=True)
    results = [s["result"] for s in result["steps"]]
    assert results[0] == "error: quota exceeded"
    assert all(r.startswith("not_run") for r in results[1:-1])
    assert google.writes == []
