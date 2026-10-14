"""
Config + library-test routes.
  GET  /api/config
  POST /api/config
  GET  /api/config/status
  POST /api/library/test
  POST /api/jellyfin/test
  POST /api/emby/test
"""
import requests
from fastapi import APIRouter, Body
from urllib.parse import urlparse

from app.config import load_config, save_config, is_configured, config_issues
from app.auth import hash_password, generate_secret_key
from app import scheduler
from app.routers._shared import log

router = APIRouter()


def _emby_like_headers(token: str) -> dict:
    """Auth headers for Jellyfin/Emby connection tests.

    Jellyfin 12 disabled legacy auth by default and stopped reading the
    X-Emby-Token header, returning 401 (issue #108). The modern
    `Authorization: MediaBrowser Token="..."` header works on every Jellyfin
    (>=10.8) and on Emby, so we send both and let each server pick the one it
    understands — no server-type branching needed.
    """
    return {
        "X-Emby-Token": token,
        "Authorization": f'MediaBrowser Token="{token}"',
    }


# --------------------------------------------------
# Config
# --------------------------------------------------

@router.get("/api/config")
def api_get_config():
    import copy
    cfg  = copy.deepcopy(load_config())
    auth = cfg.get("AUTH", {})
    # Expose whether a password is set without exposing the hash
    auth["AUTH_HAS_PASSWORD"] = bool(auth.get("AUTH_PASSWORD_HASH"))
    # Never send sensitive fields to the browser
    for key in ("AUTH_PASSWORD_HASH", "AUTH_PASSWORD_SALT", "AUTH_SECRET_KEY"):
        auth.pop(key, None)
    return cfg


@router.get("/api/config/status")
def api_config_status():
    cfg    = load_config()
    issues = config_issues(cfg)
    return {"configured": len(issues) == 0, "issues": issues}


@router.post("/api/config")
def api_save_config(payload: dict = Body(...)):
    auth_payload = payload.get("AUTH", {})
    new_password = str(auth_payload.pop("AUTH_PASSWORD", "")).strip()
    # Virtual field sent by UI — never stored directly
    auth_payload.pop("AUTH_HAS_PASSWORD", None)

    existing_auth = load_config().get("AUTH", {})

    if new_password:
        pw_hash, pw_salt = hash_password(new_password)
        auth_payload["AUTH_PASSWORD_HASH"] = pw_hash
        auth_payload["AUTH_PASSWORD_SALT"] = pw_salt
    else:
        # Preserve existing hash if no new password supplied
        auth_payload["AUTH_PASSWORD_HASH"] = existing_auth.get("AUTH_PASSWORD_HASH", "")
        auth_payload["AUTH_PASSWORD_SALT"] = existing_auth.get("AUTH_PASSWORD_SALT", "")

    # Auto-generate secret key once and keep it stable
    auth_payload["AUTH_SECRET_KEY"] = (
        existing_auth.get("AUTH_SECRET_KEY") or generate_secret_key()
    )

    payload["AUTH"] = auth_payload
    try:
        cfg = save_config(payload)
    except OSError as e:
        log.error(f"Cannot write config file: {e}")
        return {"ok": False, "error": f"Cannot write to /config — check folder permissions and PUID/PGID ({e})"}
    scheduler.restart()
    return {"ok": True, "configured": is_configured(cfg)}


# --------------------------------------------------
# Library test
# --------------------------------------------------

