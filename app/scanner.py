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

DATA_DIR = os.getenv("DATA_DIR", "/data")
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


def _set_step(index: int, detail: str = "", label: str = ""):
    step_label = label or STEPS[index]
    scan_state["step"]       = step_label
    scan_state["step_index"] = index + 1
    scan_state["detail"]     = detail
    log.info(f"[{index + 1}/{len(STEPS)}] {step_label}{' — ' + detail if detail else ''}")


# --------------------------------------------------

def load_snapshot() -> set:
    """Load the set of TMDB IDs from the last completed scan."""
    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("plex_ids", []))
    except (OSError, json.JSONDecodeError) as e:
        log.debug(f"No scan snapshot found: {e}")
        return set()


def save_snapshot(plex_ids: dict):
    """Persist current library TMDB IDs for progressive scan comparison."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = SNAPSHOT_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "plex_ids": list(plex_ids.keys()),
                "saved_at": datetime.utcnow().isoformat() + "Z",
            }, f)
        os.replace(tmp, SNAPSHOT_FILE)
    except OSError as e:
        log.warning(f"Could not save scan snapshot: {e}")


def read_results() -> dict | None:
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log.debug(f"No results file found: {e}")
        return None


def write_results(results: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = RESULTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RESULTS_FILE)


_SECTION_KEYS = ["library", "metadata", "franchises", "directors",
                 "classics", "suggestions", "actors", "scores"]


def _partial_write(acc: dict, sections: dict):
    """Write accumulated scan results mid-scan with section status map.

    Sets scanning=True so the frontend knows results are partial.
    Uses the same atomic tmp-rename pattern as write_results().
    """
    payload = {**acc, "scanning": True, "sections": dict(sections)}
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = RESULTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RESULTS_FILE)


def _analyze_collections(plex_ids, tmdb, ignore_franchises, ignore_movies, wishlist_movies):
    """Extract collection/franchise data from the library.

    Returns (franchises, franchise_completion).
    """
    collection_ids: dict = {}
    for mid in plex_ids:
        md = tmdb.movie(mid)
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
    return franchises, franchise_completion


def _analyze_directors(directors_map, plex_ids, tmdb, ignore_directors, ignore_movies, wishlist_movies):
    """Analyze director filmographies for missing films.

    Returns (directors, director_missing_total).
    """
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
    return directors, director_missing_total


def _build_classics(tmdb, plex_ids, ignore_movies, wishlist_movies, pages, min_votes, min_rating, max_results):
    """Fetch top-rated movies not already in the library.

    Returns list of classic movie dicts sorted by (-rating, -votes).
    """
    classics = []

    for page in range(1, pages + 1):
        payload = tmdb.top_rated(page)
        if not payload:
            continue
        for m in payload.get("results", []):
            mid    = int(m.get("id"))
            votes  = int(m.get("vote_count", 0))
            rating = float(m.get("vote_average", 0))

            if votes  < min_votes:  continue
            if rating < min_rating: continue
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
            if len(classics) >= max_results:
                break

        if len(classics) >= max_results:
            break

    log.info(f"Classics found: {len(classics)}")
    return sorted(classics, key=lambda x: (-x["rating"], -x["votes"]))


def _build_suggestions(plex_ids, tmdb, overrides, ignore_movies, wishlist_movies, max_results, min_score):
    """Build recommendation-based suggestions from library films.

    Returns list of suggestion dicts.

    Performance note: rec_scores is persisted in overrides.json so it never
    needs to be rebuilt from scratch. Only newly added movies contribute new
    scores. This avoids re-reading all cached recommendation responses on
    every scan (critical for libraries with thousands of movies).
    """
    rec_fetched_ids = set(overrides.get("rec_fetched_ids", []))

    # Load persisted score map — only newly added movies will add to it
    rec_scores:  dict = dict(overrides.get("rec_scores",  {}))
    rec_sources: dict = dict(overrides.get("rec_sources", {}))  # tmdb_id → [source_ids…]

    ids_to_fetch = [mid for mid in plex_ids if mid not in rec_fetched_ids]

    log.info(f"Fetching recommendations for {len(ids_to_fetch)} new films "
             f"({len(rec_fetched_ids)} already scored)")

    for mid in ids_to_fetch:
        data = tmdb.recommendations(mid)
        for r in data.get("results", []):
            rid = int(r.get("id", 0))
            if rid:
                key = str(rid)
                rec_scores[key] = rec_scores.get(key, 0) + 1
                # Track which library films triggered this recommendation (cap at 5)
                srcs = rec_sources.get(key, [])
                if mid not in srcs and len(srcs) < 5:
                    rec_sources[key] = srcs + [mid]

    # Persist updated scores and fetched IDs — no full rebuild needed next scan
    if ids_to_fetch:
        overrides["rec_scores"]      = rec_scores
        overrides["rec_sources"]     = rec_sources
        overrides["rec_fetched_ids"] = list(rec_fetched_ids | set(ids_to_fetch))
        save_json(OVERRIDES_FILE, overrides)
        log.info(f"rec_scores updated: {len(rec_scores)} candidates, "
                 f"{len(overrides['rec_fetched_ids'])} films scored")

    # Sort by score descending and cap candidates before fetching movie details.
    # max_results * 20 gives ample headroom even if many top candidates are
    # already owned, ignored, or unreleased — avoids iterating 50k+ entries.
    candidate_cap = max(max_results * 20, 500)
    candidates = sorted(rec_scores.items(), key=lambda x: -x[1])[:candidate_cap]

    suggestions = []
    today = date.today().isoformat()

    for rid_str, score in candidates:
        rid = int(rid_str)
        if rid in plex_ids or rid in ignore_movies:
            continue
        if score < min_score:
            continue

        md = tmdb.movie(rid)
        if not md:
            continue

        release = (md.get("release_date") or "")[:10]
        if not release or release > today:
            continue

        # Resolve up to 3 source titles from library
        src_ids = rec_sources.get(rid_str, [])
        sources = [plex_ids[s] for s in src_ids[:3] if s in plex_ids]

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
            "sources":    sources,          # library films that triggered this
        })

        if len(suggestions) >= max_results:
            break

    log.info(f"Suggestions built: {len(suggestions)}")
    return suggestions


def _analyze_actors(actors_map, plex_ids, tmdb, ignore_actors, ignore_movies, wishlist_movies, min_votes, max_per_actor):
    """Analyze actor filmographies for high-vote missing films.

    Returns (actors, actor_missing_total).
    """
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
            if m.get("vote_count", 0) >= min_votes
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

        missing   = []
        have_list = []
        for m in films:
            mid = int(m.get("id"))
            if mid in ignore_movies:
                continue
            release = (m.get("release_date") or "")[:10]
            if not release or release > date.today().isoformat():
                continue
            entry = {
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
            }
            if mid in plex_ids:
                if len(have_list) < 10:
                    have_list.append(entry)
            else:
                missing.append(entry)
                if len(missing) >= max_per_actor:
                    break

        if missing:
            actor_missing_total += len(missing)
            actors.append({"name": actor, "missing": missing, "have_list": have_list})

    actors = sorted(actors, key=lambda x: x["name"].lower())
    log.info(f"Actors analyzed: {len(actors)}")
    return actors, actor_missing_total


def _build_wishlist(wishlist_movies, plex_ids, overrides, tmdb):
    """Build wishlist, auto-removing movies now in library.

    Returns list of wishlist movie dicts.
    """
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

    return wishlist


def _calculate_scores(franchise_completion, directors, director_missing_total, classics, classics_max_results):
    """Calculate cinema completion scores.

    Returns dict with keys: franchise_completion_pct, directors_proxy_pct,
    classics_proxy_pct, global_cinema_score.
    """
    total_slots     = sum(x["total"] for x in franchise_completion) or 0
    total_have      = sum(x["have"]  for x in franchise_completion) or 0
    franchise_score = (total_have / total_slots * 100) if total_slots else 0
    classics_score  = max(0.0, 100.0 - (len(classics) / max(1, classics_max_results) * 100))
    directors_score = max(0.0, 100.0 - (director_missing_total / max(1, len(directors)) * 5))
    global_score    = round(
        (franchise_score * 0.5) + (directors_score * 0.25) + (classics_score * 0.25), 1
    )
    return {
        "franchise_completion_pct": round(franchise_score, 1),
        "directors_proxy_pct":      round(directors_score, 1),
        "classics_proxy_pct":       round(classics_score, 1),
        "global_cinema_score":      global_score,
    }


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
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from collections import defaultdict as _defaultdict

    libraries    = cfg.get("LIBRARIES", [])
    enabled_libs = [l for l in libraries if l.get("enabled", True)]
    if not enabled_libs:
        raise RuntimeError("No libraries enabled — enable at least one library in Config")

    lib_labels = ", ".join(
        f"{l.get('type','plex').title()} ({l.get('library_name','?')})"
        for l in enabled_libs
    )
    _set_step(1, lib_labels,
              label=f"Scanning {len(enabled_libs)} librar{'y' if len(enabled_libs)==1 else 'ies'}")

    # Validate each library's required fields before starting any threads
    for lib in enabled_libs:
        lib_type  = lib.get("type", "plex").lower()
        lib_label = lib.get("label") or lib.get("library_name") or lib_type.capitalize()
        missing   = []
        if not lib.get("url", "").strip():
            missing.append("URL")
        if lib_type in ("jellyfin", "emby"):
            if not lib.get("api_key", "").strip():
                missing.append("API key")
        else:
            if not lib.get("token", "").strip():
                missing.append("token")
        if not lib.get("library_name", "").strip():
            missing.append("library name")
        if missing:
            raise RuntimeError(
                f"{lib_label} library is missing: {', '.join(missing)} — "
                "please complete the library settings in Config."
            )

    def _scan_one(lib):
        lib_type = lib.get("type", "plex").lower()
        label    = lib.get("label") or lib.get("library_name") or lib_type
        log.info(f"Scanning {lib_type} library: {label}")
        if lib_type == "jellyfin":
            from app.jellyfin_api import scan_movies
        elif lib_type == "emby":
            from app.emby_api import scan_movies
        else:
            from app.plex_xml import scan_movies
        return scan_movies(lib)

    all_results = []
    if len(enabled_libs) == 1:
        all_results.append(_scan_one(enabled_libs[0]))
    else:
        with ThreadPoolExecutor(max_workers=len(enabled_libs)) as ex:
            futures = {ex.submit(_scan_one, lib): lib for lib in enabled_libs}
            for fut in as_completed(futures):
                all_results.append(fut.result())

    # Merge — deduplicate movies by TMDB ID across libraries
    plex_ids     = {}
    directors_map = _defaultdict(set)
    actors_map    = _defaultdict(set)
    no_tmdb_guid  = []
    duplicates    = []
    plex_stats    = {}

    for ids, dirs, acts, stats, no_guid in all_results:
        plex_ids.update(ids)
        for name, tmdb_ids in dirs.items():
            directors_map[name].update(tmdb_ids)
        for name, tmdb_ids in acts.items():
            actors_map[name].update(tmdb_ids)
        no_tmdb_guid.extend(no_guid)
        duplicates.extend(stats.pop("duplicates", []))
        for k, v in stats.items():
            plex_stats[k] = plex_stats.get(k, 0) + v if isinstance(v, int) else v

    # Re-apply the "appeared in 2+ films" filter after merging
    directors_map = {k: v for k, v in directors_map.items() if len(v) > 1}
    actors_map    = {k: v for k, v in actors_map.items()    if len(v) > 1}

    log.info(f"Merged: {len(plex_ids)} movies from {len(enabled_libs)} librar{'y' if len(enabled_libs)==1 else 'ies'}, {len(duplicates)} duplicates")

    # ---- PROGRESSIVE SCAN CHECK --------------------------------
    snapshot_ids = load_snapshot()
    current_ids  = set(plex_ids.keys())
    # Check if cached actors have the have_list field (added in v3.4); if not, force full scan
    def _cache_has_have_list(prev):
        actors = prev.get("actors", [])
        return not actors or "have_list" in actors[0]

    if snapshot_ids and current_ids == snapshot_ids:
        log.info("Progressive scan: library unchanged — reusing cached analysis")
        prev = read_results()
        if prev and _cache_has_have_list(prev):
            # Refresh only the dynamic parts (wishlist, stats, no_tmdb_guid)
            overrides       = load_json(OVERRIDES_FILE)
            wishlist_movies = set(overrides.get("wishlist_movies", []))

            tmdb    = TMDB(tmdb_api_key)
            wishlist = _build_wishlist(wishlist_movies, plex_ids, overrides, tmdb)

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

    # Seed acc with previous results so pending sections show stale data
    # rather than empty lists while they wait to be recomputed.
    _prev = read_results() or {}
    acc = {
        "generated_at":      datetime.utcnow().isoformat() + "Z",
        "media_server":      plex_stats,
        "owned_tmdb_ids":    sorted(plex_ids.keys()),
        "no_tmdb_guid":      no_tmdb_guid,
        "duplicates":        duplicates,
        "_ignored_franchises": list(ignore_franchises),
        "_ignored_directors":  list(ignore_directors),
        "_ignored_actors":     list(ignore_actors),
        # carry previous results — each section overwrites when done
        "tmdb_not_found": _prev.get("tmdb_not_found", []),
        "franchises":          _prev.get("franchises", []),
        "franchise_completion": _prev.get("franchise_completion", []),
        "directors":           _prev.get("directors", []),
        "classics":            _prev.get("classics", []),
        "suggestions":         _prev.get("suggestions", []),
        "actors":              _prev.get("actors", []),
        "scores":              _prev.get("scores", {}),
        "charts":              _prev.get("charts", {}),
        "wishlist":            _prev.get("wishlist", []),
    }
    sections = {k: "pending" for k in _SECTION_KEYS}
    sections["library"] = "done"
    _partial_write(acc, sections)

    # ---- TMDB VALIDATION --------------------------------------
    sections["metadata"] = "computing"
    _set_step(2, f"{len(plex_ids)} movies")
    _partial_write(acc, sections)
    tmdb_not_found = []
    for mid in plex_ids:
        md = tmdb.movie(mid)
        if not md:
            tmdb_not_found.append({"tmdb": mid, "title": plex_ids[mid]})
    acc["tmdb_not_found"] = tmdb_not_found
    sections["metadata"] = "done"
    _partial_write(acc, sections)

    # ---- COLLECTIONS ------------------------------------------
    sections["franchises"] = "computing"
    _set_step(3)
    _partial_write(acc, sections)
    franchises, franchise_completion = _analyze_collections(
        plex_ids, tmdb, ignore_franchises, ignore_movies, wishlist_movies
    )
    acc["franchises"]          = franchises
    acc["franchise_completion"] = franchise_completion
    sections["franchises"] = "done"
    _partial_write(acc, sections)

    # ---- DIRECTORS --------------------------------------------
    sections["directors"] = "computing"
    _set_step(4, f"{len(directors_map)} directors")
    _partial_write(acc, sections)
    directors, director_missing_total = _analyze_directors(
        directors_map, plex_ids, tmdb, ignore_directors, ignore_movies, wishlist_movies
    )
    acc["directors"] = directors
    sections["directors"] = "done"
    _partial_write(acc, sections)

    # ---- CLASSICS ---------------------------------------------
    sections["classics"] = "computing"
    _partial_write(acc, sections)
    classics = _build_classics(
        tmdb, plex_ids, ignore_movies, wishlist_movies,
        classics_pages, classics_min_votes, classics_min_rating, classics_max_results
    )
    acc["classics"] = classics
    sections["classics"] = "done"
    _partial_write(acc, sections)

    # ---- SUGGESTIONS (based on your library) ------------------
    sections["suggestions"] = "computing"
    _set_step(5, f"{len(plex_ids)} library films")
    _partial_write(acc, sections)
    suggestions = _build_suggestions(
        plex_ids, tmdb, overrides, ignore_movies, wishlist_movies,
        suggestions_max_results, suggestions_min_score
    )
    acc["suggestions"] = suggestions
    sections["suggestions"] = "done"
    _partial_write(acc, sections)

    # ---- ACTORS -----------------------------------------------
    sections["actors"] = "computing"
    _set_step(6, f"{len(actors_map)} actors")
    _partial_write(acc, sections)
    actors, actor_missing_total = _analyze_actors(
        actors_map, plex_ids, tmdb, ignore_actors, ignore_movies, wishlist_movies,
        actor_min_votes, actor_max_results_per_actor
    )
    acc["actors"] = actors
    sections["actors"] = "done"
    _partial_write(acc, sections)

    # ---- WISHLIST ---------------------------------------------
    wishlist = _build_wishlist(wishlist_movies, plex_ids, overrides, tmdb)
    acc["wishlist"] = wishlist

    # ---- SCORES -----------------------------------------------
    sections["scores"] = "computing"
    _set_step(7)
    _partial_write(acc, sections)
    actor_counts = Counter({k: len(v) for k, v in actors_map.items()})
    top_actors   = [{"name": n, "count": c} for n, c in actor_counts.most_common(40)]
    scores = _calculate_scores(
        franchise_completion, directors, director_missing_total,
        classics, classics_max_results
    )
    acc["scores"] = scores
    acc["charts"] = {
        "franchise_completion": franchise_completion[:30],
        "top_actors":           top_actors,
    }
    sections["scores"] = "done"

    # ---- FINAL WRITE ------------------------------------------
    results = {**acc, "scanning": False, "sections": sections}

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