import os
from datetime import datetime
import json
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI, Body, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.config import load_config, save_config, is_configured
from app.scanner import build, build_async, scan_state
from app.overrides import load_json, save_json, add_unique, remove_value
from app.logger import get_logger
from app import scheduler

DATA_DIR       = "/data"
RESULTS_FILE   = f"{DATA_DIR}/results.json"
OVERRIDES_FILE = f"{DATA_DIR}/overrides.json"
LOG_FILE       = f"{DATA_DIR}/cineplete.log"

APP_VERSION = os.getenv("APP_VERSION", "dev")

log = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start scheduler on boot
    cfg      = load_config()
    interval = int(cfg.get("AUTOMATION", {}).get("LIBRARY_POLL_INTERVAL", 30))
    scheduler.start(interval)
    yield
    scheduler.stop()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="/app/static"), name="static")


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def read_results() -> dict | None:
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def current_radarr() -> dict:
    return load_config()["RADARR"]


# --------------------------------------------------
# Static
# --------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    with open("/app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------
# Version
# --------------------------------------------------

@app.get("/api/version")
def api_version():
    return {"version": APP_VERSION}


# --------------------------------------------------
# Config
# --------------------------------------------------

@app.get("/api/config")
def api_get_config():
    return load_config()


@app.get("/api/config/status")
def api_config_status():
    cfg = load_config()
    return {"configured": is_configured(cfg)}


@app.post("/api/config")
def api_save_config(payload: dict = Body(...)):
    cfg = save_config(payload)
    scheduler.restart()
    return {"ok": True, "configured": is_configured(cfg)}


# --------------------------------------------------
# Results  (FIX #2 — never blocks on first load)
# --------------------------------------------------

@app.get("/api/results")
def api_results():
    if not is_configured():
        return {"configured": False, "message": "Setup required"}

    data = read_results()

    if data is None:
        # No results yet — kick off a background scan and tell the UI to poll
        launched = build_async()
        return {
            "configured": True,
            "scanning": True,
            "launched": launched,
            "message": "First scan started — poll /api/scan/status for progress",
        }

    data["configured"] = True
    data["scanning"]   = scan_state["running"]
    return data


# --------------------------------------------------
# Scan  (FIX #4, #10 — async + lock)
# --------------------------------------------------

@app.post("/api/scan")
def api_scan():
    if not is_configured():
        return {"ok": False, "error": "Setup required"}

    if scan_state["running"]:
        return {"ok": False, "error": "Scan already in progress"}

    launched = build_async()
    if not launched:
        return {"ok": False, "error": "Could not acquire scan lock"}

    return {"ok": True, "message": "Scan started"}


# --------------------------------------------------
# Scan progress  (FIX #8)
# --------------------------------------------------

@app.get("/api/scan/status")
def api_scan_status():
    """
    Returns current scan progress. Poll this while scan_state['running'] is True.
    When running is False and error is None, fetch /api/results for fresh data.
    """
    return {
        "running":        scan_state["running"],
        "step":           scan_state["step"],
        "step_index":     scan_state["step_index"],
        "step_total":     scan_state["step_total"],
        "detail":         scan_state["detail"],
        "error":          scan_state["error"],
        "last_completed": scan_state["last_completed"],
        "last_duration":  scan_state["last_duration"],
    }


# --------------------------------------------------
# Ignore / Unignore
# --------------------------------------------------

@app.post("/api/ignore")
def api_ignore(payload: dict = Body(...)):
    ov    = load_json(OVERRIDES_FILE)
    kind  = payload.get("kind")
    value = payload.get("value")

    if kind == "movie":
        add_unique(ov["ignore_movies"], int(value))
    elif kind == "franchise":
        add_unique(ov["ignore_franchises"], str(value))
    elif kind == "director":
        add_unique(ov["ignore_directors"], str(value))
    elif kind == "actor":
        add_unique(ov["ignore_actors"], str(value))
    else:
        return {"ok": False, "error": f"Unknown kind: {kind}"}

    save_json(OVERRIDES_FILE, ov)
    return {"ok": True}


@app.post("/api/unignore")
def api_unignore(payload: dict = Body(...)):
    ov    = load_json(OVERRIDES_FILE)
    kind  = payload.get("kind")
    value = payload.get("value")

    if kind == "movie":
        remove_value(ov["ignore_movies"], int(value))
    elif kind == "franchise":
        remove_value(ov["ignore_franchises"], str(value))
    elif kind == "director":
        remove_value(ov["ignore_directors"], str(value))
    elif kind == "actor":
        remove_value(ov["ignore_actors"], str(value))

    save_json(OVERRIDES_FILE, ov)
    return {"ok": True}


# --------------------------------------------------
# Wishlist
# --------------------------------------------------

@app.post("/api/wishlist/add")
def wishlist_add(payload: dict = Body(...)):
    ov = load_json(OVERRIDES_FILE)
    add_unique(ov["wishlist_movies"], int(payload.get("tmdb")))
    save_json(OVERRIDES_FILE, ov)
    return {"ok": True}


