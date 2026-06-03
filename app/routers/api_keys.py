"""
API key management routes.
  GET    /api/apikeys          — list keys (id, name, preview, created_at)
  POST   /api/apikeys          — generate new key (returns raw key ONCE)
  DELETE /api/apikeys/{key_id} — revoke a key
"""
import time

from fastapi import APIRouter, Body

from app.config import load_config, save_config
from app.auth import generate_api_key, hash_api_key, key_preview
from app.routers._shared import log

router = APIRouter()

_KEY_LIMIT = 20   # max API keys per instance


@router.get("/api/apikeys")
def list_api_keys():
    """Return all keys — id, name, preview (first 8 + last 4 chars), created_at."""
    cfg  = load_config()
    keys = cfg.get("API_KEYS", [])
    return {
        "ok":   True,
        "keys": [
            {
                "id":         k["id"],
                "name":       k.get("name", ""),
                "preview":    k.get("preview", ""),
                "created_at": k.get("created_at", 0),
            }
            for k in keys
        ],
    }


@router.post("/api/apikeys")
def create_api_key(payload: dict = Body(...)):
    """
    Generate a new API key.
    The raw key is returned ONCE here — it is never stored and cannot be
    recovered later. Only the SHA-256 hash is persisted.
    """
    name = str(payload.get("name", "")).strip() or "Unnamed key"

    cfg  = load_config()
    keys = cfg.get("API_KEYS", [])

    if len(keys) >= _KEY_LIMIT:
        return {"ok": False, "error": f"Maximum of {_KEY_LIMIT} API keys reached"}

    raw     = generate_api_key()
    preview = key_preview(raw)
    entry   = {
        "id":         f"key_{int(time.time() * 1000)}",
        "name":       name,
        "key_hash":   hash_api_key(raw),
        "preview":    preview,
        "created_at": int(time.time()),
    }
    keys.append(entry)
    cfg["API_KEYS"] = keys
    save_config(cfg)

    log.info(f"API key created: '{name}' ({preview})")
    return {
        "ok":      True,
        "key":     raw,        # returned ONCE — never available again
        "id":      entry["id"],
        "name":    name,
        "preview": preview,
    }


@router.delete("/api/apikeys/{key_id}")
def revoke_api_key(key_id: str):
    """Revoke (delete) an API key by ID."""
    cfg  = load_config()
    keys = cfg.get("API_KEYS", [])

    before = len(keys)
    keys   = [k for k in keys if k["id"] != key_id]
    if len(keys) == before:
        return {"ok": False, "error": "Key not found"}

    cfg["API_KEYS"] = keys
    save_config(cfg)
    log.info(f"API key revoked: {key_id}")
    return {"ok": True}
