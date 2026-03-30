import os
import copy
import yaml

from app.logger import get_logger

log = get_logger(__name__)

CONFIG_DIR = os.getenv("CONFIG_DIR", "/config")
CONFIG_FILE = f"{CONFIG_DIR}/config.yml"


DEFAULT_CONFIG = {
    "LIBRARIES": [],   # list of library connection dicts — auto-migrated from PLEX/JELLYFIN on first load
    "SERVER": {
        "UI_PORT": 8787,
        "TZ": "Asia/Jerusalem",
        "MEDIA_SERVER": "plex",   # "plex" or "jellyfin"
    },
    "JELLYFIN": {
        "JELLYFIN_URL": "",
        "JELLYFIN_API_KEY": "",
        "JELLYFIN_LIBRARY_NAME": "Movies",
        "JELLYFIN_PAGE_SIZE": 500,
        "SHORT_MOVIE_LIMIT": 60,
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
        "AUTO_SCAN_SCHEDULE":    "off", # "off" | "daily" | "weekly" — time-based full rescan
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
        "RADARR_GRAB_POLL_INTERVAL": 5,   # minutes between Radarr grab history polls (0 = disabled)
    },
    "RADARR_4K": {
        "RADARR_4K_ENABLED": False,
        "RADARR_4K_URL": "",
        "RADARR_4K_API_KEY": "",
        "RADARR_4K_ROOT_FOLDER_PATH": "",
        "RADARR_4K_QUALITY_PROFILE_ID": 6,
        "RADARR_4K_MONITORED": True,
        "RADARR_4K_SEARCH_ON_ADD": False,
    },
    "OVERSEERR": {
        "OVERSEERR_ENABLED": False,
        "OVERSEERR_URL": "",
        "OVERSEERR_API_KEY": "",
    },
    "JELLYSEERR": {
        "JELLYSEERR_ENABLED": False,
        "JELLYSEERR_URL": "",
        "JELLYSEERR_API_KEY": "",
    },
    "WEBHOOK": {
        "WEBHOOK_ENABLED": False,
        "WEBHOOK_SECRET": "",
    },
    "WATCHTOWER": {
        "WATCHTOWER_ENABLED": False,
        "WATCHTOWER_URL": "",
        "WATCHTOWER_API_TOKEN": "",
    },
    "FLARESOLVERR": {
        "FLARESOLVERR_URL": "",   # e.g. http://flaresolverr:8191
    },
    "AUTH": {
        # "None" | "Forms" | "DisabledForLocalAddresses"
        "AUTH_METHOD": "None",
        "AUTH_USERNAME": "",
        "AUTH_PASSWORD_HASH": "",
        "AUTH_PASSWORD_SALT": "",
        "AUTH_SECRET_KEY": "",   # auto-generated on first save
    },
}


def _migrate_libraries(cfg: dict) -> dict:
    """
    If LIBRARIES is empty, auto-migrate from the legacy flat PLEX/JELLYFIN config.
    Runs transparently on load — existing users see no disruption.
    """
    if cfg.get("LIBRARIES"):
        return cfg

    libraries = []
    media_server = cfg.get("SERVER", {}).get("MEDIA_SERVER", "plex").lower()

    plex = cfg.get("PLEX", {})
    if plex.get("PLEX_URL") or plex.get("PLEX_TOKEN"):
        libraries.append({
            "id": "plex-0",
            "type": "plex",
            "enabled": media_server == "plex",
            "label": "Plex",
            "url": plex.get("PLEX_URL", ""),
            "token": plex.get("PLEX_TOKEN", ""),
            "library_name": plex.get("LIBRARY_NAME", ""),
            "page_size": int(plex.get("PLEX_PAGE_SIZE", 500)),
            "short_movie_limit": int(plex.get("SHORT_MOVIE_LIMIT", 60)),
        })

    jf = cfg.get("JELLYFIN", {})
    if jf.get("JELLYFIN_URL") or jf.get("JELLYFIN_API_KEY"):
        libraries.append({
            "id": "jellyfin-0",
            "type": "jellyfin",
            "enabled": media_server == "jellyfin",
            "label": "Jellyfin",
            "url": jf.get("JELLYFIN_URL", ""),
            "api_key": jf.get("JELLYFIN_API_KEY", ""),
            "library_name": jf.get("JELLYFIN_LIBRARY_NAME", "Movies"),
            "page_size": int(jf.get("JELLYFIN_PAGE_SIZE", 500)),
            "short_movie_limit": int(jf.get("SHORT_MOVIE_LIMIT", 60)),
        })

    cfg["LIBRARIES"] = libraries
    return cfg


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
        return _migrate_libraries(copy.deepcopy(DEFAULT_CONFIG))

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        merged = _deep_merge(DEFAULT_CONFIG, data)
        # LIBRARIES is a list — deep_merge doesn't handle lists, carry it over directly
        if "LIBRARIES" in data:
            merged["LIBRARIES"] = data["LIBRARIES"]
        return _migrate_libraries(merged)
    except (OSError, yaml.YAMLError) as e:
        log.warning(f"Could not load config file: {e} — using defaults")
        return _migrate_libraries(copy.deepcopy(DEFAULT_CONFIG))


def save_config(data: dict) -> dict:
    ensure_config_dir()
    libraries = data.get("LIBRARIES")   # preserve list as-is
    merged = _deep_merge(DEFAULT_CONFIG, data or {})
    if libraries is not None:
        merged["LIBRARIES"] = libraries

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(merged, f, sort_keys=False, allow_unicode=True)

    return merged


def is_configured(cfg: dict | None = None) -> bool:
    cfg  = cfg or load_config()
    tmdb = cfg.get("TMDB", {})
    if not str(tmdb.get("TMDB_API_KEY", "")).strip():
        return False

    libraries = cfg.get("LIBRARIES", [])
    enabled   = [l for l in libraries if l.get("enabled")]
    for lib in enabled:
        lib_type = lib.get("type", "plex").lower()
        if lib_type == "jellyfin":
            if lib.get("url") and lib.get("api_key") and lib.get("library_name"):
                return True
        else:
            if lib.get("url") and lib.get("token") and lib.get("library_name"):
                return True

    # Fall back to legacy flat config check for users mid-migration
    media_server = cfg.get("SERVER", {}).get("MEDIA_SERVER", "plex").lower()
    if media_server == "jellyfin":
        jf = cfg.get("JELLYFIN", {})
        return all([str(jf.get("JELLYFIN_URL","")).strip(),
                    str(jf.get("JELLYFIN_API_KEY","")).strip(),
                    str(jf.get("JELLYFIN_LIBRARY_NAME","")).strip()])
    else:
        plex = cfg.get("PLEX", {})
        return all([str(plex.get("PLEX_URL","")).strip(),
                    str(plex.get("PLEX_TOKEN","")).strip(),
                    str(plex.get("LIBRARY_NAME","")).strip()])
