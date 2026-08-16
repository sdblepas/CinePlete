"""
Tests for app.scanner._resolve_person — TMDB person disambiguation.

Regression coverage for issue #98: localized (e.g. Simplified Chinese) actor
names cause TMDB's /search/person to rank an unrelated person first, so blindly
taking results[0] produced a completely wrong filmography. The resolver picks
the candidate whose credits overlap the movies we already know the person is in.
"""
import os
import sys
import types
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub `requests` before importing app modules (mirrors test_scanner.py).
_requests_stub = types.ModuleType("requests")
_requests_stub.get = MagicMock()
_requests_stub.exceptions = types.SimpleNamespace(
    ConnectionError=ConnectionError,
    Timeout=TimeoutError,
)
_requests_stub.utils = types.SimpleNamespace(quote=lambda s, **kw: s)
sys.modules.setdefault("requests", _requests_stub)

from app.scanner import _resolve_person


def _make_tmdb():
    tmdb = MagicMock()
    tmdb.search_person.return_value = {}
    tmdb.person_credits.return_value = {}
    return tmdb


class TestResolvePerson(unittest.TestCase):

    def test_picks_candidate_matching_known_movies_not_first_result(self):
        """The wrong person ranks first; the correct one overlaps known films."""
        tmdb = _make_tmdb()
        # Search returns wrong person (11) first, correct person (22) second.
        tmdb.search_person.return_value = {"results": [{"id": 11}, {"id": 22}]}

        def credits(pid):
            if pid == 11:
                return {"cast": [{"id": 9999, "title": "Unrelated"}]}
            if pid == 22:
                # Overlaps the known movie 9470 (Kung Fu).
                return {"cast": [{"id": 9470, "title": "Kung Fu"}]}
            return {}

        tmdb.person_credits.side_effect = credits

        pid, resolved = _resolve_person(tmdb, "周星驰", {9470}, "actor")
        assert pid == 22
        assert resolved["cast"][0]["id"] == 9470

    def test_prefers_largest_overlap(self):
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {"results": [{"id": 1}, {"id": 2}]}

        def credits(pid):
            if pid == 1:
                return {"cast": [{"id": 100}]}                # 1 overlap
            if pid == 2:
                return {"cast": [{"id": 100}, {"id": 200}]}   # 2 overlaps
            return {}

        tmdb.person_credits.side_effect = credits

        pid, _ = _resolve_person(tmdb, "Name", {100, 200}, "actor")
        assert pid == 2

    def test_falls_back_to_first_result_when_no_overlap(self):
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {"results": [{"id": 11}, {"id": 22}]}
        tmdb.person_credits.return_value = {"cast": [{"id": 555}]}

        pid, resolved = _resolve_person(tmdb, "Name", {9470}, "actor")
        assert pid == 11
        assert resolved == {"cast": [{"id": 555}]}

    def test_no_known_movies_keeps_first_result(self):
        """Without ground truth we don't fetch every candidate — keep first."""
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {"results": [{"id": 11}, {"id": 22}]}
        tmdb.person_credits.return_value = {"cast": []}

        pid, _ = _resolve_person(tmdb, "Name", set(), "actor")
        assert pid == 11

    def test_director_role_matches_only_director_credits(self):
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {"results": [{"id": 1}, {"id": 2}]}

        def credits(pid):
            if pid == 1:
                # Known movie 500 present but only as Actor — must NOT match.
                return {"crew": [{"id": 500, "job": "Actor"}]}
            if pid == 2:
                return {"crew": [{"id": 500, "job": "Director"}]}
            return {}

        tmdb.person_credits.side_effect = credits

        pid, _ = _resolve_person(tmdb, "Name", {500}, "director")
        assert pid == 2

    def test_empty_search_returns_none(self):
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {"results": []}
        pid, resolved = _resolve_person(tmdb, "Nobody", {1}, "actor")
        assert pid is None
        assert resolved is None

    def test_respects_max_candidates(self):
        """Only the first ``max_candidates`` results are inspected."""
        tmdb = _make_tmdb()
        tmdb.search_person.return_value = {
            "results": [{"id": i} for i in range(1, 11)]
        }
        # The correct match (id 9) sits beyond max_candidates=5.
        tmdb.person_credits.return_value = {"cast": [{"id": 42}]}

        pid, _ = _resolve_person(tmdb, "Name", {9470}, "actor", max_candidates=5)
        # No overlap within first 5 → fall back to first result.
        assert pid == 1


if __name__ == "__main__":
    unittest.main()
