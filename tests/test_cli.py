from __future__ import annotations

import pytest
from google.auth.exceptions import DefaultCredentialsError

from ga4_seo_mcp import doctor
from ga4_seo_mcp.server import main


def test_auth_command_prints_minimum_scopes(capsys):
    main(["auth-command", "--toolsets", "data"])
    out = capsys.readouterr().out.strip()
    assert out == (
        "gcloud auth application-default login --scopes="
        "https://www.googleapis.com/auth/cloud-platform,"
        "https://www.googleapis.com/auth/analytics.readonly"
    )


def test_auth_command_honors_enable_writes(capsys):
    main(["auth-command", "--toolsets", "gsc", "--enable-writes"])
    out = capsys.readouterr().out
    assert "auth/webmasters," in out and "siteverification" in out


def test_unknown_toolset_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["auth-command", "--toolsets", "nope"])
    assert exc.value.code == 2
    assert "unknown toolset" in capsys.readouterr().err


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out.startswith("ga4-seo-mcp ")


def test_doctor_without_credentials_fails_with_fix(monkeypatch, capsys):
    def no_creds(scopes=None):
        raise DefaultCredentialsError("Your default credentials were not found.")

    monkeypatch.setattr(doctor.google.auth, "default", no_creds)
    monkeypatch.delenv("PAGESPEED_API_KEY", raising=False)
    code = doctor.run_doctor(("admin", "psi"), writes=False)
    out = capsys.readouterr().out
    assert code == 1
    assert "[fail] no Google credentials" in out
    assert "gcloud auth application-default login" in out
    assert "[ok] psi" in out


def test_doctor_psi_only_needs_no_credentials(monkeypatch, capsys):
    def must_not_be_called(scopes=None):
        raise AssertionError("psi needs no Google login")

    monkeypatch.setattr(doctor.google.auth, "default", must_not_be_called)
    assert doctor.run_doctor(("psi",), writes=False) == 0
    assert "all checks passed" in capsys.readouterr().out


def test_doctor_unreadable_credentials_file_is_reported(monkeypatch, capsys):
    def unreadable(scopes=None):
        raise PermissionError(13, "Permission denied", "/creds/credentials.json")

    monkeypatch.setattr(doctor.google.auth, "default", unreadable)
    assert doctor.run_doctor(("admin",), writes=False) == 1
    assert "[fail] cannot read the credentials file" in capsys.readouterr().out


def test_doctor_does_not_leak_the_access_token_on_network_error(monkeypatch, capsys):
    class FakeCreds:
        token = "SECRET_TOKEN_XYZ"

        def refresh(self, request=None):
            pass

    monkeypatch.setattr(doctor.google.auth, "default", lambda *a, **k: (FakeCreds(), "project"))

    def boom(*a, **k):
        raise doctor.requests.exceptions.ConnectionError(
            "Max retries exceeded with url: "
            "/tokeninfo?access_token=SECRET_TOKEN_XYZ (Caused by ConnectTimeoutError)"
        )

    monkeypatch.setattr(doctor.requests, "get", boom)
    assert doctor.run_doctor(("data",), writes=False) == 1
    captured = capsys.readouterr()
    assert "SECRET_TOKEN_XYZ" not in captured.out
    assert "SECRET_TOKEN_XYZ" not in captured.err
    assert "could not read the token scopes" in captured.out
