import os
from datetime import datetime
import json
import requests
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from fastapi import FastAPI, Body, Query, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.config import load_config, save_config, is_configured
from app.scanner import build, build_async, scan_state
from app.overrides import load_json, save_json, add_unique, remove_value
from app.logger import get_logger
from app import scheduler

DATA_DIR       = os.getenv("DATA_DIR", "/data")
RESULTS_FILE   = f"{DATA_DIR}/results.json"
OVERRIDES_FILE = f"{DATA_DIR}/overrides.json"
LOG_FILE       = f"{DATA_DIR}/cineplete.log"

APP_VERSION  = os.getenv("APP_VERSION", "dev")
STATIC_DIR   = os.getenv("STATIC_DIR", "/app/static")
GITHUB_REPO = "sdblepas/CinePlete"

# Simple in-memory cache for GitHub release check (avoid hammering the API)
_release_cache: dict = {"checked_at": 0, "latest": None, "url": None}

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
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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
    with open(f"{STATIC_DIR}/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    # Inject version into script URLs for automatic browser cache-busting
    # on every new deployment (browsers re-fetch JS when ?v= changes)
    return html.replace("__VERSION__", APP_VERSION)


# --------------------------------------------------
# Version
# --------------------------------------------------

def _get_latest_release() -> dict:
    """Check GitHub for the latest release, cached for 1 hour."""
    import time
    now = time.time()
    if now - _release_cache["checked_at"] < 3600:
        return _release_cache
    try:
        r = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            _release_cache["latest"] = data.get("tag_name", "").lstrip("v")
            _release_cache["url"]    = data.get("html_url", "")
    except Exception:
        pass
    _release_cache["checked_at"] = now
    return _release_cache


@app.get("/api/version")
def api_version():
    cache = _get_latest_release()
    current = APP_VERSION.lstrip("v")
    latest  = cache.get("latest")
    has_update = bool(latest and latest != current and current not in ("dev", "e2e"))
    return {
        "version":    APP_VERSION,
        "latest":     latest,
        "has_update": has_update,
        "release_url": cache.get("url") if has_update else None,
    }


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
# Overseerr
# --------------------------------------------------

@app.post("/api/overseerr/add")
def overseerr_add(payload: dict = Body(...)):
    cfg = load_config().get("OVERSEERR", {})
    if not cfg.get("OVERSEERR_ENABLED"):
        return {"ok": False, "error": "Overseerr disabled"}
    tmdb_id = int(payload.get("tmdb"))
    headers = {"X-Api-Key": cfg["OVERSEERR_API_KEY"],
               "Content-Type": "application/json"}
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

@app.post("/api/jellyseerr/add")
def jellyseerr_add(payload: dict = Body(...)):
    cfg = load_config().get("JELLYSEERR", {})
    if not cfg.get("JELLYSEERR_ENABLED"):
        return {"ok": False, "error": "Jellyseerr disabled"}
    tmdb_id = int(payload.get("tmdb"))
    headers = {"X-Api-Key": cfg["JELLYSEERR_API_KEY"],
               "Content-Type": "application/json"}
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
# Webhook  (POST /api/webhook?secret=xxx)
# --------------------------------------------------

@app.post("/api/webhook")
def api_webhook(
    secret: str = Query(default=""),
    x_cineplete_secret: str = Header(default="", alias="x-cineplete-secret"),
):
    cfg = load_config().get("WEBHOOK", {})
    if not cfg.get("WEBHOOK_ENABLED"):
        return {"ok": False, "error": "Webhook disabled"}

    saved_secret = str(cfg.get("WEBHOOK_SECRET", "")).strip()
    provided     = secret.strip() or x_cineplete_secret.strip()

    if saved_secret and provided != saved_secret:
        return {"ok": False, "error": "Invalid secret"}

    if scan_state["running"]:
        return {"ok": False, "error": "Scan already in progress"}

    launched = build_async()
    if not launched:
        return {"ok": False, "error": "Could not acquire scan lock"}

    log.info("Webhook triggered scan")
    return {"ok": True, "message": "Scan started"}


# --------------------------------------------------
# Watchtower  (POST /api/watchtower/update)
# --------------------------------------------------

@app.post("/api/watchtower/update")
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

    # Fire-and-forget: Watchtower pulls + restarts the container (kills this process too),
    # so we dispatch in a background thread and return immediately.
    def _fire():
        try:
            r = requests.post(f"{url}/v1/update", headers=headers, timeout=300)
            log.info(f"Watchtower update response: HTTP {r.status_code}")
        except Exception as e:
            log.warning(f"Watchtower update error: {e}")

    import threading
    threading.Thread(target=_fire, daemon=True).start()
    log.info("Watchtower update dispatched (fire-and-forget)")
    return {"ok": True, "message": "Update request sent — container will restart shortly"}


# --------------------------------------------------
# Movie detail (for modal)
# --------------------------------------------------

@app.get("/api/movie/{tmdb_id}")
def api_movie_detail(tmdb_id: int):
    from app.tmdb import TMDB
    cfg     = load_config()
    api_key = cfg.get("TMDB", {}).get("TMDB_API_KEY")
    if not api_key:
        return {"error": "TMDB not configured"}
    t  = TMDB(api_key)
    md = t.movie(tmdb_id)
    if not md:
        return {"error": "Movie not found"}
    credits_url = (
        f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits"
        f"?api_key={api_key}"
    )
    credits = t.get(credits_url)
    cast = [
        {
            "name":      c["name"],
            "character": c.get("character", ""),
            "profile":   t.poster_url(c.get("profile_path")),
        }
        for c in (credits.get("cast") or [])[:8]
    ]
    backdrop = (
        f"https://image.tmdb.org/t/p/w1280{md['backdrop_path']}"
        if md.get("backdrop_path") else None
    )
    # Fetch trailer (YouTube key)
    videos_url = (
        f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos"
        f"?api_key={api_key}"
    )
    videos_data = t.get(videos_url)
    trailer_key = None
    for v in (videos_data.get("results") or []):
        if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("official"):
            trailer_key = v["key"]
            break
    if not trailer_key:
        for v in (videos_data.get("results") or []):
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                trailer_key = v.get("key")
                break

    return {
        "tmdb":        tmdb_id,
        "title":       md.get("title"),
        "year":        (md.get("release_date") or "")[:4],
        "poster":      t.poster_url(md.get("poster_path")),
        "backdrop":    backdrop,
        "overview":    md.get("overview", ""),
        "tagline":     md.get("tagline", ""),
        "rating":      md.get("vote_average", 0),
        "votes":       md.get("vote_count", 0),
        "runtime":     md.get("runtime"),
        "genres":      [g["name"] for g in md.get("genres") or []],
        "cast":        cast,
        "trailer_key": trailer_key,
        "tmdb_url":    f"https://www.themoviedb.org/movie/{tmdb_id}",
    }


# --------------------------------------------------
# Export
# --------------------------------------------------

@app.get("/api/export")
def api_export(format: str = Query(default="csv"), tab: str = Query(default="wishlist")):
    results = read_results()
    if not results:
        return PlainTextResponse("No scan data available", status_code=404)

    movies: list = []
    if tab == "wishlist":
        movies = results.get("wishlist", [])
    elif tab == "classics":
        movies = results.get("classics", [])
    elif tab == "suggestions":
        movies = results.get("suggestions", [])
    elif tab in ("franchises", "directors", "actors"):
        for g in results.get(tab, []):
            movies.extend(g.get("missing", []))

    filename = f"cineplete-{tab}.csv"

    if format == "letterboxd":
        lines = ["Title,Year,tmdbID,WatchedDate,Rating10,Review"]
        for m in movies:
            title = (m.get("title") or "").replace('"', '""')
            lines.append(f'"{title}",{m.get("year","")},{m.get("tmdb","")},,,')
        return PlainTextResponse(
            "\n".join(lines), media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Default: CSV
    lines = ["Title,Year,TMDB ID,Rating,Votes,Popularity"]
    for m in movies:
        title = (m.get("title") or "").replace('"', '""')
        lines.append(
            f'"{title}",{m.get("year","")},{m.get("tmdb","")}'
            f',{m.get("rating","")},{m.get("votes","")},{round(m.get("popularity",0),1)}'
        )
    return PlainTextResponse(
        "\n".join(lines), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------
# Global search
# --------------------------------------------------

@app.get("/api/search")
def api_search(q: str = Query(default="")):
    if not q or len(q) < 2:
        return {"results": []}
    results = read_results()
    if not results:
        return {"results": []}

    q_lower = q.lower()
    hits: list = []

    def _match(m: dict, tab: str, group: str = ""):
        if q_lower in (m.get("title") or "").lower():
            hits.append({**m, "_tab": tab, "_group": group})

    for f in results.get("franchises", []):
        for m in f.get("missing", []):
            _match(m, "franchises", f.get("name", ""))
    for d in results.get("directors", []):
        for m in d.get("missing", []):
            _match(m, "directors", d.get("name", ""))
    for a in results.get("actors", []):
        for m in a.get("missing", []):
            _match(m, "actors", a.get("name", ""))
    for m in results.get("classics", []):
        _match(m, "classics")
    for m in results.get("suggestions", []):
        _match(m, "suggestions")
    for m in results.get("wishlist", []):
        _match(m, "wishlist")

    # Deduplicate by tmdb ID, keep first occurrence
    seen: set = set()
    unique: list = []
    for h in hits:
        if h.get("tmdb") not in seen:
            seen.add(h.get("tmdb"))
            unique.append(h)

    return {"results": unique[:40], "total": len(unique)}


# --------------------------------------------------
# Jellyfin connection test
# --------------------------------------------------

@app.post("/api/jellyfin/test")
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