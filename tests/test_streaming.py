"""
Unit tests for app/routers/streaming.py
Covers: _parse_providers, get_streaming (cache hit, cache miss, no TMDB key,
        missing country, empty providers).
"""
import os
import sys
import time
import types
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub requests before app modules are imported
import types as _types
_req = _types.ModuleType("requests")
_req.get  = MagicMock()
_req.exceptions = types.SimpleNamespace(
    ConnectionError=ConnectionError,
    Timeout=TimeoutError,
    RequestException=Exception,
)
_req.utils = types.SimpleNamespace(quote=lambda s, **kw: s)
sys.modules.setdefault("requests", _req)

from app.routers.streaming import _parse_providers, get_streaming, _cache, _CACHE_TTL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_PROVIDERS = [
    {"provider_name": "Netflix",      "logo_path": "/netflix.jpg",  "provider_id": 8,  "display_priority": 1},
    {"provider_name": "Amazon Prime", "logo_path": "/prime.jpg",    "provider_id": 9,  "display_priority": 2},
    {"provider_name": "Disney+",      "logo_path": "/disney.jpg",   "provider_id": 337,"display_priority": 3},
]

SAMPLE_WATCH_PROVIDERS_RESPONSE = {
    "id": 603,
    "results": {
        "US": {
            "link": "https://www.justwatch.com/us/movie/the-matrix",
            "flatrate": SAMPLE_PROVIDERS[:2],
            "rent":     [SAMPLE_PROVIDERS[2]],
            "buy":      [],
        }
    }
}


def _make_tmdb_mock(response: dict):
    m = MagicMock()
    m.watch_providers.return_value = response
    return m


# ---------------------------------------------------------------------------
# _parse_providers
# ---------------------------------------------------------------------------

class TestParseProviders(unittest.TestCase):

    def test_returns_correct_fields(self):
        result = _parse_providers(SAMPLE_PROVIDERS[:1], "flatrate")
        self.assertEqual(len(result), 1)
        p = result[0]
        self.assertEqual(p["name"], "Netflix")
        self.assertEqual(p["type"], "flatrate")
        self.assertEqual(p["id"], 8)
        self.assertIn("netflix.jpg", p["logo"])

    def test_sorted_by_display_priority(self):
        shuffled = [SAMPLE_PROVIDERS[2], SAMPLE_PROVIDERS[0], SAMPLE_PROVIDERS[1]]
        result = _parse_providers(shuffled, "flatrate")
        self.assertEqual(result[0]["name"], "Netflix")     # priority 1
        self.assertEqual(result[1]["name"], "Amazon Prime") # priority 2
        self.assertEqual(result[2]["name"], "Disney+")     # priority 3

    def test_empty_list_returns_empty(self):
        self.assertEqual(_parse_providers([], "flatrate"), [])

    def test_none_list_returns_empty(self):
        self.assertEqual(_parse_providers(None, "flatrate"), [])

    def test_missing_logo_returns_none(self):
        raw = [{"provider_name": "TestSvc", "provider_id": 1, "display_priority": 1}]
        result = _parse_providers(raw, "flatrate")
        self.assertIsNone(result[0]["logo"])


# ---------------------------------------------------------------------------
# get_streaming
# ---------------------------------------------------------------------------

class TestGetStreaming(unittest.TestCase):

    def setUp(self):
        # Clear module-level cache before each test
        _cache.clear()

    def _mock_config(self, api_key="test-key", country="US"):
        return {"TMDB": {"TMDB_API_KEY": api_key}, "STREAMING": {"STREAMING_COUNTRY": country}}

    def test_returns_error_when_tmdb_not_configured(self):
        with patch("app.routers.streaming.load_config", return_value={"TMDB": {"TMDB_API_KEY": ""}}):
            result = get_streaming(603)
        self.assertFalse(result["ok"])
        self.assertIn("TMDB", result["error"])

    def test_returns_providers_for_configured_country(self):
        with patch("app.routers.streaming.load_config", return_value=self._mock_config()), \
             patch("app.routers.streaming.TMDB", return_value=_make_tmdb_mock(SAMPLE_WATCH_PROVIDERS_RESPONSE)):
            result = get_streaming(603)

        self.assertTrue(result["ok"])
        self.assertEqual(result["country"], "US")
        self.assertIn("justwatch.com", result["link"])

        flatrate = [p for p in result["providers"] if p["type"] == "flatrate"]
        self.assertEqual(len(flatrate), 2)
        names = {p["name"] for p in flatrate}
        self.assertIn("Netflix", names)
        self.assertIn("Amazon Prime", names)

    def test_country_with_no_data_returns_empty_providers(self):
        with patch("app.routers.streaming.load_config", return_value=self._mock_config(country="ZZ")), \
             patch("app.routers.streaming.TMDB", return_value=_make_tmdb_mock(SAMPLE_WATCH_PROVIDERS_RESPONSE)):
            result = get_streaming(603)

        self.assertTrue(result["ok"])
        self.assertEqual(result["providers"], [])
        self.assertEqual(result["link"], "")

    def test_result_is_cached(self):
        mock_tmdb = _make_tmdb_mock(SAMPLE_WATCH_PROVIDERS_RESPONSE)
        with patch("app.routers.streaming.load_config", return_value=self._mock_config()), \
             patch("app.routers.streaming.TMDB", return_value=mock_tmdb):
            get_streaming(603)
            get_streaming(603)

        # TMDB should only be instantiated once (second call served from cache)
        self.assertEqual(mock_tmdb.watch_providers.call_count, 1)

    def test_cache_expires_after_ttl(self):
        mock_tmdb = _make_tmdb_mock(SAMPLE_WATCH_PROVIDERS_RESPONSE)
        with patch("app.routers.streaming.load_config", return_value=self._mock_config()), \
             patch("app.routers.streaming.TMDB", return_value=mock_tmdb):
            get_streaming(603)
            # Manually expire the cache
            for key in _cache:
                _cache[key]["ts"] = time.time() - _CACHE_TTL - 1
            get_streaming(603)

        self.assertEqual(mock_tmdb.watch_providers.call_count, 2)

    def test_empty_tmdb_response_returns_ok_with_no_providers(self):
        with patch("app.routers.streaming.load_config", return_value=self._mock_config()), \
             patch("app.routers.streaming.TMDB", return_value=_make_tmdb_mock({})):
            result = get_streaming(603)

        self.assertTrue(result["ok"])
        self.assertEqual(result["providers"], [])

    def test_rent_providers_capped_at_three(self):
        many_rent = [
            {"provider_name": f"RentSvc{i}", "logo_path": f"/{i}.jpg", "provider_id": i, "display_priority": i}
            for i in range(1, 8)
        ]
        response = {"id": 603, "results": {"US": {"link": "", "rent": many_rent}}}
        with patch("app.routers.streaming.load_config", return_value=self._mock_config()), \
             patch("app.routers.streaming.TMDB", return_value=_make_tmdb_mock(response)):
            result = get_streaming(603)

        rent = [p for p in result["providers"] if p["type"] == "rent"]
        self.assertLessEqual(len(rent), 3)


if __name__ == "__main__":
    unittest.main()
