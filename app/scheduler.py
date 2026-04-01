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

DATA_DIR        = os.getenv("DATA_DIR", "/data")
RESULTS_FILE    = f"{DATA_DIR}/results.json"
OVERRIDES_FILE  = f"{DATA_DIR}/overrides.json"
GRAB_SEEN_FILE  = f"{DATA_DIR}/radarr_grab_seen.json"
MAX_SEEN_IDS    = 500

_scheduler = None


def _get_plex_movie_count(lib: dict) -> int | None:
    """Return total movie count for a single Plex library config or None on error."""
    try:
        url     = lib.get("url", "").rstrip("/")
        token   = lib.get("token", "")
        library = lib.get("library_name", "")

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


def _get_jellyfin_movie_count(lib: dict) -> int | None:
    """Return total movie count for a single Jellyfin library config or None on error."""
    try:
        url     = lib.get("url", "").rstrip("/")
        token   = lib.get("api_key", "")
        library = lib.get("library_name", "Movies")

        if not all([url, token, library]):
            return None

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
            log.warning(f"Jellyfin library '{library}' not found — check library_name in config")
            return None

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


def _get_total_movie_count(cfg: dict) -> int | None:
    """
    Sum movie counts across all enabled libraries.
    Returns None if every library fails to respond.
    Falls back to legacy flat config if LIBRARIES is empty.
    """
    libraries    = cfg.get("LIBRARIES", [])
    enabled_libs = [l for l in libraries if l.get("enabled", True)]

    if enabled_libs:
        total = 0
        any_ok = False
        for lib in enabled_libs:
            lib_type = lib.get("type", "plex").lower()
            count = (_get_jellyfin_movie_count(lib)
                     if lib_type == "jellyfin"
                     else _get_plex_movie_count(lib))
            if count is not None:
                total += count
                any_ok = True
        return total if any_ok else None

    # Legacy fallback
    media_server = cfg.get("SERVER", {}).get("MEDIA_SERVER", "plex").lower()
    plex_cfg = cfg.get("PLEX", {})
    jf_cfg   = cfg.get("JELLYFIN", {})
    if media_server == "jellyfin":
        legacy_lib = {
            "url": jf_cfg.get("JELLYFIN_URL", ""),
            "api_key": jf_cfg.get("JELLYFIN_API_KEY", ""),
            "library_name": jf_cfg.get("JELLYFIN_LIBRARY_NAME", "Movies"),
        }
        return _get_jellyfin_movie_count(legacy_lib)
    else:
        legacy_lib = {
            "url": plex_cfg.get("PLEX_URL", ""),
            "token": plex_cfg.get("PLEX_TOKEN", ""),
            "library_name": plex_cfg.get("LIBRARY_NAME", ""),
        }
        return _get_plex_movie_count(legacy_lib)


def _get_last_scan_count() -> int | None:
    """Return the indexed_tmdb count from the last results.json."""
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        stats = data.get("media_server") or data.get("plex") or {}
        return stats.get("indexed_tmdb")
    except Exception:
        return None


