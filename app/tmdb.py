import requests
import time
import json
import os

DATA_DIR = "/data"
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
    except Exception:
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
        self.delay = delay
        self.cache = load_cache()
        self._calls_since_flush = 0

    # --------------------------------------------------
    # Build a cache key that does NOT include the API key
    # so rotating the key doesn't invalidate the cache.
    # --------------------------------------------------

    def _cache_key(self, url: str) -> str:
        """Return url with api_key param stripped out."""
        key = url.replace(f"?api_key={self.api_key}&", "?") \
                 .replace(f"?api_key={self.api_key}", "") \
                 .replace(f"&api_key={self.api_key}", "")
        return key

    def _request(self, url: str) -> dict:
        try:
            r = requests.get(url, timeout=30)
        except Exception:
            return {}

        if r.status_code != 200:
            return {}

        try:
            return r.json()
        except Exception:
            return {}

    def get(self, url: str) -> dict:
        cache_key = self._cache_key(url)

        # Cache hit — return immediately, no sleep
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Real HTTP call — apply rate-limit delay
        time.sleep(self.delay)
        data = self._request(url)

        self.cache[cache_key] = data
        self._calls_since_flush += 1

        # Periodic flush so a mid-scan crash doesn't lose all progress
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