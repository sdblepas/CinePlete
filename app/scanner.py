import os
import json
import logging
from datetime import datetime
from collections import Counter

from app.config import load_config
from app.plex_xml import scan_movies
from app.tmdb import TMDB
from app.overrides import load_json

DATA_DIR = "/app/data"
RESULTS_FILE = f"{DATA_DIR}/results.json"
OVERRIDES_FILE = f"{DATA_DIR}/overrides.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCANNER] %(message)s"
)

log = logging.getLogger()


def write_results(results: dict):
    os.makedirs(DATA_DIR, exist_ok=True)

    tmp = RESULTS_FILE + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    os.replace(tmp, RESULTS_FILE)


def build():

    log.info("Loading configuration")

    cfg = load_config()

    # --------------------------------------------------
    # CONFIG
    # --------------------------------------------------

    classics_cfg = cfg.get("CLASSICS", {})
    actor_hits_cfg = cfg.get("ACTOR_HITS", {})
    tmdb_cfg = cfg.get("TMDB", {})

    classics_pages = int(classics_cfg.get("CLASSICS_PAGES", 4))
    classics_min_votes = int(classics_cfg.get("CLASSICS_MIN_VOTES", 5000))
    classics_min_rating = float(classics_cfg.get("CLASSICS_MIN_RATING", 8.0))
    classics_max_results = int(classics_cfg.get("CLASSICS_MAX_RESULTS", 120))

    actor_min_votes = int(actor_hits_cfg.get("ACTOR_MIN_VOTES", 500))
    actor_max_results_per_actor = int(actor_hits_cfg.get("ACTOR_MAX_RESULTS_PER_ACTOR", 10))

    tmdb_api_key = tmdb_cfg.get("TMDB_API_KEY")

    if not tmdb_api_key:
        raise RuntimeError("TMDB_API_KEY missing in config")

    # --------------------------------------------------
    # INIT
    # --------------------------------------------------

    os.makedirs(DATA_DIR, exist_ok=True)

    overrides = load_json(OVERRIDES_FILE)

    ignore_movies = set(overrides.get("ignore_movies", []))
    ignore_franchises = set(overrides.get("ignore_franchises", []))
    ignore_directors = set(overrides.get("ignore_directors", []))
    ignore_actors = set(overrides.get("ignore_actors", []))
    wishlist_movies = set(overrides.get("wishlist_movies", []))

    log.info("Scanning Plex library")

    plex_ids, directors_map, actors_map, plex_stats, no_tmdb_guid = scan_movies()

    log.info(f"Plex movies detected: {len(plex_ids)}")

    tmdb = TMDB(tmdb_api_key)

    # Cache pour éviter double appel TMDB
    movie_cache = {}

    def get_movie(mid):
        if mid not in movie_cache:
            movie_cache[mid] = tmdb.movie(mid)
        return movie_cache[mid]

    # --------------------------------------------------
    # TMDB VALIDATION
    # --------------------------------------------------

    log.info("Validating TMDB metadata")

    tmdb_not_found = []

    for mid in plex_ids:
        md = get_movie(mid)

        if not md:
            tmdb_not_found.append({"tmdb": mid})

    # --------------------------------------------------
    # COLLECTIONS
    # --------------------------------------------------

    log.info("Analyzing collections")

    collection_ids = {}

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

            missing.append({
                "title": p.get("title"),
                "tmdb": pid,
                "year": (p.get("release_date") or "")[:4] or None,
                "poster": tmdb.poster_url(p.get("poster_path")),
                "popularity": p.get("popularity", 0),
                "votes": p.get("vote_count", 0),
                "rating": p.get("vote_average", 0),
                "wishlist": pid in wishlist_movies
            })

        franchises.append({
            "name": name,
            "tmdb_collection": cid,
            "have": have,
            "total": total,
            "missing": sorted(
                missing,
                key=lambda x: (x.get("year") or "9999", x.get("title") or "")
            )
        })

        franchise_completion.append({
            "name": name,
            "have": have,
            "total": total
        })

    log.info(f"Collections analyzed: {len(franchises)}")

    # --------------------------------------------------
    # DIRECTORS
    # --------------------------------------------------

    log.info("Analyzing directors")

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

            missing.append({
                "title": m.get("title"),
                "tmdb": mid,
                "year": (m.get("release_date") or "")[:4] or None,
                "poster": tmdb.poster_url(m.get("poster_path")),
                "popularity": m.get("popularity", 0),
                "votes": m.get("vote_count", 0),
                "rating": m.get("vote_average", 0),
                "wishlist": mid in wishlist_movies
            })

        if missing:

            director_missing_total += len(missing)

            directors.append({
                "name": director,
                "missing": sorted(
                    missing,
                    key=lambda x: (-x.get("popularity", 0), -x.get("votes", 0))
                )
            })

    log.info(f"Directors analyzed: {len(directors)}")

    # --------------------------------------------------
    # CLASSICS
    # --------------------------------------------------

    log.info("Searching classic movies")

    classics = []
    suggestions = []

    for page in range(1, classics_pages + 1):

        payload = tmdb.top_rated(page)

        if not payload:
            continue

        for m in payload.get("results", []):

            mid = int(m.get("id"))

            votes = int(m.get("vote_count", 0))
            rating = float(m.get("vote_average", 0))

            if votes < classics_min_votes:
                continue

            if rating < classics_min_rating:
                continue

            if mid in plex_ids or mid in ignore_movies:
                continue

            item = {
                "title": m.get("title"),
                "tmdb": mid,
                "year": (m.get("release_date") or "")[:4] or None,
                "poster": tmdb.poster_url(m.get("poster_path")),
                "popularity": m.get("popularity", 0),
                "votes": votes,
                "rating": rating,
                "wishlist": mid in wishlist_movies
            }

            classics.append(item)
            suggestions.append(item)

            if len(classics) >= classics_max_results:
                break

        if len(classics) >= classics_max_results:
            break

    log.info(f"Classic suggestions found: {len(classics)}")

    classics = sorted(
        classics,
        key=lambda x: (-x["rating"], -x["votes"])
    )

    # --------------------------------------------------
    # ACTORS
    # --------------------------------------------------

    log.info("Analyzing actors")

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

        films = [
            m for m in credits.get("cast", [])
            if m.get("vote_count", 0) >= actor_min_votes
        ]

        films = sorted(
            films,
            key=lambda x: (
                x.get("popularity", 0),
                x.get("vote_count", 0),
                x.get("vote_average", 0)
            ),
            reverse=True
        )

        missing = []

        for m in films:

            mid = int(m.get("id"))

            if mid in plex_ids or mid in ignore_movies:
                continue

            missing.append({
                "title": m.get("title"),
                "tmdb": mid,
                "year": (m.get("release_date") or "")[:4] or None,
                "poster": tmdb.poster_url(m.get("poster_path")),
                "popularity": m.get("popularity", 0),
                "votes": m.get("vote_count", 0),
                "rating": m.get("vote_average", 0),
                "wishlist": mid in wishlist_movies
            })

            if len(missing) >= actor_max_results_per_actor:
                break

        if missing:
            actor_missing_total += len(missing)
            actors.append({"name": actor, "missing": missing})

    actors = sorted(actors, key=lambda x: x["name"].lower())

    log.info(f"Actors analyzed: {len(actors)}")

    # --------------------------------------------------
    # WISHLIST
    # --------------------------------------------------

    log.info("Building wishlist")

    wishlist = []

    for mid in sorted(wishlist_movies):

        md = get_movie(mid)

        if not md:
            continue

        wishlist.append({
            "tmdb": mid,
            "title": md.get("title"),
            "year": (md.get("release_date") or "")[:4] or None,
            "poster": tmdb.poster_url(md.get("poster_path")),
            "popularity": md.get("popularity", 0),
            "votes": md.get("vote_count", 0),
            "rating": md.get("vote_average", 0),
            "wishlist": True
        })

    # --------------------------------------------------
    # SCORES
    # --------------------------------------------------

    actor_counts = Counter({k: len(v) for k, v in actors_map.items()})
    top_actors = [{"name": n, "count": c} for n, c in actor_counts.most_common(40)]

    total_slots = sum(x["total"] for x in franchise_completion) or 0
    total_have = sum(x["have"] for x in franchise_completion) or 0

    franchise_score = (total_have / total_slots * 100) if total_slots else 0

    classics_score = max(0.0, 100.0 - (len(classics) / max(1, classics_max_results) * 100))
    directors_score = max(0.0, 100.0 - (director_missing_total / max(1, len(directors)) * 5))

    global_score = round(
        (franchise_score * 0.5) +
        (directors_score * 0.25) +
        (classics_score * 0.25),
        1
    )

    # --------------------------------------------------
    # RESULTS
    # --------------------------------------------------

    log.info("Writing results")

    results = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "plex": plex_stats,
        "scores": {
            "franchise_completion_pct": round(franchise_score, 1),
            "directors_proxy_pct": round(directors_score, 1),
            "classics_proxy_pct": round(classics_score, 1),
            "global_cinema_score": global_score
        },
        "charts": {
            "franchise_completion": franchise_completion[:30],
            "top_actors": top_actors
        },
        "no_tmdb_guid": no_tmdb_guid,
        "tmdb_not_found": tmdb_not_found,
        "franchises": franchises,
        "directors": directors,
        "actors": actors,
        "classics": classics,
        "suggestions": suggestions[:200],
        "wishlist": wishlist
    }

    tmdb.flush()

    write_results(results)

    log.info("Scan completed")

    return results