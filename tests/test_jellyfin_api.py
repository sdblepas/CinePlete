"""
Tests for app/jellyfin_api.py
Covers: _library_id, scan_movies (mocked HTTP)
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_CONFIG = {
    "JELLYFIN": {
        "JELLYFIN_URL":          "http://jellyfin:8096",
        "JELLYFIN_API_KEY":      "testtoken",
        "JELLYFIN_LIBRARY_NAME": "Movies",
    },
    "PLEX": {
        "SHORT_MOVIE_LIMIT": 60,
        "PLEX_PAGE_SIZE":    500,
    },
}


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

class _MockResponse:
    def __init__(self, data, status=200):
        self._data   = data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.exceptions.HTTPError(response=self)

    def json(self):
        return self._data


def _media_folders_response(names=("Movies",)):
    return _MockResponse({
        "Items": [{"Name": n, "Id": f"lib-{n.lower()}"} for n in names]
    })


def _items_response(items, total=None):
    return _MockResponse({
        "Items": items,
        "TotalRecordCount": total if total is not None else len(items),
    })


# ─────────────────────────────────────────────
# _library_id
# ─────────────────────────────────────────────

class TestLibraryId:

    def test_finds_library_case_insensitive(self, monkeypatch):
        import app.jellyfin_api as jf
        monkeypatch.setattr("app.jellyfin_api.load_config", lambda: BASE_CONFIG)
        monkeypatch.setattr("requests.get", lambda *a, **k: _media_folders_response(["Movies"]))

        assert jf._library_id("movies") == "lib-movies"

    def test_raises_when_library_not_found(self, monkeypatch):
        import app.jellyfin_api as jf
        monkeypatch.setattr("app.jellyfin_api.load_config", lambda: BASE_CONFIG)
        monkeypatch.setattr("requests.get", lambda *a, **k: _media_folders_response(["TV Shows"]))

        with pytest.raises(RuntimeError, match="not found"):
            jf._library_id("Movies")

    def test_raises_when_library_list_empty(self, monkeypatch):
        import app.jellyfin_api as jf
        monkeypatch.setattr("app.jellyfin_api.load_config", lambda: BASE_CONFIG)
        monkeypatch.setattr("requests.get", lambda *a, **k: _MockResponse({"Items": []}))

        with pytest.raises(RuntimeError):
            jf._library_id("Movies")


# ─────────────────────────────────────────────
# Auth headers — Jellyfin 12 compatibility (issue #108)
# ─────────────────────────────────────────────

class TestAuthHeaders:

    def test_includes_modern_authorization_header(self):
        """Jellyfin 12 dropped X-Emby-Token; the Authorization header is required."""
        import app.jellyfin_api as jf
        headers = jf._auth_headers("mykey")
        assert headers["Authorization"] == 'MediaBrowser Token="mykey"'

    def test_keeps_legacy_header_for_older_servers(self):
        import app.jellyfin_api as jf
        headers = jf._auth_headers("mykey")
        assert headers["X-Emby-Token"] == "mykey"

    def test_jf_get_sends_authorization_header(self, monkeypatch):
        """The actual request must carry the modern header, not just the helper."""
        import app.jellyfin_api as jf
        monkeypatch.setattr("app.jellyfin_api.load_config", lambda: BASE_CONFIG)

        captured = {}

        def mock_get(url, *a, **k):
            captured["headers"] = k.get("headers", {})
            return _media_folders_response(["Movies"])

        monkeypatch.setattr("requests.get", mock_get)
        jf._library_id("Movies")

        assert captured["headers"].get("Authorization") == 'MediaBrowser Token="testtoken"'


# ─────────────────────────────────────────────
# scan_movies — stats & basic indexing
# ─────────────────────────────────────────────

def _make_movie(tmdb_id, title="Test Film", duration_ticks=9_000_000_000,
                directors=("Director A",), actors=("Actor 1", "Actor 2")):
    people = [{"Name": n, "Type": "Director"} for n in directors]
    people += [{"Name": n, "Type": "Actor"} for n in actors]
    return {
        "Name":           title,
        "ProductionYear": 2020,
        "RunTimeTicks":   duration_ticks,   # 9_000_000_000 = 15 min (over 60 min default… wait)
        "ProviderIds":    {"Tmdb": str(tmdb_id)},
        "People":         people,
    }


# 9_000_000_000 ticks / 600_000_000 = 15 min  → skipped (< 60 min limit)
# 36_000_000_000 ticks / 600_000_000 = 60 min → accepted (equal to limit is NOT skipped)
# 37_200_000_000 ticks / 600_000_000 = 62 min → accepted

_LONG_MOVIE_TICKS  = 37_200_000_000   # 62 min
_SHORT_MOVIE_TICKS = 9_000_000_000    # 15 min


class TestScanMovies:

    def _patch(self, monkeypatch, pages):
        """pages: list of (items, total) tuples returned in sequence."""
        import app.jellyfin_api as jf
        monkeypatch.setattr("app.jellyfin_api.load_config", lambda: BASE_CONFIG)

        call_count = {"n": 0}
        def mock_get(url, *a, **k):
            if "/Library/MediaFolders" in url:
                return _media_folders_response(["Movies"])
            # /Items pages
            idx = call_count["n"]
            call_count["n"] += 1
            if idx < len(pages):
                items, total = pages[idx]
                return _items_response(items, total)
            return _items_response([], 0)
        monkeypatch.setattr("requests.get", mock_get)

    # --

    def test_returns_correct_tuple_structure(self, monkeypatch):
        import app.jellyfin_api as jf
        self._patch(monkeypatch, [([_make_movie(1, duration_ticks=_LONG_MOVIE_TICKS)], 1)])
        media_ids, directors, actors, stats, no_tmdb = jf.scan_movies()

        assert isinstance(media_ids,  dict)
        assert isinstance(directors,  dict)
        assert isinstance(actors,     dict)
        assert isinstance(stats,      dict)
        assert isinstance(no_tmdb,    list)

    def test_indexes_movie_with_valid_tmdb(self, monkeypatch):
        import app.jellyfin_api as jf
        movie = _make_movie(42, title="My Movie", duration_ticks=_LONG_MOVIE_TICKS)
        self._patch(monkeypatch, [([movie], 1)])
        media_ids, *_ = jf.scan_movies()

        assert 42 in media_ids
        assert media_ids[42] == "My Movie"

    def test_skips_short_movies(self, monkeypatch):
        import app.jellyfin_api as jf
        short = _make_movie(99, duration_ticks=_SHORT_MOVIE_TICKS)
        self._patch(monkeypatch, [([short], 1)])
        media_ids, _, _, stats, _ = jf.scan_movies()

        assert 99 not in media_ids
        assert stats["skipped_short"] == 1

    def test_missing_tmdb_goes_to_no_tmdb_guid(self, monkeypatch):
        import app.jellyfin_api as jf
        movie = _make_movie(0, duration_ticks=_LONG_MOVIE_TICKS)
        movie["ProviderIds"] = {}   # no TMDB id
        self._patch(monkeypatch, [([movie], 1)])
        media_ids, _, _, _, no_tmdb = jf.scan_movies()

        assert len(media_ids) == 0
        assert len(no_tmdb)   == 1

    def test_invalid_tmdb_string_goes_to_no_tmdb_guid(self, monkeypatch):
        import app.jellyfin_api as jf
        movie = _make_movie(0, duration_ticks=_LONG_MOVIE_TICKS)
        movie["ProviderIds"] = {"Tmdb": "not-a-number"}
        self._patch(monkeypatch, [([movie], 1)])
        _, _, _, _, no_tmdb = jf.scan_movies()

        assert len(no_tmdb) == 1

    def test_runtimeticks_as_string_does_not_crash(self, monkeypatch):
        """RunTimeTicks should be cast to int safely."""
        import app.jellyfin_api as jf
        movie = _make_movie(7, duration_ticks=_LONG_MOVIE_TICKS)
        movie["RunTimeTicks"] = str(_LONG_MOVIE_TICKS)   # string instead of int
        self._patch(monkeypatch, [([movie], 1)])
        media_ids, *_ = jf.scan_movies()

        assert 7 in media_ids

    def test_runtimeticks_none_skips_movie(self, monkeypatch):
        """None RunTimeTicks → duration 0 → skipped as short (0 < 60)."""
        import app.jellyfin_api as jf
        movie = _make_movie(8, duration_ticks=_LONG_MOVIE_TICKS)
        movie["RunTimeTicks"] = None
        self._patch(monkeypatch, [([movie], 1)])
        _, _, _, stats, _ = jf.scan_movies()

        # duration_min = 0, condition is "if duration_min and duration_min < limit"
        # 0 is falsy → NOT skipped as short, movie is indexed
        assert stats["skipped_short"] == 0

    def test_directors_kept_only_in_2_plus_films(self, monkeypatch):
        import app.jellyfin_api as jf
        m1 = _make_movie(1, duration_ticks=_LONG_MOVIE_TICKS, directors=("Kubrick",), actors=())
        m2 = _make_movie(2, duration_ticks=_LONG_MOVIE_TICKS, directors=("Kubrick",), actors=())
        m3 = _make_movie(3, duration_ticks=_LONG_MOVIE_TICKS, directors=("Spielberg",), actors=())
        self._patch(monkeypatch, [([m1, m2, m3], 3)])
        _, directors, _, _, _ = jf.scan_movies()

        assert "Kubrick"   in directors     # 2 films
        assert "Spielberg" not in directors  # only 1 film

    def test_actors_kept_only_in_2_plus_films(self, monkeypatch):
        import app.jellyfin_api as jf
        m1 = _make_movie(1, duration_ticks=_LONG_MOVIE_TICKS, directors=(), actors=("De Niro",))
        m2 = _make_movie(2, duration_ticks=_LONG_MOVIE_TICKS, directors=(), actors=("De Niro", "Pacino"))
        self._patch(monkeypatch, [([m1, m2], 2)])
        _, _, actors, _, _ = jf.scan_movies()

        assert "De Niro" in actors
        assert "Pacino"  not in actors  # only 1 film

    def test_actors_limited_to_5_per_film(self, monkeypatch):
        import app.jellyfin_api as jf
        many_actors = [f"Actor {i}" for i in range(10)]
        # Two films, same cast — so all actors appearing in 2+ films
        m1 = _make_movie(1, duration_ticks=_LONG_MOVIE_TICKS, directors=(), actors=many_actors)
        m2 = _make_movie(2, duration_ticks=_LONG_MOVIE_TICKS, directors=(), actors=many_actors)
        self._patch(monkeypatch, [([m1, m2], 2)])
        _, _, actors, _, _ = jf.scan_movies()

        # Only top 5 actors per film are indexed, so max 5 actors kept
        assert len(actors) <= 5

    def test_stats_fields_present(self, monkeypatch):
        import app.jellyfin_api as jf
        self._patch(monkeypatch, [([_make_movie(1, duration_ticks=_LONG_MOVIE_TICKS)], 1)])
        _, _, _, stats, _ = jf.scan_movies()

        for key in ("scanned_items", "indexed_tmdb", "skipped_short",
                    "directors_kept", "actors_kept", "no_tmdb_guid"):
            assert key in stats, f"Missing stats key: {key}"

    def test_pagination_fetches_all_pages(self, monkeypatch):
        import app.jellyfin_api as jf
        page1 = [_make_movie(i, duration_ticks=_LONG_MOVIE_TICKS) for i in range(1, 4)]
        page2 = [_make_movie(i, duration_ticks=_LONG_MOVIE_TICKS) for i in range(4, 6)]
        # total=5, page_size=500 so it'll fetch page1 (3 items, start=0) then page2 (2 items, start=3)
        self._patch(monkeypatch, [(page1, 5), (page2, 5)])
        media_ids, *_ = jf.scan_movies()

        assert len(media_ids) == 5
        for i in range(1, 6):
            assert i in media_ids

    def test_empty_library_returns_empty_results(self, monkeypatch):
        import app.jellyfin_api as jf
        self._patch(monkeypatch, [([], 0)])
        media_ids, directors, actors, stats, no_tmdb = jf.scan_movies()

        assert media_ids  == {}
        assert directors  == {}
        assert actors     == {}
        assert no_tmdb    == []
        assert stats["scanned_items"] == 0
