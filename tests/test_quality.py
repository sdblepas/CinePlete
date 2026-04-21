"""
Unit tests for app/routers/quality.py
Covers: _resolution, _quality_name, _poster_url, _fetch_radarr_movies,
        get_quality_upgrades (Radarr disabled, no file, below/at/above 4K,
        already in Radarr 4K, Radarr unreachable, cache behaviour).
"""
import os
import sys
import time
import types
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub requests before app modules are imported
_req = types.ModuleType("requests")
_req.exceptions = types.SimpleNamespace(
    ConnectionError=ConnectionError,
    Timeout=TimeoutError,
    RequestException=Exception,
)
_req.utils = types.SimpleNamespace(quote=lambda s, **kw: s)

_mock_get = MagicMock()
_req.get = _mock_get
sys.modules.setdefault("requests", _req)

import requests as _requests_mod
_requests_mod.get = _mock_get

from app.routers.quality import (
    _resolution,
    _quality_name,
    _poster_url,
    get_quality_upgrades,
    refresh_quality_cache,
    _cache,
    _CACHE_TTL,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _movie(tmdb_id=603, title="The Matrix", year=1999,
           resolution=720, quality_name="WEBDL-720p", has_file=True):
    """Build a minimal Radarr movie dict."""
    base = {
        "tmdbId": tmdb_id,
        "title":  title,
        "year":   year,
        "hasFile": has_file,
        "images": [{"coverType": "poster", "remoteUrl": f"https://example.com/{tmdb_id}.jpg"}],
        "ratings": {"tmdb": {"value": 7.5}},
    }
    if has_file:
        base["movieFile"] = {
            "quality": {
                "quality": {
                    "name":       quality_name,
                    "resolution": resolution,
                }
            }
        }
    return base


def _make_response(movies, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = movies
    return r


BASE_CFG = {
    "RADARR": {
        "RADARR_ENABLED":    True,
        "RADARR_URL":        "http://radarr:7878",
        "RADARR_API_KEY":    "key",
    },
    "RADARR_4K": {
        "RADARR_4K_ENABLED": False,
        "RADARR_4K_URL":     "",
        "RADARR_4K_API_KEY": "",
    },
}


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------

class TestHelpers(unittest.TestCase):

    def test_resolution_with_file(self):
        self.assertEqual(_resolution(_movie(resolution=1080)), 1080)

    def test_resolution_4k(self):
        self.assertEqual(_resolution(_movie(resolution=2160, quality_name="Bluray-2160p")), 2160)

    def test_resolution_no_file(self):
        self.assertEqual(_resolution(_movie(has_file=False)), 0)

    def test_resolution_missing_key(self):
        self.assertEqual(_resolution({"hasFile": True, "movieFile": {}}), 0)

    def test_quality_name(self):
        self.assertEqual(_quality_name(_movie()), "WEBDL-720p")

    def test_quality_name_no_file(self):
        self.assertEqual(_quality_name({"hasFile": False}), "Unknown")

    def test_poster_url_found(self):
        url = _poster_url(_movie())
        self.assertIn("example.com", url)

    def test_poster_url_not_found(self):
        self.assertIsNone(_poster_url({"images": []}))

    def test_poster_url_wrong_type(self):
        m = {"images": [{"coverType": "fanart", "remoteUrl": "http://x.jpg"}]}
        self.assertIsNone(_poster_url(m))


# ---------------------------------------------------------------------------
# get_quality_upgrades
# ---------------------------------------------------------------------------

class TestGetQualityUpgrades(unittest.TestCase):

    def setUp(self):
        _cache["data"]       = None
        _cache["ts"]         = 0.0
        _mock_get.reset_mock()
        _mock_get.side_effect = None   # reset_mock() doesn't clear side_effect by default

    def test_returns_error_when_radarr_disabled(self):
        cfg = dict(BASE_CFG)
        cfg["RADARR"] = {**BASE_CFG["RADARR"], "RADARR_ENABLED": False}
        with patch("app.routers.quality.load_config", return_value=cfg):
            result = get_quality_upgrades()
        self.assertFalse(result["ok"])
        self.assertIn("Radarr not enabled", result["error"])

    def test_returns_error_when_radarr_unreachable(self):
        _mock_get.return_value = _make_response([], status=500)
        with patch("app.routers.quality.load_config", return_value=BASE_CFG):
            result = get_quality_upgrades()
        self.assertFalse(result["ok"])

    def test_filters_movies_without_files(self):
        movies = [_movie(tmdb_id=1, has_file=False), _movie(tmdb_id=2, has_file=True)]
        _mock_get.return_value = _make_response(movies)
        with patch("app.routers.quality.load_config", return_value=BASE_CFG):
            result = get_quality_upgrades()
        ids = {m["tmdb"] for m in result["movies"]}
        self.assertNotIn(1, ids)   # no file → excluded
        self.assertIn(2, ids)

    def test_filters_out_above_720p_movies(self):
        """Only 720p-or-lower movies are upgrade candidates; 1080p and 4K are excluded."""
        movies = [
            _movie(tmdb_id=1, resolution=720),
            _movie(tmdb_id=2, resolution=1080, quality_name="Bluray-1080p"),
            _movie(tmdb_id=3, resolution=2160, quality_name="Bluray-2160p"),
        ]
        _mock_get.return_value = _make_response(movies)
        with patch("app.routers.quality.load_config", return_value=BASE_CFG):
            result = get_quality_upgrades()
        ids = {m["tmdb"] for m in result["movies"]}
        self.assertIn(1, ids)       # 720p → included
        self.assertNotIn(2, ids)    # 1080p → excluded
        self.assertNotIn(3, ids)    # 4K → excluded

    def test_excludes_movies_already_in_radarr_4k(self):
        primary = [_movie(tmdb_id=603, resolution=720), _movie(tmdb_id=680, resolution=720)]
        # 603 is already in Radarr 4K
        radarr4k = [{"tmdbId": 603, "hasFile": False, "images": [], "ratings": {}}]

        cfg = {
            "RADARR": BASE_CFG["RADARR"],
            "RADARR_4K": {
                "RADARR_4K_ENABLED": True,
                "RADARR_4K_URL":     "http://radarr4k:7879",
                "RADARR_4K_API_KEY": "key4k",
            },
        }
        _mock_get.side_effect = [
            _make_response(primary),   # primary Radarr
            _make_response(radarr4k),  # Radarr 4K
        ]
        with patch("app.routers.quality.load_config", return_value=cfg):
            result = get_quality_upgrades()

        ids = {m["tmdb"] for m in result["movies"]}
        self.assertNotIn(603, ids)  # in Radarr 4K → skipped
        self.assertIn(680, ids)

    def test_results_sorted_by_title(self):
        movies = [
            _movie(tmdb_id=1, title="Zodiac"),
            _movie(tmdb_id=2, title="Alien"),
            _movie(tmdb_id=3, title="Matrix"),
        ]
        _mock_get.return_value = _make_response(movies)
        with patch("app.routers.quality.load_config", return_value=BASE_CFG):
            result = get_quality_upgrades()
        titles = [m["title"] for m in result["movies"]]
        self.assertEqual(titles, sorted(titles, key=str.lower))

    def test_result_is_cached(self):
        _mock_get.return_value = _make_response([_movie()])
        with patch("app.routers.quality.load_config", return_value=BASE_CFG):
            get_quality_upgrades()
            get_quality_upgrades()
        # Radarr should only be called once
        self.assertEqual(_mock_get.call_count, 1)

    def test_cache_busted_after_refresh(self):
        _mock_get.return_value = _make_response([_movie()])
        with patch("app.routers.quality.load_config", return_value=BASE_CFG):
            get_quality_upgrades()
            refresh_quality_cache()
            get_quality_upgrades()
        self.assertEqual(_mock_get.call_count, 2)

    def test_count_matches_movies_length(self):
        movies = [_movie(tmdb_id=i) for i in range(1, 4)]
        _mock_get.return_value = _make_response(movies)
        with patch("app.routers.quality.load_config", return_value=BASE_CFG):
            result = get_quality_upgrades()
        self.assertEqual(result["count"], len(result["movies"]))

    def test_movie_fields_present(self):
        _mock_get.return_value = _make_response([_movie()])
        with patch("app.routers.quality.load_config", return_value=BASE_CFG):
            result = get_quality_upgrades()
        m = result["movies"][0]
        for field in ("tmdb", "title", "year", "poster", "rating", "current_quality", "resolution"):
            self.assertIn(field, m, f"Missing field: {field}")


# ---------------------------------------------------------------------------
# refresh_quality_cache
# ---------------------------------------------------------------------------

class TestRefreshQualityCache(unittest.TestCase):

    def test_refresh_returns_ok(self):
        result = refresh_quality_cache()
        self.assertTrue(result["ok"])

    def test_refresh_resets_cache_timestamp(self):
        _cache["ts"] = time.time()
        refresh_quality_cache()
        self.assertEqual(_cache["ts"], 0.0)


if __name__ == "__main__":
    unittest.main()
