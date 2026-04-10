"""
Radarr / Overseerr / Jellyseerr / Webhook / Watchtower routes.
  GET  /api/radarr/profiles
  POST /api/radarr/add
  GET  /api/radarr/status
  POST /api/overseerr/add
  POST /api/jellyseerr/add
  POST /api/webhook
  POST /api/watchtower/update
"""
import time
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Body, Header, Query

from app.config import load_config
from app.scanner import build_async, scan_state
from app.routers._shared import log, _parse_tmdb_id

router = APIRouter()


# --------------------------------------------------
# Radarr helpers
# --------------------------------------------------

def _radarr_post(
    cfg_section: dict,
    prefix: str,
    tmdb_id: int,
    title: str,
    quality_override: int | None = None,
    root_override: str | None = None,
) -> dict:
    """Shared logic for posting a movie to any Radarr instance.
    quality_override and root_override, when provided, take precedence over config."""
    url       = str(cfg_section.get(f"{prefix}_URL", "")).rstrip("/")
    api_key   = str(cfg_section.get(f"{prefix}_API_KEY", "")).strip()
    root      = root_override if root_override is not None else str(cfg_section.get(f"{prefix}_ROOT_FOLDER_PATH", ""))
    quality   = quality_override if quality_override is not None else int(cfg_section.get(f"{prefix}_QUALITY_PROFILE_ID", 6))
    monitored = bool(cfg_section.get(f"{prefix}_MONITORED", True))
    search    = bool(cfg_section.get(f"{prefix}_SEARCH_ON_ADD", False))

    if not url:
        return {"ok": False, "error": "Radarr URL not configured"}

    body = {
        "title":            title,
        "tmdbId":           tmdb_id,
        "qualityProfileId": quality,
        "rootFolderPath":   root,
        "monitored":        monitored,
        "addOptions":       {"searchForMovie": search},
    }
    try:
        r = requests.post(
            f"{url}/api/v3/movie",
            json=body,
            headers={"X-Api-Key": api_key},
            timeout=20,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}

    if r.status_code not in (200, 201):
        return {"ok": False, "error": r.text}
    return {"ok": True}


_radarr_status_cache: dict = {"data": None, "ts": 0.0}


# --------------------------------------------------
# Radarr
# --------------------------------------------------

@router.get("/api/radarr/profiles")
def radarr_profiles(instance: str = Query(default="primary")):
    """Fetch quality profiles from a Radarr instance for the config UI dropdown."""
    cfg = load_config()
    if instance == "4k":
        section = cfg.get("RADARR_4K", {})
        url = str(section.get("RADARR_4K_URL", "")).rstrip("/")
        key = str(section.get("RADARR_4K_API_KEY", "")).strip()
    else:
        section = cfg.get("RADARR", {})
        url = str(section.get("RADARR_URL", "")).rstrip("/")
        key = str(section.get("RADARR_API_KEY", "")).strip()

    if not url or not key:
        return {"ok": False, "error": "URL and API key required"}

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {"ok": False, "error": "Invalid Radarr URL"}

    try:
        r = requests.get(
            f"{url}/api/v3/qualityprofile",
            headers={"X-Api-Key": key},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}

    if r.status_code == 401:
        return {"ok": False, "error": "Invalid API key"}
    if r.status_code != 200:
        return {"ok": False, "error": f"HTTP {r.status_code}"}

    profiles = [{"id": p["id"], "name": p["name"]} for p in r.json()]
    return {"ok": True, "profiles": profiles}


