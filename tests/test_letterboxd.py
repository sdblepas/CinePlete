"""
Tests for Letterboxd RSS parsing and API endpoints introduced in v2.7.

Covers:
  - _parse_films_from_html()          pure HTML extraction
  - _fetch_via_flaresolverr()         mocked HTTP
  - _fetch_letterboxd_rss() URL logic mocked HTTP
  - /api/letterboxd/urls              CRUD
  - /api/ignored                      list ignored movies
  - /api/ignore / /api/unignore       kind validation
"""
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── helpers ──────────────────────────────────────────────────────────────────

def _tmp_overrides(**extra):
    """Write a temporary overrides.json and return its path."""
    data = {
        "ignore_movies":      [],
        "ignore_movies_meta": {},
        "ignore_franchises":  [],
        "ignore_directors":   [],
        "ignore_actors":      [],
        "wishlist_movies":    [],
        "rec_fetched_ids":    [],
        "letterboxd_urls":    [],
        **extra,
    }
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


# ── _parse_films_from_html ────────────────────────────────────────────────────

class TestParseFilmsFromHtml:

    def _call(self, html):
        from app.web import _parse_films_from_html
        return _parse_films_from_html(html)

    def test_extracts_film_titles(self):
        html = '''
        <ul>
          <li><a href="https://letterboxd.com/film/taxi-driver/">Taxi Driver</a></li>
          <li><a href="https://letterboxd.com/film/goodfellas/">Goodfellas</a></li>
        </ul>
        '''
        result = self._call(html)
        titles = [r["title"] for r in result]
        assert "Taxi Driver" in titles
        assert "Goodfellas" in titles

    def test_deduplicates_by_slug(self):
        html = '''
        <a href="https://letterboxd.com/film/taxi-driver/">Taxi Driver</a>
        <a href="https://letterboxd.com/film/taxi-driver/">Taxi Driver</a>
        '''
        result = self._call(html)
        assert len(result) == 1

    def test_skips_known_non_film_links(self):
        html = '''
        <a href="https://letterboxd.com/film/goodfellas/">Goodfellas</a>
        <a href="https://letterboxd.com/film/some-list/">View the full list on Letterboxd</a>
        '''
        result = self._call(html)
        titles = [r["title"] for r in result]
        assert "Goodfellas" in titles
        assert "View the full list on Letterboxd" not in titles

    def test_returns_empty_on_no_film_links(self):
        html = "<p>No films here.</p>"
        assert self._call(html) == []

    def test_ignores_non_film_paths(self):
        html = '<a href="https://letterboxd.com/mscorsese/lists/">His lists</a>'
        assert self._call(html) == []

    def test_trims_whitespace_from_titles(self):
        html = '<a href="https://letterboxd.com/film/the-godfather/">  The Godfather  </a>'
        result = self._call(html)
        assert result[0]["title"] == "The Godfather"


# ── _fetch_via_flaresolverr ───────────────────────────────────────────────────

