"""
Scan + results + movie detail + export + search + logs routes.
  POST /api/scan
  GET  /api/scan/status
  GET  /api/results
  GET  /api/movie/{tmdb_id}
  GET  /api/export
  GET  /api/search
  GET  /api/logs
"""
from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from app.config import load_config, is_configured
from app.scanner import build_async, scan_state, _scan_lock
from app.routers._shared import log, read_results, LOG_FILE

router = APIRouter()


# --------------------------------------------------
# Results
# --------------------------------------------------

@router.get("/api/results")
def api_results():
    if not is_configured():
        return {"configured": False, "message": "Setup required"}

    data = read_results()

    if data is None:
        # No results yet — kick off a background scan and tell the UI to poll
        launched = build_async()
        return {
            "configured": True,
            "scanning":   True,
            "launched":   launched,
            "message":    "First scan started — poll /api/scan/status for progress",
        }

    data["configured"] = True
    data["scanning"]   = scan_state["running"]
    return data


# --------------------------------------------------
# Scan
# --------------------------------------------------

@router.post("/api/scan")
def api_scan():
    if not is_configured():
        return {"ok": False, "error": "Setup required"}

    if scan_state["running"]:
        return {"ok": False, "error": "Scan already in progress"}

    launched = build_async()
    if not launched:
        return {"ok": False, "error": "Could not acquire scan lock"}

    return {"ok": True, "message": "Scan started"}


@router.get("/api/scan/status")
def api_scan_status():
    """
    Returns current scan progress. Poll this while scan_state['running'] is True.
    When running is False and error is None, fetch /api/results for fresh data.
    """
    with _scan_lock:
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
# Movie detail (for modal)
# --------------------------------------------------

@router.get("/api/movie/{tmdb_id}")
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
    videos_url  = (
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

@router.get("/api/export")
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

@router.get("/api/search")
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
# Logs
# --------------------------------------------------

@router.get("/api/logs")
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
