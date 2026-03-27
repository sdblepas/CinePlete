import copy
import os
from datetime import datetime
import json
import requests
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from fastapi import FastAPI, Body, Query, Header, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import load_config, save_config, is_configured
from app.scanner import build, build_async, scan_state
from app.overrides import load_json, save_json, add_unique, remove_value
from app.logger import get_logger
from app import scheduler
from app.auth import (
    COOKIE_NAME, get_client_ip, is_local_address,
    hash_password, verify_password,
    create_token, verify_token, generate_secret_key,
)

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

# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

_PUBLIC_PATHS    = {"/login", "/api/auth/login", "/api/auth/status", "/api/version"}
_PUBLIC_PREFIXES = ("/static/",)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Always public
        if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        cfg      = load_config()
        auth_cfg = cfg.get("AUTH", {})
        method   = auth_cfg.get("AUTH_METHOD", "None")

        if method == "None":
            return await call_next(request)

        if method == "DisabledForLocalAddresses":
            if is_local_address(get_client_ip(request)):
                return await call_next(request)

        # Validate session cookie
        token  = request.cookies.get(COOKIE_NAME, "")
        secret = auth_cfg.get("AUTH_SECRET_KEY", "")
        if token and secret and verify_token(token, secret):
            return await call_next(request)

        # Not authenticated
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=302)


app.add_middleware(AuthMiddleware)


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


def _radarr_post(cfg_section: dict, prefix: str, tmdb_id: int, title: str) -> dict:
    """Shared logic for posting a movie to any Radarr instance."""
    url     = str(cfg_section.get(f"{prefix}_URL", "")).rstrip("/")
    api_key = str(cfg_section.get(f"{prefix}_API_KEY", "")).strip()
    root    = str(cfg_section.get(f"{prefix}_ROOT_FOLDER_PATH", ""))
    quality = int(cfg_section.get(f"{prefix}_QUALITY_PROFILE_ID", 6))
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


@app.get("/login", response_class=HTMLResponse)
def login_page():
    with open(f"{STATIC_DIR}/login.html", "r", encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------
# Auth API
# --------------------------------------------------

@app.get("/api/auth/status")
def api_auth_status(request: Request):
    """Returns current auth mode and whether the current request is authenticated."""
    cfg      = load_config()
    auth_cfg = cfg.get("AUTH", {})
    method   = auth_cfg.get("AUTH_METHOD", "None")
    has_user = bool(auth_cfg.get("AUTH_USERNAME") and auth_cfg.get("AUTH_PASSWORD_HASH"))

    authed = False
    if method == "None":
        authed = True
    elif method == "DisabledForLocalAddresses" and is_local_address(get_client_ip(request)):
        authed = True
    else:
        token  = request.cookies.get(COOKIE_NAME, "")
        secret = auth_cfg.get("AUTH_SECRET_KEY", "")
        authed = bool(token and secret and verify_token(token, secret))

    return {"method": method, "authenticated": authed, "has_user": has_user}


@app.post("/api/auth/login")
async def api_auth_login(request: Request, response: Response):
    body        = await request.json()
    username    = str(body.get("username", "")).strip()
    password    = str(body.get("password", ""))
    remember_me = bool(body.get("remember_me", False))

    cfg      = load_config()
    auth_cfg = cfg.get("AUTH", {})

    stored_user = auth_cfg.get("AUTH_USERNAME", "")
    stored_hash = auth_cfg.get("AUTH_PASSWORD_HASH", "")
    stored_salt = auth_cfg.get("AUTH_PASSWORD_SALT", "")
    secret      = auth_cfg.get("AUTH_SECRET_KEY", "")

    if not stored_user or not stored_hash:
        return {"ok": False, "error": "No user configured — set credentials in Config first"}

    if not secret:
        return {"ok": False, "error": "Auth not fully configured (missing secret key)"}

    if username != stored_user or not verify_password(password, stored_hash, stored_salt):
        log.warning(f"Auth failed for '{username}' from {get_client_ip(request)}")
        return {"ok": False, "error": "Invalid username or password"}

    token   = create_token(username, remember_me, secret)
    max_age = 30 * 86_400 if remember_me else 86_400
    response.set_cookie(
        COOKIE_NAME, token,
        max_age=max_age, httponly=True, samesite="lax", path="/",
    )
    log.info(f"Auth success for '{username}' from {get_client_ip(request)}")
    return {"ok": True}


@app.post("/api/auth/logout")
def api_auth_logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


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


def _parse_ver(v: str):
    """Parse a semver string into a comparable tuple, e.g. '2.4.0' → (2, 4, 0)."""
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0, 0, 0)


