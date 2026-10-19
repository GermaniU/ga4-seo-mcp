"""
Tools del MCP para Google Analytics Admin API (GA4).

Cubre: cuentas, propiedades, data streams, key events, custom dimensions.
Requiere scope ADC: analytics.edit
"""

from __future__ import annotations

from typing import Any

from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
from google.analytics.admin_v1beta.types import (
    CustomDimension,
    DataStream,
    KeyEvent,
    Property,
    UpdateDataStreamRequest,
    UpdatePropertyRequest,
)
from google.analytics.admin_v1alpha import (
    AnalyticsAdminServiceClient as AnalyticsAdminAlphaClient,
)
from google.analytics.admin_v1alpha.types import GoogleAdsLink
from google.protobuf.field_mask_pb2 import FieldMask

from .mcp_app import mcp


# ---------- helpers ----------

def _client() -> AnalyticsAdminServiceClient:
    return AnalyticsAdminServiceClient()


def _alpha_client() -> AnalyticsAdminAlphaClient:
    """Cliente v1alpha. Necesario para recursos que aún no migraron a v1beta
    (ej. GoogleAdsLinks). Mantenemos v1beta como default para todo lo demás."""
    return AnalyticsAdminAlphaClient()


def _norm_account(account_id: str) -> str:
    return account_id if account_id.startswith("accounts/") else f"accounts/{account_id}"


def _norm_property(property_id: str) -> str:
    return property_id if property_id.startswith("properties/") else f"properties/{property_id}"


def _norm_stream(property_id: str, stream_id: str) -> str:
    if stream_id.startswith("properties/"):
        return stream_id
    return f"{_norm_property(property_id)}/dataStreams/{stream_id}"


def _property_to_dict(p: Property) -> dict[str, Any]:
    return {
        "name": p.name,
        "property_id": p.name.split("/")[-1] if p.name else None,
        "parent": p.parent,
        "display_name": p.display_name,
        "time_zone": p.time_zone,
        "currency_code": p.currency_code,
        "industry_category": p.industry_category.name if p.industry_category else None,
        "property_type": p.property_type.name if p.property_type else None,
        "create_time": p.create_time.isoformat() if p.create_time else None,
        "delete_time": p.delete_time.isoformat() if p.delete_time else None,
    }


def _stream_to_dict(s: DataStream) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": s.name,
        "stream_id": s.name.split("/")[-1] if s.name else None,
        "display_name": s.display_name,
        "type": s.type_.name if s.type_ else None,
        "create_time": s.create_time.isoformat() if s.create_time else None,
    }
    if s.web_stream_data and s.web_stream_data.default_uri:
        out["web"] = {
            "default_uri": s.web_stream_data.default_uri,
            "measurement_id": s.web_stream_data.measurement_id,
            "firebase_app_id": s.web_stream_data.firebase_app_id,
        }
    if s.android_app_stream_data and s.android_app_stream_data.package_name:
        out["android"] = {"package_name": s.android_app_stream_data.package_name}
    if s.ios_app_stream_data and s.ios_app_stream_data.bundle_id:
        out["ios"] = {"bundle_id": s.ios_app_stream_data.bundle_id}
    return out


# ---------- tools: lectura cuentas/propiedades ----------

@mcp.tool()
def list_account_summaries() -> list[dict[str, Any]]:
    """Lista todas las cuentas GA accesibles + un resumen de sus propiedades."""
    client = _client()
    out = []
    for s in client.list_account_summaries():
        out.append({
            "account": s.account,
            "account_id": s.account.split("/")[-1] if s.account else None,
            "display_name": s.display_name,
            "property_summaries": [
                {
                    "property": p.property,
                    "property_id": p.property.split("/")[-1] if p.property else None,
                    "display_name": p.display_name,
                    "property_type": p.property_type.name if p.property_type else None,
                    "parent": p.parent,
                }
                for p in s.property_summaries
            ],
        })
    return out


@mcp.tool()
def list_properties(account_id: str, include_deleted: bool = False) -> list[dict[str, Any]]:
    """Lista propiedades bajo una cuenta GA."""
    from google.analytics.admin_v1beta.types import ListPropertiesRequest
    client = _client()
    req = ListPropertiesRequest(
        filter=f"parent:{_norm_account(account_id)}",
        show_deleted=include_deleted,
    )
    return [_property_to_dict(p) for p in client.list_properties(request=req)]


@mcp.tool()
def get_property(property_id: str) -> dict[str, Any]:
    """Detalles completos de una propiedad GA4."""
    client = _client()
    return _property_to_dict(client.get_property(name=_norm_property(property_id)))


@mcp.tool()
def list_data_streams(property_id: str) -> list[dict[str, Any]]:
    """Lista data streams (web/iOS/Android) de una propiedad."""
    client = _client()
    return [_stream_to_dict(s) for s in client.list_data_streams(parent=_norm_property(property_id))]


