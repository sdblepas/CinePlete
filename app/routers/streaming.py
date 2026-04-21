"""
GET /api/streaming/{tmdb_id} — Streaming availability via TMDB watch/providers (JustWatch data).
Results are cached per movie+country for 30 minutes.
"""
import time
import logging

from fastapi import APIRouter

from app.config import load_config
from app.tmdb import TMDB

router = APIRouter()
log    = logging.getLogger("cineplete")

_cache: dict = {}
_CACHE_TTL   = 1800          # 30 minutes
_LOGO_BASE   = "https://image.tmdb.org/t/p/original"


def _parse_providers(raw: list, type_: str) -> list[dict]:
    """Convert a TMDB provider list into our simplified format, sorted by display priority."""
    out = []
    for p in sorted(raw or [], key=lambda x: x.get("display_priority", 999)):
        logo = p.get("logo_path")
        out.append({
            "name": p.get("provider_name", ""),
            "logo": (_LOGO_BASE + logo) if logo else None,
            "type": type_,
            "id":   p.get("provider_id"),
        })
    return out


@router.get("/api/streaming/{tmdb_id}")
def get_streaming(tmdb_id: int):
    """Return streaming providers for a movie (flatrate / free / rent / buy)."""
    cfg     = load_config()
    api_key = cfg.get("TMDB", {}).get("TMDB_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "TMDB not configured", "providers": [], "link": ""}

    country   = cfg.get("STREAMING", {}).get("STREAMING_COUNTRY", "US")
    cache_key = f"{tmdb_id}:{country}"

    cached = _cache.get(cache_key)
    if cached and time.time() - cached["ts"] < _CACHE_TTL:
        return cached["data"]

    tmdb         = TMDB(api_key)
    raw          = tmdb.watch_providers(tmdb_id) or {}
    country_data = (raw.get("results") or {}).get(country, {})

    providers: list[dict] = []
    providers += _parse_providers(country_data.get("flatrate"), "flatrate")
    providers += _parse_providers(country_data.get("free"),     "free")
    # Limit transactional providers — less important for the user
    providers += _parse_providers((country_data.get("rent") or [])[:3], "rent")
    providers += _parse_providers((country_data.get("buy")  or [])[:3], "buy")

    result = {
        "ok":        True,
        "providers": providers,
        "link":      country_data.get("link", ""),
        "country":   country,
    }

    _cache[cache_key] = {"ts": time.time(), "data": result}
    return result
