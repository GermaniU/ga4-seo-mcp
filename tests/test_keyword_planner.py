"""Unit tests for the Google Ads Keyword Planner module (keyword_planner.py).

No network calls. They cover token handling (a clear RuntimeError before any client is built)
and the request/response mapping, using REAL protobuf messages from the installed `google-ads`
package so field names and types are the true ones.

`_client()` is mocked as a whole: building a real GoogleAdsClient triggers
`google.auth.default()` against this machine's real ADC.
"""

from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

import pytest

pytest.importorskip("google.ads.googleads")

# Same API version the real client resolves at runtime, so the test follows package upgrades.
from google.ads.googleads.client import _DEFAULT_VERSION as _GADS_VERSION  # noqa: E402

from ga4_seo_mcp import keyword_planner as kp  # noqa: E402
from ga4_seo_mcp.keyword_planner import GoogleAdsException  # noqa: E402

kpis = import_module(
    f"google.ads.googleads.{_GADS_VERSION}.services.types.keyword_plan_idea_service"
)
kpc = import_module(f"google.ads.googleads.{_GADS_VERSION}.common.types.keyword_plan_common")
kpcl = import_module(
    f"google.ads.googleads.{_GADS_VERSION}.enums.types.keyword_plan_competition_level"
)
kpn = import_module(f"google.ads.googleads.{_GADS_VERSION}.enums.types.keyword_plan_network")

_CompetitionLevel = kpcl.KeywordPlanCompetitionLevelEnum.KeywordPlanCompetitionLevel
_KeywordPlanNetwork = kpn.KeywordPlanNetworkEnum.KeywordPlanNetwork


class _FakeGoogleAdsService:
    """Only the path builders the module uses, with the real resource-name formats."""

    @staticmethod
    def geo_target_constant_path(location_id: str) -> str:
        return f"geoTargetConstants/{location_id}"

    @staticmethod
    def language_constant_path(language_id: str) -> str:
        return f"languageConstants/{language_id}"


class _FakeKeywordPlanIdeaService:
    def __init__(self, ideas_fn=None, historical_fn=None):
        self._ideas_fn = ideas_fn
        self._historical_fn = historical_fn
        self.last_request = None

    def generate_keyword_ideas(self, request):
        self.last_request = request
        return self._ideas_fn(request)

    def generate_keyword_historical_metrics(self, request):
        self.last_request = request
        return self._historical_fn(request)


class _FakeGoogleAdsClient:
    """`get_type` builds REAL protobuf messages; services and enums are light fakes because a
    real GoogleAdsServiceClient validates transport and credentials."""

    def __init__(self, kpi_service: _FakeKeywordPlanIdeaService):
        self._kpi_service = kpi_service
        self.enums = SimpleNamespace(KeywordPlanNetworkEnum=_KeywordPlanNetwork)

    def get_service(self, name: str):
        if name == "GoogleAdsService":
            return _FakeGoogleAdsService()
        if name == "KeywordPlanIdeaService":
            return self._kpi_service
        raise AssertionError(f"unexpected service: {name}")

    def get_type(self, name: str):
        return getattr(kpis, name)()


@pytest.fixture
def _gads_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "test-dev-token")
    monkeypatch.delenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", raising=False)


def _metrics(
    avg_monthly_searches=12100,
    competition=_CompetitionLevel.LOW,
    competition_index=34,
    low_bid_micros=550_000,
    high_bid_micros=1_200_000,
):
    return kpc.KeywordPlanHistoricalMetrics(
        avg_monthly_searches=avg_monthly_searches,
        competition=competition,
        competition_index=competition_index,
        low_top_of_page_bid_micros=low_bid_micros,
        high_top_of_page_bid_micros=high_bid_micros,
    )


def test_kw_ideas_gads_missing_developer_token_raises_clear_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    # The token file may exist on this machine; disable it to test "no token anywhere".
    monkeypatch.setattr(kp, "_read_token_file", lambda: None)

    with pytest.raises(RuntimeError, match="GOOGLE_ADS_DEVELOPER_TOKEN"):
        kp.kw_ideas_gads(customer_id="1234567890", keywords=["restaurante"])


def test_kw_volume_gads_missing_developer_token_raises_clear_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    monkeypatch.setattr(kp, "_read_token_file", lambda: None)

    with pytest.raises(RuntimeError, match="GOOGLE_ADS_DEVELOPER_TOKEN"):
        kp.kw_volume_gads(customer_id="1234567890", keywords=["restaurante cdmx"])


