"""
Tools del MCP para Google Ads API (Keyword Planner) — keyword research desde la
fuente "oficial" de Google, a diferencia de `keywords_dataforseo.py` (Fase 1,
third-party, ya mergeado).

Nombres definitivos `kw_ideas_gads` / `kw_volume_gads` (el sufijo `_gads` los
distingue de `kw_ideas`/`kw_volume` de DataForSEO — FastMCP no admite dos tools
con el mismo nombre). DECIDIDO tras validar con developer token real (2026-07-18): Google Ads y DataForSEO CONVIVEN, no se reemplazan — Google Ads da
volumen BUCKETED pero es gratis y trae `competition`/CPC "oficiales"; DataForSEO
da volumen EXACTO en long-tail es-MX (de pago). Este módulo NO toca
`keywords_dataforseo.py`.

Cubre:
- `kw_ideas_gads`  — descubrimiento de keywords long-tail a partir de seeds,
  vía `KeywordPlanIdeaService.GenerateKeywordIdeas`.
- `kw_volume_gads` — métricas históricas para queries YA CONOCIDAS, vía
  `KeywordPlanIdeaService.GenerateKeywordHistoricalMetrics` (mismo servicio,
  otro RPC).

Auth: paquete `google-ads`, cliente `GoogleAdsClient` con Application Default
Credentials — mismo mecanismo ADC que `admin.py`/`data.py` (NO HTTP Basic Auth
como DataForSEO). Requiere el developer token (env var `GOOGLE_ADS_DEVELOPER_TOKEN`
con precedencia, o el archivo `~/.config/ga4-seo-mcp/dev-token`). Opcional
`GOOGLE_ADS_LOGIN_CUSTOMER_ID` (solo si se opera bajo una cuenta manager/MCC —
NO hace falta para una cuenta accesible directo por el usuario OAuth). Scope
OAuth `https://www.googleapis.com/auth/adwords` agregado a `scripts/auth-v2.sh`.

────────────────────────────────────────────────────────────────────────────
✅ VALIDADO E2E CON DEVELOPER TOKEN BASIC (2026-07-18)
────────────────────────────────────────────────────────────────────────────
El token Basic se aprobó el 2026-07-17; el smoke test real (cuenta de
prueba, acceso directo, sin login_customer_id) validó el flujo completo
contra `googleads.googleapis.com`. Lo que ya se había verificado antes por
introspección estática del paquete `google-ads` 31.1.0 instalado (leyendo el
.proto compilado, no una llamada a Google):

  - El shape del protobuf (nombres de campo, tipos) coincide con la respuesta
    real — `keyword_plan_idea_service`, `keyword_plan_common`, etc.
  - Que `use_application_default_credentials=True` hace que el cliente pida
    credenciales vía `google.auth.default(scopes=[".../auth/adwords"])`,
    reutilizando el mismo ADC storage que `admin.py`/`data.py` una vez que
    `auth-v2.sh` corre con el scope `adwords`.
  - Que la config dict requiere `developer_token` Y `use_proto_plus` (hallado
    en `google/ads/googleads/config.py:_REQUIRED_KEYS`, no en la doc pública).

El estado de cada punto validado/pendiente está en la lista consolidada al
final de este docstring y marcado inline (`# VALIDADO(...)` / `# TODO`).

⚠️ HALLAZGO DE VOLUMEN (resuelto con el token real): `avg_monthly_searches`
viene BUCKETED — redondeado a los buckets canónicos del Keyword Planner (10,
30, 50, 70, 170, 210, 3600, …), igual que la UI de Google Ads, porque la cuenta
no tiene gasto activo. NO es volumen exacto. Por eso Google Ads NO reemplaza a
DataForSEO (que sí da el número exacto en long-tail es-MX): se complementan.
Google Ads = gratis + `competition`/CPC oficiales para comparación relativa;
DataForSEO = el número exacto cuando la decisión lo pide.

Estado de validación (smoke 2026-07-18 con token Basic):
  1. Auth ADC E2E ......................... ✅ OK (sin login_customer_id)
  2. Cuenta sin campañas/gasto aceptada ... ✅ OK
  3. Volumen exacto-vs-bucketed ........... ✅ RESUELTO → bucketed (arriba)
  6. Geo/language IDs (2484 MX / 1003 ES).. ✅ OK (resultados es-MX coherentes)
  4. Tope real de GenerateKeywordIdeas .... ⏳ cota 1000 conservadora, máx real sin exigir
  5. Formato de GoogleAdsException real .... ⏳ sin ejercitar (ver `# TODO` en `_run`)
"""

from __future__ import annotations

import itertools
import os
from typing import Any

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

from .mcp_app import mcp


# VALIDADO(2026-07-18): 2484 (México) / 1003 (español) confirmados contra la
# API real — devuelven resultados es-MX coherentes.
DEFAULT_LOCATION_ID_MX = "2484"
DEFAULT_LANGUAGE_ID_ES = "1003"

# Tope conservador para `page_size` en kw_ideas_gads — NO confirmado contra la
# doc específica de GenerateKeywordIdeas (ver TODO en la función).
_MAX_PAGE_SIZE = 1000