def _load_seen_ids() -> set:
    try:
        with open(GRAB_SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_seen_ids(ids: set) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        # Keep only the most recent MAX_SEEN_IDS (Radarr IDs are monotonically increasing)
        trimmed = sorted(ids)[-MAX_SEEN_IDS:]
        with open(GRAB_SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(trimmed, f)
    except Exception as e:
        log.warning(f"Could not save Radarr grab seen IDs: {e}")


def _poll_radarr_grabs() -> None:
    """
    Poll Radarr's grab history and send a Telegram notification for every
    wishlist movie that Radarr grabbed since the last check.

    Uses /data/radarr_grab_seen.json to track which event IDs have already
    triggered a notification. On first run the file is absent — we seed it
    with all current grab event IDs and return without notifying (avoids a
    flood of notifications for past grabs on first start).
    """
    import time
    from app.telegram import send_radarr_grab, send_radarr_grab_batch

    cfg    = load_config()
    radarr = cfg.get("RADARR", {})
    tg     = cfg.get("TELEGRAM", {})

    if not radarr.get("RADARR_ENABLED") or not tg.get("TELEGRAM_ENABLED"):
        return

    url = radarr.get("RADARR_URL", "").rstrip("/")
    key = radarr.get("RADARR_API_KEY", "")
    if not url or not key:
        return

    # Load wishlist
    try:
        with open(OVERRIDES_FILE, "r", encoding="utf-8") as f:
            ov = json.load(f)
        wishlist: set = set(ov.get("wishlist_movies", []))
    except Exception:
        wishlist = set()

    if not wishlist:
        return

    # Fetch recent grab history from Radarr
    try:
        r = requests.get(
            f"{url}/api/v3/history",
            headers={"X-Api-Key": key},
            params={"eventType": "grabbed", "pageSize": 100,
                    "sortKey": "date", "sortDir": "desc"},
            timeout=15,
        )
        r.raise_for_status()
        records = r.json().get("records", [])
    except Exception as e:
        log.debug(f"Radarr grab poll error: {e}")
        return

    seen_ids   = _load_seen_ids()
    first_run  = not os.path.exists(GRAB_SEEN_FILE)

    if first_run:
        # Seed only recent events (last 7 days) to avoid loading unbounded history
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        for event in records:
            grabbed_at = event.get("date", "")
            try:
                dt = datetime.fromisoformat(grabbed_at.replace("Z", "+00:00"))
                if dt >= cutoff:
                    seen_ids.add(event.get("id"))
            except Exception:
                seen_ids.add(event.get("id"))
        _save_seen_ids(seen_ids)
        log.info(f"Radarr grab poller: first run, seeded {len(seen_ids)} recent event IDs")
        return

    grabbed_movies: list[tuple[str, str | None]] = []
    for event in records:
        event_id = event.get("id")
        if not event_id or event_id in seen_ids:
            seen_ids.add(event_id)
            continue
        seen_ids.add(event_id)

        tmdb_id = event.get("movie", {}).get("tmdbId")
        if tmdb_id and tmdb_id in wishlist:
            title = event.get("movie", {}).get("title", "Unknown")
            year  = str(event.get("movie", {}).get("year", "")) or None
            grabbed_movies.append((title, year))

    _save_seen_ids(seen_ids)

    if grabbed_movies:
        if len(grabbed_movies) == 1:
            send_radarr_grab(*grabbed_movies[0])
        else:
            send_radarr_grab_batch(grabbed_movies)
        log.info(f"Radarr grab poller: {len(grabbed_movies)} wishlist grab(s) notified")


def _scheduled_scan():
    """Called by APScheduler for time-based auto-scans (daily/weekly)."""
    from app.scanner import build_async, scan_state
    if scan_state["running"]:
        log.debug("Scheduled scan skipped — scan already running")
        return
    log.info("Scheduled auto-scan triggered")
    launched = build_async()
    if not launched:
        log.warning("Scheduled auto-scan could not start (lock busy)")


def _poll():
    """Called by APScheduler. Triggers a scan if library size changed."""
    # Import here to avoid circular import
    from app.scanner import build_async, scan_state

    if scan_state["running"]:
        log.debug("Library poll skipped — scan already running")
        return

    cfg     = load_config()
    current = _get_total_movie_count(cfg)
    if current is None:
        log.debug("Library poll: could not reach media server")
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

    cfg      = load_config()
    schedule = cfg.get("AUTOMATION", {}).get("AUTO_SCAN_SCHEDULE", "off")

    if interval_minutes <= 0 and schedule == "off":
        log.info("Library polling and scheduled auto-scan both disabled")
        return

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)

    _scheduler = BackgroundScheduler(daemon=True)

    if interval_minutes > 0:
        _scheduler.add_job(
            _poll,
            trigger="interval",
            minutes=interval_minutes,
            id="library_poll",
            replace_existing=True,
        )
        log.info(f"Library polling started — checking every {interval_minutes} minute(s)")

    if schedule == "daily":
        _scheduler.add_job(
            _scheduled_scan,
            trigger="cron",
            hour=2, minute=0,
            id="auto_scan",
            replace_existing=True,
        )
        log.info("Scheduled auto-scan: daily at 02:00")
    elif schedule == "weekly":
        _scheduler.add_job(
            _scheduled_scan,
            trigger="cron",
            day_of_week="sun", hour=2, minute=0,
            id="auto_scan",
            replace_existing=True,
        )
        log.info("Scheduled auto-scan: weekly on Sunday at 02:00")

    # Radarr grab notifications (every 5 minutes when both Radarr + Telegram enabled)
    radarr_poll = int(cfg.get("RADARR", {}).get("RADARR_GRAB_POLL_INTERVAL", 5))
    if (radarr_poll > 0
            and cfg.get("RADARR", {}).get("RADARR_ENABLED")
            and cfg.get("TELEGRAM", {}).get("TELEGRAM_ENABLED")):
        _scheduler.add_job(
            _poll_radarr_grabs,
            trigger="interval",
            minutes=radarr_poll,
            id="radarr_grab_poll",
            replace_existing=True,
        )
        log.info(f"Radarr grab notifications: polling every {radarr_poll} minute(s)")

    _scheduler.start()


def stop():
    """Stop the scheduler cleanly."""
    global _scheduler
    if _scheduler and _scheduler.running:
        # wait=True lets any in-flight poll/trigger job finish before shutting down
        # (jobs are short — they only launch threads, not block until scan completes)
        _scheduler.shutdown(wait=True)
        log.info("Library polling stopped")


def restart():
    """Reload interval from config and restart scheduler."""
    cfg      = load_config()
    interval = int(cfg.get("AUTOMATION", {}).get("LIBRARY_POLL_INTERVAL", 30))
    stop()
    start(interval)