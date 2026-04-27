"""
Regression test: GET /api/results must strip ignored movies from the response
so that movies ignored between scans don't reappear on browser refresh.

Covers:
  - Flat lists: classics, suggestions
  - Grouped lists: franchises[].missing, directors[].missing, actors[].missing
  - Ignored IDs must NOT bleed into non-missing keys (wishlist, owned, etc.)
  - GET /api/search must also exclude ignored movies
"""
import copy
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_RESULTS = {
    "franchises": [
        {
            "name": "Alien Collection",
            "have": 2, "total": 3,
            "missing": [
                {"tmdb": 1001, "title": "Alien Romulus", "year": "2024"},
                {"tmdb": 1002, "title": "Alien Covenant", "year": "2017"},
            ],
        }
    ],
    "directors": [
        {
            "name": "Christopher Nolan",
            "missing": [
                {"tmdb": 2001, "title": "Following",  "year": "1998"},
                {"tmdb": 2002, "title": "Insomnia",   "year": "2002"},
            ],
        }
    ],
    "actors": [
        {
            "name": "Tom Hanks",
            "missing": [
                {"tmdb": 3001, "title": "Cast Away",    "year": "2000"},
                {"tmdb": 3002, "title": "Philadelphia", "year": "1993"},
            ],
        }
    ],
    "classics":    [{"tmdb": 4001, "title": "2001: A Space Odyssey"}, {"tmdb": 4002, "title": "Metropolis"}],
    "suggestions": [{"tmdb": 5001, "title": "Blade Runner"},          {"tmdb": 5002, "title": "Akira"}],
    "wishlist":    [{"tmdb": 9001, "title": "Kept Movie"}],
    "generated_at": "2024-01-01T00:00:00Z",
}

_OVERRIDES_IGNORING = {
    "ignore_movies":      [1001, 2001, 3001, 4001, 5001],
    "ignore_movies_meta": {},
    "ignore_franchises":  [],
    "ignore_directors":   [],
    "ignore_actors":      [],
    "wishlist_movies":    [9001],
    "rec_fetched_ids":    [],
    "letterboxd_urls":    [],
}

_OVERRIDES_EMPTY = {
    **_OVERRIDES_IGNORING,
    "ignore_movies": [],
}


def _make_client(overrides: dict):
    from app.routers import scan as scan_mod
    app = FastAPI()
    app.include_router(scan_mod.router)

    with patch("app.routers.scan.is_configured", return_value=True), \
         patch("app.routers.scan.read_results",  return_value=copy.deepcopy(_RESULTS)), \
         patch("app.routers.scan.scan_state",    {"running": False}), \
         patch("app.routers.scan._load_overrides", return_value=overrides), \
         patch("app.routers.scan.OVERRIDES_FILE", "/fake/overrides.json"):
        client = TestClient(app)
        response = client.get("/api/results")
        return response.json()


# ---------------------------------------------------------------------------
# /api/results — ignore filtering
# ---------------------------------------------------------------------------

class TestResultsIgnoreFilter:

    def test_ignored_movies_removed_from_classics(self):
        data = _make_client(_OVERRIDES_IGNORING)
        ids = [m["tmdb"] for m in data["classics"]]
        assert 4001 not in ids      # ignored
        assert 4002 in ids          # kept

    def test_ignored_movies_removed_from_suggestions(self):
        data = _make_client(_OVERRIDES_IGNORING)
        ids = [m["tmdb"] for m in data["suggestions"]]
        assert 5001 not in ids
        assert 5002 in ids

    def test_ignored_movies_removed_from_franchise_missing(self):
        data = _make_client(_OVERRIDES_IGNORING)
        missing = data["franchises"][0]["missing"]
        ids = [m["tmdb"] for m in missing]
        assert 1001 not in ids      # ignored
        assert 1002 in ids          # kept

    def test_ignored_movies_removed_from_director_missing(self):
        data = _make_client(_OVERRIDES_IGNORING)
        missing = data["directors"][0]["missing"]
        ids = [m["tmdb"] for m in missing]
        assert 2001 not in ids
        assert 2002 in ids

    def test_ignored_movies_removed_from_actor_missing(self):
        data = _make_client(_OVERRIDES_IGNORING)
        missing = data["actors"][0]["missing"]
        ids = [m["tmdb"] for m in missing]
        assert 3001 not in ids
        assert 3002 in ids

    def test_wishlist_untouched_by_ignore_filter(self):
        """Wishlist movies should never be stripped even if their TMDB ID happened
        to be in ignore_movies (edge case — shouldn't happen in practice)."""
        # 9001 is in wishlist_movies but NOT in ignore_movies, so it should appear
        data = _make_client(_OVERRIDES_IGNORING)
        ids = [m["tmdb"] for m in data["wishlist"]]
        assert 9001 in ids

    def test_no_filtering_when_ignore_list_empty(self):
        data = _make_client(_OVERRIDES_EMPTY)
        assert len(data["classics"])    == 2
        assert len(data["suggestions"]) == 2
        assert len(data["franchises"][0]["missing"]) == 2
        assert len(data["directors"][0]["missing"])  == 2
        assert len(data["actors"][0]["missing"])     == 2


# ---------------------------------------------------------------------------
# /api/search — ignore filtering
# ---------------------------------------------------------------------------

class TestSearchIgnoreFilter:

    def _search(self, q: str, overrides: dict):
        from app.routers import scan as scan_mod
        app = FastAPI()
        app.include_router(scan_mod.router)
        with patch("app.routers.scan.is_configured", return_value=True), \
             patch("app.routers.scan.read_results",  return_value=copy.deepcopy(_RESULTS)), \
             patch("app.routers.scan.scan_state",    {"running": False}), \
             patch("app.routers.scan._load_overrides", return_value=overrides), \
             patch("app.routers.scan.OVERRIDES_FILE", "/fake/overrides.json"):
            client = TestClient(app)
            return client.get(f"/api/search?q={q}").json()

    def test_ignored_movie_not_in_search_results(self):
        data = self._search("Alien Romulus", _OVERRIDES_IGNORING)
        ids  = [r["tmdb"] for r in data["results"]]
        assert 1001 not in ids

    def test_non_ignored_movie_still_in_search_results(self):
        data = self._search("Alien Covenant", _OVERRIDES_IGNORING)
        ids  = [r["tmdb"] for r in data["results"]]
        assert 1002 in ids

    def test_search_returns_results_when_ignore_list_empty(self):
        data = self._search("Alien", _OVERRIDES_EMPTY)
        ids  = [r["tmdb"] for r in data["results"]]
        assert 1001 in ids
        assert 1002 in ids