class TestFetchViaFlaresolverr:

    def _call(self, rss_url, fs_url):
        from app.web import _fetch_via_flaresolverr
        return _fetch_via_flaresolverr(rss_url, fs_url)

    def test_returns_content_on_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "ok",
            "solution": {"response": "<rss>content</rss>"},
        }
        with patch("requests.post", return_value=mock_resp):
            result = self._call("https://letterboxd.com/user/rss/", "http://flaresolverr:8191")
        assert result == b"<rss>content</rss>"

    def test_returns_none_on_bad_status(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "error", "message": "Cloudflare timeout"}
        with patch("requests.post", return_value=mock_resp):
            result = self._call("https://letterboxd.com/user/rss/", "http://flaresolverr:8191")
        assert result is None

    def test_returns_none_on_network_error(self):
        import requests as req
        with patch("requests.post", side_effect=req.exceptions.ConnectionError("refused")):
            result = self._call("https://letterboxd.com/user/rss/", "http://flaresolverr:8191")
        assert result is None

    def test_strips_trailing_slash_from_base_url(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok", "solution": {"response": "data"}}
        with patch("requests.post", return_value=mock_resp) as m:
            self._call("https://letterboxd.com/user/rss/", "http://flaresolverr:8191/")
        called_url = m.call_args[0][0]
        assert called_url == "http://flaresolverr:8191/v1"


# ── _fetch_letterboxd_rss URL normalisation ──────────────────────────────────

class TestFetchLetterboxdRssUrls:
    """Test that the function builds the correct RSS URL from various inputs."""

    def _captured_rss_url(self, input_url):
        """Run _fetch_letterboxd_rss and return the RSS URL it tried to fetch."""
        captured = {}
        def fake_get(url, **kwargs):
            captured["url"] = url
            r = MagicMock()
            r.status_code = 404   # abort early, we just want the URL
            return r
        with patch("requests.get", side_effect=fake_get):
            from app.web import _fetch_letterboxd_rss
            _fetch_letterboxd_rss(input_url)
        return captured.get("url")

    def test_watchlist_appends_rss(self):
        url = self._captured_rss_url("https://letterboxd.com/user/watchlist/")
        assert url == "https://letterboxd.com/user/watchlist/rss/"

    def test_named_list_appends_rss(self):
        url = self._captured_rss_url("https://letterboxd.com/user/list/my-list/")
        assert url == "https://letterboxd.com/user/list/my-list/rss/"

    def test_rss_url_kept_as_is(self):
        url = self._captured_rss_url("https://letterboxd.com/user/rss/")
        assert url == "https://letterboxd.com/user/rss/"

    def test_films_page_falls_back_to_diary(self):
        url = self._captured_rss_url("https://letterboxd.com/mscorsese/films/")
        assert url == "https://letterboxd.com/mscorsese/rss/"

    def test_rss_without_trailing_slash_normalised(self):
        url = self._captured_rss_url("https://letterboxd.com/user/rss")
        assert url == "https://letterboxd.com/user/rss/"


# ── Endpoint test helpers ─────────────────────────────────────────────────────

from fastapi.testclient import TestClient
import app.web as _web_module
from app.web import app as _app

_BASE_CFG = {
    "TMDB":        {"TMDB_API_KEY": "testkey"},
    "FLARESOLVERR":{"FLARESOLVERR_URL": ""},
    "AUTH":        {"AUTH_METHOD": "None"},
    "SERVER":      {"MEDIA_SERVER": "plex"},
}

def _client_ctx(overrides_path):
    """Context manager yielding a TestClient with OVERRIDES_FILE patched."""
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        client = TestClient(_app, raise_server_exceptions=True)
        with patch.object(_web_module, "OVERRIDES_FILE", overrides_path), \
             patch("app.web.load_config", return_value=_BASE_CFG):
            yield client

    return _ctx()


# ── /api/ignore + /api/unignore ──────────────────────────────────────────────

class TestIgnoreEndpoints:

    def test_ignore_unknown_kind_returns_error(self):
        path = _tmp_overrides()
        try:
            with _client_ctx(path) as client:
                r = client.post("/api/ignore", json={"kind": "unknown", "value": "123"})
            assert r.status_code == 200
            assert r.json()["ok"] is False
        finally:
            os.unlink(path)

    def test_ignore_none_kind_returns_error(self):
        path = _tmp_overrides()
        try:
            with _client_ctx(path) as client:
                r = client.post("/api/ignore", json={"value": "123"})
            assert r.json()["ok"] is False
        finally:
            os.unlink(path)

    def test_ignore_movie_stores_meta(self):
        path = _tmp_overrides()
        try:
            with _client_ctx(path) as client:
                r = client.post("/api/ignore", json={
                    "kind": "movie", "value": "550",
                    "title": "Fight Club", "year": "1999", "poster": "/poster.jpg",
                })
            assert r.json()["ok"] is True
            data = json.load(open(path))
            assert 550 in data["ignore_movies"]
            assert data["ignore_movies_meta"]["550"]["title"] == "Fight Club"
        finally:
            os.unlink(path)

    def test_unignore_unknown_kind_returns_error(self):
        path = _tmp_overrides()
        try:
            with _client_ctx(path) as client:
                r = client.post("/api/unignore", json={"kind": "bad", "value": "123"})
            assert r.json()["ok"] is False
        finally:
            os.unlink(path)

    def test_unignore_removes_meta(self):
        path = _tmp_overrides(
            ignore_movies=[550],
            ignore_movies_meta={"550": {"title": "Fight Club", "year": "1999", "poster": ""}},
        )
        try:
            with _client_ctx(path) as client:
                r = client.post("/api/unignore", json={"kind": "movie", "value": "550"})
            assert r.json()["ok"] is True
            data = json.load(open(path))
            assert 550 not in data["ignore_movies"]
            assert "550" not in data["ignore_movies_meta"]
        finally:
            os.unlink(path)


# ── /api/ignored ─────────────────────────────────────────────────────────────

class TestIgnoredEndpoint:

    def test_returns_empty_list(self):
        path = _tmp_overrides()
        try:
            with _client_ctx(path) as client:
                r = client.get("/api/ignored")
            assert r.json() == {"ok": True, "movies": []}
        finally:
            os.unlink(path)

    def test_returns_movies_with_meta(self):
        path = _tmp_overrides(
            ignore_movies=[550],
            ignore_movies_meta={"550": {"title": "Fight Club", "year": "1999", "poster": "/p.jpg"}},
        )
        try:
            with _client_ctx(path) as client:
                r = client.get("/api/ignored")
            movies = r.json()["movies"]
            assert len(movies) == 1
            assert movies[0]["tmdb"] == 550
            assert movies[0]["title"] == "Fight Club"
        finally:
            os.unlink(path)

    def test_falls_back_to_generic_title_when_no_meta(self):
        path = _tmp_overrides(ignore_movies=[999])
        try:
            with _client_ctx(path) as client:
                r = client.get("/api/ignored")
            movies = r.json()["movies"]
            assert movies[0]["title"] == "Movie 999"
        finally:
            os.unlink(path)


# ── /api/letterboxd/urls ─────────────────────────────────────────────────────

class TestLetterboxdUrlsCRUD:

    def test_get_urls_empty(self):
        path = _tmp_overrides()
        try:
            with _client_ctx(path) as client:
                r = client.get("/api/letterboxd/urls")
            assert r.json() == {"ok": True, "urls": []}
        finally:
            os.unlink(path)

    def test_add_valid_url(self):
        path = _tmp_overrides()
        try:
            with _client_ctx(path) as client:
                r = client.post("/api/letterboxd/urls", json={"url": "https://letterboxd.com/user/watchlist/"})
                assert r.json()["ok"] is True
                r2 = client.get("/api/letterboxd/urls")
            assert "https://letterboxd.com/user/watchlist/" in r2.json()["urls"]
        finally:
            os.unlink(path)

    def test_add_non_letterboxd_url_rejected(self):
        path = _tmp_overrides()
        try:
            with _client_ctx(path) as client:
                r = client.post("/api/letterboxd/urls", json={"url": "https://example.com/list"})
            assert r.json()["ok"] is False
        finally:
            os.unlink(path)

    def test_add_duplicate_url_not_stored_twice(self):
        path = _tmp_overrides()
        url = "https://letterboxd.com/user/watchlist/"
        try:
            with _client_ctx(path) as client:
                client.post("/api/letterboxd/urls", json={"url": url})
                client.post("/api/letterboxd/urls", json={"url": url})
                urls = client.get("/api/letterboxd/urls").json()["urls"]
            assert urls.count(url) == 1
        finally:
            os.unlink(path)

    def test_remove_url(self):
        path = _tmp_overrides(letterboxd_urls=["https://letterboxd.com/user/watchlist/"])
        try:
            with _client_ctx(path) as client:
                r = client.post("/api/letterboxd/urls/remove", json={"url": "https://letterboxd.com/user/watchlist/"})
                assert r.json()["ok"] is True
                assert client.get("/api/letterboxd/urls").json()["urls"] == []
        finally:
            os.unlink(path)