@app.get("/api/version")
def api_version():
    cache = _get_latest_release()
    current = APP_VERSION.lstrip("v")
    latest  = cache.get("latest")
    # Only show update banner when latest is strictly NEWER than current.
    # If current > latest (e.g. pre-release ahead of published tag) → no banner.
    has_update = bool(
        latest
        and current not in ("dev", "e2e")
        and _parse_ver(latest) > _parse_ver(current)
    )
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
    cfg  = copy.deepcopy(load_config())
    auth = cfg.get("AUTH", {})
    # Expose whether a password is set without exposing the hash
    auth["AUTH_HAS_PASSWORD"] = bool(auth.get("AUTH_PASSWORD_HASH"))
    # Never send sensitive fields to the browser
    for key in ("AUTH_PASSWORD_HASH", "AUTH_PASSWORD_SALT", "AUTH_SECRET_KEY"):
        auth.pop(key, None)
    return cfg


@app.get("/api/config/status")
def api_config_status():
    cfg = load_config()
    return {"configured": is_configured(cfg)}


@app.post("/api/config")
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
        tmdb_id = int(value)
        add_unique(ov["ignore_movies"], tmdb_id)
        ov.setdefault("ignore_movies_meta", {})[str(tmdb_id)] = {
            "title":  payload.get("title", ""),
            "year":   payload.get("year"),
            "poster": payload.get("poster"),
        }
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
        tmdb_id = int(value)
        remove_value(ov["ignore_movies"], tmdb_id)
        ov.setdefault("ignore_movies_meta", {}).pop(str(tmdb_id), None)
    elif kind == "franchise":
        remove_value(ov["ignore_franchises"], str(value))
    elif kind == "director":
        remove_value(ov["ignore_directors"], str(value))
    elif kind == "actor":
        remove_value(ov["ignore_actors"], str(value))

    save_json(OVERRIDES_FILE, ov)
    return {"ok": True}


@app.get("/api/ignored")
def api_ignored():
    ov   = load_json(OVERRIDES_FILE)
    ids  = ov.get("ignore_movies", [])
    meta = ov.get("ignore_movies_meta", {})
    movies = []
    for tmdb_id in ids:
        m = meta.get(str(tmdb_id), {})
        movies.append({
            "tmdb":   tmdb_id,
            "title":  m.get("title", f"Movie {tmdb_id}"),
            "year":   m.get("year"),
            "poster": m.get("poster"),
        })
    return {"ok": True, "movies": movies}


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
# Watchlist import (Letterboxd via RSS)
# --------------------------------------------------

def _tmdb_search(api_key: str, title: str, year=None) -> int | None:
    """Search TMDB by title+year, return first matching TMDB ID or None."""
    params = {"api_key": api_key, "query": title, "include_adult": "false"}
    if year:
        params["year"] = str(year)
    try:
        r = requests.get(
            "https://api.themoviedb.org/3/search/movie",
            params=params,
            timeout=8,
        )
        results = r.json().get("results", [])
        return results[0]["id"] if results else None
    except Exception:
        return None


def _fetch_via_flaresolverr(rss_url: str, flaresolverr_url: str) -> bytes | None:
    """
    Route a request through FlareSolverr to bypass Cloudflare.
    Returns raw response bytes on success, None on failure.
    """
    base = flaresolverr_url.rstrip("/")
    try:
        resp = requests.post(
            f"{base}/v1",
            json={"cmd": "request.get", "url": rss_url, "maxTimeout": 60000},
            headers={"Content-Type": "application/json"},
            timeout=70,
        )
        data = resp.json()
        if data.get("status") == "ok":
            content = data.get("solution", {}).get("response", "")
            return content.encode("utf-8") if isinstance(content, str) else content
    except Exception as e:
        log.debug(f"FlareSolverr error for {rss_url}: {e}")
    return None


