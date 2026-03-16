import requests
import defusedxml.ElementTree as ET
from collections import defaultdict

from app.config import load_config


def plex_get(path, params=None):
    cfg = load_config()
    plex_cfg = cfg["PLEX"]

    if params is None:
        params = {}

    params["X-Plex-Token"] = plex_cfg["PLEX_TOKEN"]

    r = requests.get(
        plex_cfg["PLEX_URL"] + path,
        params=params,
        timeout=30
    )
    r.raise_for_status()
    return r.text


def library_key():
    cfg = load_config()
    plex_cfg = cfg["PLEX"]

    xml = plex_get("/library/sections")
    root = ET.fromstring(xml)

    for d in root.findall("Directory"):
        if d.attrib.get("title") == plex_cfg["LIBRARY_NAME"]:
            return d.attrib.get("key")

    raise RuntimeError(f"Library '{plex_cfg['LIBRARY_NAME']}' not found")


def scan_movies():
    cfg = load_config()
    plex_cfg = cfg["PLEX"]

    short_movie_limit = int(plex_cfg["SHORT_MOVIE_LIMIT"])
    page_size = int(plex_cfg["PLEX_PAGE_SIZE"])

    key = library_key()

    plex_ids = {}          # {tmdb_id: plex_title}  — dict so we keep the title
    directors = defaultdict(set)
    actors = defaultdict(set)
    no_tmdb_guid = []

    start = 0
    scanned = 0
    skipped_short = 0

    while True:
        xml = plex_get(
            f"/library/sections/{key}/all",
            {
                "type": "1",
                "includeGuids": "1",
                "X-Plex-Container-Start": start,
                "X-Plex-Container-Size": page_size,
            },
        )

        root = ET.fromstring(xml)
        videos = root.findall("Video")

        if not videos:
            break

        for v in videos:
            scanned += 1

            title = v.attrib.get("title")
            year = v.attrib.get("year")

            duration_ms = v.attrib.get("duration")
            duration_min = int(duration_ms) / 60000 if duration_ms else 0

            if duration_min < short_movie_limit:
                skipped_short += 1
                continue

            tmdb_id = None

            for g in v.findall("Guid"):
                gid = g.attrib.get("id")
                if gid and gid.startswith("tmdb://"):
                    try:
                        tmdb_id = int(gid.split("tmdb://")[1])
                    except Exception:
                        tmdb_id = None
                    break

            if not tmdb_id:
                no_tmdb_guid.append({
                    "title": title,
                    "year": year
                })
                continue

            # Store title alongside tmdb_id so we can show it if TMDB lookup fails
            plex_ids[tmdb_id] = title

            for d in v.findall("Director"):
                tag = d.attrib.get("tag")
                if tag:
                    directors[tag].add(tmdb_id)

            for r in v.findall("Role"):
                tag = r.attrib.get("tag")
                if tag:
                    actors[tag].add(tmdb_id)

        start += len(videos)

    directors = {k: v for k, v in directors.items() if len(v) > 1}
    actors = {k: v for k, v in actors.items() if len(v) > 1}

    stats = {
        "scanned_items": scanned,
        "indexed_tmdb": len(plex_ids),
        "skipped_short": skipped_short,
        "directors_kept": len(directors),
        "actors_kept": len(actors),
        "no_tmdb_guid": len(no_tmdb_guid),
    }

    return plex_ids, directors, actors, stats, no_tmdb_guid