@app.post("/api/wishlist/remove")
def wishlist_remove(payload: dict = Body(...)):
    ov = load_json(OVERRIDES_FILE)
    remove_value(ov["wishlist_movies"], int(payload.get("tmdb")))
    save_json(OVERRIDES_FILE, ov)
    return {"ok": True}


# --------------------------------------------------
# Radarr
# --------------------------------------------------

@app.post("/api/radarr/add")
def radarr_add(payload: dict = Body(...)):
    radarr_cfg = current_radarr()

    if not radarr_cfg["RADARR_ENABLED"]:
        return {"ok": False, "error": "Radarr disabled"}

    tmdb_id = int(payload.get("tmdb"))
    title   = payload.get("title")

    body = {
        "title":            title,
        "tmdbId":           tmdb_id,
        "qualityProfileId": int(radarr_cfg["RADARR_QUALITY_PROFILE_ID"]),
        "rootFolderPath":   radarr_cfg["RADARR_ROOT_FOLDER_PATH"],
        "monitored":        bool(radarr_cfg["RADARR_MONITORED"]),
        "addOptions":       {"searchForMovie": bool(radarr_cfg.get("RADARR_SEARCH_ON_ADD", False))},
    }

    headers = {"X-Api-Key": radarr_cfg["RADARR_API_KEY"]}

    try:
        r = requests.post(
            f"{radarr_cfg['RADARR_URL']}/api/v3/movie",
            json=body,
            headers=headers,
            timeout=20,
        )
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}

    if r.status_code not in (200, 201):
        return {"ok": False, "error": r.text}

    return {"ok": True}



# --------------------------------------------------
# Cache
# --------------------------------------------------

@app.get("/api/cache/info")
def api_cache_info():
    """Return TMDB cache file age and size."""
    cache_file = f"{DATA_DIR}/tmdb_cache.json"
    try:
        stat = os.stat(cache_file)
        age_s = int(datetime.utcnow().timestamp() - stat.st_mtime)
        size_mb = round(stat.st_size / 1024 / 1024, 1)
        return {"exists": True, "age_seconds": age_s, "size_mb": size_mb}
    except FileNotFoundError:
        return {"exists": False, "age_seconds": None, "size_mb": 0}

@app.post("/api/cache/backup")
def api_cache_backup():
    """Copy tmdb_cache.json → tmdb_cache.backup.json"""
    import shutil
    cache_file  = f"{DATA_DIR}/tmdb_cache.json"
    backup_file = f"{DATA_DIR}/tmdb_cache.backup.json"
    try:
        if not os.path.exists(cache_file):
            return {"ok": False, "error": "No cache file to back up"}
        shutil.copy2(cache_file, backup_file)
        stat = os.stat(backup_file)
        size_mb = round(stat.st_size / 1024 / 1024, 1)
        log.info(f"TMDB cache backed up ({size_mb} MB)")
        return {"ok": True, "size_mb": size_mb}
    except Exception as e:
        log.error(f"Cache backup failed: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/api/cache/restore")
def api_cache_restore():
    """Copy tmdb_cache.backup.json → tmdb_cache.json"""
    import shutil
    cache_file  = f"{DATA_DIR}/tmdb_cache.json"
    backup_file = f"{DATA_DIR}/tmdb_cache.backup.json"
    try:
        if not os.path.exists(backup_file):
            return {"ok": False, "error": "No backup file found"}
        shutil.copy2(backup_file, cache_file)
        stat = os.stat(cache_file)
        size_mb = round(stat.st_size / 1024 / 1024, 1)
        log.info(f"TMDB cache restored from backup ({size_mb} MB)")
        return {"ok": True, "size_mb": size_mb}
    except Exception as e:
        log.error(f"Cache restore failed: {e}")
        return {"ok": False, "error": str(e)}

@app.get("/api/cache/backup/info")
def api_cache_backup_info():
    """Return backup file age and size if it exists."""
    backup_file = f"{DATA_DIR}/tmdb_cache.backup.json"
    try:
        stat    = os.stat(backup_file)
        age_s   = int(datetime.utcnow().timestamp() - stat.st_mtime)
        size_mb = round(stat.st_size / 1024 / 1024, 1)
        return {"exists": True, "age_seconds": age_s, "size_mb": size_mb}
    except FileNotFoundError:
        return {"exists": False}

@app.post("/api/cache/clear")
def api_cache_clear():
    """Delete the TMDB cache file."""
    cache_file = f"{DATA_DIR}/tmdb_cache.json"
    try:
        os.remove(cache_file)
        log.info("TMDB cache cleared by user")
        return {"ok": True}
    except FileNotFoundError:
        return {"ok": True, "message": "Cache was already empty"}
    except Exception as e:
        log.error(f"Could not clear cache: {e}")
        return {"ok": False, "error": str(e)}

# --------------------------------------------------
# Logs
# --------------------------------------------------

@app.get("/api/logs")
def api_logs(lines: int = Query(default=200, le=500)):
    """Return the last N lines of cineplete.log."""
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:]
        return {"lines": [l.rstrip() for l in tail]}
    except FileNotFoundError:
        return {"lines": ["No log file yet — run a scan first."]}
    except Exception as e:
        log.error(f"Could not read log file: {e}")
        return {"lines": [f"Error reading log file: {e}"]}