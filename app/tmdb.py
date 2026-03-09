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

    def search_person(self, name):

        url = (
            "https://api.themoviedb.org/3/search/person"
            f"?api_key={self.api_key}&query={requests.utils.quote(name)}"
        )

        data = self.get(url)

        results = data.get("results", [])

        if not results:
            return None

        return results[0]["id"]

    def person_movies(self, person_id):

        url = (
            "https://api.themoviedb.org/3/person/"
            f"{person_id}/movie_credits?api_key={self.api_key}"
        )

        data = self.get(url)

        return data.get("cast", [])

    def movie(self, tmdb_id):

        url = (
            "https://api.themoviedb.org/3/movie/"
            f"{tmdb_id}?api_key={self.api_key}"
        )

        return self.get(url)

    def collection(self, collection_id):

        url = (
            "https://api.themoviedb.org/3/collection/"
            f"{collection_id}?api_key={self.api_key}"
        )

        return self.get(url)

    def discover(self, page=1):

        url = (
            "https://api.themoviedb.org/3/discover/movie"
            f"?api_key={self.api_key}&sort_by=vote_average.desc"
            f"&vote_count.gte=5000&page={page}"
        )

        return self.get(url)

    def flush(self):

        save_cache(self.cache)