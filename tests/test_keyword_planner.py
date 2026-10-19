"""Tests para el módulo Google Ads Keyword Planner (keyword_planner.py).

Tests UNITARIOS mockeados — cero llamadas reales a Google Ads (el flujo E2E ya
se validó con token Basic el 2026-07-18, ver docstring de keyword_planner.py;
estos tests cubren la lógica pura, independiente del token). Validan:

  1. El manejo del token (falta GOOGLE_ADS_DEVELOPER_TOKEN Y archivo dev-token
     -> RuntimeError claro, ANTES de construir ningún cliente).
  2. El NORMALIZADOR (`_historical_metrics_to_dict`) y la construcción del
     request (customer_id sin guiones, geo/language resource names,
     keyword_plan_network) contra objetos protobuf REALES del paquete
     `google-ads` instalado — no un mock inventado a mano, así que field-names
     y tipos son los verdaderos.

El comportamiento del backend real (auth ADC, aceptación del customer_id, y que
avg_monthly_searches viene bucketed) se validó por smoke E2E, no acá — estos
tests no tocan la red a propósito.

Se mockea `_client()` COMPLETO (no solo la llamada RPC, a diferencia de
test_keywords_dataforseo.py que solo mockea `requests.post`) porque construir
un GoogleAdsClient real dispara `google.auth.default()` contra las
credenciales ADC reales de esta máquina — hay un riesgo real de disparar
auth de verdad si solo se mockea la capa de red. DataForSEO no tiene ese
problema porque su "auth" es solo un tuple de strings sin side-effects.
"""

from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

import pytest

from ga4_seo_mcp import keyword_planner as kp
from ga4_seo_mcp.keyword_planner import GoogleAdsException

# Se usa la MISMA versión default que el cliente real resolvería en runtime
# (google.ads.googleads.client._DEFAULT_VERSION), para no hardcodear "v24" y
# quedar desincronizado si el paquete instalado bumpea de versión.
from google.ads.googleads.client import _DEFAULT_VERSION as _GADS_VERSION

kpis = import_module(f"google.ads.googleads.{_GADS_VERSION}.services.types.keyword_plan_idea_service")
kpc = import_module(f"google.ads.googleads.{_GADS_VERSION}.common.types.keyword_plan_common")
kpcl = import_module(f"google.ads.googleads.{_GADS_VERSION}.enums.types.keyword_plan_competition_level")
kpn = import_module(f"google.ads.googleads.{_GADS_VERSION}.enums.types.keyword_plan_network")

_CompetitionLevel = kpcl.KeywordPlanCompetitionLevelEnum.KeywordPlanCompetitionLevel
_KeywordPlanNetwork = kpn.KeywordPlanNetworkEnum.KeywordPlanNetwork


class _FakeGoogleAdsService:
    """Fake de GoogleAdsService — solo los path-builders que usa el módulo.
    Réplica de los formatos reales confirmados por introspección
    (GoogleAdsServiceClient.geo_target_constant_path/language_constant_path),
    sin necesitar credenciales ni transport gRPC.
    """

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
    """Fake de GoogleAdsClient. `get_type` instancia mensajes protobuf REALES
    del paquete `google-ads` instalado (misma versión default que usaría el
    cliente real) para que el test verifique field-names verdaderos.
    `get_service`/`enums` son fakes livianos: instanciar un GoogleAdsServiceClient
    real dispara validación de transport/credenciales que no queremos en un
    test unitario.
    """

    def __init__(self, kpi_service: _FakeKeywordPlanIdeaService):
        self._kpi_service = kpi_service
        self.enums = SimpleNamespace(KeywordPlanNetworkEnum=_KeywordPlanNetwork)

    def get_service(self, name: str):
        if name == "GoogleAdsService":
            return _FakeGoogleAdsService()
        if name == "KeywordPlanIdeaService":
            return self._kpi_service
        raise AssertionError(f"servicio no esperado en el fake: {name}")

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
    # También neutralizar el fallback por archivo (~/.config/ga4-seo-mcp/dev-token
    # puede existir en la máquina) para ejercitar "sin token por ninguna vía".
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

    # Request bien armado: customer_id sin guiones, geo/language resource
    # names con el formato real, red default GOOGLE_SEARCH, seeds cargadas.
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
    """Cubre la normalización de GOOGLE_ADS_LOGIN_CUSTOMER_ID (con guiones)
    dentro de `_client()` — no mockeamos `_client` acá para ejercitar la
    función real, solo mockeamos `GoogleAdsClient.load_from_dict` (el punto
    exacto donde se dispararía la resolución de credenciales reales).
    """
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
    """`_run()` debe convertir GoogleAdsException en RuntimeError legible, NO
    dejar pasar el stacktrace de gRPC crudo. GoogleAdsException requiere
    (error, call, failure, request_id) reales para construirse — acá se arma
    con Nones/placeholders donde el constructor lo permite, ya que lo único
    que se ejercita es el manejo de `ex.failure.errors`.
    """
    err_types = import_module(f"google.ads.googleads.{_GADS_VERSION}.errors.types.errors")

    gads_failure = err_types.GoogleAdsFailure(
        errors=[err_types.GoogleAdsError(message="Invalid customer ID.")]
    )

    def boom(request):
        raise GoogleAdsException(None, None, gads_failure, "req-123")

    with pytest.raises(RuntimeError, match="Invalid customer ID"):
        kp._run(boom, request=object())