@router.get("/api/radarr/rootfolders")
def radarr_rootfolders(instance: str = Query(default="primary")):
    """Fetch root folders from a Radarr instance for the per-item picker."""
    cfg = load_config()
    if instance == "4k":
        section = cfg.get("RADARR_4K", {})
        url = str(section.get("RADARR_4K_URL", "")).rstrip("/")
        key = str(section.get("RADARR_4K_API_KEY", "")).strip()
    else:
        section = cfg.get("RADARR", {})
        url = str(section.get("RADARR_URL", "")).rstrip("/")
        key = str(section.get("RADARR_API_KEY", "")).strip()

    if not url or not key:
        return {"ok": False, "error": "URL and API key required"}

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {"ok": False, "error": "Invalid Radarr URL"}

    try:
        r = requests.get(
            f"{url}/api/v3/rootfolder",
            headers={"X-Api-Key": key},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}

    if r.status_code == 401:
        return {"ok": False, "error": "Invalid API key"}
    if r.status_code != 200:
        return {"ok": False, "error": f"HTTP {r.status_code}"}

    folders = [{"path": f["path"], "freeSpace": f.get("freeSpace", 0)} for f in r.json()]
    return {"ok": True, "folders": folders}


@router.post("/api/radarr/add")
def radarr_add(payload: dict = Body(...), instance: str = Query(default="primary")):
    tmdb_id = _parse_tmdb_id(payload.get("tmdb"))
    if tmdb_id is None:
        return {"ok": False, "error": "Invalid TMDB ID"}
    title            = str(payload.get("title", ""))
    quality_override = payload.get("qualityProfileId")
    root_override    = payload.get("rootFolderPath")
    cfg              = load_config()

    if quality_override is not None:
        try:
            quality_override = int(quality_override)
        except (ValueError, TypeError):
            quality_override = None

    if instance == "4k":
        section = cfg.get("RADARR_4K", {})
        if not section.get("RADARR_4K_ENABLED"):
            return {"ok": False, "error": "Radarr 4K disabled"}
        return _radarr_post(section, "RADARR_4K", tmdb_id, title, quality_override, root_override)

    section = cfg.get("RADARR", {})
    if not section.get("RADARR_ENABLED"):
        return {"ok": False, "error": "Radarr disabled"}
    return _radarr_post(section, "RADARR", tmdb_id, title, quality_override, root_override)


@router.get("/api/radarr/status")
def radarr_status():
    """
    Return a dict of tmdb_id → status for every movie in Radarr.
    status values: "available" (has file), "monitored" (searching), "unmonitored".
    Result is cached for 60 seconds to avoid hammering Radarr on every Wishlist render.
    """
    cfg    = load_config()
    radarr = cfg.get("RADARR", {})
    if not radarr.get("RADARR_ENABLED"):
        return {"ok": False, "error": "Radarr disabled"}

    now = time.time()
    if _radarr_status_cache["data"] and now - _radarr_status_cache["ts"] < 60:
        return _radarr_status_cache["data"]

    url = radarr.get("RADARR_URL", "").rstrip("/")
    key = radarr.get("RADARR_API_KEY", "")
    if not url or not key:
        return {"ok": False, "error": "Radarr not configured"}

    try:
        r = requests.get(
            f"{url}/api/v3/movie",
            headers={"X-Api-Key": key},
            timeout=15,
        )
        r.raise_for_status()
        movies = r.json()
    except Exception as e:
        log.debug(f"Radarr status fetch failed: {e}")
        return {"ok": False, "error": "Could not reach Radarr"}

    statuses: dict[int, str] = {}
    for m in movies:
        tmdb_id = m.get("tmdbId")
        if not tmdb_id:
            continue
        if m.get("hasFile"):
            statuses[tmdb_id] = "available"
        elif m.get("monitored"):
            statuses[tmdb_id] = "monitored"
        else:
            statuses[tmdb_id] = "unmonitored"

    result = {"ok": True, "statuses": statuses}
    _radarr_status_cache["data"] = result
    _radarr_status_cache["ts"]   = now
    return result


# --------------------------------------------------
# Overseerr
# --------------------------------------------------

