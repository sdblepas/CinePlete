import requests
import time
import json
import os
import threading

from app.logger import get_logger

log = get_logger(__name__)

DATA_DIR   = "/data"
CACHE_FILE = f"{DATA_DIR}/tmdb_cache.json"

# Flush cache to disk every N real HTTP calls so a crash doesn't lose all progress
FLUSH_EVERY = 50


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_cache():
    ensure_data_dir()
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        log.debug("No TMDB cache found — starting fresh")
        return {}
    except Exception as e:
        log.warning(f"Could not load TMDB cache: {e} — starting fresh")
        return {}


def save_cache(cache):
    ensure_data_dir()
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    os.replace(tmp, CACHE_FILE)


class TMDB:

    def __init__(self, api_key, delay=0.02):
        self.api_key = api_key
        self.delay   = delay
        self.cache   = load_cache()
        self._calls_since_flush = 0
        self._error_count = 0
        self._lock = threading.Lock()  # protects cache dict for concurrent workers

    # --------------------------------------------------
    # Build a cache key that does NOT include the API key
    # so rotating the key doesn't invalidate the cache.
    # --------------------------------------------------

    def _cache_key(self, url: str) -> str:
        key = url.replace(f"?api_key={self.api_key}&", "?") \
                 .replace(f"?api_key={self.api_key}", "") \
                 .replace(f"&api_key={self.api_key}", "")
        return key

    def _request(self, url: str) -> dict:
        cache_key = self._cache_key(url)

        try:
            r = requests.get(url, timeout=30)
        except requests.exceptions.ConnectionError as e:
            self._error_count += 1
            log.error(f"TMDB connection error — check network. url={cache_key} error={e}")
            return {}
        except requests.exceptions.Timeout:
            self._error_count += 1
            log.warning(f"TMDB request timed out — url={cache_key}")
            return {}
        except Exception as e:
            self._error_count += 1
            log.error(f"TMDB unexpected request error — url={cache_key} error={e}")
            return {}

        if r.status_code == 401:
            self._error_count += 1
            log.error("TMDB API key is invalid or missing (HTTP 401) — check your TMDB_API_KEY in config")
            return {}

        if r.status_code == 404:
            log.debug(f"TMDB 404 — resource not found: {cache_key}")
            return {}

        if r.status_code == 429:
            self._error_count += 1
            log.warning("TMDB rate limit hit (HTTP 429) — consider increasing TMDB_MIN_DELAY in config")
            return {}

        if r.status_code != 200:
            self._error_count += 1
            log.warning(f"TMDB unexpected status {r.status_code} — url={cache_key}")
            return {}

        try:
            return r.json()
        except Exception as e:
            log.warning(f"TMDB response JSON parse error — url={cache_key} error={e}")
            return {}

    def get(self, url: str) -> dict:
        cache_key = self._cache_key(url)

        # Cache hit — check under lock, return immediately
        with self._lock:
            if cache_key in self.cache:
                return self.cache[cache_key]

        # Real HTTP call — outside lock so other threads aren't blocked
        time.sleep(self.delay)
        data = self._request(url)

        # Write back under lock
        with self._lock:
            # Double-check: another thread may have fetched same key while we waited
            if cache_key in self.cache:
                return self.cache[cache_key]

            if data:
                self.cache[cache_key] = data
                self._calls_since_flush += 1

                if self._calls_since_flush >= FLUSH_EVERY:
                    save_cache(self.cache)
                    self._calls_since_flush = 0

        return data

    # ------------------------------------------------
    # MOVIES
    # ------------------------------------------------

    def movie(self, tmdb_id: int) -> dict:
        url = (
            f"https://api.themoviedb.org/3/movie/{tmdb_id}"
            f"?api_key={self.api_key}"
        )
        return self.get(url)

    def collection(self, collection_id: int) -> dict:
        url = (
            f"https://api.themoviedb.org/3/collection/{collection_id}"
            f"?api_key={self.api_key}"
        )
        return self.get(url)

    def top_rated(self, page: int = 1) -> dict:
        url = (
            "https://api.themoviedb.org/3/movie/top_rated"
            f"?api_key={self.api_key}&page={page}"
        )
        return self.get(url)

    def recommendations(self, tmdb_id: int) -> dict:
        url = (
            f"https://api.themoviedb.org/3/movie/{tmdb_id}/recommendations"
            f"?api_key={self.api_key}"
        )
        return self.get(url)

    # ------------------------------------------------
    # PEOPLE
    # ------------------------------------------------

    def search_person(self, name: str) -> dict:
        url = (
            "https://api.themoviedb.org/3/search/person"
            f"?api_key={self.api_key}&query={requests.utils.quote(name)}"
        )
        return self.get(url)

    def person_credits(self, person_id: int) -> dict:
        url = (
            f"https://api.themoviedb.org/3/person/{person_id}/movie_credits"
            f"?api_key={self.api_key}"
        )
        return self.get(url)

    # ------------------------------------------------
    # IMAGES
    # ------------------------------------------------

    def poster_url(self, path: str | None) -> str | None:
        if not path:
            return None
        return f"https://image.tmdb.org/t/p/w500{path}"

    # ------------------------------------------------

    def flush(self):
        save_cache(self.cache)
        self._calls_since_flush = 0
        if self._error_count:
            log.warning(f"TMDB scan completed with {self._error_count} API errors")
        else:
            log.info("TMDB cache flushed successfully")