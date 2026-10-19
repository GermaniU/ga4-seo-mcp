"""Secrets come only from env vars or a 0600 file, and never leak into errors."""

from __future__ import annotations

import os

import pytest

from ga4_seo_mcp import pagespeed


class _Resp:
    ok = False
    status_code = 429
    reason = "Too Many Requests"

    def json(self):
        return {"error": {"message": "Quota exceeded for quota metric 'Queries'."}}


def test_psi_error_does_not_leak_api_key(monkeypatch):
    monkeypatch.setenv("PAGESPEED_API_KEY", "AIzaFAKEKEY-for-tests")
    seen = {}

    def fake_get(url, params, timeout):
        seen["params"] = params
        return _Resp()

    monkeypatch.setattr(pagespeed.requests, "get", fake_get)
    with pytest.raises(RuntimeError) as err:
        pagespeed.psi_audit("https://example.com/?a=1&b=2")
    assert "AIzaFAKEKEY" not in str(err.value)
    assert "429" in str(err.value)
    # The target URL is sent as a parameter (encoded by requests), not glued into the query string.
    assert ("url", "https://example.com/?a=1&b=2") in seen["params"]
    assert ("key", "AIzaFAKEKEY-for-tests") in seen["params"]


def test_psi_without_key_sends_no_key(monkeypatch):
    monkeypatch.delenv("PAGESPEED_API_KEY", raising=False)
    seen = {}

    def fake_get(url, params, timeout):
        seen["params"] = params
        return _Resp()

    monkeypatch.setattr(pagespeed.requests, "get", fake_get)
    with pytest.raises(RuntimeError):
        pagespeed.psi_audit("https://example.com/")
    assert all(k != "key" for k, _ in seen["params"])


kp = pytest.importorskip("ga4_seo_mcp.keyword_planner")


def test_dev_token_file_must_be_0600(tmp_path, monkeypatch):
    token_file = tmp_path / "dev-token"
    token_file.write_text("super-secret-dev-token\n")
    monkeypatch.setattr(kp, "TOKEN_FILE", str(token_file))

    os.chmod(token_file, 0o644)
    with pytest.raises(RuntimeError, match="chmod 600") as err:
        kp._read_token_file()
    assert "super-secret" not in str(err.value)

    os.chmod(token_file, 0o600)
    assert kp._read_token_file() == "super-secret-dev-token"


def test_missing_dev_token_error_does_not_echo_env(monkeypatch, tmp_path):
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    monkeypatch.setattr(kp, "TOKEN_FILE", str(tmp_path / "absent"))
    with pytest.raises(RuntimeError, match="GOOGLE_ADS_DEVELOPER_TOKEN"):
        kp._client()
