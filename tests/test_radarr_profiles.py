"""
Tests for GET /api/radarr/profiles endpoint.
Covers: primary + 4K instances, missing config, auth errors, HTTP errors.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.web import app

client = TestClient(app, raise_server_exceptions=True)

SAMPLE_PROFILES = [
    {"id": 4, "name": "Any"},
    {"id": 6, "name": "Ultra-HD"},
    {"id": 9, "name": "HD-1080p"},
]

BASE_CFG = {
    "RADARR": {
        "RADARR_ENABLED": True,
        "RADARR_URL": "http://radarr:7878",
        "RADARR_API_KEY": "abc123",
        "RADARR_ROOT_FOLDER_PATH": "/movies",
        "RADARR_QUALITY_PROFILE_ID": 6,
        "RADARR_MONITORED": True,
        "RADARR_SEARCH_ON_ADD": False,
    },
    "RADARR_4K": {
        "RADARR_4K_ENABLED": True,
        "RADARR_4K_URL": "http://radarr4k:7879",
        "RADARR_4K_API_KEY": "xyz789",
        "RADARR_4K_ROOT_FOLDER_PATH": "/movies4k",
        "RADARR_4K_QUALITY_PROFILE_ID": 6,
        "RADARR_4K_MONITORED": True,
        "RADARR_4K_SEARCH_ON_ADD": False,
    },
    "AUTH": {"AUTH_METHOD": "None", "AUTH_USERNAME": "", "AUTH_PASSWORD_HASH": "",
             "AUTH_PASSWORD_SALT": "", "AUTH_SECRET_KEY": ""},
}


def _mock_response(status_code=200, json_data=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data or SAMPLE_PROFILES
    return mock


class TestRadarrProfilesPrimary:

    def test_returns_profiles_primary(self):
        with patch("app.web.load_config", return_value=BASE_CFG), \
             patch("app.web.requests.get", return_value=_mock_response()) as mock_get:
            res = client.get("/api/radarr/profiles?instance=primary")
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert len(data["profiles"]) == 3
        assert data["profiles"][0] == {"id": 4, "name": "Any"}
        mock_get.assert_called_once_with(
            "http://radarr:7878/api/v3/qualityprofile",
            headers={"X-Api-Key": "abc123"},
            timeout=10,
        )

    def test_default_instance_is_primary(self):
        with patch("app.web.load_config", return_value=BASE_CFG), \
             patch("app.web.requests.get", return_value=_mock_response()):
            res = client.get("/api/radarr/profiles")
        assert res.json()["ok"] is True

    def test_returns_profiles_4k(self):
        with patch("app.web.load_config", return_value=BASE_CFG), \
             patch("app.web.requests.get", return_value=_mock_response()) as mock_get:
            res = client.get("/api/radarr/profiles?instance=4k")
        assert res.status_code == 200
        assert res.json()["ok"] is True
        mock_get.assert_called_once_with(
            "http://radarr4k:7879/api/v3/qualityprofile",
            headers={"X-Api-Key": "xyz789"},
            timeout=10,
        )

    def test_profile_names_and_ids_mapped(self):
        with patch("app.web.load_config", return_value=BASE_CFG), \
             patch("app.web.requests.get", return_value=_mock_response()):
            res = client.get("/api/radarr/profiles")
        profiles = res.json()["profiles"]
        ids   = [p["id"]   for p in profiles]
        names = [p["name"] for p in profiles]
        assert ids   == [4, 6, 9]
        assert names == ["Any", "Ultra-HD", "HD-1080p"]


class TestRadarrProfilesErrorCases:

    def test_missing_url_returns_error(self):
        cfg = {**BASE_CFG, "RADARR": {**BASE_CFG["RADARR"], "RADARR_URL": ""}}
        with patch("app.web.load_config", return_value=cfg):
            res = client.get("/api/radarr/profiles")
        data = res.json()
        assert data["ok"] is False
        assert "URL" in data["error"] or "required" in data["error"]

    def test_missing_api_key_returns_error(self):
        cfg = {**BASE_CFG, "RADARR": {**BASE_CFG["RADARR"], "RADARR_API_KEY": ""}}
        with patch("app.web.load_config", return_value=cfg):
            res = client.get("/api/radarr/profiles")
        data = res.json()
        assert data["ok"] is False

    def test_invalid_url_scheme_returns_error(self):
        cfg = {**BASE_CFG, "RADARR": {**BASE_CFG["RADARR"], "RADARR_URL": "ftp://radarr:7878"}}
        with patch("app.web.load_config", return_value=cfg):
            res = client.get("/api/radarr/profiles")
        data = res.json()
        assert data["ok"] is False
        assert "Invalid" in data["error"]

    def test_401_invalid_api_key(self):
        with patch("app.web.load_config", return_value=BASE_CFG), \
             patch("app.web.requests.get", return_value=_mock_response(status_code=401)):
            res = client.get("/api/radarr/profiles")
        data = res.json()
        assert data["ok"] is False
        assert "API key" in data["error"]

    def test_non_200_http_error(self):
        with patch("app.web.load_config", return_value=BASE_CFG), \
             patch("app.web.requests.get", return_value=_mock_response(status_code=503)):
            res = client.get("/api/radarr/profiles")
        data = res.json()
        assert data["ok"] is False
        assert "503" in data["error"]

    def test_network_error(self):
        import requests as req_lib
        with patch("app.web.load_config", return_value=BASE_CFG), \
             patch("app.web.requests.get", side_effect=req_lib.exceptions.ConnectionError("refused")):
            res = client.get("/api/radarr/profiles")
        data = res.json()
        assert data["ok"] is False
        assert "refused" in data["error"]

    def test_missing_4k_url_returns_error(self):
        cfg = {**BASE_CFG, "RADARR_4K": {**BASE_CFG["RADARR_4K"], "RADARR_4K_URL": ""}}
        with patch("app.web.load_config", return_value=cfg):
            res = client.get("/api/radarr/profiles?instance=4k")
        assert res.json()["ok"] is False
