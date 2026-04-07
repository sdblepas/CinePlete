import requests
import defusedxml.ElementTree as ET
from collections import defaultdict

from app.config import load_config


def _build_lib_cfg(lib_cfg):
    """Resolve lib_cfg — if None, fall back to legacy PLEX config section."""
    if lib_cfg is not None:
        url = lib_cfg.get("url", "").strip()
        if not url:
            label = lib_cfg.get("label") or lib_cfg.get("library_name") or "Plex"
            raise RuntimeError(
                f"Plex library '{label}' has no URL configured — "
                "please fill in the URL in Config."
            )
        token = lib_cfg.get("token", "").strip()
        if not token:
            label = lib_cfg.get("label") or lib_cfg.get("library_name") or "Plex"
            raise RuntimeError(
                f"Plex library '{label}' has no token configured — "
                "please fill in the Plex token in Config."
            )
        return lib_cfg
    cfg = load_config()
    plex = cfg["PLEX"]
    url = plex.get("PLEX_URL", "").strip()
    if not url:
        raise RuntimeError(
            "Plex URL is not configured — please fill in the Plex URL in Config."
        )
    return {
        "url": url,
        "token": plex["PLEX_TOKEN"],
        "library_name": plex["LIBRARY_NAME"],
        "page_size": int(plex.get("PLEX_PAGE_SIZE", 500)),
        "short_movie_limit": int(plex.get("SHORT_MOVIE_LIMIT", 60)),
    }


def plex_get(path, lib_cfg=None, params=None):
    lc = _build_lib_cfg(lib_cfg)
    if params is None:
        params = {}
    params["X-Plex-Token"] = lc["token"]
    r = requests.get(lc["url"].rstrip("/") + path, params=params, timeout=30)
    r.raise_for_status()
    return r.text


def library_key(lib_cfg=None):
    lc = _build_lib_cfg(lib_cfg)
    xml = plex_get("/library/sections", lc)
    root = ET.fromstring(xml)
    for d in root.findall("Directory"):
        if d.attrib.get("title") == lc["library_name"]:
            return d.attrib.get("key")
    raise RuntimeError(f"Plex library '{lc['library_name']}' not found on {lc['url']}")


def scan_movies(lib_cfg=None):
    lc = _build_lib_cfg(lib_cfg)
    short_movie_limit = int(lc.get("short_movie_limit", 60))
    page_size = int(lc.get("page_size", 500))
    key = library_key(lc)

    plex_ids = {}
    plex_editions = {}
    tmdb_id_dupes = {}
    directors = defaultdict(set)
    actors = defaultdict(set)
    no_tmdb_guid = []
    start = 0
    scanned = 0
    skipped_short = 0

    while True:
        xml = plex_get(
            f"/library/sections/{key}/all",
            lc,
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
                no_tmdb_guid.append({"title": title, "year": year})
                continue
            edition = v.attrib.get("editionTitle", "")
            if tmdb_id in plex_ids:
                if tmdb_id not in tmdb_id_dupes:
                    tmdb_id_dupes[tmdb_id] = [{"title": plex_ids[tmdb_id], "edition": plex_editions.get(tmdb_id, "")}]
                tmdb_id_dupes[tmdb_id].append({"title": title, "edition": edition})
            else:
                plex_ids[tmdb_id] = title
                plex_editions[tmdb_id] = edition
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
        "duplicates": [
            {"tmdb": tmdb_id, "titles": titles}
            for tmdb_id, titles in tmdb_id_dupes.items()
        ],
    }
    return plex_ids, directors, actors, stats, no_tmdb_guid