def test_kw_ideas_gads_normalizes_response_and_builds_request(monkeypatch, _gads_env):
    fake_results = [
        kpis.GenerateKeywordIdeaResult(
            text="restaurante cerca de mi",
            keyword_idea_metrics=_metrics(),
        ),
        kpis.GenerateKeywordIdeaResult(
            text="comida a domicilio cdmx",
            keyword_idea_metrics=_metrics(
                avg_monthly_searches=8100,
                competition=_CompetitionLevel.MEDIUM,
                competition_index=61,
                low_bid_micros=720_000,
                high_bid_micros=1_500_000,
            ),
        ),
    ]

    kpi_service = _FakeKeywordPlanIdeaService(ideas_fn=lambda request: fake_results)
    monkeypatch.setattr(kp, "_client", lambda: _FakeGoogleAdsClient(kpi_service))

    result = kp.kw_ideas_gads(
        customer_id="123-456-7890",
        keywords=["restaurante"],
        limit=2,
    )

    # customer_id without dashes, real geo/language resource names, GOOGLE_SEARCH network.
    req = kpi_service.last_request
    assert req.customer_id == "1234567890"
    assert req.geo_target_constants == ["geoTargetConstants/2484"]
    assert req.language == "languageConstants/1003"
    assert req.keyword_plan_network == _KeywordPlanNetwork.GOOGLE_SEARCH
    assert list(req.keyword_seed.keywords) == ["restaurante"]

    assert result == [
        {
            "keyword": "restaurante cerca de mi",
            "avg_monthly_searches": 12100,
            "competition": "LOW",
            "competition_index": 34,
            "low_top_of_page_bid": 0.55,
            "high_top_of_page_bid": 1.2,
        },
        {
            "keyword": "comida a domicilio cdmx",
            "avg_monthly_searches": 8100,
            "competition": "MEDIUM",
            "competition_index": 61,
            "low_top_of_page_bid": 0.72,
            "high_top_of_page_bid": 1.5,
        },
    ]


def test_kw_ideas_gads_limit_truncates_client_side(monkeypatch, _gads_env):
    fake_results = [
        kpis.GenerateKeywordIdeaResult(text=f"kw {i}", keyword_idea_metrics=_metrics())
        for i in range(5)
    ]
    kpi_service = _FakeKeywordPlanIdeaService(ideas_fn=lambda request: fake_results)
    monkeypatch.setattr(kp, "_client", lambda: _FakeGoogleAdsClient(kpi_service))

    result = kp.kw_ideas_gads(customer_id="1234567890", keywords=["kw"], limit=2)

    assert len(result) == 2
    assert [r["keyword"] for r in result] == ["kw 0", "kw 1"]


def test_kw_volume_gads_normalizes_response_and_builds_request(monkeypatch, _gads_env):
    fake_response = kpis.GenerateKeywordHistoricalMetricsResponse(
        results=[
            kpis.GenerateKeywordHistoricalMetricsResult(
                text="restaurante cdmx",
                keyword_metrics=_metrics(
                    avg_monthly_searches=5400,
                    competition=_CompetitionLevel.HIGH,
                    competition_index=100,
                    low_bid_micros=1_230_000,
                    high_bid_micros=2_000_000,
                ),
            )
        ]
    )
    kpi_service = _FakeKeywordPlanIdeaService(historical_fn=lambda request: fake_response)
    monkeypatch.setattr(kp, "_client", lambda: _FakeGoogleAdsClient(kpi_service))

    result = kp.kw_volume_gads(customer_id="1234567890", keywords=["restaurante cdmx"])

    req = kpi_service.last_request
    assert req.customer_id == "1234567890"
    assert list(req.keywords) == ["restaurante cdmx"]
    assert req.geo_target_constants == ["geoTargetConstants/2484"]
    assert req.language == "languageConstants/1003"

    assert result == [
        {
            "keyword": "restaurante cdmx",
            "avg_monthly_searches": 5400,
            "competition": "HIGH",
            "competition_index": 100,
            "low_top_of_page_bid": 1.23,
            "high_top_of_page_bid": 2.0,
        }
    ]


def test_kw_volume_gads_login_customer_id_normalized(monkeypatch, _gads_env):
    """Runs the real `_client()`, mocking only `load_from_dict`, where credentials resolve."""
    captured_config = {}

    def fake_load_from_dict(config):
        captured_config.update(config)
        kpi_service = _FakeKeywordPlanIdeaService(
            historical_fn=lambda request: kpis.GenerateKeywordHistoricalMetricsResponse(results=[])
        )
        return _FakeGoogleAdsClient(kpi_service)

    monkeypatch.setenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "987-654-3210")
    monkeypatch.setattr(kp.GoogleAdsClient, "load_from_dict", staticmethod(fake_load_from_dict))

    kp.kw_volume_gads(customer_id="1234567890", keywords=["restaurante cdmx"])

    assert captured_config["login_customer_id"] == "9876543210"
    assert captured_config["developer_token"] == "test-dev-token"
    assert captured_config["use_proto_plus"] is True
    assert captured_config["use_application_default_credentials"] is True


def test_run_wraps_google_ads_exception(monkeypatch, _gads_env):
    """`_run()` turns GoogleAdsException into a readable RuntimeError, not a raw gRPC trace."""
    err_types = import_module(f"google.ads.googleads.{_GADS_VERSION}.errors.types.errors")

    gads_failure = err_types.GoogleAdsFailure(
        errors=[err_types.GoogleAdsError(message="Invalid customer ID.")]
    )

    def boom(request):
        raise GoogleAdsException(None, None, gads_failure, "req-123")

    with pytest.raises(RuntimeError, match="Invalid customer ID"):
        kp._run(boom, request=object())
