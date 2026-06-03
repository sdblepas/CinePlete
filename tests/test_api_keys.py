"""
Tests for API key management and authentication.

Covers:
  - generate_api_key / hash_api_key / key_preview / verify_api_key helpers
  - GET  /api/apikeys  — list
  - POST /api/apikeys  — create (returns raw key once, stores hash)
  - DELETE /api/apikeys/{id} — revoke
  - AuthMiddleware: X-Api-Key header grants access when auth is enabled
  - AuthMiddleware: ?apikey= query param grants access
  - AuthMiddleware: wrong key is rejected
"""
import os
import sys
import json
import tempfile
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import (
    generate_api_key, hash_api_key, key_preview, verify_api_key,
    API_KEY_PREFIX,
)


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

def _make_client(stored_keys: list):
    """Build a TestClient with the api_keys router and a temp overrides file."""
    from app.routers import api_keys as ak_mod

    app = FastAPI()
    app.include_router(ak_mod.router)

    def _fake_load():
        return {"API_KEYS": stored_keys}

    saved = {}

    def _fake_save(cfg):
        saved["cfg"] = cfg

    with patch("app.routers.api_keys.load_config", side_effect=_fake_load), \
         patch("app.routers.api_keys.save_config", side_effect=_fake_save):
        client = TestClient(app)
        yield client, saved


# ---------------------------------------------------------------------------
# Unit tests — auth helpers
# ---------------------------------------------------------------------------

class TestApiKeyHelpers:

    def test_generate_api_key_has_prefix(self):
        key = generate_api_key()
        assert key.startswith(API_KEY_PREFIX)

    def test_generate_api_key_length(self):
        key = generate_api_key()
        # prefix (3) + 64 hex chars = 67
        assert len(key) == len(API_KEY_PREFIX) + 64

    def test_generate_api_key_unique(self):
        assert generate_api_key() != generate_api_key()

    def test_hash_api_key_deterministic(self):
        key = generate_api_key()
        assert hash_api_key(key) == hash_api_key(key)

    def test_hash_api_key_different_keys(self):
        assert hash_api_key(generate_api_key()) != hash_api_key(generate_api_key())

    def test_key_preview_format(self):
        key = API_KEY_PREFIX + "a" * 64
        preview = key_preview(key)
        assert preview.startswith(API_KEY_PREFIX)
        assert "…" in preview

    def test_verify_api_key_correct(self):
        raw = generate_api_key()
        stored = [{"id": "k1", "name": "test", "key_hash": hash_api_key(raw), "created_at": 0}]
        assert verify_api_key(raw, stored) is True

    def test_verify_api_key_wrong(self):
        stored = [{"id": "k1", "name": "test", "key_hash": hash_api_key(generate_api_key()), "created_at": 0}]
        assert verify_api_key(generate_api_key(), stored) is False

    def test_verify_api_key_empty_list(self):
        assert verify_api_key(generate_api_key(), []) is False

    def test_verify_api_key_empty_key(self):
        stored = [{"id": "k1", "name": "test", "key_hash": "abc", "created_at": 0}]
        assert verify_api_key("", stored) is False


# ---------------------------------------------------------------------------
# Route tests — list / create / revoke
# ---------------------------------------------------------------------------

