"""
Trakt.tv integration — device-code OAuth + watched-movie history.

  POST /api/trakt/device/code   — start device-code flow
  POST /api/trakt/device/poll   — poll for token (frontend calls every 5 s)
  POST /api/trakt/disconnect    — revoke / clear stored tokens
  GET  /api/trakt/watched       — return TMDB IDs of watched movies (cached 1 h)
  GET  /api/trakt/status        — connection state for the config UI
"""
import time
import logging

import requests
from fastapi import APIRouter, Body

from app.config import load_config, save_config

router = APIRouter()
log    = logging.getLogger("cineplete")

_TRAKT_BASE  = "https://api.trakt.tv"
_CACHE_TTL   = 3600   # 1 hour

_watched_cache: dict = {"data": None, "ts": 0.0}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _trakt_headers(client_id: str, access_token: str = "") -> dict:
    h = {
        "Content-Type":    "application/json",
        "trakt-api-version": "2",
        "trakt-api-key":   client_id,
    }
    if access_token:
        h["Authorization"] = f"Bearer {access_token}"
    return h


def _refresh_access_token(cfg: dict) -> dict | None:
    """Use the stored refresh token to get a new access token.
    Returns updated TRAKT config dict on success, None on failure."""
    trakt = cfg.get("TRAKT", {})
    client_id     = trakt.get("TRAKT_CLIENT_ID", "").strip()
    client_secret = trakt.get("TRAKT_CLIENT_SECRET", "").strip()
    refresh_token = trakt.get("TRAKT_REFRESH_TOKEN", "").strip()
    if not all([client_id, client_secret, refresh_token]):
        return None
    try:
        r = requests.post(
            f"{_TRAKT_BASE}/oauth/token",
            json={
                "refresh_token": refresh_token,
                "client_id":     client_id,
                "client_secret": client_secret,
                "redirect_uri":  "urn:ietf:wg:oauth:2.0:oob",
                "grant_type":    "refresh_token",
            },
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            trakt["TRAKT_ACCESS_TOKEN"]  = data["access_token"]
            trakt["TRAKT_REFRESH_TOKEN"] = data["refresh_token"]
            cfg["TRAKT"] = trakt
            save_config(cfg)
            log.info("Trakt: access token refreshed")
            return trakt
    except requests.exceptions.RequestException as e:
        log.warning(f"Trakt token refresh failed: {e}")
    return None


def _fetch_watched(client_id: str, access_token: str) -> list[int]:
    """Return list of TMDB IDs from the authenticated user's watched movies."""
    try:
        r = requests.get(
            f"{_TRAKT_BASE}/users/me/watched/movies",
            headers=_trakt_headers(client_id, access_token),
            timeout=30,
        )
        if r.status_code == 401:
            return None   # signal: token needs refresh
        if r.status_code == 200:
            tmdb_ids = []
            for entry in r.json():
                tmdb_id = entry.get("movie", {}).get("ids", {}).get("tmdb")
                if tmdb_id:
                    tmdb_ids.append(int(tmdb_id))
            return tmdb_ids
    except requests.exceptions.RequestException as e:
        log.warning(f"Trakt watched fetch failed: {e}")
    return []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/api/trakt/device/code")
def trakt_device_code(payload: dict = Body(...)):
    """
    Start the Trakt device-code flow.
    Accepts client_id (and optionally client_secret) in the request body so
    the user does not have to save config before connecting.
    """
    client_id     = str(payload.get("client_id", "")).strip()
    client_secret = str(payload.get("client_secret", "")).strip()

    if not client_id:
        return {"ok": False, "error": "Client ID is required"}

    try:
        r = requests.post(
            f"{_TRAKT_BASE}/oauth/device/code",
            json={"client_id": client_id},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}

    if r.status_code != 200:
        return {"ok": False, "error": f"Trakt returned HTTP {r.status_code}"}

    data = r.json()
    return {
        "ok":               True,
        "device_code":      data["device_code"],
        "user_code":        data["user_code"],
        "verification_url": data.get("verification_url", "https://trakt.tv/activate"),
        "expires_in":       data.get("expires_in", 600),
        "interval":         data.get("interval", 5),
    }


@router.post("/api/trakt/device/poll")
def trakt_device_poll(payload: dict = Body(...)):
    """
    Poll Trakt to see if the user has approved the device code.
    On success: saves tokens + username to config, clears watched cache.
    Returns { ok, status } where status is one of:
      "pending" | "success" | "denied" | "expired" | "error"
    """
    client_id     = str(payload.get("client_id", "")).strip()
    client_secret = str(payload.get("client_secret", "")).strip()
    device_code   = str(payload.get("device_code", "")).strip()

    if not all([client_id, client_secret, device_code]):
        return {"ok": False, "status": "error", "error": "Missing required fields"}

    try:
        r = requests.post(
            f"{_TRAKT_BASE}/oauth/device/token",
            json={
                "code":          device_code,
                "client_id":     client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "status": "error", "error": str(e)}

    if r.status_code == 200:
        data         = r.json()
        access_token = data["access_token"]

        # Fetch username
        username = ""
        try:
            u = requests.get(
                f"{_TRAKT_BASE}/users/me",
                headers=_trakt_headers(client_id, access_token),
                timeout=10,
            )
            if u.status_code == 200:
                username = u.json().get("username", "")
        except requests.exceptions.RequestException:
            pass

        # Persist to config
        cfg   = load_config()
        trakt = cfg.get("TRAKT", {})
        trakt.update({
            "TRAKT_ENABLED":       True,
            "TRAKT_CLIENT_ID":     client_id,
            "TRAKT_CLIENT_SECRET": client_secret,
            "TRAKT_ACCESS_TOKEN":  access_token,
            "TRAKT_REFRESH_TOKEN": data["refresh_token"],
            "TRAKT_USERNAME":      username,
        })
        cfg["TRAKT"] = trakt
        save_config(cfg)
        _watched_cache["ts"] = 0.0   # bust cache
        log.info(f"Trakt: connected as @{username}")
        return {"ok": True, "status": "success", "username": username}

    status_map = {400: "pending", 404: "error", 409: "error",
                  410: "expired", 418: "denied", 429: "pending"}
    status = status_map.get(r.status_code, "error")
    return {"ok": False, "status": status}


@router.post("/api/trakt/disconnect")
def trakt_disconnect():
    """Clear stored Trakt tokens from config."""
    cfg   = load_config()
    trakt = cfg.get("TRAKT", {})
    trakt.update({
        "TRAKT_ENABLED":       False,
        "TRAKT_ACCESS_TOKEN":  "",
        "TRAKT_REFRESH_TOKEN": "",
        "TRAKT_USERNAME":      "",
    })
    cfg["TRAKT"] = trakt
    save_config(cfg)
    _watched_cache["ts"] = 0.0
    return {"ok": True}


@router.get("/api/trakt/watched")
def trakt_watched():
    """
    Return TMDB IDs of all movies in the authenticated user's Trakt watch history.
    Cached for 1 hour. Silently returns [] when Trakt is disabled / not connected.
    """
    now = time.time()
    if _watched_cache["data"] is not None and now - _watched_cache["ts"] < _CACHE_TTL:
        return _watched_cache["data"]

    cfg   = load_config()
    trakt = cfg.get("TRAKT", {})

    if not trakt.get("TRAKT_ENABLED") or not trakt.get("TRAKT_ACCESS_TOKEN"):
        result = {"ok": True, "tmdb_ids": []}
        _watched_cache.update({"data": result, "ts": now})
        return result

    client_id    = trakt.get("TRAKT_CLIENT_ID", "").strip()
    access_token = trakt.get("TRAKT_ACCESS_TOKEN", "").strip()

    tmdb_ids = _fetch_watched(client_id, access_token)

    if tmdb_ids is None:
        # 401 — try a token refresh
        refreshed = _refresh_access_token(cfg)
        if refreshed:
            access_token = refreshed.get("TRAKT_ACCESS_TOKEN", "")
            tmdb_ids = _fetch_watched(client_id, access_token) or []
        else:
            tmdb_ids = []

    result = {"ok": True, "tmdb_ids": tmdb_ids}
    _watched_cache.update({"data": result, "ts": now})
    log.info(f"Trakt: {len(tmdb_ids)} watched movies cached")
    return result


@router.get("/api/trakt/status")
def trakt_status():
    """Return connection state for the config UI."""
    cfg   = load_config()
    trakt = cfg.get("TRAKT", {})
    connected = bool(trakt.get("TRAKT_ACCESS_TOKEN"))
    return {
        "ok":        True,
        "connected": connected,
        "username":  trakt.get("TRAKT_USERNAME", "") if connected else "",
        "enabled":   trakt.get("TRAKT_ENABLED", False),
    }
