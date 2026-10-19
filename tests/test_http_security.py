from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from ga4_seo_mcp.http_security import build_http_app, transport_security
from ga4_seo_mcp.server import build_server, parse_args

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _client(host="127.0.0.1", token=None, cors=None, allowed_hosts=None):
    mcp = build_server(("psi",), writes=False)
    app = build_http_app(
        mcp,
        "streamable-http",
        host=host,
        auth_token=token,
        cors_origins=cors,
        allowed_hosts=allowed_hosts,
    )
    return TestClient(app, base_url="http://127.0.0.1:8000")


def _post(client, headers=None, **kw):
    with client:
        return client.post("/mcp", json=INIT, headers={**HEADERS, **(headers or {})}, **kw)


def test_cli_defaults(monkeypatch):
    for var in ("MCP_HOST", "MCP_PORT", "MCP_TRANSPORT", "GA4SEO_ENABLE_WRITES", "GA4SEO_TOOLSETS"):
        monkeypatch.delenv(var, raising=False)
    args = parse_args([])
    assert args.host == "127.0.0.1"
    assert args.transport == "stdio"
    assert args.enable_writes is False
    assert args.toolsets == ("admin", "data", "gsc", "psi")


def test_enable_writes_from_env(monkeypatch):
    monkeypatch.setenv("GA4SEO_ENABLE_WRITES", "1")
    assert parse_args([]).enable_writes is True
    monkeypatch.setenv("GA4SEO_ENABLE_WRITES", "0")
    assert parse_args([]).enable_writes is False


def test_dns_rebinding_protection_on_by_default():
    settings = transport_security("127.0.0.1")
    assert settings.enable_dns_rebinding_protection is True
    assert "127.0.0.1:*" in settings.allowed_hosts


def test_non_local_host_is_added_to_allowed_hosts():
    settings = transport_security("192.0.2.10")
    assert settings.enable_dns_rebinding_protection is True
    assert "192.0.2.10:*" in settings.allowed_hosts


def test_initialize_ok_without_token():
    assert _post(_client()).status_code == 200


def test_allowed_hosts_env_lets_lan_clients_in(monkeypatch):
    # El caso real: bindear 0.0.0.0 y que el cliente conecte por la IP de la LAN.
    client = _client(host="0.0.0.0", allowed_hosts=["192.0.2.10"])
    resp = _post(client, headers={"Host": "192.0.2.10:8200"})
    assert resp.status_code == 200


def test_all_interfaces_without_allowed_hosts_warns(monkeypatch, capsys):
    _client(host="0.0.0.0")
    err = capsys.readouterr().err
    assert "MCP_ALLOWED_HOSTS" in err


def test_rebinding_host_header_rejected():
    resp = _post(_client(), headers={"Host": "evil.example.com"})
    assert resp.status_code == 421


def test_foreign_origin_rejected():
    resp = _post(_client(), headers={"Origin": "https://evil.example.com"})
    assert resp.status_code == 403


def test_401_without_token():
    resp = _post(_client(token="s3cret"))
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


def test_401_with_wrong_token():
    resp = _post(_client(token="s3cret"), headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_200_with_token():
    resp = _post(_client(token="s3cret"), headers={"Authorization": "Bearer s3cret"})
    assert resp.status_code == 200


def test_no_cors_by_default():
    resp = _post(_client(), headers={"Origin": "http://localhost:3000"})
    assert "access-control-allow-origin" not in resp.headers


def test_cors_only_for_listed_origins():
    client = _client(cors=["http://localhost:3000"])
    with client:
        ok = client.options(
            "/mcp",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
        )
        bad = client.options(
            "/mcp",
            headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
        )
    assert ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in bad.headers


def test_cors_origin_is_allowed_by_rebinding_check():
    resp = _post(
        _client(cors=["http://localhost:3000"]), headers={"Origin": "http://localhost:3000"}
    )
    assert resp.status_code == 200


@pytest.mark.parametrize("host", ["0.0.0.0", "::"])
def test_warns_when_listening_on_all_interfaces_without_token(capsys, host):
    _client(host=host)
    assert "WARNING" in capsys.readouterr().err


def test_no_warning_on_loopback(capsys):
    _client()
    assert "WARNING" not in capsys.readouterr().err
