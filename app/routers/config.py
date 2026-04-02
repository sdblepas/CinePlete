"""
Config + library-test routes.
  GET  /api/config
  POST /api/config
  GET  /api/config/status
  POST /api/library/test
  POST /api/jellyfin/test
"""
import requests
from fastapi import APIRouter, Body
from urllib.parse import urlparse

from app.config import load_config, save_config, is_configured, config_issues
from app.auth import hash_password, generate_secret_key
from app import scheduler
from app.routers._shared import log

router = APIRouter()


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
        if lib_type == "jellyfin":
            import requests as _req
            url = payload.get("url", "").rstrip("/")
            key = payload.get("api_key", "")
            lib = payload.get("library_name", "")
            if not url or not key:
                return {"ok": False, "error": "URL and API key are required"}
            if urlparse(url).scheme not in ("http", "https"):
                return {"ok": False, "error": "URL must start with http:// or https://"}
            r = _req.get(f"{url}/Library/MediaFolders",
                         headers={"X-Emby-Token": key}, timeout=10)
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
# Jellyfin connection test
# --------------------------------------------------

@router.post("/api/jellyfin/test")
def api_jellyfin_test(payload: dict = Body(...)):
    """Test Jellyfin connectivity with the provided credentials."""
    url     = str(payload.get("url",     "")).rstrip("/")
    token   = str(payload.get("token",   ""))
    library = str(payload.get("library", "")).strip()

    if not url or not token:
        return {"ok": False, "error": "URL and API key are required"}

    # SSRF guard: only allow http/https schemes
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return {"ok": False, "error": "URL must start with http:// or https://"}
    except Exception:
        return {"ok": False, "error": "Invalid URL format"}

    headers = {"X-Emby-Token": token}

    try:
        r = requests.get(f"{url}/System/Info", headers=headers, timeout=10)
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
        r2 = requests.get(f"{url}/Library/MediaFolders", headers=headers, timeout=10)
        r2.raise_for_status()
        folders = [i.get("Name", "") for i in r2.json().get("Items", [])]
        match = next((f for f in folders if f.lower() == library.lower()), None)
        if not match:
            return {"ok": False, "error": f"Library '{library}' not found. Available: {', '.join(folders) or 'none'}"}
        return {"ok": True, "message": f"Connected — library '{match}' found"}
    except Exception as e:
        return {"ok": False, "error": f"Could not list libraries: {e}"}
