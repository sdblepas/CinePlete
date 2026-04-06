"""
Tests for app/scanner.py
Covers: _set_step, load_snapshot, save_snapshot, read_results, write_results,
        _analyze_collections, _analyze_directors, _build_classics,
        _build_suggestions, _analyze_actors, _build_wishlist, _calculate_scores
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub out `requests` before any app modules are imported, since the test
# environment may have a broken certifi installation.
import types
_requests_stub = types.ModuleType("requests")
_requests_stub.get = MagicMock()
_requests_stub.exceptions = types.SimpleNamespace(
    ConnectionError=ConnectionError,
    Timeout=TimeoutError,
)
_requests_stub.utils = types.SimpleNamespace(quote=lambda s, **kw: s)
sys.modules.setdefault("requests", _requests_stub)

import app.scanner as scanner
from app.scanner import (
    _analyze_actors,
    _analyze_collections,
    _analyze_directors,
    _build_classics,
    _build_suggestions,
    _build_wishlist,
    _calculate_scores,
    _set_step,
    load_snapshot,
    read_results,
    save_snapshot,
    write_results,
    scan_state,
    STEPS,
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _make_tmdb():
    """Return a MagicMock that mimics the TMDB client interface."""
    tmdb = MagicMock()
    tmdb.movie.return_value = {}
    tmdb.collection.return_value = {}
    tmdb.search_person.return_value = {}
    tmdb.person_credits.return_value = {}
    tmdb.top_rated.return_value = {}
    tmdb.recommendations.return_value = {}
    tmdb.poster_url.return_value = None
    return tmdb


def _movie(mid, title="Movie", release="2000-01-01", votes=1000, rating=7.5,
           popularity=10.0, collection=None, genres=None):
    m = {
        "id": mid,
        "title": title,
        "release_date": release,
        "vote_count": votes,
        "vote_average": rating,
        "popularity": popularity,
        "poster_path": None,
        "overview": "",
        "genre_ids": [],
        "genres": genres or [],
    }
    if collection:
        m["belongs_to_collection"] = collection
    return m


# ─────────────────────────────────────────────
# TestSetStep
# ─────────────────────────────────────────────

class TestSetStep(unittest.TestCase):

    def test_updates_step_name(self):
        _set_step(0)
        assert scan_state["step"] == STEPS[0]

    def test_step_index_is_one_based(self):
        _set_step(0)
        assert scan_state["step_index"] == 1
        _set_step(2)
        assert scan_state["step_index"] == 3

    def test_detail_set(self):
        _set_step(1, "some detail")
        assert scan_state["detail"] == "some detail"

    def test_detail_empty_by_default(self):
        _set_step(0)
        assert scan_state["detail"] == ""

    def test_all_steps_accessible(self):
        for i in range(len(STEPS)):
            _set_step(i)
            assert scan_state["step"] == STEPS[i]
            assert scan_state["step_index"] == i + 1


# ─────────────────────────────────────────────
# TestLoadSnapshot
# ─────────────────────────────────────────────

class TestLoadSnapshot(unittest.TestCase):

    def test_returns_empty_set_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(scanner, "SNAPSHOT_FILE", os.path.join(tmpdir, "missing.json")):
                result = load_snapshot()
        assert result == set()

    def test_returns_correct_ids_from_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = os.path.join(tmpdir, "snap.json")
            with open(snap, "w") as f:
                json.dump({"plex_ids": [1, 2, 3]}, f)
            with patch.object(scanner, "SNAPSHOT_FILE", snap):
                result = load_snapshot()
        assert result == {1, 2, 3}

    def test_returns_empty_set_on_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = os.path.join(tmpdir, "snap.json")
            with open(snap, "w") as f:
                f.write("not valid json {{{{")
            with patch.object(scanner, "SNAPSHOT_FILE", snap):
                result = load_snapshot()
        assert result == set()

    def test_returns_empty_set_on_missing_plex_ids_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = os.path.join(tmpdir, "snap.json")
            with open(snap, "w") as f:
                json.dump({"other_key": []}, f)
            with patch.object(scanner, "SNAPSHOT_FILE", snap):
                result = load_snapshot()
        assert result == set()


# ─────────────────────────────────────────────
# TestSaveSnapshot
# ─────────────────────────────────────────────

class TestSaveSnapshot(unittest.TestCase):

    def test_writes_correct_json_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = os.path.join(tmpdir, "snap.json")
            with patch.object(scanner, "SNAPSHOT_FILE", snap), \
                 patch.object(scanner, "DATA_DIR", tmpdir):
                save_snapshot({10: "Movie A", 20: "Movie B"})
            with open(snap) as f:
                data = json.load(f)
        assert "plex_ids" in data
        assert "saved_at" in data
        assert set(data["plex_ids"]) == {10, 20}

    def test_creates_data_dir_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "newdir")
            snap   = os.path.join(subdir, "snap.json")
            with patch.object(scanner, "SNAPSHOT_FILE", snap), \
                 patch.object(scanner, "DATA_DIR", subdir):
                save_snapshot({1: "A"})
            assert os.path.isfile(snap)

    def test_logs_warning_on_oserror(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = os.path.join(tmpdir, "snap.json")
            with patch.object(scanner, "SNAPSHOT_FILE", snap), \
                 patch.object(scanner, "DATA_DIR", tmpdir), \
                 patch("builtins.open", side_effect=OSError("disk full")), \
                 patch.object(scanner.log, "warning") as mock_warn:
                save_snapshot({1: "A"})   # must not raise
            mock_warn.assert_called_once()
            assert "Could not save scan snapshot" in mock_warn.call_args[0][0]


# ─────────────────────────────────────────────
# TestReadResults
# ─────────────────────────────────────────────

class TestReadResults(unittest.TestCase):

    def test_returns_none_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(scanner, "RESULTS_FILE", os.path.join(tmpdir, "missing.json")):
                result = read_results()
        assert result is None

    def test_returns_dict_from_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rf = os.path.join(tmpdir, "results.json")
            with open(rf, "w") as f:
                json.dump({"key": "value"}, f)
            with patch.object(scanner, "RESULTS_FILE", rf):
                result = read_results()
        assert result == {"key": "value"}

    def test_returns_none_on_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rf = os.path.join(tmpdir, "results.json")
            with open(rf, "w") as f:
                f.write("{{bad json")
            with patch.object(scanner, "RESULTS_FILE", rf):
                result = read_results()
        assert result is None


# ─────────────────────────────────────────────
# TestWriteResults
# ─────────────────────────────────────────────

class TestWriteResults(unittest.TestCase):

    def test_creates_data_dir_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "newdir")
            rf     = os.path.join(subdir, "results.json")
            with patch.object(scanner, "RESULTS_FILE", rf), \
                 patch.object(scanner, "DATA_DIR", subdir):
                write_results({"test": True})
            assert os.path.isfile(rf)

    def test_atomic_write_via_tmp_file(self):
        """write_results should use a .tmp file then os.replace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rf  = os.path.join(tmpdir, "results.json")
            tmp = rf + ".tmp"
            with patch.object(scanner, "RESULTS_FILE", rf), \
                 patch.object(scanner, "DATA_DIR", tmpdir), \
                 patch("os.replace", wraps=os.replace) as mock_replace:
                write_results({"key": "val"})
            mock_replace.assert_called_once_with(tmp, rf)

    def test_written_content_is_correct(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rf = os.path.join(tmpdir, "results.json")
            with patch.object(scanner, "RESULTS_FILE", rf), \
                 patch.object(scanner, "DATA_DIR", tmpdir):
                write_results({"answer": 42})
            with open(rf) as f:
                data = json.load(f)
        assert data == {"answer": 42}


# ─────────────────────────────────────────────
# TestAnalyzeCollections
# ─────────────────────────────────────────────

class TestAnalyzeCollections(unittest.TestCase):

    def _run(self, plex_ids, tmdb, ignore_franchises=None, ignore_movies=None, wishlist_movies=None):
        return _analyze_collections(
            plex_ids,
            tmdb,
            ignore_franchises or set(),
            ignore_movies or set(),
            wishlist_movies or set(),
        )

    def test_movie_with_collection_appears_in_franchises(self):
        tmdb = _make_tmdb()
        col  = {"id": 10, "name": "Test Collection"}
        tmdb.movie.side_effect = lambda mid: _movie(mid, collection=col) if mid == 1 else {}
        tmdb.collection.return_value = {
            "parts": [
                {"id": 1, "title": "Part 1", "release_date": "2000-01-01"},
                {"id": 2, "title": "Part 2", "release_date": "2001-01-01"},
            ]
        }
        franchises, completion = self._run({1: "Part 1"}, tmdb)
        assert len(franchises) == 1
        assert franchises[0]["name"] == "Test Collection"

    def test_movie_without_collection_not_in_franchises(self):
        tmdb = _make_tmdb()
        tmdb.movie.return_value = _movie(1)
        franchises, _ = self._run({1: "Movie"}, tmdb)
        assert franchises == []

    def test_ignored_franchise_is_skipped(self):
        tmdb = _make_tmdb()
        col  = {"id": 10, "name": "Ignore Me"}
        tmdb.movie.side_effect = lambda mid: _movie(mid, collection=col)
        franchises, _ = self._run({1: "Movie"}, tmdb, ignore_franchises={"Ignore Me"})
        assert franchises == []

    def test_missing_movie_appears_in_missing_list(self):
        tmdb = _make_tmdb()
        col  = {"id": 10, "name": "Col"}
        tmdb.movie.side_effect = lambda mid: _movie(mid, collection=col) if mid == 1 else {}
        tmdb.collection.return_value = {
            "parts": [
                {"id": 1, "title": "Part 1", "release_date": "2000-01-01"},
                {"id": 2, "title": "Part 2", "release_date": "2001-01-01"},
            ]
        }
        franchises, _ = self._run({1: "Part 1"}, tmdb)
        assert len(franchises[0]["missing"]) == 1
        assert franchises[0]["missing"][0]["tmdb"] == 2

    def test_already_owned_movie_not_in_missing(self):
        tmdb = _make_tmdb()
        col  = {"id": 10, "name": "Col"}
        tmdb.movie.side_effect = lambda mid: _movie(mid, collection=col)
        tmdb.collection.return_value = {
            "parts": [
                {"id": 1, "title": "Part 1", "release_date": "2000-01-01"},
                {"id": 2, "title": "Part 2", "release_date": "2001-01-01"},
            ]
        }
        franchises, _ = self._run({1: "Part 1", 2: "Part 2"}, tmdb)
        assert franchises[0]["missing"] == []

    def test_future_release_not_in_missing(self):
        tmdb = _make_tmdb()
        col  = {"id": 10, "name": "Col"}
        tmdb.movie.side_effect = lambda mid: _movie(mid, collection=col) if mid == 1 else {}
        tmdb.collection.return_value = {
            "parts": [
                {"id": 1, "title": "Part 1", "release_date": "2000-01-01"},
                {"id": 2, "title": "Part 2", "release_date": "2099-01-01"},
            ]
        }
        franchises, _ = self._run({1: "Part 1"}, tmdb)
        assert franchises[0]["missing"] == []


# ─────────────────────────────────────────────
# TestAnalyzeDirectors
# ─────────────────────────────────────────────

class TestAnalyzeDirectors(unittest.TestCase):

    def _run(self, directors_map, plex_ids, tmdb, ignore_directors=None, ignore_movies=None, wishlist_movies=None):
        return _analyze_directors(
            directors_map,
            plex_ids,
            tmdb,
            ignore_directors or set(),
            ignore_movies or set(),
            wishlist_movies or set(),
        )

    def test_director_in_ignore_list_skipped(self):
        tmdb = _make_tmdb()
        directors, total = self._run({"Kubrick": [1]}, {1: "Film"}, tmdb, ignore_directors={"Kubrick"})
        assert directors == []
        assert total == 0

    def test_director_with_missing_films_appears(self):
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {"results": [{"id": 99}]}
        tmdb.person_credits.return_value = {
            "crew": [{"id": 200, "job": "Director", "title": "Missing Film", "release_date": "2000-01-01"}]
        }
        tmdb.poster_url.return_value = None
        directors, total = self._run({"Kubrick": [1]}, {1: "Film"}, tmdb)
        assert len(directors) == 1
        assert directors[0]["name"] == "Kubrick"
        assert total == 1

    def test_director_with_all_films_owned_not_in_directors(self):
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {"results": [{"id": 99}]}
        tmdb.person_credits.return_value = {
            "crew": [{"id": 1, "job": "Director", "title": "Owned", "release_date": "2000-01-01"}]
        }
        directors, total = self._run({"Kubrick": [1]}, {1: "Owned"}, tmdb)
        assert directors == []
        assert total == 0

    def test_returns_correct_director_missing_total(self):
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {"results": [{"id": 99}]}
        tmdb.person_credits.return_value = {
            "crew": [
                {"id": 200, "job": "Director", "title": "Film A", "release_date": "2000-01-01"},
                {"id": 201, "job": "Director", "title": "Film B", "release_date": "2001-01-01"},
                {"id": 202, "job": "Actor",    "title": "Film C", "release_date": "2002-01-01"},
            ]
        }
        tmdb.poster_url.return_value = None
        directors, total = self._run({"Kubrick": [1]}, {}, tmdb)
        assert total == 2   # only director credits


# ─────────────────────────────────────────────
# TestBuildClassics
# ─────────────────────────────────────────────

class TestBuildClassics(unittest.TestCase):

    def _run(self, tmdb, plex_ids=None, ignore_movies=None, wishlist_movies=None,
             pages=1, min_votes=100, min_rating=7.0, max_results=10):
        return _build_classics(
            tmdb,
            plex_ids or {},
            ignore_movies or set(),
            wishlist_movies or set(),
            pages, min_votes, min_rating, max_results,
        )

    def test_movie_below_min_votes_excluded(self):
        tmdb = _make_tmdb()
        tmdb.top_rated.return_value = {
            "results": [{"id": 1, "title": "Low", "vote_count": 50, "vote_average": 9.0, "release_date": "2000-01-01"}]
        }
        result = self._run(tmdb, min_votes=100)
        assert result == []

    def test_movie_below_min_rating_excluded(self):
        tmdb = _make_tmdb()
        tmdb.top_rated.return_value = {
            "results": [{"id": 1, "title": "OK", "vote_count": 5000, "vote_average": 6.0, "release_date": "2000-01-01"}]
        }
        result = self._run(tmdb, min_votes=100, min_rating=7.0)
        assert result == []

    def test_movie_already_in_library_excluded(self):
        tmdb = _make_tmdb()
        tmdb.top_rated.return_value = {
            "results": [{"id": 1, "title": "Owned", "vote_count": 5000, "vote_average": 9.0, "release_date": "2000-01-01"}]
        }
        result = self._run(tmdb, plex_ids={1: "Owned"})
        assert result == []

    def test_ignored_movie_excluded(self):
        tmdb = _make_tmdb()
        tmdb.top_rated.return_value = {
            "results": [{"id": 1, "title": "Ignored", "vote_count": 5000, "vote_average": 9.0, "release_date": "2000-01-01"}]
        }
        result = self._run(tmdb, ignore_movies={1})
        assert result == []

    def test_valid_movie_included_and_sorted(self):
        tmdb = _make_tmdb()
        tmdb.top_rated.return_value = {
            "results": [
                {"id": 1, "title": "B Film", "vote_count": 5000, "vote_average": 8.0, "release_date": "2000-01-01"},
                {"id": 2, "title": "A Film", "vote_count": 9000, "vote_average": 9.0, "release_date": "2001-01-01"},
            ]
        }
        result = self._run(tmdb, min_votes=100, min_rating=7.0)
        assert len(result) == 2
        assert result[0]["tmdb"] == 2   # highest rating first
        assert result[1]["tmdb"] == 1

    def test_max_results_limit_respected(self):
        tmdb = _make_tmdb()
        tmdb.top_rated.return_value = {
            "results": [
                {"id": i, "title": f"Film {i}", "vote_count": 5000, "vote_average": 8.0, "release_date": "2000-01-01"}
                for i in range(1, 11)
            ]
        }
        result = self._run(tmdb, max_results=3)
        assert len(result) == 3


# ─────────────────────────────────────────────
# TestBuildSuggestions
# ─────────────────────────────────────────────

class TestBuildSuggestions(unittest.TestCase):

    def _run(self, plex_ids, tmdb, overrides=None, ignore_movies=None,
             wishlist_movies=None, max_results=10, min_score=2):
        with patch("app.scanner.save_json"), patch("app.scanner.OVERRIDES_FILE", "/tmp/ov.json"):
            return _build_suggestions(
                plex_ids,
                tmdb,
                overrides or {"rec_fetched_ids": []},
                ignore_movies or set(),
                wishlist_movies or set(),
                max_results,
                min_score,
            )

    def test_below_min_score_excluded(self):
        tmdb = _make_tmdb()
        # movie 99 is recommended once — below min_score=2
        tmdb.recommendations.side_effect = lambda mid: {"results": [{"id": 99}]}
        tmdb.movie.return_value = _movie(99, release="2000-01-01")
        result = self._run({1: "Film"}, tmdb, min_score=2)
        assert result == []

    def test_in_library_excluded(self):
        tmdb = _make_tmdb()
        # Both library movies recommend movie 1, but movie 1 is in library
        tmdb.recommendations.side_effect = lambda mid: {"results": [{"id": 1}]}
        tmdb.movie.return_value = _movie(1, release="2000-01-01")
        result = self._run({1: "Film", 2: "Film2"}, tmdb, min_score=1)
        assert result == []

    def test_future_release_excluded(self):
        tmdb = _make_tmdb()
        # Two library movies both recommend movie 99
        tmdb.recommendations.side_effect = lambda mid: {"results": [{"id": 99}]}
        tmdb.movie.return_value = _movie(99, release="2099-01-01")
        result = self._run({1: "A", 2: "B"}, tmdb, min_score=1)
        assert result == []

    def test_valid_suggestion_included_with_rec_score(self):
        tmdb = _make_tmdb()
        # library movie 1 recommends 99; movie 2 was scored in a previous scan
        # and its contribution is already persisted in rec_scores (new behaviour:
        # scores are never rebuilt from cached HTTP responses, only from deltas)
        tmdb.recommendations.side_effect = lambda mid: {"results": [{"id": 99}]}
        tmdb.movie.return_value = _movie(99, release="2000-01-01")
        result = self._run(
            {1: "A"}, tmdb,
            overrides={"rec_fetched_ids": [2], "rec_scores": {"99": 1}},
            min_score=2,
        )
        assert len(result) == 1
        assert result[0]["tmdb"] == 99
        assert result[0]["rec_score"] == 2

    def test_max_results_limit_respected(self):
        tmdb = _make_tmdb()
        # Two library movies both recommend movies 100-119, giving score 2 each
        def side_effect_recommendations(mid):
            return {"results": [{"id": i} for i in range(100, 120)]}
        def side_effect_movie(mid):
            return _movie(mid, release="2000-01-01")
        tmdb.recommendations.side_effect = side_effect_recommendations
        tmdb.movie.side_effect = side_effect_movie
        result = self._run({1: "A", 2: "B"}, tmdb, min_score=2, max_results=5)
        assert len(result) <= 5


# ─────────────────────────────────────────────
# TestAnalyzeActors
# ─────────────────────────────────────────────

class TestAnalyzeActors(unittest.TestCase):

    def _run(self, actors_map, plex_ids, tmdb, ignore_actors=None,
             ignore_movies=None, wishlist_movies=None, min_votes=100, max_per_actor=10):
        return _analyze_actors(
            actors_map,
            plex_ids,
            tmdb,
            ignore_actors or set(),
            ignore_movies or set(),
            wishlist_movies or set(),
            min_votes,
            max_per_actor,
        )

    def test_actor_in_ignore_list_skipped(self):
        tmdb = _make_tmdb()
        actors, total = self._run({"Tom Hanks": [1]}, {}, tmdb, ignore_actors={"Tom Hanks"})
        assert actors == []
        assert total == 0

    def test_actor_with_high_vote_missing_films_appears(self):
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {"results": [{"id": 99}]}
        tmdb.person_credits.return_value = {
            "cast": [{"id": 200, "title": "Film", "vote_count": 1000, "vote_average": 8.0,
                      "popularity": 20.0, "release_date": "2000-01-01"}]
        }
        tmdb.poster_url.return_value = None
        actors, total = self._run({"Tom Hanks": [1]}, {}, tmdb, min_votes=100)
        assert len(actors) == 1
        assert actors[0]["name"] == "Tom Hanks"
        assert total == 1

    def test_max_per_actor_limit_respected(self):
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {"results": [{"id": 99}]}
        tmdb.person_credits.return_value = {
            "cast": [
                {"id": i, "title": f"Film {i}", "vote_count": 1000, "vote_average": 8.0,
                 "popularity": 20.0, "release_date": "2000-01-01"}
                for i in range(200, 220)
            ]
        }
        tmdb.poster_url.return_value = None
        actors, total = self._run({"Tom Hanks": [1]}, {}, tmdb, min_votes=100, max_per_actor=3)
        assert len(actors[0]["missing"]) == 3

    def test_returns_correct_actor_missing_total(self):
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {"results": [{"id": 99}]}
        tmdb.person_credits.return_value = {
            "cast": [
                {"id": 200, "title": "Film A", "vote_count": 1000, "vote_average": 8.0,
                 "popularity": 10.0, "release_date": "2000-01-01"},
                {"id": 201, "title": "Film B", "vote_count": 1000, "vote_average": 7.0,
                 "popularity": 9.0, "release_date": "2001-01-01"},
            ]
        }
        tmdb.poster_url.return_value = None
        actors, total = self._run({"Actor": [1]}, {}, tmdb, min_votes=100)
        assert total == 2


# ─────────────────────────────────────────────
# TestBuildWishlist
# ─────────────────────────────────────────────

class TestBuildWishlist(unittest.TestCase):

    def test_movie_in_library_removed_from_wishlist(self):
        tmdb = _make_tmdb()
        tmdb.movie.return_value = _movie(1)

        wishlist_movies = {1, 2}
        plex_ids        = {1: "Already Owned"}
        overrides       = {"wishlist_movies": [1, 2]}

        with patch("app.scanner.remove_value") as mock_remove, \
             patch("app.scanner.save_json"):
            wishlist = _build_wishlist(wishlist_movies, plex_ids, overrides, tmdb)

        mock_remove.assert_called_once_with([1, 2], 1)

    def test_returns_wishlist_items_not_in_library(self):
        tmdb = _make_tmdb()
        tmdb.movie.side_effect = lambda mid: _movie(mid, genres=[{"id": 28}])

        wishlist_movies = {10, 20}
        plex_ids        = {}
        overrides       = {"wishlist_movies": [10, 20]}

        wishlist = _build_wishlist(wishlist_movies, plex_ids, overrides, tmdb)
        assert len(wishlist) == 2
        tmdb_ids = {w["tmdb"] for w in wishlist}
        assert tmdb_ids == {10, 20}

    def test_wishlist_item_has_wishlist_true(self):
        tmdb = _make_tmdb()
        tmdb.movie.return_value = _movie(5, genres=[{"id": 28}])

        wishlist_movies = {5}
        plex_ids        = {}
        overrides       = {"wishlist_movies": [5]}

        wishlist = _build_wishlist(wishlist_movies, plex_ids, overrides, tmdb)
        assert wishlist[0]["wishlist"] is True


# ─────────────────────────────────────────────
# TestCalculateScores
# ─────────────────────────────────────────────

class TestCalculateScores(unittest.TestCase):

    def test_franchise_score_have_over_total(self):
        fc = [{"name": "F1", "have": 1, "total": 2}]
        scores = _calculate_scores(fc, [], 0, [], 120)
        assert scores["franchise_completion_pct"] == 50.0

    def test_global_score_weighted_average(self):
        fc = [{"name": "F1", "have": 2, "total": 2}]   # franchise = 100%
        # classics empty -> classics_score = 100%
        # directors empty but director_missing_total=0 -> directors_score = 100% (no directors)
        scores = _calculate_scores(fc, [], 0, [], 120)
        assert scores["global_cinema_score"] == 100.0

    def test_empty_franchise_completion_gives_zero_franchise_score(self):
        scores = _calculate_scores([], [], 0, [], 120)
        assert scores["franchise_completion_pct"] == 0.0

    def test_returns_all_four_expected_keys(self):
        scores = _calculate_scores([], [], 0, [], 120)
        assert "franchise_completion_pct" in scores
        assert "directors_proxy_pct" in scores
        assert "classics_proxy_pct" in scores
        assert "global_cinema_score" in scores

    def test_classics_score_decreases_with_more_classics(self):
        # 60 classics out of max 120 -> classics_score = 50%
        classics = [{"title": f"Film {i}"} for i in range(60)]
        scores   = _calculate_scores([], [], 0, classics, 120)
        assert scores["classics_proxy_pct"] == 50.0

    def test_directors_score_penalized_for_missing(self):
        # 1 director with 20 missing films -> directors_score = max(0, 100 - 20/1 * 5) = max(0, 0) = 0
        directors = [{"name": "Kubrick", "missing": [{}] * 20}]
        scores    = _calculate_scores([], directors, 20, [], 120)
        assert scores["directors_proxy_pct"] == 0.0


if __name__ == "__main__":
    unittest.main()
