import os
import json
import threading
from datetime import datetime, date
from collections import Counter

from app.config import load_config
from app.tmdb import TMDB
from app.overrides import load_json, save_json, remove_value
from app.logger import get_logger
from app import telegram

DATA_DIR = "/data"
RESULTS_FILE   = f"{DATA_DIR}/results.json"
OVERRIDES_FILE = f"{DATA_DIR}/overrides.json"
SNAPSHOT_FILE  = f"{DATA_DIR}/scan_snapshot.json"

log = get_logger(__name__)

# --------------------------------------------------
# Scan state — shared with web.py for progress API
# --------------------------------------------------

_scan_lock = threading.Lock()

scan_state = {
    "running": False,
    "step": "",
    "step_index": 0,
    "step_total": 8,
    "detail": "",
    "error": None,
    "last_completed": None,
    "last_duration":  None,   # seconds
}

STEPS = [
    "Loading configuration",
    "Scanning Plex library",
    "Validating TMDB metadata",
    "Analyzing collections",
    "Analyzing directors",
    "Building suggestions",
    "Analyzing actors",
    "Building results",
]


def _set_step(index: int, detail: str = ""):
    scan_state["step"]       = STEPS[index]
    scan_state["step_index"] = index + 1
    scan_state["detail"]     = detail
    log.info(f"[{index + 1}/{len(STEPS)}] {STEPS[index]}{' — ' + detail if detail else ''}")


# --------------------------------------------------

def load_snapshot() -> set:
    """Load the set of TMDB IDs from the last completed scan."""
    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("plex_ids", []))
    except Exception:
        return set()


