"""
Cineplete — Telegram notifications
------------------------------------
Sends a scan summary to a Telegram chat when a scan completes.

Respects TELEGRAM_MIN_INTERVAL to avoid spamming on frequent scans.
Last notification time is stored in /data/last_telegram.txt
"""

import os
import time
import requests

from app.config import load_config
from app.logger import get_logger

log        = get_logger(__name__)
DATA_DIR   = "/data"
STAMP_FILE = f"{DATA_DIR}/last_telegram.txt"


def _send(token: str, chat_id: str, text: str) -> bool:
    """Raw Telegram sendMessage. Returns True on success."""
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        if r.status_code == 200:
            return True
        log.warning(f"Telegram API error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
    return False


def _last_sent() -> float:
    """Return timestamp of last notification, or 0 if never sent."""
    try:
        with open(STAMP_FILE, "r") as f:
            return float(f.read().strip())
    except Exception:
        return 0.0


def _save_sent():
    """Persist current timestamp as last notification time."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(STAMP_FILE, "w") as f:
            f.write(str(time.time()))
    except Exception as e:
        log.warning(f"Could not save Telegram timestamp: {e}")


def send_scan_summary(results: dict, duration_s: int | None = None):
    """
    Send a scan summary to Telegram if enabled and interval allows.

    Args:
        results:    The full results dict from scanner.build()
        duration_s: Scan duration in seconds (optional)
    """
    cfg      = load_config()
    tg       = cfg.get("TELEGRAM", {})

    if not tg.get("TELEGRAM_ENABLED"):
        return

    token    = tg.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id  = tg.get("TELEGRAM_CHAT_ID", "").strip()
    min_int  = int(tg.get("TELEGRAM_MIN_INTERVAL", 30))

    if not token or not chat_id:
        log.warning("Telegram enabled but BOT_TOKEN or CHAT_ID is missing")
        return

    # Respect minimum interval
    if min_int > 0:
        elapsed_min = (time.time() - _last_sent()) / 60
        if elapsed_min < min_int:
            log.debug(f"Telegram notification skipped — last sent {elapsed_min:.1f}m ago (min={min_int}m)")
            return

    # Build message
    plex    = results.get("plex", {})
    scores  = results.get("scores", {})

    lib_count   = plex.get("indexed_tmdb", 0)
    global_score= scores.get("global_cinema_score", 0)

    franchise_missing = sum(len(f.get("missing", [])) for f in results.get("franchises", []))
    director_missing  = sum(len(d.get("missing", [])) for d in results.get("directors",  []))
    classics_missing  = len(results.get("classics",    []))
    suggestions_count = len(results.get("suggestions", []))
    no_guid           = len(results.get("no_tmdb_guid",  []))
    no_match          = len(results.get("tmdb_not_found",[]))

    dur_str = ""
    if duration_s:
        if duration_s < 60:
            dur_str = f"{duration_s}s"
        else:
            m, s = divmod(duration_s, 60)
            dur_str = f"{m}m {s}s" if s else f"{m}m"

    lines = [
        "🎬 *Cineplete Scan Complete*",
        "",
        f"📚 Library: {lib_count} movies" + (f"  ·  ⏱ {dur_str}" if dur_str else ""),
        f"🎯 Global Score: *{global_score}%*",
        "",
        f"🔴 Franchises missing: {franchise_missing}",
        f"🎭 Directors missing: {director_missing}",
        f"⭐ Classics missing: {classics_missing}",
        f"💡 Suggestions: {suggestions_count}",
    ]

    if no_guid or no_match:
        lines += ["", f"⚠️ Metadata issues: {no_guid} no GUID · {no_match} no match"]

    text = "\n".join(lines)

    if _send(token, chat_id, text):
        _save_sent()
        log.info("Telegram scan summary sent")


def send_radarr_grab(title: str, year: str | None = None) -> None:
    """
    Send a Telegram notification when Radarr grabs a single wishlist movie.
    Does NOT enforce TELEGRAM_MIN_INTERVAL — each grab is a discrete event.
    """
    cfg     = load_config()
    tg      = cfg.get("TELEGRAM", {})
    if not tg.get("TELEGRAM_ENABLED"):
        return
    token   = tg.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = tg.get("TELEGRAM_CHAT_ID",   "").strip()
    if not token or not chat_id:
        return
    year_str = f" ({year})" if year else ""
    text     = f"⬇️ *Radarr grabbed:* {title}{year_str}"
    if _send(token, chat_id, text):
        log.info(f"Telegram grab notification sent: {title}")
        time.sleep(1.1)   # respect Telegram rate limit (1 msg/sec for private chats)


def send_radarr_grab_batch(movies: list[tuple[str, str | None]]) -> None:
    """
    Send a single batched Telegram notification for multiple Radarr grabs.
    Used when more than one wishlist movie is grabbed at once to avoid
    hitting Telegram's rate limit with individual messages.
    """
    cfg     = load_config()
    tg      = cfg.get("TELEGRAM", {})
    if not tg.get("TELEGRAM_ENABLED"):
        return
    token   = tg.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = tg.get("TELEGRAM_CHAT_ID",   "").strip()
    if not token or not chat_id:
        return
    lines = []
    for title, year in movies:
        year_str = f" ({year})" if year else ""
        lines.append(f"• {title}{year_str}")
    text = f"⬇️ *Radarr grabbed {len(movies)} wishlist movies:*\n" + "\n".join(lines)
    if _send(token, chat_id, text):
        log.info(f"Telegram batch grab notification sent: {len(movies)} movies")