def _parse_films_from_html(html_text: str) -> list[dict]:
    """
    Extract film titles from the HTML description in a Letterboxd lists-feed
    item.  Matches: <a href="https://letterboxd.com/film/slug/">Title</a>
    Used as fallback when the list RSS itself is blocked (403/404).
    """
    import re
    skip = {"View the full list on Letterboxd", "here", "letterboxd.com"}
    pattern = re.compile(
        r'href="https://letterboxd\.com/film/([^/"]+)/"[^>]*>([^<]{1,120})</a>',
        re.IGNORECASE,
    )
    seen: set = set()
    results = []
    for m in pattern.finditer(html_text):
        title = m.group(2).strip()
        slug  = m.group(1)
        if title and title not in skip and slug not in seen:
            seen.add(slug)
            results.append({"title": title})
    return results


def _fetch_letterboxd_rss(url: str, _depth: int = 0, flaresolverr: str = "") -> list[dict]:
    """
    Fetch movies from a Letterboxd RSS feed.

    Accepts any public Letterboxd URL and derives the RSS endpoint:
      /username/watchlist/      → /username/watchlist/rss/
      /username/list/my-list/   → /username/list/my-list/rss/
      /username/rss/            → used as-is (diary or curator lists feed)
      /username/films/          → /username/rss/ (no /films/rss/ endpoint)

    Element matching is namespace-agnostic (local name only).

    Auto-expansion for curator accounts: if the RSS is a "lists feed" (items
    link to /list/ pages with no filmTitle/movieId), each linked list's RSS is
    fetched (one level deep, max 10 lists). When a list RSS is blocked (403),
    FlareSolverr is tried if configured; otherwise titles are extracted from
    the item's description HTML as a partial fallback.
    """
    import xml.etree.ElementTree as ET

    path = urlparse(url).path.rstrip("/")

    if path.endswith("/rss"):
        rss_url = url.rstrip("/") + "/"
    elif path.endswith("/films"):
        # No /films/rss/ — fall back to the user's diary RSS
        username = path.lstrip("/").split("/")[0]
        rss_url = f"https://letterboxd.com/{username}/rss/"
    else:
        rss_url = url.rstrip("/") + "/rss/"

    # Try direct fetch first; on Cloudflare block (403) try FlareSolverr
    content: bytes | None = None
    try:
        resp = requests.get(
            rss_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CinePlete/1.0)"},
            timeout=15,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            content = resp.content
        elif resp.status_code == 403 and flaresolverr:
            log.debug(f"Letterboxd: 403 on {rss_url}, retrying via FlareSolverr")
            content = _fetch_via_flaresolverr(rss_url, flaresolverr)
    except requests.exceptions.RequestException:
        if flaresolverr:
            content = _fetch_via_flaresolverr(rss_url, flaresolverr)

    if not content:
        return []

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    # Extract local name from Clark-notation "{uri}local" or plain "local"
    def local(tag: str) -> str:
        return tag.split("}")[-1] if "}" in tag else tag

    movies: list[dict] = []
    # list_links: (url, description_html) for curator-style list feeds
    list_links: list[tuple[str, str]] = []

    for item in root.findall(".//item"):
        tmdb_id = title = year = None
        item_link: str | None = None
        item_desc: str        = ""

        for child in item:
            lname = local(child.tag)
            text  = (child.text or "").strip()
            if lname == "movieId" and text:
                try:
                    tmdb_id = int(text)
                except (ValueError, TypeError):
                    pass
            elif lname == "filmTitle" and text:
                title = text
            elif lname == "filmYear" and text:
                try:
                    year = int(text)
                except ValueError:
                    pass
            elif lname == "link" and text and "/list/" in text:
                item_link = text
            elif lname == "description" and text:
                item_desc = text

        if tmdb_id:
            movies.append({"tmdb_id": tmdb_id})
        elif title:
            movies.append({"title": title, "year": year})
        elif item_link:
            list_links.append((item_link, item_desc))

    # If this is a curator's lists-feed (no film entries, only list links),
    # try each list's RSS; fall back to parsing description HTML on 403/404.
    if not movies and list_links and _depth == 0:
        log.debug(
            f"Letterboxd: lists feed at {rss_url} — expanding {len(list_links)} lists"
        )
        for list_url, desc_html in list_links[:10]:
            child_movies = _fetch_letterboxd_rss(list_url, _depth=1, flaresolverr=flaresolverr)
            if child_movies:
                movies.extend(child_movies)
            elif desc_html:
                # List RSS blocked — salvage titles from description HTML
                fallback = _parse_films_from_html(desc_html)
                log.debug(
                    f"Letterboxd: list RSS blocked for {list_url}, "
                    f"extracted {len(fallback)} titles from description"
                )
                movies.extend(fallback)

    return movies


