"""
GET /api/theaters — Now playing + upcoming films not already owned.
Results are cached for 4 hours.
"""
import time
import logging

from fastapi import APIRouter

from app.config import load_config
from app.tmdb import TMDB
from app.scanner import load_snapshot

router = APIRouter()
log    = logging.getLogger("cineplete")

_cache: dict = {"data": None, "ts": 0.0}
_CACHE_TTL = 4 * 3600  # 4 hours


@router.get("/api/theaters")
def get_theaters():
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _CACHE_TTL:
        return _cache["data"]

    cfg     = load_config()
    api_key = cfg.get("TMDB", {}).get("TMDB_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "TMDB API key not configured", "movies": []}

    tmdb     = TMDB(api_key)
    owned    = load_snapshot()          # set of int TMDB IDs

    movies: dict[int, dict] = {}

    for endpoint in ("now_playing", "upcoming"):
        for page in (1, 2):
            data = tmdb.get(
                f"https://api.themoviedb.org/3/movie/{endpoint}"
                f"?api_key={api_key}&page={page}&language=en-US&region=US"
            ) or {}
            for m in data.get("results", []):
                mid = int(m.get("id") or 0)
                if not mid or mid in owned or mid in movies:
                    continue
                release = (m.get("release_date") or "")[:10]
                movies[mid] = {
                    "title":        m.get("title"),
                    "tmdb":         mid,
                    "year":         release[:4] or None,
                    "poster":       tmdb.poster_url(m.get("poster_path")),
                    "overview":     m.get("overview", ""),
                    "genre_ids":    m.get("genre_ids", []),
                    "popularity":   m.get("popularity", 0),
                    "votes":        m.get("vote_count", 0),
                    "rating":       m.get("vote_average", 0),
                    "release_date": release,
                    "wishlist":     False,
                }

    sorted_movies = sorted(
        movies.values(),
        key=lambda x: x.get("release_date") or "",
        reverse=True,
    )

    result = {"ok": True, "movies": sorted_movies, "count": len(sorted_movies)}
    _cache["data"] = result
    _cache["ts"]   = now
    log.info(f"Theaters: {len(sorted_movies)} films (owned={len(owned)} filtered out)")
    return result
