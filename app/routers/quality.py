"""
GET /api/quality/upgrades — Movies in primary Radarr with files at 720p or lower
that have not yet been added to Radarr 4K.  Cached for 15 minutes.

POST /api/quality/refresh — Bust the upgrade cache (called after a 4K add).
"""
import time
import logging

import requests
from urllib.parse import urlparse
from fastapi import APIRouter

from app.config import load_config

router = APIRouter()
log    = logging.getLogger("cineplete")

_cache: dict = {"data": None, "ts": 0.0}
_CACHE_TTL   = 900   # 15 minutes


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_radarr_movies(url: str, api_key: str) -> list[dict]:
    """GET /api/v3/movie from any Radarr instance.  Returns [] on any error."""
    try:
        r = requests.get(
            f"{url}/api/v3/movie",
            headers={"X-Api-Key": api_key},
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()
        log.warning(f"Quality: Radarr returned HTTP {r.status_code}")
    except requests.exceptions.RequestException as e:
        log.warning(f"Quality: Radarr request failed — {e}")
    return []


def _resolution(movie: dict) -> int:
    """Return the file resolution (e.g. 1080) or 0 when no file exists."""
    if not movie.get("hasFile"):
        return 0
    try:
        return int(movie["movieFile"]["quality"]["quality"]["resolution"])
    except (KeyError, TypeError, ValueError):
        return 0


def _quality_name(movie: dict) -> str:
    """Return the quality label string for display (e.g. 'Bluray-1080p')."""
    try:
        return movie["movieFile"]["quality"]["quality"]["name"]
    except (KeyError, TypeError):
        return "Unknown"


def _poster_url(movie: dict) -> str | None:
    """Extract the poster remote URL from a Radarr movie dict."""
    for img in movie.get("images") or []:
        if img.get("coverType") == "poster":
            return img.get("remoteUrl")
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/quality/upgrades")
def get_quality_upgrades():
    """Return movies in Radarr at 720p or lower, not yet added to Radarr 4K."""
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _CACHE_TTL:
        return _cache["data"]

    cfg      = load_config()
    radarr   = cfg.get("RADARR", {})
    radarr4k = cfg.get("RADARR_4K", {})

    if not radarr.get("RADARR_ENABLED"):
        result = {"ok": False, "error": "Radarr not enabled", "movies": [], "count": 0}
        _cache.update({"data": result, "ts": now})
        return result

    url = str(radarr.get("RADARR_URL", "")).rstrip("/")
    key = str(radarr.get("RADARR_API_KEY", "")).strip()
    if not url or urlparse(url).scheme not in ("http", "https"):
        result = {"ok": False, "error": "Radarr URL not configured", "movies": [], "count": 0}
        _cache.update({"data": result, "ts": now})
        return result

    primary_movies = _fetch_radarr_movies(url, key)
    if not primary_movies:
        result = {"ok": False, "error": "Could not reach Radarr", "movies": [], "count": 0}
        _cache.update({"data": result, "ts": now})
        return result

    # Collect TMDB IDs already managed by Radarr 4K
    already_4k: set[int] = set()
    if radarr4k.get("RADARR_4K_ENABLED"):
        url4k = str(radarr4k.get("RADARR_4K_URL", "")).rstrip("/")
        key4k = str(radarr4k.get("RADARR_4K_API_KEY", "")).strip()
        if url4k and urlparse(url4k).scheme in ("http", "https"):
            for m in _fetch_radarr_movies(url4k, key4k):
                tid = m.get("tmdbId")
                if tid:
                    already_4k.add(int(tid))

    candidates: list[dict] = []
    for m in primary_movies:
        tmdb_id    = int(m.get("tmdbId") or 0)
        resolution = _resolution(m)
        if not tmdb_id or resolution == 0 or resolution > 720:
            continue
        if tmdb_id in already_4k:
            continue

        # Radarr stores ratings under movie.ratings.tmdb.value (v3 API)
        rating = 0.0
        try:
            rating = float(m.get("ratings", {}).get("tmdb", {}).get("value", 0))
        except (TypeError, ValueError):
            pass

        candidates.append({
            "tmdb":            tmdb_id,
            "title":           m.get("title", ""),
            "year":            str(m.get("year") or ""),
            "poster":          _poster_url(m),
            "rating":          rating,
            "current_quality": _quality_name(m),
            "resolution":      resolution,
            "wishlist":        False,
        })

    candidates.sort(key=lambda x: x["title"].lower())

    result = {"ok": True, "movies": candidates, "count": len(candidates)}
    _cache.update({"data": result, "ts": now})
    log.info(
        f"Quality upgrades: {len(candidates)} candidates "
        f"({len(already_4k)} already in Radarr 4K, skipped)"
    )
    return result


@router.post("/api/quality/refresh")
def refresh_quality_cache():
    """Bust the upgrade cache so the next GET fetches fresh data from Radarr."""
    _cache["ts"] = 0.0
    return {"ok": True}
