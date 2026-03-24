"""
Cineplete — Jellyfin scanner
-----------------------------
Drop-in replacement for plex_xml.py.
Returns the exact same tuple: (plex_ids, directors, actors, stats, no_tmdb_guid)
so scanner.py needs no logic changes.
"""

import requests
from collections import defaultdict

from app.config import load_config
from app.logger import get_logger

log = get_logger(__name__)


def _jf_get(path: str, params: dict = None) -> dict:
    """Make an authenticated GET request to Jellyfin and return JSON."""
    cfg = load_config()
    jf  = cfg["JELLYFIN"]

    headers = {"X-Emby-Token": jf["JELLYFIN_API_KEY"]}
    url     = jf["JELLYFIN_URL"].rstrip("/") + path

    r = requests.get(url, headers=headers, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def _library_id(library_name: str) -> str:
    """Resolve a library name to its Jellyfin item ID."""
    data = _jf_get("/Library/MediaFolders")
    for item in data.get("Items", []):
        if item.get("Name", "").lower() == library_name.lower():
            return item["Id"]
    raise RuntimeError(f"Jellyfin library '{library_name}' not found")


def scan_movies():
    """
    Scan the configured Jellyfin movie library.

    Returns:
        plex_ids      dict[int, str]   — {tmdb_id: title}
        directors     dict[str, set]   — {director_name: {tmdb_id, ...}}
        actors        dict[str, set]   — {actor_name: {tmdb_id, ...}}
        stats         dict             — scan statistics
        no_tmdb_guid  list[dict]       — films without a TMDB provider ID
    """
    cfg    = load_config()
    jf_cfg = cfg["JELLYFIN"]

    short_movie_limit = int(cfg.get("PLEX", {}).get("SHORT_MOVIE_LIMIT", 60))
    page_size         = int(cfg.get("PLEX", {}).get("PLEX_PAGE_SIZE", 500))
    library_name      = jf_cfg.get("JELLYFIN_LIBRARY_NAME", "Movies")

    library_id = _library_id(library_name)
    log.info(f"Jellyfin library '{library_name}' → ID {library_id}")

    media_ids   = {}          # {tmdb_id: title}
    directors   = defaultdict(set)
    actors      = defaultdict(set)
    no_tmdb_guid = []

    start     = 0
    scanned   = 0
    skipped_short = 0

    while True:
        data = _jf_get("/Items", {
            "ParentId":        library_id,
            "IncludeItemTypes":"Movie",
            "Recursive":       "true",
            "Fields":          "ProviderIds,People,RunTimeTicks",
            "StartIndex":      start,
            "Limit":           page_size,
        })

        items = data.get("Items", [])
        if not items:
            break

        for item in items:
            scanned += 1

            title = item.get("Name", "")
            year  = str(item.get("ProductionYear", "")) or None

            # RunTimeTicks → minutes (1 tick = 100 nanoseconds)
            ticks      = item.get("RunTimeTicks") or 0
            duration_min = ticks / 600_000_000

            if duration_min and duration_min < short_movie_limit:
                skipped_short += 1
                continue

            # TMDB ID — stored as plain string in ProviderIds.Tmdb
            provider_ids = item.get("ProviderIds", {})
            tmdb_raw     = provider_ids.get("Tmdb") or provider_ids.get("tmdb")

            if not tmdb_raw:
                no_tmdb_guid.append({"title": title, "year": year})
                continue

            try:
                tmdb_id = int(tmdb_raw)
            except (ValueError, TypeError):
                no_tmdb_guid.append({"title": title, "year": year})
                continue

            media_ids[tmdb_id] = title

            # People — directors and actors are in the same array
            # Limit actors to top 5 per film to match Plex behavior
            # (Jellyfin returns ALL people including minor roles)
            actor_count = 0
            for person in item.get("People", []):
                name      = person.get("Name", "").strip()
                role_type = person.get("Type", "")
                if not name:
                    continue
                if role_type == "Director":
                    directors[name].add(tmdb_id)
                elif role_type == "Actor" and actor_count < 5:
                    actors[name].add(tmdb_id)
                    actor_count += 1

        total = data.get("TotalRecordCount", 0)
        start += len(items)
        if start >= total:
            break

    # Only keep directors/actors appearing in 2+ films
    directors = {k: v for k, v in directors.items() if len(v) > 1}
    actors    = {k: v for k, v in actors.items()    if len(v) > 1}

    stats = {
        "scanned_items":  scanned,
        "indexed_tmdb":   len(media_ids),
        "skipped_short":  skipped_short,
        "directors_kept": len(directors),
        "actors_kept":    len(actors),
        "no_tmdb_guid":   len(no_tmdb_guid),
    }

    return media_ids, directors, actors, stats, no_tmdb_guid
