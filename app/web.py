import os
import json
import requests
from fastapi import FastAPI, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

from app.scanner import build
from app.overrides import load_json, save_json, add_unique, remove_value

load_dotenv()

DATA_DIR = "/app/data"
RESULTS_FILE = f"{DATA_DIR}/results.json"
OVERRIDES_FILE = f"{DATA_DIR}/overrides.json"

RADARR_ENABLED = os.getenv("RADARR_ENABLED", "false").lower() == "true"
RADARR_URL = os.getenv("RADARR_URL", "")
RADARR_API_KEY = os.getenv("RADARR_API_KEY", "")
RADARR_ROOT = os.getenv("RADARR_ROOT_FOLDER_PATH", "/movies")
RADARR_PROFILE = int(os.getenv("RADARR_QUALITY_PROFILE_ID", "1"))
RADARR_MONITORED = os.getenv("RADARR_MONITORED", "true").lower() == "true"

app = FastAPI()

app.mount("/static", StaticFiles(directory="/app/static"), name="static")


def read_results():

    try:
        with open(RESULTS_FILE) as f:
            return json.load(f)
    except Exception:
        return None


@app.get("/", response_class=HTMLResponse)
def index():

    with open("/app/static/index.html") as f:
        return f.read()


@app.get("/api/results")
def api_results():

    data = read_results()

    if data is None:
        data = build()

    return data


@app.post("/api/scan")
def api_scan():

    return build()


@app.post("/api/ignore")
def api_ignore(payload: dict = Body(...)):

    ov = load_json(OVERRIDES_FILE)

    kind = payload.get("kind")
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
        return {"ok": False}

    save_json(OVERRIDES_FILE, ov)

    return {"ok": True}


@app.post("/api/unignore")
def api_unignore(payload: dict = Body(...)):

    ov = load_json(OVERRIDES_FILE)

    kind = payload.get("kind")
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


@app.post("/api/wishlist/add")
def wishlist_add(payload: dict = Body(...)):

    ov = load_json(OVERRIDES_FILE)

    tmdb = int(payload.get("tmdb"))

    add_unique(ov["wishlist_movies"], tmdb)

    save_json(OVERRIDES_FILE, ov)

    return {"ok": True}


@app.post("/api/wishlist/remove")
def wishlist_remove(payload: dict = Body(...)):

    ov = load_json(OVERRIDES_FILE)

    tmdb = int(payload.get("tmdb"))

    remove_value(ov["wishlist_movies"], tmdb)

    save_json(OVERRIDES_FILE, ov)

    return {"ok": True}


@app.post("/api/radarr/add")
def radarr_add(payload: dict = Body(...)):

    if not RADARR_ENABLED:
        return {"ok": False, "error": "RADARR disabled"}

    tmdb_id = int(payload.get("tmdb"))
    title = payload.get("title")

    body = {
        "title": title,
        "tmdbId": tmdb_id,
        "qualityProfileId": RADARR_PROFILE,
        "rootFolderPath": RADARR_ROOT,
        "monitored": RADARR_MONITORED,
        "addOptions": {
            "searchForMovie": False
        }
    }

    headers = {
        "X-Api-Key": RADARR_API_KEY
    }

    r = requests.post(
        f"{RADARR_URL}/api/v3/movie",
        json=body,
        headers=headers,
        timeout=20
    )

    if r.status_code not in (200, 201):
        return {"ok": False, "error": r.text}

    return {"ok": True}