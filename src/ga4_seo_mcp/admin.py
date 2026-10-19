"""GA4 Admin API tools: accounts, properties, data streams, key events, custom dimensions."""

from __future__ import annotations

from typing import Any

from google.analytics.admin_v1alpha import AnalyticsAdminServiceClient as AnalyticsAdminAlphaClient
from google.analytics.admin_v1alpha.types import GoogleAdsLink
from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
from google.analytics.admin_v1beta.types import (
    CustomDimension,
    DataStream,
    KeyEvent,
    ListPropertiesRequest,
    Property,
    UpdateDataStreamRequest,
    UpdatePropertyRequest,
)
from google.protobuf.field_mask_pb2 import FieldMask
from mcp.server.fastmcp import FastMCP

from .annotations import CREATE, DELETE, READ, UPDATE
from .auth import credentials
from .scopes import ANALYTICS_EDIT, ANALYTICS_READONLY


def _client(write: bool = False) -> AnalyticsAdminServiceClient:
    return AnalyticsAdminServiceClient(
        credentials=credentials(ANALYTICS_EDIT if write else ANALYTICS_READONLY)
    )


def _alpha_client(write: bool = False) -> AnalyticsAdminAlphaClient:
    # Google Ads links are only exposed by v1alpha; everything else stays on v1beta.
    return AnalyticsAdminAlphaClient(
        credentials=credentials(ANALYTICS_EDIT if write else ANALYTICS_READONLY)
    )


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


# ---------- read ----------


def list_account_summaries() -> list[dict[str, Any]]:
    """List every GA4 account you can access, with a summary of its properties.

    Start here to find the account_id and property_id the other tools need.
    """
    out = []
    for s in _client().list_account_summaries():
        out.append(
            {
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
            }
        )
    return out


def list_properties(account_id: str, include_deleted: bool = False) -> list[dict[str, Any]]:
    """List the GA4 properties under an account.

    Args:
        account_id: numeric account ID or 'accounts/123456789'.
        include_deleted: also return properties in the trash (soft-deleted, kept 35 days).
    """
    req = ListPropertiesRequest(
        filter=f"parent:{_norm_account(account_id)}",
        show_deleted=include_deleted,
    )
    return [_property_to_dict(p) for p in _client().list_properties(request=req)]


def get_property(property_id: str) -> dict[str, Any]:
    """Get the full settings of a GA4 property (time zone, currency, industry, type)."""
    return _property_to_dict(_client().get_property(name=_norm_property(property_id)))


def list_data_streams(property_id: str) -> list[dict[str, Any]]:
    """List the data streams (web, iOS, Android) of a GA4 property.

    Web streams include their measurement ID (G-XXXXXXX) and default URI.
    """
    client = _client()
    return [
        _stream_to_dict(s) for s in client.list_data_streams(parent=_norm_property(property_id))
    ]


def get_data_stream(property_id: str, stream_id: str) -> dict[str, Any]:
    """Get one data stream, including the measurement ID of a web stream."""
    client = _client()
    return _stream_to_dict(client.get_data_stream(name=_norm_stream(property_id, stream_id)))


def list_key_events(property_id: str) -> list[dict[str, Any]]:
    """List the key events (formerly conversions) declared on a GA4 property."""
    return [
        {
            "name": ke.name,
            "event_name": ke.event_name,
            "counting_method": ke.counting_method.name if ke.counting_method else None,
            "create_time": ke.create_time.isoformat() if ke.create_time else None,
        }
        for ke in _client().list_key_events(parent=_norm_property(property_id))
    ]


def list_custom_dimensions(property_id: str) -> list[dict[str, Any]]:
    """List the custom dimensions declared on a GA4 property, with their scope."""
    return [
        {
            "name": cd.name,
            "parameter_name": cd.parameter_name,
            "display_name": cd.display_name,
            "scope": cd.scope.name if cd.scope else None,
        }
        for cd in _client().list_custom_dimensions(parent=_norm_property(property_id))
    ]


def list_google_ads_links(property_id: str) -> list[dict[str, Any]]:
    """List the links between a GA4 property and Google Ads accounts."""
    return [
        _ads_link_to_dict(link)
        for link in _alpha_client().list_google_ads_links(parent=_norm_property(property_id))
    ]


# ---------- write ----------


def create_property(
    account_id: str,
    display_name: str,
    time_zone: str,
    currency_code: str,
    industry_category: str | None = None,
) -> dict[str, Any]:
    """Create a GA4 property under an account.

    Args:
        account_id: numeric account ID or 'accounts/123456789'.
        display_name: human-readable property name.
        time_zone: IANA time zone used for reporting days, e.g. 'America/Mexico_City'.
        currency_code: ISO 4217 code for revenue, e.g. 'USD' or 'MXN'.
        industry_category: optional enum name, e.g. 'TECHNOLOGY'.
    """
    prop = Property(
        parent=_norm_account(account_id),
        display_name=display_name,
        time_zone=time_zone,
        currency_code=currency_code,
    )
    if industry_category:
        prop.industry_category = industry_category  # type: ignore[assignment]
    return _property_to_dict(_client(write=True).create_property(property=prop))


def update_property(
    property_id: str,
    display_name: str | None = None,
    time_zone: str | None = None,
    currency_code: str | None = None,
) -> dict[str, Any]:
    """Change the display name, time zone or currency of a GA4 property.

    Only the fields you pass are updated. Pass at least one.
    """
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
        raise ValueError("Pass at least one field to update.")
    req = UpdatePropertyRequest(property=prop, update_mask=FieldMask(paths=paths))
    return _property_to_dict(_client(write=True).update_property(request=req))