@mcp.tool()
def get_data_stream(property_id: str, stream_id: str) -> dict[str, Any]:
    """Detalle de un stream (incluye measurement_id para GA4 web)."""
    client = _client()
    return _stream_to_dict(client.get_data_stream(name=_norm_stream(property_id, stream_id)))


# ---------- tools: escritura propiedades/streams ----------

@mcp.tool()
def create_property(
    account_id: str,
    display_name: str,
    time_zone: str = "America/Mexico_City",
    currency_code: str = "MXN",
    industry_category: str | None = None,
) -> dict[str, Any]:
    """Crea una propiedad GA4 bajo una cuenta."""
    client = _client()
    prop = Property(
        parent=_norm_account(account_id),
        display_name=display_name,
        time_zone=time_zone,
        currency_code=currency_code,
    )
    if industry_category:
        prop.industry_category = industry_category  # type: ignore[assignment]
    return _property_to_dict(client.create_property(property=prop))


@mcp.tool()
def update_property(
    property_id: str,
    display_name: str | None = None,
    time_zone: str | None = None,
    currency_code: str | None = None,
) -> dict[str, Any]:
    """Actualiza campos editables de una propiedad."""
    client = _client()
    prop = Property(name=_norm_property(property_id))
    paths = []
    if display_name is not None:
        prop.display_name = display_name
        paths.append("display_name")
    if time_zone is not None:
        prop.time_zone = time_zone
        paths.append("time_zone")
    if currency_code is not None:
        prop.currency_code = currency_code
        paths.append("currency_code")
    if not paths:
        raise ValueError("Debes pasar al menos un campo a actualizar.")
    req = UpdatePropertyRequest(property=prop, update_mask=FieldMask(paths=paths))
    return _property_to_dict(client.update_property(request=req))


@mcp.tool()
def delete_property(property_id: str) -> dict[str, Any]:
    """Soft-delete (papelera 35 días) de una propiedad GA4."""
    client = _client()
    p = client.delete_property(name=_norm_property(property_id))
    return {"deleted": True, "property": _property_to_dict(p)}


@mcp.tool()
def create_web_data_stream(property_id: str, display_name: str, default_uri: str) -> dict[str, Any]:
    """Crea un data stream web (sitio) en una propiedad GA4."""
    client = _client()
    stream = DataStream(
        type_=DataStream.DataStreamType.WEB_DATA_STREAM,
        display_name=display_name,
        web_stream_data=DataStream.WebStreamData(default_uri=default_uri),
    )
    return _stream_to_dict(client.create_data_stream(parent=_norm_property(property_id), data_stream=stream))


@mcp.tool()
def update_web_data_stream(
    property_id: str,
    stream_id: str,
    display_name: str | None = None,
    default_uri: str | None = None,
) -> dict[str, Any]:
    """Actualiza nombre o default_uri de un stream web."""
    client = _client()
    stream = DataStream(name=_norm_stream(property_id, stream_id))
    paths = []
    if display_name is not None:
        stream.display_name = display_name
        paths.append("display_name")
    if default_uri is not None:
        stream.web_stream_data = DataStream.WebStreamData(default_uri=default_uri)
        paths.append("web_stream_data.default_uri")
    if not paths:
        raise ValueError("Debes pasar al menos un campo a actualizar.")
    req = UpdateDataStreamRequest(data_stream=stream, update_mask=FieldMask(paths=paths))
    return _stream_to_dict(client.update_data_stream(request=req))


@mcp.tool()
def delete_data_stream(property_id: str, stream_id: str) -> dict[str, str]:
    """Borra (definitivo) un data stream."""
    client = _client()
    client.delete_data_stream(name=_norm_stream(property_id, stream_id))
    return {"deleted": "true", "stream": _norm_stream(property_id, stream_id)}


# ---------- tools: Key Events y Custom Dimensions ----------

@mcp.tool()
def list_key_events(property_id: str) -> list[dict[str, Any]]:
    """Lista key events (conversions) declarados en la propiedad."""
    client = _client()
    return [
        {
            "name": ke.name,
            "event_name": ke.event_name,
            "counting_method": ke.counting_method.name if ke.counting_method else None,
            "create_time": ke.create_time.isoformat() if ke.create_time else None,
        }
        for ke in client.list_key_events(parent=_norm_property(property_id))
    ]


@mcp.tool()
def create_key_event(property_id: str, event_name: str, counting: str = "ONCE_PER_EVENT") -> dict[str, Any]:
    """
    Marca un event_name como key event (conversion).

    Args:
        event_name: ej. 'contact_form_submit', 'click_plan_cta'.
        counting: 'ONCE_PER_EVENT' (default) o 'ONCE_PER_SESSION'.
    """
    client = _client()
    ke = KeyEvent(
        event_name=event_name,
        counting_method=KeyEvent.CountingMethod[counting],
    )
    created = client.create_key_event(parent=_norm_property(property_id), key_event=ke)
    return {"name": created.name, "event_name": created.event_name}


