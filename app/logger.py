"""
Cineplete logger
----------------
Single source of truth for logging across all modules.

- Console handler  : INFO+  (always visible in docker logs)
- File handler     : DEBUG+ (rotating, /data/cineplete.log, 2 MB × 3 files)

Usage:
    from app.logger import get_logger
    log = get_logger(__name__)
    log.info("hello")
    log.warning("something odd")
    log.error("something broke")
    log.debug("verbose detail")
"""

import logging
import os
from logging.handlers import RotatingFileHandler

DATA_DIR  = "/data"
LOG_FILE  = f"{DATA_DIR}/cineplete.log"
LOG_BYTES = 2 * 1024 * 1024   # 2 MB per file
LOG_COUNT = 3                  # keep 3 rotated files

_configured = False


def _setup():
    global _configured
    if _configured:
        return
    _configured = True

    os.makedirs(DATA_DIR, exist_ok=True)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # ── Console (INFO+) ──────────────────────────────────
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    # ── Rotating file (DEBUG+) ───────────────────────────
    try:
        fh = RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_BYTES,
            backupCount=LOG_COUNT,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception as e:
        root.warning(f"Could not open log file {LOG_FILE}: {e}")

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    _setup()
    return logging.getLogger(name)