class TestApiKeyRoutes:

    def test_list_empty(self):
        for client, _ in _make_client([]):
            res = client.get("/api/apikeys")
            assert res.json() == {"ok": True, "keys": []}
            break

    def test_list_returns_safe_fields(self):
        raw = generate_api_key()
        stored = [{"id": "k1", "name": "HA", "key_hash": hash_api_key(raw),
                   "preview": key_preview(raw), "created_at": 1000}]
        for client, _ in _make_client(stored):
            data = client.get("/api/apikeys").json()
            assert len(data["keys"]) == 1
            k = data["keys"][0]
            assert k["id"] == "k1"
            assert k["name"] == "HA"
            assert "key_hash" not in k       # must NOT be exposed
            assert "preview" in k
            assert k["created_at"] == 1000
            break

    def test_create_returns_raw_key_once(self):
        for client, saved in _make_client([]):
            res = client.post("/api/apikeys", json={"name": "n8n"})
            data = res.json()
            assert data["ok"] is True
            assert data["key"].startswith(API_KEY_PREFIX)
            assert data["name"] == "n8n"
            assert "preview" in data
            # key_hash must be saved, raw key must NOT be in saved config
            entry = saved["cfg"]["API_KEYS"][0]
            assert entry["key_hash"] == hash_api_key(data["key"])
            assert "key" not in entry
            break

    def test_create_default_name(self):
        for client, saved in _make_client([]):
            res = client.post("/api/apikeys", json={})
            assert res.json()["name"] == "Unnamed key"
            break

    def test_create_respects_limit(self):
        # Fill up to limit
        dummy = [{"id": f"k{i}", "name": f"k{i}", "key_hash": "x", "created_at": 0}
                 for i in range(20)]
        for client, _ in _make_client(dummy):
            res = client.post("/api/apikeys", json={"name": "overflow"})
            assert res.json()["ok"] is False
            assert "Maximum" in res.json()["error"]
            break

    def test_revoke_existing_key(self):
        raw = generate_api_key()
        stored = [{"id": "k1", "name": "test", "key_hash": hash_api_key(raw),
                   "preview": key_preview(raw), "created_at": 0}]
        for client, saved in _make_client(stored):
            res = client.delete("/api/apikeys/k1")
            assert res.json() == {"ok": True}
            assert saved["cfg"]["API_KEYS"] == []
            break

    def test_revoke_nonexistent_key(self):
        for client, _ in _make_client([]):
            res = client.delete("/api/apikeys/does-not-exist")
            assert res.json()["ok"] is False
            break


# ---------------------------------------------------------------------------
# Middleware integration — API key bypasses session-cookie auth
# ---------------------------------------------------------------------------

def _make_auth_app(method: str, stored_keys: list):
    """Build a minimal app with AuthMiddleware active."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from app.web import AuthMiddleware

    inner = FastAPI()

    @inner.get("/api/ping")
    def ping():
        return {"pong": True}

    inner.add_middleware(AuthMiddleware)

    def _fake_load():
        return {
            "AUTH": {"AUTH_METHOD": method, "AUTH_SECRET_KEY": "s", "TRUSTED_PROXIES": ""},
            "API_KEYS": stored_keys,
        }

    with patch("app.web.load_config", side_effect=_fake_load):
        yield TestClient(inner, raise_server_exceptions=False)


class TestApiKeyMiddleware:

    def _stored(self, raw: str) -> list:
        return [{"id": "k1", "name": "test", "key_hash": hash_api_key(raw), "created_at": 0}]

    def test_valid_header_grants_access(self):
        raw = generate_api_key()
        for client in _make_auth_app("Forms", self._stored(raw)):
            res = client.get("/api/ping", headers={"X-Api-Key": raw})
            assert res.status_code == 200
            assert res.json()["pong"] is True
            break

    def test_valid_query_param_grants_access(self):
        raw = generate_api_key()
        for client in _make_auth_app("Forms", self._stored(raw)):
            res = client.get(f"/api/ping?apikey={raw}")
            assert res.status_code == 200
            break

    def test_wrong_key_is_rejected(self):
        raw = generate_api_key()
        wrong = generate_api_key()
        for client in _make_auth_app("Forms", self._stored(raw)):
            res = client.get("/api/ping", headers={"X-Api-Key": wrong})
            assert res.status_code == 401
            break

    def test_no_key_is_rejected_when_auth_enabled(self):
        raw = generate_api_key()
        for client in _make_auth_app("Forms", self._stored(raw)):
            res = client.get("/api/ping")
            assert res.status_code == 401
            break

    def test_key_not_required_when_auth_none(self):
        """When AUTH_METHOD is None, API works without any key."""
        for client in _make_auth_app("None", []):
            res = client.get("/api/ping")
            assert res.status_code == 200
            break
