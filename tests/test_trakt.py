"""
Tests for Trakt.tv integration (app/routers/trakt.py).

Covers:
  - _trakt_headers()
  - _refresh_access_token()
  - _fetch_watched()
  - POST /api/trakt/device/code
  - POST /api/trakt/device/poll
  - POST /api/trakt/disconnect
  - GET  /api/trakt/watched       (cache, token refresh)
  - GET  /api/trakt/status
"""
import os
import sys
import tempfile
import time
from unittest.mock import patch, MagicMock, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(enabled=True, access="access123", refresh="refresh456",
         client_id="cid", client_secret="csec", username="testuser"):
    return {
        "TRAKT": {
            "TRAKT_ENABLED":       enabled,
            "TRAKT_CLIENT_ID":     client_id,
            "TRAKT_CLIENT_SECRET": client_secret,
            "TRAKT_ACCESS_TOKEN":  access,
            "TRAKT_REFRESH_TOKEN": refresh,
            "TRAKT_USERNAME":      username,
            "TRAKT_HIDE_WATCHED":  False,
        }
    }


def _make_response(status_code, json_data=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    return r


# ---------------------------------------------------------------------------
# Unit: _trakt_headers
# ---------------------------------------------------------------------------

class TestTraktHeaders:
    def _call(self, client_id, access_token=""):
        from app.routers.trakt import _trakt_headers
        return _trakt_headers(client_id, access_token)

    def test_base_headers(self):
        h = self._call("my-client-id")
        assert h["trakt-api-key"] == "my-client-id"
        assert h["trakt-api-version"] == "2"
        assert "Authorization" not in h

    def test_includes_bearer_when_token_set(self):
        h = self._call("cid", "tok123")
        assert h["Authorization"] == "Bearer tok123"

    def test_no_bearer_when_empty_token(self):
        h = self._call("cid", "")
        assert "Authorization" not in h


# ---------------------------------------------------------------------------
# Unit: _refresh_access_token
# ---------------------------------------------------------------------------

class TestRefreshAccessToken:
    def _call(self, cfg):
        from app.routers.trakt import _refresh_access_token
        return _refresh_access_token(cfg)

    def test_returns_none_when_missing_fields(self):
        assert self._call({"TRAKT": {}}) is None

    def test_returns_none_on_http_error(self):
        cfg = _cfg()
        with patch("app.routers.trakt.requests.post") as mock_post:
            mock_post.return_value = _make_response(401)
            result = self._call(cfg)
        assert result is None

    def test_updates_tokens_on_success(self, tmp_path):
        cfg = _cfg()
        new_tokens = {"access_token": "new_access", "refresh_token": "new_refresh"}
        with patch("app.routers.trakt.requests.post") as mock_post, \
             patch("app.routers.trakt.save_config") as mock_save:
            mock_post.return_value = _make_response(200, new_tokens)
            result = self._call(cfg)

        assert result is not None
        assert result["TRAKT_ACCESS_TOKEN"]  == "new_access"
        assert result["TRAKT_REFRESH_TOKEN"] == "new_refresh"
        mock_save.assert_called_once()

    def test_returns_none_on_network_error(self):
        import requests as req
        cfg = _cfg()
        with patch("app.routers.trakt.requests.post") as mock_post:
            mock_post.side_effect = req.exceptions.RequestException("timeout")
            result = self._call(cfg)
        assert result is None


# ---------------------------------------------------------------------------
# Unit: _fetch_watched
# ---------------------------------------------------------------------------

class TestFetchWatched:
    def _call(self, client_id, access_token):
        from app.routers.trakt import _fetch_watched
        return _fetch_watched(client_id, access_token)

    def test_returns_tmdb_ids_on_success(self):
        payload = [
            {"movie": {"ids": {"tmdb": 550}}},
            {"movie": {"ids": {"tmdb": 278}}},
            {"movie": {"ids": {"tmdb": None}}},   # no tmdb id → skipped
        ]
        with patch("app.routers.trakt.requests.get") as mock_get:
            mock_get.return_value = _make_response(200, payload)
            result = self._call("cid", "tok")
        assert result == [550, 278]

    def test_returns_none_on_401(self):
        with patch("app.routers.trakt.requests.get") as mock_get:
            mock_get.return_value = _make_response(401)
            result = self._call("cid", "tok")
        assert result is None

    def test_returns_empty_list_on_network_error(self):
        import requests as req
        with patch("app.routers.trakt.requests.get") as mock_get:
            mock_get.side_effect = req.exceptions.RequestException("err")
            result = self._call("cid", "tok")
        assert result == []


# ---------------------------------------------------------------------------
# FastAPI route tests
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from fastapi import FastAPI


def _make_app():
    from app.routers import trakt
    # Reset the watched cache before each test
    trakt._watched_cache["data"] = None
    trakt._watched_cache["ts"]   = 0.0
    app = FastAPI()
    app.include_router(trakt.router)
    return app


# ---------------------------------------------------------------------------
# POST /api/trakt/device/code
# ---------------------------------------------------------------------------

class TestDeviceCode:
    def setup_method(self):
        self.client = TestClient(_make_app())

    def test_returns_device_info_on_success(self):
        payload = {
            "device_code": "dev123",
            "user_code": "ABC-DEF",
            "verification_url": "https://trakt.tv/activate",
            "expires_in": 600,
            "interval": 5,
        }
        with patch("app.routers.trakt.requests.post") as mock_post:
            mock_post.return_value = _make_response(200, payload)
            res = self.client.post("/api/trakt/device/code",
                                   json={"client_id": "cid", "client_secret": "csec"})
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["user_code"] == "ABC-DEF"
        assert data["device_code"] == "dev123"
        assert data["interval"] == 5

    def test_returns_error_when_client_id_missing(self):
        res = self.client.post("/api/trakt/device/code", json={})
        assert res.json()["ok"] is False

    def test_returns_error_on_http_failure(self):
        with patch("app.routers.trakt.requests.post") as mock_post:
            mock_post.return_value = _make_response(400)
            res = self.client.post("/api/trakt/device/code",
                                   json={"client_id": "cid"})
        assert res.json()["ok"] is False


# ---------------------------------------------------------------------------
# POST /api/trakt/device/poll
# ---------------------------------------------------------------------------

class TestDevicePoll:
    def setup_method(self):
        self.client = TestClient(_make_app())

    def _post(self, **kw):
        body = {"client_id": "cid", "client_secret": "csec", "device_code": "dev123", **kw}
        return self.client.post("/api/trakt/device/poll", json=body)

    def test_returns_pending_on_400(self):
        with patch("app.routers.trakt.requests.post") as mock_post:
            mock_post.return_value = _make_response(400)
            res = self._post()
        assert res.json()["status"] == "pending"

    def test_returns_expired_on_410(self):
        with patch("app.routers.trakt.requests.post") as mock_post:
            mock_post.return_value = _make_response(410)
            res = self._post()
        assert res.json()["status"] == "expired"

    def test_returns_denied_on_418(self):
        with patch("app.routers.trakt.requests.post") as mock_post:
            mock_post.return_value = _make_response(418)
            res = self._post()
        assert res.json()["status"] == "denied"

    def test_success_saves_config_and_returns_username(self):
        token_resp = {
            "access_token": "acc123",
            "refresh_token": "ref456",
        }
        user_resp = {"username": "johndoe"}

        with patch("app.routers.trakt.requests.post") as mock_post, \
             patch("app.routers.trakt.requests.get")  as mock_get, \
             patch("app.routers.trakt.load_config")   as mock_load, \
             patch("app.routers.trakt.save_config")   as mock_save:

            mock_post.return_value = _make_response(200, token_resp)
            mock_get.return_value  = _make_response(200, user_resp)
            mock_load.return_value = {"TRAKT": {}}

            res = self._post()

        data = res.json()
        assert data["ok"] is True
        assert data["status"] == "success"
        assert data["username"] == "johndoe"
        mock_save.assert_called_once()

    def test_returns_error_when_fields_missing(self):
        res = self.client.post("/api/trakt/device/poll", json={"client_id": "cid"})
        assert res.json()["ok"] is False

    def test_returns_pending_on_429(self):
        with patch("app.routers.trakt.requests.post") as mock_post:
            mock_post.return_value = _make_response(429)
            res = self._post()
        assert res.json()["status"] == "pending"


# ---------------------------------------------------------------------------
# POST /api/trakt/disconnect
# ---------------------------------------------------------------------------

class TestDisconnect:
    def setup_method(self):
        self.client = TestClient(_make_app())

    def test_clears_tokens_and_returns_ok(self):
        with patch("app.routers.trakt.load_config") as mock_load, \
             patch("app.routers.trakt.save_config") as mock_save:
            mock_load.return_value = _cfg()
            res = self.client.post("/api/trakt/disconnect")

        assert res.json()["ok"] is True
        saved = mock_save.call_args[0][0]
        trakt = saved["TRAKT"]
        assert trakt["TRAKT_ENABLED"]       is False
        assert trakt["TRAKT_ACCESS_TOKEN"]  == ""
        assert trakt["TRAKT_REFRESH_TOKEN"] == ""
        assert trakt["TRAKT_USERNAME"]      == ""


# ---------------------------------------------------------------------------
# POST /api/trakt/watched/refresh
# ---------------------------------------------------------------------------

class TestWatchedRefresh:
    def setup_method(self):
        self.client = TestClient(_make_app())

    def test_busts_cache_and_returns_ok(self):
        from app.routers import trakt as trakt_mod
        # Prime the cache with a recent timestamp
        trakt_mod._watched_cache["data"] = {"ok": True, "tmdb_ids": [1, 2]}
        trakt_mod._watched_cache["ts"]   = time.time()

        res = self.client.post("/api/trakt/watched/refresh")

        assert res.json()["ok"] is True
        # Cache timestamp should now be 0 (expired)
        assert trakt_mod._watched_cache["ts"] == 0.0


# ---------------------------------------------------------------------------
# GET /api/trakt/watched
# ---------------------------------------------------------------------------

class TestWatched:
    def setup_method(self):
        self.client = TestClient(_make_app())

    def test_returns_empty_when_disabled(self):
        with patch("app.routers.trakt.load_config") as mock_load:
            mock_load.return_value = _cfg(enabled=False, access="")
            res = self.client.get("/api/trakt/watched")
        assert res.json() == {"ok": True, "tmdb_ids": []}

    def test_returns_tmdb_ids_when_connected(self):
        watch_payload = [
            {"movie": {"ids": {"tmdb": 550}}},
            {"movie": {"ids": {"tmdb": 278}}},
        ]
        with patch("app.routers.trakt.load_config") as mock_load, \
             patch("app.routers.trakt.requests.get") as mock_get:
            mock_load.return_value = _cfg()
            mock_get.return_value  = _make_response(200, watch_payload)
            res = self.client.get("/api/trakt/watched")

        data = res.json()
        assert data["ok"] is True
        assert set(data["tmdb_ids"]) == {550, 278}

    def test_refreshes_token_on_401(self):
        """On 401 from watched endpoint, router should call _refresh_access_token."""
        watch_payload = [{"movie": {"ids": {"tmdb": 999}}}]
        refresh_resp  = {
            "TRAKT_ACCESS_TOKEN":  "new_access",
            "TRAKT_REFRESH_TOKEN": "new_refresh",
        }

        def _get_side_effect(url, **kw):
            if "watched" in url:
                if _get_side_effect._calls == 0:
                    _get_side_effect._calls += 1
                    return _make_response(401)
                return _make_response(200, watch_payload)
            return _make_response(200, {})
        _get_side_effect._calls = 0

        with patch("app.routers.trakt.load_config") as mock_load, \
             patch("app.routers.trakt.requests.get", side_effect=_get_side_effect), \
             patch("app.routers.trakt._refresh_access_token", return_value=refresh_resp):
            mock_load.return_value = _cfg()
            res = self.client.get("/api/trakt/watched")

        data = res.json()
        assert data["ok"] is True
        assert 999 in data["tmdb_ids"]

    def test_returns_cached_data(self):
        from app.routers import trakt as trakt_mod
        trakt_mod._watched_cache["data"] = {"ok": True, "tmdb_ids": [42, 43]}
        trakt_mod._watched_cache["ts"]   = time.time()

        with patch("app.routers.trakt.load_config") as mock_load:
            mock_load.return_value = _cfg()
            res = self.client.get("/api/trakt/watched")

        assert res.json()["tmdb_ids"] == [42, 43]
        mock_load.assert_not_called()   # served from cache without hitting config


# ---------------------------------------------------------------------------
# GET /api/trakt/status
# ---------------------------------------------------------------------------

class TestStatus:
    def setup_method(self):
        self.client = TestClient(_make_app())

    def test_connected_state(self):
        with patch("app.routers.trakt.load_config") as mock_load:
            mock_load.return_value = _cfg()
            res = self.client.get("/api/trakt/status")
        data = res.json()
        assert data["ok"]        is True
        assert data["connected"] is True
        assert data["username"]  == "testuser"
        assert data["enabled"]   is True

    def test_disconnected_state(self):
        with patch("app.routers.trakt.load_config") as mock_load:
            mock_load.return_value = _cfg(access="", username="")
            res = self.client.get("/api/trakt/status")
        data = res.json()
        assert data["connected"] is False
        assert data["username"]  == ""