@router.post("/api/overseerr/add")
def overseerr_add(payload: dict = Body(...)):
    cfg = load_config().get("OVERSEERR", {})
    if not cfg.get("OVERSEERR_ENABLED"):
        return {"ok": False, "error": "Overseerr disabled"}
    tmdb_id = _parse_tmdb_id(payload.get("tmdb"))
    if tmdb_id is None:
        return {"ok": False, "error": "Invalid TMDB ID"}
    api_key = cfg.get("OVERSEERR_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "Overseerr API key not configured"}
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    try:
        r = requests.post(
            f"{cfg['OVERSEERR_URL'].rstrip('/')}/api/v1/request",
            json={"mediaType": "movie", "mediaId": tmdb_id},
            headers=headers, timeout=20,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}
    if r.status_code not in (200, 201):
        return {"ok": False, "error": r.text}
    return {"ok": True}


# --------------------------------------------------
# Jellyseerr
# --------------------------------------------------

@router.post("/api/jellyseerr/add")
def jellyseerr_add(payload: dict = Body(...)):
    cfg = load_config().get("JELLYSEERR", {})
    if not cfg.get("JELLYSEERR_ENABLED"):
        return {"ok": False, "error": "Jellyseerr disabled"}
    tmdb_id = _parse_tmdb_id(payload.get("tmdb"))
    if tmdb_id is None:
        return {"ok": False, "error": "Invalid TMDB ID"}
    api_key = cfg.get("JELLYSEERR_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "Jellyseerr API key not configured"}
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    try:
        r = requests.post(
            f"{cfg['JELLYSEERR_URL'].rstrip('/')}/api/v1/request",
            json={"mediaType": "movie", "mediaId": tmdb_id},
            headers=headers, timeout=20,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}
    if r.status_code not in (200, 201):
        return {"ok": False, "error": r.text}
    return {"ok": True}


# --------------------------------------------------
# Webhook
# --------------------------------------------------

@router.post("/api/webhook")
def api_webhook(
    secret: str = Query(default=""),
    x_cineplete_secret: str = Header(default="", alias="x-cineplete-secret"),
):
    cfg = load_config().get("WEBHOOK", {})
    if not cfg.get("WEBHOOK_ENABLED"):
        return {"ok": False, "error": "Webhook disabled"}

    saved_secret = str(cfg.get("WEBHOOK_SECRET", "")).strip()
    provided     = secret.strip() or x_cineplete_secret.strip()

    if not saved_secret:
        return {"ok": False, "error": "Webhook secret not configured"}
    if provided != saved_secret:
        return {"ok": False, "error": "Invalid secret"}

    if scan_state["running"]:
        return {"ok": False, "error": "Scan already in progress"}

    launched = build_async()
    if not launched:
        return {"ok": False, "error": "Could not acquire scan lock"}

    log.info("Webhook triggered scan")
    return {"ok": True, "message": "Scan started"}


# --------------------------------------------------
# Watchtower
# --------------------------------------------------

@router.post("/api/watchtower/update")
def api_watchtower_update():
    cfg = load_config().get("WATCHTOWER", {})
    if not cfg.get("WATCHTOWER_ENABLED"):
        return {"ok": False, "error": "Watchtower disabled"}

    url   = str(cfg.get("WATCHTOWER_URL", "")).rstrip("/")
    token = str(cfg.get("WATCHTOWER_API_TOKEN", "")).strip()

    if not url:
        return {"ok": False, "error": "Watchtower URL not configured"}

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {"ok": False, "error": "Invalid Watchtower URL scheme"}

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    def _fire():
        try:
            r = requests.post(f"{url}/v1/update?scope=cineplete", headers=headers, timeout=300)
            log.info(f"Watchtower update response: HTTP {r.status_code}")
        except Exception as e:
            log.warning(f"Watchtower update error: {e}")

    import threading
    threading.Thread(target=_fire, daemon=True).start()
    log.info("Watchtower update dispatched (fire-and-forget)")
    return {"ok": True, "message": "Update request sent — container will restart shortly"}
