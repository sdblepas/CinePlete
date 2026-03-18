"""
Cineplete scheduler
-------------------
Polls Plex library size at a configurable interval.
If the movie count changes vs the last scan results, triggers a new scan.

Controlled by config:
    AUTOMATION.LIBRARY_POLL_INTERVAL  — minutes between checks (0 = disabled)
"""

import json
import os

import requests
import defusedxml.ElementTree as ET
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import load_config
from app.logger import get_logger

log = get_logger(__name__)

DATA_DIR     = "/data"
RESULTS_FILE = f"{DATA_DIR}/results.json"

_scheduler = None


def _get_plex_movie_count() -> int | None:
    """Return total movie count from Plex or None on error."""
    try:
        cfg      = load_config()
        plex_cfg = cfg["PLEX"]
        url      = plex_cfg["PLEX_URL"]
        token    = plex_cfg["PLEX_TOKEN"]
        library  = plex_cfg["LIBRARY_NAME"]

        if not all([url, token, library]):
            return None

        r = requests.get(
            f"{url}/library/sections",
            params={"X-Plex-Token": token},
            timeout=10,
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)

        key = None
        for d in root.findall("Directory"):
            if d.attrib.get("title") == library:
                key = d.attrib.get("key")
                break

        if not key:
            return None

        r2 = requests.get(
            f"{url}/library/sections/{key}/all",
            params={
                "type": "1",
                "X-Plex-Token": token,
                "X-Plex-Container-Start": 0,
                "X-Plex-Container-Size": 1,
            },
            timeout=10,
        )
        r2.raise_for_status()
        root2 = ET.fromstring(r2.text)
        total = root2.attrib.get("totalSize") or root2.attrib.get("size")
        return int(total) if total else None

    except Exception as e:
        log.debug(f"Plex library poll error: {e}")
        return None


def _get_jellyfin_movie_count() -> int | None:
    """Return total movie count from Jellyfin or None on error."""
    try:
        cfg    = load_config()
        jf_cfg = cfg.get("JELLYFIN", {})
        url    = jf_cfg.get("JELLYFIN_URL", "").rstrip("/")
        token  = jf_cfg.get("JELLYFIN_API_KEY", "")
        library = jf_cfg.get("JELLYFIN_LIBRARY_NAME", "Movies")

        if not all([url, token, library]):
            return None

        # Get library ID
        r = requests.get(
            f"{url}/Library/MediaFolders",
            headers={"X-Emby-Token": token},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()

        lib_id = None
        for item in data.get("Items", []):
            if item.get("Name", "").lower() == library.lower():
                lib_id = item["Id"]
                break

        if not lib_id:
            return None

        # Get count only — Limit=1 is enough to get TotalRecordCount
        r2 = requests.get(
            f"{url}/Items",
            headers={"X-Emby-Token": token},
            params={
                "ParentId":         lib_id,
                "IncludeItemTypes": "Movie",
                "Recursive":        "true",
                "Limit":            1,
            },
            timeout=10,
        )
        r2.raise_for_status()
        return r2.json().get("TotalRecordCount")

    except Exception as e:
        log.debug(f"Jellyfin library poll error: {e}")
        return None


def _get_last_scan_count() -> int | None:
    """Return the indexed_tmdb count from the last results.json."""
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("plex", {}).get("indexed_tmdb")
    except Exception:
        return None


def _poll():
    """Called by APScheduler. Triggers a scan if library size changed."""
    # Import here to avoid circular import
    from app.scanner import build_async, scan_state

    if scan_state["running"]:
        log.debug("Library poll skipped — scan already running")
        return

    cfg = load_config()
    media_server = cfg.get("SERVER", {}).get("MEDIA_SERVER", "plex").lower()
    if media_server == "jellyfin":
        current = _get_jellyfin_movie_count()
    else:
        current = _get_plex_movie_count()
    if current is None:
        log.debug("Library poll: could not reach Plex")
        return

    last = _get_last_scan_count()

    if last is None:
        log.debug("Library poll: no previous scan results, skipping auto-trigger")
        return

    if current != last:
        log.info(f"Library change detected: {last} → {current} movies — triggering auto-scan")
        launched = build_async()
        if not launched:
            log.warning("Auto-scan could not start (lock busy)")
    else:
        log.debug(f"Library poll: no change ({current} movies)")


def start(interval_minutes: int):
    """Start the background scheduler with the given poll interval."""
    global _scheduler

    if interval_minutes <= 0:
        log.info("Library polling disabled (LIBRARY_POLL_INTERVAL = 0)")
        return

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _poll,
        trigger="interval",
        minutes=interval_minutes,
        id="library_poll",
        replace_existing=True,
    )
    _scheduler.start()
    log.info(f"Library polling started — checking every {interval_minutes} minute(s)")


def stop():
    """Stop the scheduler cleanly."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Library polling stopped")


def restart():
    """Reload interval from config and restart scheduler."""
    cfg      = load_config()
    interval = int(cfg.get("AUTOMATION", {}).get("LIBRARY_POLL_INTERVAL", 30))
    stop()
    start(interval)