@app.post("/api/import/watchlist")
def import_watchlist(payload: dict = Body(...)):
    """
    Import movies from a public Letterboxd URL into the wishlist via RSS.
    Supports: watchlist, named lists, diary feed (/rss/), and /films/ pages.
    TMDB IDs come directly from the RSS feed; title-only entries are resolved
    via TMDB search (requires TMDB API key in config).
    """
    url = str(payload.get("url", "")).strip()
    if not url:
        return {"ok": False, "error": "URL is required"}

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {"ok": False, "error": "Invalid URL"}

    host = parsed.netloc.lower().replace("www.", "")
    if "letterboxd.com" not in host:
        return {"ok": False, "error": "Only Letterboxd URLs are supported"}

    cfg          = load_config()
    api_key      = cfg.get("TMDB", {}).get("TMDB_API_KEY", "")
    flaresolverr = cfg.get("FLARESOLVERR", {}).get("FLARESOLVERR_URL", "").rstrip("/")

    raw = _fetch_letterboxd_rss(url, flaresolverr=flaresolverr)
    if not raw:
        return {"ok": False, "error": "No movies found — check the URL is a public Letterboxd list or watchlist"}

    ov       = load_json(OVERRIDES_FILE)
    existing = set(ov.get("wishlist_movies", []))
    added    = 0
    skipped  = 0

    for item in raw:
        tmdb_id = item.get("tmdb_id")
        if not tmdb_id:
            # Needs TMDB search — only possible if API key is configured
            if not api_key:
                skipped += 1
                continue
            tmdb_id = _tmdb_search(api_key, item["title"], item.get("year"))
        if not tmdb_id or tmdb_id in existing:
            skipped += 1
            continue
        add_unique(ov["wishlist_movies"], tmdb_id)
        existing.add(tmdb_id)
        added += 1

    save_json(OVERRIDES_FILE, ov)
    return {"ok": True, "added": added, "skipped": skipped, "total": added + skipped}


# --------------------------------------------------
# Letterboxd tab — persistent URL list + scored movies
# --------------------------------------------------

def _validate_letterboxd_url(url: str):
    """Return (cleaned_url, error_string_or_None)."""
    url = url.strip()
    if not url:
        return None, "URL is required"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None, "Invalid URL"
    host = parsed.netloc.lower().replace("www.", "")
    if "letterboxd.com" not in host:
        return None, "Only Letterboxd URLs are supported"
    return url, None


@app.get("/api/letterboxd/urls")
def letterboxd_get_urls():
    ov = load_json(OVERRIDES_FILE)
    return {"ok": True, "urls": ov.get("letterboxd_urls", [])}


@app.post("/api/letterboxd/urls")
def letterboxd_add_url(payload: dict = Body(...)):
    url, err = _validate_letterboxd_url(str(payload.get("url", "")))
    if err:
        return {"ok": False, "error": err}
    ov = load_json(OVERRIDES_FILE)
    ov.setdefault("letterboxd_urls", [])
    if url not in ov["letterboxd_urls"]:
        ov["letterboxd_urls"].append(url)
        save_json(OVERRIDES_FILE, ov)
    return {"ok": True}