@mcp.tool()
def list_custom_dimensions(property_id: str) -> list[dict[str, Any]]:
    """Lista custom dimensions declaradas en la propiedad."""
    client = _client()
    return [
        {
            "name": cd.name,
            "parameter_name": cd.parameter_name,
            "display_name": cd.display_name,
            "scope": cd.scope.name if cd.scope else None,
        }
        for cd in client.list_custom_dimensions(parent=_norm_property(property_id))
    ]


@mcp.tool()
def create_custom_dimension(
    property_id: str,
    parameter_name: str,
    display_name: str,
    scope: str = "EVENT",
) -> dict[str, Any]:
    """
    Crea una custom dimension.

    Args:
        parameter_name: nombre técnico (ej. 'tenant_id', 'lead_source').
        display_name: solo letras, números, underscore o espacio (sin acentos ni paréntesis).
        scope: 'EVENT' (default), 'USER' o 'ITEM'.
    """
    client = _client()
    cd = CustomDimension(
        parameter_name=parameter_name,
        display_name=display_name,
        scope=CustomDimension.DimensionScope[scope],
    )
    created = client.create_custom_dimension(parent=_norm_property(property_id), custom_dimension=cd)
    return {
        "name": created.name,
        "parameter_name": created.parameter_name,
        "display_name": created.display_name,
        "scope": created.scope.name,
    }


# ---------- Google Ads Links (v1alpha) ----------
# Vincular GA4 ↔ Google Ads habilita 2 cosas críticas que la UI a veces no
# permite hacer fácil (sobre todo cuando la cuenta Ads no aparece en GA4):
#   1. Importar key events GA4 como conversion actions en Google Ads
#   2. Audiencias remarketing basadas en eventos GA4
#
# Pasos típicos post-link (manual UI, no API):
#   - Activar Auto-tagging en Google Ads → Settings (cross-domain attribution)
#   - Google Ads → Conversions → +Crear → Importar → GA4 (Web) → seleccionar eventos

def _ads_link_to_dict(link: GoogleAdsLink) -> dict[str, Any]:
    return {
        "name": link.name,
        "link_id": link.name.split("/")[-1] if link.name else None,
        "customer_id": link.customer_id,
        "ads_personalization_enabled": link.ads_personalization_enabled,
        "can_manage_clients": link.can_manage_clients,
        "creator_email_address": link.creator_email_address,
        "create_time": link.create_time.isoformat() if link.create_time else None,
        "update_time": link.update_time.isoformat() if link.update_time else None,
    }


@mcp.tool()
def list_google_ads_links(property_id: str) -> list[dict[str, Any]]:
    """Lista vínculos GA4 ↔ Google Ads de la propiedad."""
    client = _alpha_client()
    return [
        _ads_link_to_dict(link)
        for link in client.list_google_ads_links(parent=_norm_property(property_id))
    ]


@mcp.tool()
def create_google_ads_link(
    property_id: str,
    customer_id: str,
    ads_personalization_enabled: bool = True,
) -> dict[str, Any]:
    """
    Vincula una propiedad GA4 con una cuenta de Google Ads.

    Args:
        property_id: ID GA4 (ej. '123456789' o 'properties/123456789').
        customer_id: ID Google Ads. Acepta con o sin guiones
            (ej. '123-456-7890' o '1234567890').
        ads_personalization_enabled: si Google Ads puede usar datos GA4 para
            audiencias personalizadas. Default True.

    Returns:
        Datos del link creado incluyendo `link_id` para futuro delete.

    Notas operativas:
        - Tras crear el link, Google Ads tarda 5-30 min en mostrar la propiedad
          GA4 como fuente importable en su pantalla de Conversions.
        - Auto-tagging y la importación de conversion actions específicas
          siguen siendo UI manual (requieren Google Ads API con developer
          token aparte, no cubierto por ADC actual).
    """
    client = _alpha_client()
    cid = customer_id.replace("-", "").strip()
    link = GoogleAdsLink(
        customer_id=cid,
        ads_personalization_enabled=ads_personalization_enabled,
    )
    created = client.create_google_ads_link(
        parent=_norm_property(property_id),
        google_ads_link=link,
    )
    return _ads_link_to_dict(created)


@mcp.tool()
def delete_google_ads_link(property_id: str, link_id: str) -> dict[str, str]:
    """
    Elimina un vínculo GA4 ↔ Google Ads.

    Args:
        property_id: ID GA4.
        link_id: ID del link (ej. '1234567890'). También acepta el
            resource name completo (ej. 'properties/123456789/googleAdsLinks/...').
    """
    client = _alpha_client()
    if link_id.startswith("properties/"):
        name = link_id
    else:
        name = f"{_norm_property(property_id)}/googleAdsLinks/{link_id}"
    client.delete_google_ads_link(name=name)
    return {"deleted": name}