def save_snapshot(plex_ids: dict):
    """Persist current library TMDB IDs for progressive scan comparison."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "plex_ids": list(plex_ids.keys()),
                "saved_at": datetime.utcnow().isoformat() + "Z",
            }, f)
    except Exception:
        pass


def read_results() -> dict | None:
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_results(results: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = RESULTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RESULTS_FILE)


def build():
    """
    Run a full scan synchronously.
    Should be called inside a background thread via build_async().
    Returns the results dict on success, raises on error.
    """

    # ---- CONFIG -----------------------------------------------
    _set_step(0)
    cfg = load_config()

    classics_cfg    = cfg.get("CLASSICS", {})
    actor_hits_cfg  = cfg.get("ACTOR_HITS", {})
    suggestions_cfg = cfg.get("SUGGESTIONS", {})
    tmdb_cfg        = cfg.get("TMDB", {})

    classics_pages              = int(classics_cfg.get("CLASSICS_PAGES", 4))
    classics_min_votes          = int(classics_cfg.get("CLASSICS_MIN_VOTES", 5000))
    classics_min_rating         = float(classics_cfg.get("CLASSICS_MIN_RATING", 8.0))
    classics_max_results        = int(classics_cfg.get("CLASSICS_MAX_RESULTS", 120))
    actor_min_votes             = int(actor_hits_cfg.get("ACTOR_MIN_VOTES", 500))
    actor_max_results_per_actor = int(actor_hits_cfg.get("ACTOR_MAX_RESULTS_PER_ACTOR", 10))
    suggestions_max_results     = int(suggestions_cfg.get("SUGGESTIONS_MAX_RESULTS", 100))
    suggestions_min_score       = int(suggestions_cfg.get("SUGGESTIONS_MIN_SCORE", 2))
    tmdb_api_key                = tmdb_cfg.get("TMDB_API_KEY")

    if not tmdb_api_key:
        log.error("TMDB_API_KEY is missing from config — scan cannot continue")
        raise RuntimeError("TMDB_API_KEY missing in config")

    # Quick sanity check — validate the API key before running the full scan
    log.debug("Validating TMDB API key...")
    test = TMDB(tmdb_api_key)
    if not test.movie(603):   # The Matrix — reliable test target
        log.error("TMDB API key validation failed — all movie lookups will return empty. "
                  "Check your TMDB_API_KEY in config.")
        raise RuntimeError("TMDB API key invalid or unreachable")

    os.makedirs(DATA_DIR, exist_ok=True)

    overrides         = load_json(OVERRIDES_FILE)
    ignore_movies     = set(overrides.get("ignore_movies", []))
    ignore_franchises = set(overrides.get("ignore_franchises", []))
    ignore_directors  = set(overrides.get("ignore_directors", []))
    ignore_actors     = set(overrides.get("ignore_actors", []))
    wishlist_movies   = set(overrides.get("wishlist_movies", []))
    rec_fetched_ids   = set(overrides.get("rec_fetched_ids", []))

    # ---- MEDIA SERVER SCAN ------------------------------------
    media_server = cfg.get("SERVER", {}).get("MEDIA_SERVER", "plex").lower()
    if media_server == "jellyfin":
        from app.jellyfin_api import scan_movies
        STEPS[1] = "Scanning Jellyfin library"
        log.info("Using Jellyfin scanner")
    else:
        from app.plex_xml import scan_movies
        STEPS[1] = "Scanning Plex library"
        log.info("Using Plex scanner")
    _set_step(1)
    plex_ids, directors_map, actors_map, plex_stats, no_tmdb_guid = scan_movies()
    duplicates = plex_stats.pop("duplicates", [])
    log.info(f"Movies detected: {len(plex_ids)}, duplicates: {len(duplicates)}")

    # ---- PROGRESSIVE SCAN CHECK --------------------------------
    snapshot_ids = load_snapshot()
    current_ids  = set(plex_ids.keys())
    if snapshot_ids and current_ids == snapshot_ids:
        log.info("Progressive scan: library unchanged — reusing cached analysis")
        prev = read_results()
        if prev:
            # Refresh only the dynamic parts (wishlist, stats, no_tmdb_guid)
            overrides     = load_json(OVERRIDES_FILE)
            wishlist_movies = set(overrides.get("wishlist_movies", []))

            # Auto-clean wishlist movies now in library
            cleaned = False
            for mid in list(wishlist_movies):
                if mid in plex_ids:
                    log.info(f"Wishlist auto-cleanup: tmdb {mid} is now in library")
                    remove_value(overrides["wishlist_movies"], mid)
                    wishlist_movies.discard(mid)
                    cleaned = True
            if cleaned:
                save_json(OVERRIDES_FILE, overrides)

            tmdb = TMDB(tmdb_api_key)
            wishlist = []
            for mid in sorted(wishlist_movies):
                md = tmdb.movie(mid)
                if not md:
                    continue
                wishlist.append({
                    "tmdb":       mid,
                    "title":      md.get("title"),
                    "year":       (md.get("release_date") or "")[:4] or None,
                    "poster":     tmdb.poster_url(md.get("poster_path")),
                    "overview":   md.get("overview", ""),
                    "genre_ids":  [g["id"] for g in md.get("genres", [])],
                    "popularity": md.get("popularity", 0),
                    "votes":      md.get("vote_count", 0),
                    "rating":     md.get("vote_average", 0),
                    "wishlist":   True,
                })

            prev["generated_at"] = datetime.utcnow().isoformat() + "Z"
            prev["media_server"] = plex_stats
            prev["no_tmdb_guid"] = no_tmdb_guid
            prev["duplicates"]   = duplicates
            prev["wishlist"]     = wishlist
            prev["scanning"]     = False
            tmdb.flush()
            write_results(prev)
            log.info("Progressive scan completed")
            return prev

    tmdb = TMDB(tmdb_api_key)
    movie_cache: dict = {}

    def get_movie(mid: int) -> dict:
        if mid not in movie_cache:
            movie_cache[mid] = tmdb.movie(mid)
        return movie_cache[mid]

    # ---- TMDB VALIDATION --------------------------------------
    _set_step(2, f"{len(plex_ids)} movies")
    tmdb_not_found = []
    for mid in plex_ids:
        md = get_movie(mid)
        if not md:
            tmdb_not_found.append({"tmdb": mid, "title": plex_ids[mid]})

    # ---- COLLECTIONS ------------------------------------------
    _set_step(3)
    collection_ids: dict = {}
    for mid in plex_ids:
        md = get_movie(mid)
        if not md:
            continue
        c = md.get("belongs_to_collection")
        if c and c.get("id") and c.get("name"):
            collection_ids[int(c["id"])] = c["name"]

    franchises = []
    franchise_completion = []

    for cid, name in collection_ids.items():
        if name in ignore_franchises:
            continue

        cd = tmdb.collection(cid)
        if not cd:
            continue

        parts = cd.get("parts", []) or []
        total = len(parts)
        if total < 2:
            continue

        have = sum(1 for p in parts if int(p.get("id", -1)) in plex_ids)
        missing = []

        for p in parts:
            pid = p.get("id")
            if not pid:
                continue
            pid = int(pid)
            if pid in plex_ids or pid in ignore_movies:
                continue
            release = (p.get("release_date") or "")[:10]
            if not release or release > date.today().isoformat():
                continue
            missing.append({
                "title":      p.get("title"),
                "tmdb":       pid,
                "year":       (p.get("release_date") or "")[:4] or None,
                "poster":     tmdb.poster_url(p.get("poster_path")),
                "overview":   p.get("overview", ""),
                "genre_ids":  p.get("genre_ids", []),
                "popularity": p.get("popularity", 0),
                "votes":      p.get("vote_count", 0),
                "rating":     p.get("vote_average", 0),
                "wishlist":   pid in wishlist_movies,
            })

        franchises.append({
            "name":            name,
            "tmdb_collection": cid,
            "have":            have,
            "total":           total,
            "missing":         sorted(
                missing,
                key=lambda x: (x.get("year") or "9999", x.get("title") or "")
            ),
        })
        franchise_completion.append({"name": name, "have": have, "total": total})

    log.info(f"Collections analyzed: {len(franchises)}")

    # ---- DIRECTORS --------------------------------------------
    _set_step(4, f"{len(directors_map)} directors")
    directors = []
    director_missing_total = 0

    for director in directors_map.keys():
        if director in ignore_directors:
            continue

        sr = tmdb.search_person(director)
        if not sr or not sr.get("results"):
            continue

        pid = sr["results"][0].get("id")
        if not pid:
            continue

        credits = tmdb.person_credits(pid)
        if not credits:
            continue

        missing = []
        for m in credits.get("crew", []):
            if m.get("job") != "Director":
                continue
            mid = m.get("id")
            if not mid:
                continue
            mid = int(mid)
            if mid in plex_ids or mid in ignore_movies:
                continue
            release = (m.get("release_date") or "")[:10]
            if not release or release > date.today().isoformat():
                continue
            missing.append({
                "title":      m.get("title"),
                "tmdb":       mid,
                "year":       (m.get("release_date") or "")[:4] or None,
                "poster":     tmdb.poster_url(m.get("poster_path")),
                "overview":   m.get("overview", ""),
                "genre_ids":  m.get("genre_ids", []),
                "popularity": m.get("popularity", 0),
                "votes":      m.get("vote_count", 0),
                "rating":     m.get("vote_average", 0),
                "wishlist":   mid in wishlist_movies,
            })

        if missing:
            director_missing_total += len(missing)
            directors.append({
                "name":    director,
                "missing": sorted(
                    missing,
                    key=lambda x: (-x.get("popularity", 0), -x.get("votes", 0))
                ),
            })

    log.info(f"Directors analyzed: {len(directors)}")

    # ---- CLASSICS ---------------------------------------------
    classics = []

    for page in range(1, classics_pages + 1):
        payload = tmdb.top_rated(page)
        if not payload:
            continue
        for m in payload.get("results", []):
            mid    = int(m.get("id"))
            votes  = int(m.get("vote_count", 0))
            rating = float(m.get("vote_average", 0))

            if votes  < classics_min_votes:  continue
            if rating < classics_min_rating: continue
            if mid in plex_ids or mid in ignore_movies: continue

            classics.append({
                "title":      m.get("title"),
                "tmdb":       mid,
                "year":       (m.get("release_date") or "")[:4] or None,
                "poster":     tmdb.poster_url(m.get("poster_path")),
                "overview":   m.get("overview", ""),
                "genre_ids":  m.get("genre_ids", []),
                "popularity": m.get("popularity", 0),
                "votes":      votes,
                "rating":     rating,
                "wishlist":   mid in wishlist_movies,
            })
            if len(classics) >= classics_max_results:
                break

        if len(classics) >= classics_max_results:
            break

    log.info(f"Classics found: {len(classics)}")
    classics = sorted(classics, key=lambda x: (-x["rating"], -x["votes"]))

    # ---- SUGGESTIONS (based on your library) ------------------
    _set_step(5, f"{len(plex_ids)} library films")

    # Score map: {tmdb_id: recommendation_count}
    rec_scores: dict = {}

    # Only fetch recs for IDs not yet in rec_fetched_ids
    ids_to_fetch = [mid for mid in plex_ids if mid not in rec_fetched_ids]
    newly_fetched = []

    log.info(f"Fetching recommendations for {len(ids_to_fetch)} new films "
             f"({len(rec_fetched_ids)} already cached)")

    for mid in ids_to_fetch:
        data = tmdb.recommendations(mid)
        for r in data.get("results", []):
            rid = int(r.get("id", 0))
            if rid:
                rec_scores[rid] = rec_scores.get(rid, 0) + 1
        newly_fetched.append(mid)

    # Also score from previously fetched IDs using cached responses
    for mid in rec_fetched_ids:
        data = tmdb.recommendations(mid)   # will hit cache, no HTTP call
        for r in data.get("results", []):
            rid = int(r.get("id", 0))
            if rid:
                rec_scores[rid] = rec_scores.get(rid, 0) + 1

    # Persist newly fetched IDs
    if newly_fetched:
        overrides["rec_fetched_ids"] = list(rec_fetched_ids | set(newly_fetched))
        save_json(OVERRIDES_FILE, overrides)
        log.info(f"rec_fetched_ids updated: {len(overrides['rec_fetched_ids'])} total")

    # Build suggestions list — exclude library, ignored, unreleased, below min score
    suggestions = []
    today = date.today().isoformat()

    for rid, score in sorted(rec_scores.items(), key=lambda x: -x[1]):
        if rid in plex_ids or rid in ignore_movies:
            continue
        if score < suggestions_min_score:
            continue

        md = get_movie(rid)
        if not md:
            continue

        release = (md.get("release_date") or "")[:10]
        if not release or release > today:
            continue

        suggestions.append({
            "title":      md.get("title"),
            "tmdb":       rid,
            "year":       (md.get("release_date") or "")[:4] or None,
            "poster":     tmdb.poster_url(md.get("poster_path")),
            "overview":   md.get("overview", ""),
            "genre_ids":  [g["id"] for g in md.get("genres", [])],
            "popularity": md.get("popularity", 0),
            "votes":      md.get("vote_count", 0),
            "rating":     md.get("vote_average", 0),
            "wishlist":   rid in wishlist_movies,
            "rec_score":  score,
        })

        if len(suggestions) >= suggestions_max_results:
            break

    log.info(f"Suggestions built: {len(suggestions)}")

    # ---- ACTORS -----------------------------------------------
    _set_step(6, f"{len(actors_map)} actors")
    actors = []
    actor_missing_total = 0

    for actor in actors_map.keys():
        if actor in ignore_actors:
            continue

        sr = tmdb.search_person(actor)
        if not sr or not sr.get("results"):
            continue

        pid = sr["results"][0]["id"]

        credits = tmdb.person_credits(pid)
        if not credits:
            continue

        films = [
            m for m in credits.get("cast", [])
            if m.get("vote_count", 0) >= actor_min_votes
        ]
        films = sorted(
            films,
            key=lambda x: (
                x.get("popularity", 0),
                x.get("vote_count", 0),
                x.get("vote_average", 0),
            ),
            reverse=True,
        )

        missing = []
        for m in films:
            mid = int(m.get("id"))
            if mid in plex_ids or mid in ignore_movies:
                continue
            release = (m.get("release_date") or "")[:10]
            if not release or release > date.today().isoformat():
                continue
            missing.append({
                "title":      m.get("title"),
                "tmdb":       mid,
                "year":       (m.get("release_date") or "")[:4] or None,
                "poster":     tmdb.poster_url(m.get("poster_path")),
                "overview":   m.get("overview", ""),
                "genre_ids":  m.get("genre_ids", []),
                "popularity": m.get("popularity", 0),
                "votes":      m.get("vote_count", 0),
                "rating":     m.get("vote_average", 0),
                "wishlist":   mid in wishlist_movies,
            })
            if len(missing) >= actor_max_results_per_actor:
                break

        if missing:
            actor_missing_total += len(missing)
            actors.append({"name": actor, "missing": missing})

    actors = sorted(actors, key=lambda x: x["name"].lower())
    log.info(f"Actors analyzed: {len(actors)}")

    # ---- WISHLIST ---------------------------------------------
    # FIX #2: auto-remove wishlist movies that are now in the library
    cleaned = False
    for mid in list(wishlist_movies):
        if mid in plex_ids:
            log.info(f"Wishlist auto-cleanup: tmdb {mid} is now in library, removing")
            remove_value(overrides["wishlist_movies"], mid)
            wishlist_movies.discard(mid)
            cleaned = True

    if cleaned:
        save_json(OVERRIDES_FILE, overrides)

    wishlist = []
    for mid in sorted(wishlist_movies):
        md = get_movie(mid)
        if not md:
            continue
        wishlist.append({
            "tmdb":       mid,
            "title":      md.get("title"),
            "year":       (md.get("release_date") or "")[:4] or None,
            "poster":     tmdb.poster_url(md.get("poster_path")),
            "overview":   md.get("overview", ""),
            "genre_ids":  [g["id"] for g in md.get("genres", [])],
            "popularity": md.get("popularity", 0),
            "votes":      md.get("vote_count", 0),
            "rating":     md.get("vote_average", 0),
            "wishlist":   True,
        })

    # ---- SCORES -----------------------------------------------
    _set_step(7)
    actor_counts = Counter({k: len(v) for k, v in actors_map.items()})
    top_actors   = [{"name": n, "count": c} for n, c in actor_counts.most_common(40)]

    total_slots     = sum(x["total"] for x in franchise_completion) or 0
    total_have      = sum(x["have"]  for x in franchise_completion) or 0
    franchise_score = (total_have / total_slots * 100) if total_slots else 0
    classics_score  = max(0.0, 100.0 - (len(classics) / max(1, classics_max_results) * 100))
    directors_score = max(0.0, 100.0 - (director_missing_total / max(1, len(directors)) * 5))
    global_score    = round(
        (franchise_score * 0.5) + (directors_score * 0.25) + (classics_score * 0.25), 1
    )

    # ---- RESULTS ----------------------------------------------
    results = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "media_server": plex_stats,
        "scores": {
            "franchise_completion_pct": round(franchise_score, 1),
            "directors_proxy_pct":      round(directors_score, 1),
            "classics_proxy_pct":       round(classics_score, 1),
            "global_cinema_score":      global_score,
        },
        "charts": {
            "franchise_completion": franchise_completion[:30],
            "top_actors":           top_actors,
        },
        # Expose ignored lists so the dashboard can filter charts without a second call
        "_ignored_franchises": list(ignore_franchises),
        "_ignored_directors":  list(ignore_directors),
        "_ignored_actors":     list(ignore_actors),
        "no_tmdb_guid":   no_tmdb_guid,
        "tmdb_not_found": tmdb_not_found,
        "duplicates":     duplicates,
        "franchises":     franchises,
        "directors":      directors,
        "actors":         actors,
        "classics":       classics,
        "suggestions":    suggestions,
        "wishlist":       wishlist,
    }

    tmdb.flush()
    save_snapshot(plex_ids)
    write_results(results)
    log.info("Scan completed")
    return results


def _notify(results: dict, duration_s: int | None = None):
    """Fire Telegram notification safely — never raises."""
    try:
        telegram.send_scan_summary(results, duration_s)
    except Exception as e:
        log.warning(f"Telegram notification error: {e}")


def build_async():
    """
    Launch build() in a background thread.
    Returns immediately. Poll scan_state for progress.
    Only one scan can run at a time — concurrent calls are rejected.
    """
    if not _scan_lock.acquire(blocking=False):
        return False  # already running

    def _run():
        scan_state["running"] = True
        scan_state["error"]   = None
        _start = datetime.utcnow()
        try:
            results = build()
            duration = round((datetime.utcnow() - _start).total_seconds())
            scan_state["last_completed"] = datetime.utcnow().isoformat() + "Z"
            scan_state["last_duration"]  = duration
            _notify(results, duration)
        except Exception as e:
            log.exception("Scan failed")
            scan_state["error"] = str(e)
        finally:
            scan_state["running"]    = False
            scan_state["step"]       = ""
            scan_state["step_index"] = 0
            scan_state["detail"]     = ""
            _scan_lock.release()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return True