# El developer token es un secreto: se lee del env var GOOGLE_ADS_DEVELOPER_TOKEN
# (precedencia) o, si falta, de ~/.config/ga4-seo-mcp/dev-token (chmod 600, fuera
# del repo y fuera de ~/.claude.json). Así el MCP funciona sin poner el secreto en
# texto plano en la config del cliente MCP. Ver README paso 7.
_TOKEN_FILE = os.path.expanduser("~/.config/ga4-seo-mcp/dev-token")


def _read_token_file() -> str | None:
    """Lee el developer token del archivo local si existe. Devuelve None ante
    cualquier problema (archivo ausente/ilegible) para que `_client()` levante
    el mismo RuntimeError claro que cuando falta el env var."""
    try:
        with open(_TOKEN_FILE, encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def _client() -> GoogleAdsClient:
    """Construye el GoogleAdsClient vía ADC. Mismo estilo de error temprano y
    claro que `keywords_dataforseo._auth()` — falla ANTES de tocar la red si
    falta el developer token.
    """
    developer_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN") or _read_token_file()
    if not developer_token:
        raise RuntimeError(
            "Falta el developer token: definí GOOGLE_ADS_DEVELOPER_TOKEN en el "
            "entorno o dejá el token en ~/.config/ga4-seo-mcp/dev-token. Sin un "
            "developer token aprobado por Google Ads, la API rechaza cualquier "
            "request (ver https://developers.google.com/google-ads/api/docs/get-started/dev-token)."
        )

    config: dict[str, Any] = {
        "developer_token": developer_token,
        "use_proto_plus": True,
        "use_application_default_credentials": True,
    }

    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
    if login_customer_id:
        # Mismo criterio de normalización que create_google_ads_link() en
        # admin.py: acepta el ID con o sin guiones.
        config["login_customer_id"] = login_customer_id.replace("-", "").strip()

    # VALIDADO(2026-07-18): con el token Basic aprobado y el scope
    # `adwords` en el ADC, `google.auth.default()` autentica E2E sin necesidad
    # de `login_customer_id` para una cuenta accesible directo por el usuario
    # OAuth (confirmado contra la API real).
    return GoogleAdsClient.load_from_dict(config)


def _run(fn: Any, *, request: Any) -> Any:
    """Ejecuta una llamada RPC envolviendo `GoogleAdsException` en un
    RuntimeError legible — mismo espíritu que `_post()` en
    keywords_dataforseo.py (no dejar pasar un stacktrace opaco de gRPC).
    """
    try:
        return fn(request=request)
    except GoogleAdsException as ex:
        # TODO(validar-con-token): el smoke E2E (2026-07-18) NO disparó un
        # GoogleAdsException real (todas las llamadas fueron 200). `error.message`
        # es un string simple (confirmado por introspección del .proto), pero
        # `error.error_code` es un oneof de ~169 variantes — acá se usa su repr
        # por defecto en vez de extraer el campo exacto. Confirmar que el repr
        # sea legible la primera vez que se dispare un error real.
        details = "; ".join(
            f"{err.message} ({err.error_code})" for err in ex.failure.errors
        )
        raise RuntimeError(f"Google Ads API error: {details or ex}") from ex


def _historical_metrics_to_dict(text: str, metrics: Any | None) -> dict[str, Any]:
    """Normaliza un `KeywordPlanHistoricalMetrics` — mensaje COMPARTIDO entre
    `GenerateKeywordIdeaResult.keyword_idea_metrics` y
    `GenerateKeywordHistoricalMetricsResult.keyword_metrics` (mismo tipo
    protobuf en ambos RPCs, confirmado por introspección) — a un dict plano.

    Shape confirmado leyendo el .proto instalado y validado contra la respuesta
    real: avg_monthly_searches (int64), competition (enum
    KeywordPlanCompetitionLevel: UNSPECIFIED/UNKNOWN/LOW/MEDIUM/HIGH — los
    enums proto-plus siempre exponen `.name`, nunca son None, aunque el valor
    sea el default UNSPECIFIED), competition_index (int64, 0-100 según doc),
    low/high_top_of_page_bid_micros (int64, se convierten a unidad de moneda
    de la cuenta dividiendo /1_000_000 — convención estándar de Google Ads
    para todo campo `*_micros`).

    # VALIDADO(2026-07-18): con el token real, avg_monthly_searches viene
    # BUCKETED (redondeado a los buckets canónicos del Keyword Planner: 10, 30,
    # 50, 70, 170, 210, 3600, …) sin gasto activo — ver docstring del módulo.
    # Nota proto3: un avg_monthly_searches=0 aparece con competition=UNSPECIFIED
    # (keyword sin volumen suficiente); no hay forma a nivel wire de distinguir
    # "0 búsquedas" de "sin dato", pero el UNSPECIFIED lo señala en la práctica.
    """
    if metrics is None:
        return {
            "keyword": text,
            "avg_monthly_searches": None,
            "competition": None,
            "competition_index": None,
            "low_top_of_page_bid": None,
            "high_top_of_page_bid": None,
        }
    return {
        "keyword": text,
        "avg_monthly_searches": metrics.avg_monthly_searches,
        "competition": metrics.competition.name,
        "competition_index": metrics.competition_index,
        "low_top_of_page_bid": metrics.low_top_of_page_bid_micros / 1_000_000,
        "high_top_of_page_bid": metrics.high_top_of_page_bid_micros / 1_000_000,
    }


@mcp.tool()
def kw_ideas_gads(
    customer_id: str,
    keywords: list[str],
    location_id: str = DEFAULT_LOCATION_ID_MX,
    language_id: str = DEFAULT_LANGUAGE_ID_ES,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Descubrimiento de keywords long-tail vía Google Ads API
    (`KeywordPlanIdeaService.GenerateKeywordIdeas`) — la fuente "oficial" de
    Keyword Planner, a diferencia de `kw_ideas` (DataForSEO, third-party,
    Fase 1). ⚠️ El volumen viene BUCKETED (ver docstring del módulo); para el
    número exacto en long-tail usar `kw_ideas` (DataForSEO).

    Args:
        customer_id: ID de cuenta Google Ads (10 dígitos, con o sin guiones)
            bajo la cual corre la consulta. Keyword Planner NO requiere que
            la cuenta tenga campañas activas ni gasto — cualquier cuenta Ads
            accesible por el developer token sirve. Obligatorio: la API
            rechaza el request sin un customer_id válido.
        keywords: seeds de búsqueda (ej. ['restaurante cdmx', 'comida a domicilio']).
        location_id: geo target constant ID (default '2484' = México).
        language_id: language constant ID (default '1003' = español).
        limit: máximo de resultados a devolver (default 50). Se aplica
            client-side con `itertools.islice` sobre la respuesta — el
            request SÍ tiene `page_size`/`page_token` (confirmado por
            introspección), pero `page_size` controla el tamaño de cada
            página, no el total, así que igual hace falta cortar del lado
            del cliente para respetar `limit`.

    Devuelve lista de dicts normalizados: keyword, avg_monthly_searches,
    competition, competition_index, low_top_of_page_bid, high_top_of_page_bid
    (bid ya convertido de micros a unidad de moneda de la cuenta).
    """
    # VALIDADO(2026-07-18): flujo E2E confirmado contra la API real.
    client = _client()
    google_ads_service = client.get_service("GoogleAdsService")
    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id.replace("-", "").strip()
    request.language = google_ads_service.language_constant_path(language_id)
    request.geo_target_constants.append(
        google_ads_service.geo_target_constant_path(location_id)
    )
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    request.keyword_seed.keywords.extend(keywords)
    request.page_size = min(limit, _MAX_PAGE_SIZE)

    response = _run(keyword_plan_idea_service.generate_keyword_ideas, request=request)

    return [
        _historical_metrics_to_dict(idea.text, idea.keyword_idea_metrics)
        for idea in itertools.islice(response, limit)
    ]


@mcp.tool()
def kw_volume_gads(
    customer_id: str,
    keywords: list[str],
    location_id: str = DEFAULT_LOCATION_ID_MX,
    language_id: str = DEFAULT_LANGUAGE_ID_ES,
) -> list[dict[str, Any]]:
    """
    Métricas históricas para queries YA CONOCIDAS, vía
    `KeywordPlanIdeaService.GenerateKeywordHistoricalMetrics` (mismo servicio
    que `kw_ideas_gads`, otro RPC) — análogo a `kw_volume` (DataForSEO, Fase 1)
    pero con datos "oficiales" de Google Ads.

    A diferencia de `kw_ideas_gads`, no descubre keywords nuevas y el request
    no tiene `page_size`/`page_token` (confirmado por introspección — no está
    paginado), así que no expone `limit`, igual que `kw_volume` de Fase 1.

    Args:
        customer_id: igual que en kw_ideas_gads.
        keywords: queries exactas a consultar.
        location_id: ver kw_ideas_gads.
        language_id: ver kw_ideas_gads.

    Devuelve lista de dicts: keyword, avg_monthly_searches, competition,
    competition_index, low_top_of_page_bid, high_top_of_page_bid.

    ⚠️ El volumen viene BUCKETED (buckets canónicos del Keyword Planner, ver
    docstring del módulo) porque la cuenta no tiene gasto activo — es dato de
    Google "oficial" pero redondeado. Para el número EXACTO en long-tail es-MX
    usar `kw_volume` (DataForSEO). Los dos conviven a propósito.
    """
    # VALIDADO(2026-07-18): flujo E2E confirmado contra la API real.
    client = _client()
    google_ads_service = client.get_service("GoogleAdsService")
    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordHistoricalMetricsRequest")
    request.customer_id = customer_id.replace("-", "").strip()
    request.keywords.extend(keywords)
    request.language = google_ads_service.language_constant_path(language_id)
    request.geo_target_constants.append(
        google_ads_service.geo_target_constant_path(location_id)
    )
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

    response = _run(
        keyword_plan_idea_service.generate_keyword_historical_metrics,
        request=request,
    )

    return [
        _historical_metrics_to_dict(result.text, result.keyword_metrics)
        for result in response.results
    ]
