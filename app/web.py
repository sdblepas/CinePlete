import os
import json
import requests
from fastapi import FastAPI, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.config import load_config, save_config, is_configured
from app.scanner import build, build_async, scan_state
from app.overrides import load_json, save_json, add_unique, remove_value

DATA_DIR = "/app/data"
RESULTS_FILE = f"{DATA_DIR}/results.json"
OVERRIDES_FILE = f"{DATA_DIR}/overrides.json"

app = FastAPI()
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
        "addOptions":       {"searchForMovie": False},
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