import os
import copy
import yaml

CONFIG_DIR = "/config"
CONFIG_FILE = f"{CONFIG_DIR}/config.yml"


DEFAULT_CONFIG = {
    "SERVER": {
        "UI_PORT": 8787,
        "TZ": "Asia/Jerusalem",
        "MEDIA_SERVER": "plex",   # "plex" or "jellyfin"
    },
    "JELLYFIN": {
        "JELLYFIN_URL": "",
        "JELLYFIN_API_KEY": "",
        "JELLYFIN_LIBRARY_NAME": "Movies",
    },
    "PLEX": {
        "PLEX_URL": "",
        "PLEX_TOKEN": "",
        "LIBRARY_NAME": "",
        "PLEX_PAGE_SIZE": 500,
        "SHORT_MOVIE_LIMIT": 60,
    },
    "TMDB": {
        "TMDB_API_KEY": "",
        "TMDB_MIN_DELAY": 0.02,
        "TMDB_WORKERS": 6,       # concurrent workers for TMDB calls (1-10)
    },
    "CLASSICS": {
        "CLASSICS_PAGES": 4,
        "CLASSICS_MIN_VOTES": 5000,
        "CLASSICS_MIN_RATING": 8.0,
        "CLASSICS_MAX_RESULTS": 120,
    },
    "ACTOR_HITS": {
        "ACTOR_MIN_VOTES": 500,
        "ACTOR_MAX_RESULTS_PER_ACTOR": 10,
    },
    "SUGGESTIONS": {
        "SUGGESTIONS_MAX_RESULTS": 100,
        "SUGGESTIONS_MIN_SCORE": 2,    # min number of your films that must recommend it
    },
    "AUTOMATION": {
        "LIBRARY_POLL_INTERVAL": 30,   # minutes between library size checks (0 = disabled)
    },
    "TELEGRAM": {
        "TELEGRAM_ENABLED": False,
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "TELEGRAM_MIN_INTERVAL": 30,   # minimum minutes between notifications (0 = always)
    },
    "RADARR": {
        "RADARR_ENABLED": False,
        "RADARR_URL": "",
        "RADARR_API_KEY": "",
        "RADARR_ROOT_FOLDER_PATH": "",
        "RADARR_QUALITY_PROFILE_ID": 6,
        "RADARR_MONITORED": True,
        "RADARR_SEARCH_ON_ADD": False,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def ensure_config_dir() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config() -> dict:
    ensure_config_dir()

    if not os.path.exists(CONFIG_FILE):
        return copy.deepcopy(DEFAULT_CONFIG)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return _deep_merge(DEFAULT_CONFIG, data)
    except Exception:
        return copy.deepcopy(DEFAULT_CONFIG)


def save_config(data: dict) -> dict:
    ensure_config_dir()
    merged = _deep_merge(DEFAULT_CONFIG, data or {})

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(merged, f, sort_keys=False, allow_unicode=True)

    return merged


def is_configured(cfg: dict | None = None) -> bool:
    cfg          = cfg or load_config()
    tmdb         = cfg.get("TMDB", {})
    media_server = cfg.get("SERVER", {}).get("MEDIA_SERVER", "plex").lower()

    if not str(tmdb.get("TMDB_API_KEY", "")).strip():
        return False

    if media_server == "jellyfin":
        jf = cfg.get("JELLYFIN", {})
        return all([
            str(jf.get("JELLYFIN_URL", "")).strip(),
            str(jf.get("JELLYFIN_API_KEY", "")).strip(),
            str(jf.get("JELLYFIN_LIBRARY_NAME", "")).strip(),
        ])
    else:
        plex = cfg.get("PLEX", {})
        return all([
            str(plex.get("PLEX_URL", "")).strip(),
            str(plex.get("PLEX_TOKEN", "")).strip(),
            str(plex.get("LIBRARY_NAME", "")).strip(),
        ])
