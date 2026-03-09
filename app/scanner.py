import os
import json
from datetime import datetime
from collections import Counter

from app.config import load_config
from app.plex_xml import scan_movies
from app.tmdb import TMDB
from app.overrides import load_json

DATA_DIR = "/app/data"
RESULTS_FILE = f"{DATA_DIR}/results.json"
OVERRIDES_FILE = f"{DATA_DIR}/overrides.json"


def write_results(results: dict):
    os.makedirs(DATA_DIR, exist_ok=True)

    tmp = RESULTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    os.replace(tmp, RESULTS_FILE)


def build():
    cfg = load_config()

    classics_cfg = cfg["CLASSICS"]
    actor_hits_cfg = cfg["ACTOR_HITS"]

    classics_pages = int(classics_cfg["CLASSICS_PAGES"])
    classics_min_votes = int(classics_cfg["CLASSICS_MIN_VOTES"])
    classics_min_rating = float(classics_cfg["CLASSICS_MIN_RATING"])
    classics_max_results = int(classics_cfg["CLASSICS_MAX_RESULTS"])

    actor_min_votes = int(actor_hits_cfg["ACTOR_MIN_VOTES"])
    actor_max_results_per_actor = int(actor_hits_cfg["ACTOR_MAX_RESULTS_PER_ACTOR"])

    os.makedirs(DATA_DIR, exist_ok=True)

    overrides = load_json(OVERRIDES_FILE)
    ignore_movies = set(overrides.get("ignore_movies", []))
    ignore_franchises = set(overrides.get("ignore_franchises", []))
    ignore_directors = set(overrides.get("ignore_directors", []))
    ignore_actors = set(overrides.get("ignore_actors", []))
    wishlist_movies = set(overrides.get("wishlist_movies", []))

    plex_ids, directors_map, actors_map, plex_stats, no_tmdb_guid = scan_movies()
    tmdb = TMDB()

    tmdb_not_found = []
    for mid in plex_ids:
        md = tmdb.movie(mid)
        if not md:
            tmdb_not_found.append({"tmdb": mid})

    collection_ids = {}
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
            ),
        })

        franchise_completion.append({"name": name, "have": have, "total": total})

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

        credits = tmdb.person_credits(int(pid))
        if not credits:
            continue

        missing = []
        for m in credits.get("crew", []) or []:
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
                    key=lambda x: (-x.get("popularity", 0), -x.get("votes", 0), x.get("title") or "")
                ),
            })

    classics = []
    suggestions = []

    for page in range(1, classics_pages + 1):
        payload = tmdb.top_rated(page)
        if not payload:
            continue

        for m in payload.get("results", []) or []:
            mid = m.get("id")
            if not mid:
                continue
            mid = int(mid)

            votes = int(m.get("vote_count", 0) or 0)
            rating = float(m.get("vote_average", 0) or 0)

            if votes < classics_min_votes or rating < classics_min_rating:
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

    classics = sorted(
        classics,
        key=lambda x: (-x.get("rating", 0), -x.get("votes", 0), x.get("title") or "")
    )

    actors = []
    actor_missing_total = 0

    for actor in actors_map.keys():
        if actor in ignore_actors:
            continue

        sr = tmdb.search_person(actor)
        if not sr or not sr.get("results"):
            continue

        pid = sr["results"][0].get("id")
        if not pid:
            continue

        credits = tmdb.person_credits(int(pid))
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

            if len(missing) >= actor_max_results_per_actor:
                break

        if missing:
            actor_missing_total += len(missing)
            actors.append({"name": actor, "missing": missing})

    actors = sorted(actors, key=lambda x: x["name"].lower())

    wishlist = []
    for mid in sorted(wishlist_movies):
        md = tmdb.movie(mid)
        if not md:
            wishlist.append({
                "tmdb": mid,
                "title": f"tmdb:{mid}",
                "year": None,
                "poster": None,
                "popularity": 0,
                "votes": 0,
                "rating": 0,
                "wishlist": True
            })
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

    actor_counts = Counter({k: len(v) for k, v in actors_map.items()})
    top_actors = [{"name": n, "count": c} for n, c in actor_counts.most_common(40)]

    total_slots = sum(x["total"] for x in franchise_completion) or 0
    total_have = sum(x["have"] for x in franchise_completion) or 0
    franchise_score = (total_have / total_slots * 100) if total_slots else 0

    classics_score = max(0.0, 100.0 - (len(classics) / max(1, classics_max_results) * 100.0))
    directors_score = max(0.0, 100.0 - (director_missing_total / max(1, len(directors)) * 5.0))
    global_score = round((franchise_score * 0.5) + (directors_score * 0.25) + (classics_score * 0.25), 1)

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
            "franchise_completion": sorted(
                franchise_completion,
                key=lambda x: (x["have"] / x["total"]),
                reverse=True
            )[:30],
            "top_actors": top_actors
        },
        "no_tmdb_guid": sorted(
            no_tmdb_guid,
            key=lambda x: ((x.get("year") or ""), (x.get("title") or ""))
        ),
        "tmdb_not_found": sorted(
            tmdb_not_found,
            key=lambda x: x["tmdb"]
        ),
        "franchises": sorted(
            franchises,
            key=lambda x: (x["have"] / x["total"], x["name"]),
            reverse=True
        ),
        "directors": sorted(directors, key=lambda x: x["name"].lower()),
        "actors": actors,
        "classics": classics,
        "suggestions": sorted(
            suggestions,
            key=lambda x: (-x.get("rating", 0), -x.get("votes", 0))
        )[:200],
        "wishlist": wishlist,
    }

    tmdb.flush()
    write_results(results)
    return results