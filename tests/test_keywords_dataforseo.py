"""DataForSEO module tests. Everything is mocked (`requests.post`): no credit is spent."""

from __future__ import annotations

import pytest

from ga4_seo_mcp import keywords_dataforseo as kwds


class _FakeResponse:
    def __init__(self, json_data: dict, status: int = 200):
        self._json_data = json_data
        self.status_code = status
        self.ok = status < 400
        self.reason = "Error" if status >= 400 else "OK"

    def json(self) -> dict:
        return self._json_data


KEYWORD_IDEAS_OK = {
    "status_code": 20000,
    "status_message": "Ok.",
    "tasks": [
        {
            "status_code": 20000,
            "status_message": "Ok.",
            "result": [
                {
                    "items": [
                        {
                            "keyword": "restaurante cerca de mi",
                            "keyword_info": {
                                "search_volume": 12100,
                                "competition": 0.34,
                                "competition_level": "LOW",
                                "cpc": 0.55,
                            },
                        },
                        {
                            "keyword": "comida a domicilio cdmx",
                            "keyword_info": {
                                "search_volume": 8100,
                                "competition": 0.61,
                                "competition_level": "MEDIUM",
                                "cpc": 0.72,
                            },
                        },
                    ],
                    "total_count": 2,
                }
            ],
        }
    ],
}

SEARCH_VOLUME_OK = {
    "status_code": 20000,
    "status_message": "Ok.",
    "tasks": [
        {
            "status_code": 20000,
            "status_message": "Ok.",
            "result": [
                {
                    "keyword": "restaurante cdmx",
                    "spell": None,
                    "competition": "HIGH",
                    "competition_index": 100,
                    "search_volume": 5400,
                    "cpc": 1.23,
                    "monthly_searches": [
                        {"year": 2026, "month": 6, "search_volume": 5100},
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture(autouse=True)
def _dataforseo_env(monkeypatch):
    monkeypatch.setenv("DATAFORSEO_LOGIN", "test-login")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "test-password")


def test_kw_ideas_normalizes_response(monkeypatch):
    def fake_post(url, json, auth, timeout):
        assert url == f"{kwds.DATAFORSEO_BASE}/v3/dataforseo_labs/google/keyword_ideas/live"
        assert auth == ("test-login", "test-password")
        return _FakeResponse(KEYWORD_IDEAS_OK)

    monkeypatch.setattr(kwds.requests, "post", fake_post)

    result = kwds.kw_ideas(keywords=["restaurante"], limit=2)

    assert result == [
        {
            "keyword": "restaurante cerca de mi",
            "search_volume": 12100,
            "competition": 0.34,
            "competition_level": "LOW",
            "cpc": 0.55,
        },
        {
            "keyword": "comida a domicilio cdmx",
            "search_volume": 8100,
            "competition": 0.61,
            "competition_level": "MEDIUM",
            "cpc": 0.72,
        },
    ]


def test_kw_volume_normalizes_response(monkeypatch):
    def fake_post(url, json, auth, timeout):
        assert url == f"{kwds.DATAFORSEO_BASE}/v3/keywords_data/google_ads/search_volume/live"
        return _FakeResponse(SEARCH_VOLUME_OK)

    monkeypatch.setattr(kwds.requests, "post", fake_post)

    result = kwds.kw_volume(keywords=["restaurante cdmx"])

    assert result == [
        {
            "keyword": "restaurante cdmx",
            "search_volume": 5400,
            "cpc": 1.23,
            "competition": "HIGH",
            "monthly_searches": [{"year": 2026, "month": 6, "search_volume": 5100}],
        }
    ]


def test_kw_ideas_missing_env_vars_raises_clear_error(monkeypatch):
    monkeypatch.delenv("DATAFORSEO_LOGIN", raising=False)
    monkeypatch.delenv("DATAFORSEO_PASSWORD", raising=False)

    def fake_post(*args, **kwargs):
        raise AssertionError("must not hit the network without credentials")

    monkeypatch.setattr(kwds.requests, "post", fake_post)

    with pytest.raises(RuntimeError, match="DATAFORSEO_LOGIN"):
        kwds.kw_ideas(keywords=["restaurante"])


def test_kw_volume_missing_password_raises_clear_error(monkeypatch):
    monkeypatch.delenv("DATAFORSEO_PASSWORD", raising=False)

    def fake_post(*args, **kwargs):
        raise AssertionError("must not hit the network without credentials")

    monkeypatch.setattr(kwds.requests, "post", fake_post)

    with pytest.raises(RuntimeError, match="DATAFORSEO_LOGIN/DATAFORSEO_PASSWORD"):
        kwds.kw_volume(keywords=["restaurante cdmx"])


def test_top_level_status_code_error_raises_with_api_message(monkeypatch):
    error_response = {
        "status_code": 40101,
        "status_message": "Authentication failed.",
        "tasks": [],
    }

    def fake_post(url, json, auth, timeout):
        return _FakeResponse(error_response)

    monkeypatch.setattr(kwds.requests, "post", fake_post)

    with pytest.raises(RuntimeError, match="Authentication failed"):
        kwds.kw_ideas(keywords=["restaurante"])


def test_task_status_code_error_raises_with_api_message(monkeypatch):
    error_response = {
        "status_code": 20000,
        "status_message": "Ok.",
        "tasks": [
            {
                "status_code": 40501,
                "status_message": "Invalid Field: 'keywords'.",
                "result": None,
            }
        ],
    }

    def fake_post(url, json, auth, timeout):
        return _FakeResponse(error_response)

    monkeypatch.setattr(kwds.requests, "post", fake_post)

    with pytest.raises(RuntimeError, match="Invalid Field"):
        kwds.kw_volume(keywords=["restaurante cdmx"])