def delete_property(property_id: str) -> dict[str, Any]:
    """Move a GA4 property to the trash.

    Google keeps it for 35 days, during which it can be restored from the GA4 UI;
    after that it is permanently deleted with all its data.
    """
    p = _client(write=True).delete_property(name=_norm_property(property_id))
    return {"deleted": True, "property": _property_to_dict(p)}


def create_web_data_stream(property_id: str, display_name: str, default_uri: str) -> dict[str, Any]:
    """Create a web data stream for a site and return its measurement ID (G-XXXXXXX).

    Args:
        default_uri: the site URL, e.g. 'https://example.com'.
    """
    stream = DataStream(
        type_=DataStream.DataStreamType.WEB_DATA_STREAM,
        display_name=display_name,
        web_stream_data=DataStream.WebStreamData(default_uri=default_uri),
    )
    created = _client(write=True).create_data_stream(
        parent=_norm_property(property_id), data_stream=stream
    )
    return _stream_to_dict(created)


def update_web_data_stream(
    property_id: str,
    stream_id: str,
    display_name: str | None = None,
    default_uri: str | None = None,
) -> dict[str, Any]:
    """Change the display name or default URI of a web data stream. Pass at least one."""
    stream = DataStream(name=_norm_stream(property_id, stream_id))
    paths = []
    if display_name is not None:
        stream.display_name = display_name
        paths.append("display_name")
    if default_uri is not None:
        stream.web_stream_data = DataStream.WebStreamData(default_uri=default_uri)
        paths.append("web_stream_data.default_uri")
    if not paths:
        raise ValueError("Pass at least one field to update.")
    req = UpdateDataStreamRequest(data_stream=stream, update_mask=FieldMask(paths=paths))
    return _stream_to_dict(_client(write=True).update_data_stream(request=req))


def delete_data_stream(property_id: str, stream_id: str) -> dict[str, str]:
    """Permanently delete a data stream. The site stops sending data to this property."""
    name = _norm_stream(property_id, stream_id)
    _client(write=True).delete_data_stream(name=name)
    return {"deleted": "true", "stream": name}


def create_key_event(
    property_id: str, event_name: str, counting: str = "ONCE_PER_EVENT"
) -> dict[str, Any]:
    """Mark an event name as a key event (formerly called a conversion).

    Args:
        event_name: e.g. 'generate_lead' or 'contact_form_submit'.
        counting: 'ONCE_PER_EVENT' (default) or 'ONCE_PER_SESSION'.
    """
    ke = KeyEvent(event_name=event_name, counting_method=KeyEvent.CountingMethod[counting])
    created = _client(write=True).create_key_event(parent=_norm_property(property_id), key_event=ke)
    return {"name": created.name, "event_name": created.event_name}


def create_custom_dimension(
    property_id: str,
    parameter_name: str,
    display_name: str,
    scope: str = "EVENT",
) -> dict[str, Any]:
    """Register an event or user parameter as a custom dimension.

    Args:
        parameter_name: the parameter sent with your events, e.g. 'plan_type'.
        display_name: letters, digits, underscores and spaces only.
        scope: 'EVENT' (default), 'USER' or 'ITEM'.
    """
    cd = CustomDimension(
        parameter_name=parameter_name,
        display_name=display_name,
        scope=CustomDimension.DimensionScope[scope],
    )
    created = _client(write=True).create_custom_dimension(
        parent=_norm_property(property_id), custom_dimension=cd
    )
    return {
        "name": created.name,
        "parameter_name": created.parameter_name,
        "display_name": created.display_name,
        "scope": created.scope.name,
    }


def create_google_ads_link(
    property_id: str,
    customer_id: str,
    ads_personalization_enabled: bool = True,
) -> dict[str, Any]:
    """Link a GA4 property to a Google Ads account.

    The link lets Google Ads import GA4 key events as conversions and build audiences.
    Google Ads can take 5-30 minutes to show the property as an import source.

    Args:
        customer_id: Google Ads customer ID, with or without dashes ('123-456-7890').
        ads_personalization_enabled: allow Google Ads to use GA4 data for personalized ads.
    """
    link = GoogleAdsLink(
        customer_id=customer_id.replace("-", "").strip(),
        ads_personalization_enabled=ads_personalization_enabled,
    )
    created = _alpha_client(write=True).create_google_ads_link(
        parent=_norm_property(property_id), google_ads_link=link
    )
    return _ads_link_to_dict(created)


def delete_google_ads_link(property_id: str, link_id: str) -> dict[str, str]:
    """Remove a link between a GA4 property and a Google Ads account.

    Args:
        link_id: the link ID from list_google_ads_links, or its full resource name.
    """
    if link_id.startswith("properties/"):
        name = link_id
    else:
        name = f"{_norm_property(property_id)}/googleAdsLinks/{link_id}"
    _alpha_client(write=True).delete_google_ads_link(name=name)
    return {"deleted": name}


READ_TOOLS = (
    list_account_summaries,
    list_properties,
    get_property,
    list_data_streams,
    get_data_stream,
    list_key_events,
    list_custom_dimensions,
    list_google_ads_links,
)
WRITE_TOOLS = {
    create_property: CREATE,
    update_property: UPDATE,
    delete_property: DELETE,
    create_web_data_stream: CREATE,
    update_web_data_stream: UPDATE,
    delete_data_stream: DELETE,
    create_key_event: CREATE,
    create_custom_dimension: CREATE,
    create_google_ads_link: CREATE,
    delete_google_ads_link: DELETE,
}


def register(mcp: FastMCP, *, writes: bool) -> None:
    for fn in READ_TOOLS:
        mcp.add_tool(fn, annotations=READ)
    if writes:
        for fn, annotations in WRITE_TOOLS.items():
            mcp.add_tool(fn, annotations=annotations)
