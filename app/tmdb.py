import requests
import time
import json
import os

DATA_DIR = "/app/data"
CACHE_FILE = f"{DATA_DIR}/tmdb_cache.json"


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

    def _request(self, url):

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

    def get(self, url):

        if url in self.cache:
            return self.cache[url]

        time.sleep(self.delay)

        data = self._request(url)

        self.cache[url] = data

        return data

    # ------------------------------------------------
    # MOVIES
    # ------------------------------------------------

    def movie(self, tmdb_id):

        url = (
            f"https://api.themoviedb.org/3/movie/{tmdb_id}"
            f"?api_key={self.api_key}"
        )

        return self.get(url)

    def collection(self, collection_id):

        url = (
            f"https://api.themoviedb.org/3/collection/{collection_id}"
            f"?api_key={self.api_key}"
        )

        return self.get(url)

    def top_rated(self, page=1):

        url = (
            "https://api.themoviedb.org/3/movie/top_rated"
            f"?api_key={self.api_key}&page={page}"
        )

        return self.get(url)

    # ------------------------------------------------
    # PEOPLE
    # ------------------------------------------------

    def search_person(self, name):

        url = (
            "https://api.themoviedb.org/3/search/person"
            f"?api_key={self.api_key}&query={requests.utils.quote(name)}"
        )

        return self.get(url)

    def person_credits(self, person_id):

        url = (
            f"https://api.themoviedb.org/3/person/{person_id}/movie_credits"
            f"?api_key={self.api_key}"
        )

        return self.get(url)

    # ------------------------------------------------
    # IMAGES
    # ------------------------------------------------

    def poster_url(self, path):

        if not path:
            return None

        return f"https://image.tmdb.org/t/p/w500{path}"

    # ------------------------------------------------

    def flush(self):

        save_cache(self.cache)