@app.post("/api/letterboxd/urls/remove")
def letterboxd_remove_url(payload: dict = Body(...)):
    url = str(payload.get("url", "")).strip()
    ov  = load_json(OVERRIDES_FILE)
    urls = ov.get("letterboxd_urls", [])
    if url in urls:
        urls.remove(url)
        save_json(OVERRIDES_FILE, ov)
    return {"ok": True}


@app.get("/api/letterboxd/movies")
def letterboxd_get_movies():
    """
    Fetch all saved Letterboxd URLs, merge their movie lists, score each
    movie by how many lists it appears in, enrich with TMDB metadata, and
    return sorted by score desc (ties broken by TMDB rating).
    """
    from app.tmdb import TMDB
    from collections import Counter

    cfg             = load_config()
    api_key         = cfg.get("TMDB", {}).get("TMDB_API_KEY", "")
    flaresolverr    = cfg.get("FLARESOLVERR", {}).get("FLARESOLVERR_URL", "").rstrip("/")
    if not api_key:
        return {"ok": False, "error": "TMDB API key not configured"}

    ov   = load_json(OVERRIDES_FILE)
    urls = ov.get("letterboxd_urls", [])
    if not urls:
        return {"ok": True, "movies": [], "urls": []}

    counts: Counter = Counter()   # tmdb_id (int) → appearance count
    url_status: list[dict] = []   # per-URL fetch results for UI feedback

    for lb_url in urls:
        raw = _fetch_letterboxd_rss(lb_url, flaresolverr=flaresolverr)
        seen_this_url: set = set()
        resolved = 0
        for item in raw:
            tmdb_id = item.get("tmdb_id")
            if not tmdb_id and item.get("title"):
                tmdb_id = _tmdb_search(api_key, item["title"], item.get("year"))
            if tmdb_id and tmdb_id not in seen_this_url:
                counts[tmdb_id] += 1
                seen_this_url.add(tmdb_id)
                resolved += 1
        url_status.append({
            "url":      lb_url,
            "raw":      len(raw),
            "resolved": resolved,
        })

    if not counts:
        return {"ok": True, "movies": [], "urls": urls, "url_status": url_status}

    t        = TMDB(api_key)
    wishlist = set(ov.get("wishlist_movies", []))
    ignored  = set(ov.get("ignore_movies", []))

    movies = []
    for tmdb_id, score in counts.most_common():
        if tmdb_id in ignored:
            continue
        md = t.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={api_key}")
        if not md or md.get("success") is False:
            continue
        movies.append({
            "tmdb":     tmdb_id,
            "title":    md.get("title"),
            "year":     (md.get("release_date") or "")[:4],
            "poster":   t.poster_url(md.get("poster_path")),
            "rating":   md.get("vote_average", 0),
            "score":    score,
            "wishlist": tmdb_id in wishlist,
        })

    # Sort: score desc, then rating desc as tie-breaker
    movies.sort(key=lambda m: (-m["score"], -(m["rating"] or 0)))

    return {
        "ok":         True,
        "movies":     movies,
        "urls":       urls,
        "raw_count":  sum(counts.values()),   # total appearances across all lists (debug)
        "unique":     len(counts),            # unique TMDB IDs found before enrichment
    }


# --------------------------------------------------
# Radarr
# --------------------------------------------------

@app.get("/api/radarr/profiles")
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


@app.post("/api/radarr/add")
def radarr_add(payload: dict = Body(...), instance: str = Query(default="primary")):
    tmdb_id = int(payload.get("tmdb"))
    title   = str(payload.get("title", ""))
    cfg     = load_config()

    if instance == "4k":
        section = cfg.get("RADARR_4K", {})
        if not section.get("RADARR_4K_ENABLED"):
            return {"ok": False, "error": "Radarr 4K disabled"}
        return _radarr_post(section, "RADARR_4K", tmdb_id, title)

    # primary
    section = cfg.get("RADARR", {})
    if not section.get("RADARR_ENABLED"):
        return {"ok": False, "error": "Radarr disabled"}
    return _radarr_post(section, "RADARR", tmdb_id, title)



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
            r = requests.post(f"{url}/v1/update?scope=cineplete", headers=headers, timeout=300)
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