@router.post("/api/library/test")
def library_test(payload: dict = Body(...)):
    lib_type = payload.get("type", "plex").lower()
    try:
        if lib_type in ("jellyfin", "emby"):
            import requests as _req
            url     = payload.get("url", "").rstrip("/")
            key     = payload.get("api_key", "")
            lib     = payload.get("library_name", "")
            prefix  = "/emby" if lib_type == "emby" else ""
            name    = lib_type.capitalize()
            if not url or not key:
                return {"ok": False, "error": "URL and API key are required"}
            if urlparse(url).scheme not in ("http", "https"):
                return {"ok": False, "error": "URL must start with http:// or https://"}
            r = _req.get(f"{url}{prefix}/Library/MediaFolders",
                         headers=_emby_like_headers(key), timeout=10)
            r.raise_for_status()
            folders = [i.get("Name","") for i in r.json().get("Items",[])]
            if lib and lib not in folders:
                return {"ok": False, "error": f"Library '{lib}' not found. Available: {', '.join(folders)}"}
            return {"ok": True, "libraries": folders}
        else:
            from app.plex_xml import plex_get
            import defusedxml.ElementTree as _ET
            url   = payload.get("url", "").rstrip("/")
            token = payload.get("token", "")
            lib   = payload.get("library_name", "")
            if not url or not token:
                return {"ok": False, "error": "URL and token are required"}
            if urlparse(url).scheme not in ("http", "https"):
                return {"ok": False, "error": "URL must start with http:// or https://"}
            import requests as _req
            lib_cfg = {"url": url, "token": token, "library_name": lib,
                       "page_size": 500, "short_movie_limit": 60}
            try:
                xml  = plex_get("/library/sections", lib_cfg)
            except _req.exceptions.ConnectionError as ce:
                return {"ok": False, "error": f"Cannot reach Plex at {url} — {ce}"}
            except _req.exceptions.HTTPError as he:
                code = he.response.status_code if he.response is not None else "?"
                if code == 401:
                    return {"ok": False, "error": "Invalid Plex token (401 Unauthorized)"}
                return {"ok": False, "error": f"Plex returned HTTP {code}"}
            root = _ET.fromstring(xml)
            libs = [d.attrib.get("title","") for d in root.findall("Directory")
                    if d.attrib.get("type") == "movie"]
            if lib and lib not in libs:
                return {"ok": False, "error": f"Library '{lib}' not found. Available: {', '.join(libs) or 'none'}"}
            return {"ok": True, "libraries": libs}
    except Exception as e:
        log.warning(f"Library test failed: {e}")
        return {"ok": False, "error": str(e) or "Could not connect — check URL and credentials"}


# --------------------------------------------------
# Jellyfin / Emby connection tests
# --------------------------------------------------

def _test_emby_like(url: str, token: str, library: str, path_prefix: str, server_name: str):
    """Shared logic for testing Jellyfin and Emby connectivity."""
    if not url or not token:
        return {"ok": False, "error": "URL and API key are required"}

    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return {"ok": False, "error": "URL must start with http:// or https://"}
    except Exception:
        return {"ok": False, "error": "Invalid URL format"}

    headers = _emby_like_headers(token)

    try:
        r = requests.get(f"{url}{path_prefix}/System/Info", headers=headers, timeout=10)
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": f"Cannot connect to {url}"}
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            return {"ok": False, "error": "Invalid API key"}
        return {"ok": False, "error": f"Server error: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    if not library:
        return {"ok": True, "message": "Connected successfully"}

    try:
        r2 = requests.get(f"{url}{path_prefix}/Library/MediaFolders", headers=headers, timeout=10)
        r2.raise_for_status()
        folders = [i.get("Name", "") for i in r2.json().get("Items", [])]
        match = next((f for f in folders if f.lower() == library.lower()), None)
        if not match:
            return {"ok": False, "error": f"Library '{library}' not found. Available: {', '.join(folders) or 'none'}"}
        return {"ok": True, "message": f"Connected — library '{match}' found"}
    except Exception as e:
        return {"ok": False, "error": f"Could not list libraries: {e}"}


@router.post("/api/jellyfin/test")
def api_jellyfin_test(payload: dict = Body(...)):
    """Test Jellyfin connectivity with the provided credentials."""
    return _test_emby_like(
        url         = str(payload.get("url",     "")).rstrip("/"),
        token       = str(payload.get("token",   "")),
        library     = str(payload.get("library", "")).strip(),
        path_prefix = "",
        server_name = "Jellyfin",
    )


@router.post("/api/emby/test")
def api_emby_test(payload: dict = Body(...)):
    """Test Emby connectivity with the provided credentials."""
    return _test_emby_like(
        url         = str(payload.get("url",     "")).rstrip("/"),
        token       = str(payload.get("token",   "")),
        library     = str(payload.get("library", "")).strip(),
        path_prefix = "/emby",
        server_name = "Emby",
    )
