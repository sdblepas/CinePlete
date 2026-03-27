"""
Tests for app/overrides.py
Covers: add_unique, remove_value, load_json, rec_fetched_ids default
"""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.overrides import add_unique, remove_value, load_json, save_json, DEFAULT


# ─────────────────────────────────────────────
# add_unique
# ─────────────────────────────────────────────

class TestAddUnique:

    def test_adds_new_value(self):
        lst = [1, 2]
        add_unique(lst, 3)
        assert lst == [1, 2, 3]

    def test_does_not_add_duplicate(self):
        lst = [1, 2, 3]
        add_unique(lst, 2)
        assert lst == [1, 2, 3]

    def test_adds_to_empty_list(self):
        lst = []
        add_unique(lst, 42)
        assert lst == [42]

    def test_string_dedup(self):
        lst = ["Nolan", "Kubrick"]
        add_unique(lst, "Nolan")
        assert lst.count("Nolan") == 1


# ─────────────────────────────────────────────
# remove_value
# ─────────────────────────────────────────────

class TestRemoveValue:

    def test_removes_existing_value(self):
        lst = [1, 2, 3]
        remove_value(lst, 2)
        assert lst == [1, 3]

    def test_no_error_on_missing_value(self):
        lst = [1, 2, 3]
        remove_value(lst, 99)
        assert lst == [1, 2, 3]

    def test_removes_string(self):
        lst = ["Nolan", "Kubrick"]
        remove_value(lst, "Nolan")
        assert lst == ["Kubrick"]

    def test_removes_only_first_occurrence(self):
        lst = [1, 2, 2, 3]
        remove_value(lst, 2)
        assert lst == [1, 2, 3]


# ─────────────────────────────────────────────
# load_json
# ─────────────────────────────────────────────

class TestLoadJson:

    def test_returns_default_when_file_missing(self):
        result = load_json("/nonexistent/path/overrides.json")
        assert result == DEFAULT

    def test_loads_valid_file(self):
        data = {"ignore_movies": [1, 2], "wishlist_movies": [99]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            result = load_json(path)
            assert result["ignore_movies"] == [1, 2]
            assert result["wishlist_movies"] == [99]
        finally:
            os.unlink(path)

    def test_fills_missing_keys_with_defaults(self):
        data = {"ignore_movies": [1]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            result = load_json(path)
            assert "wishlist_movies" in result
            assert result["wishlist_movies"] == []
        finally:
            os.unlink(path)

    def test_returns_default_on_corrupt_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ this is not json }")
            path = f.name
        try:
            result = load_json(path)
            assert result == DEFAULT
        finally:
            os.unlink(path)


# ─────────────────────────────────────────────
# DEFAULT keys
# ─────────────────────────────────────────────

class TestDefaultKeys:

    def test_rec_fetched_ids_in_default(self):
        assert "rec_fetched_ids" in DEFAULT

    def test_rec_fetched_ids_default_empty_list(self):
        assert DEFAULT["rec_fetched_ids"] == []

    def test_rec_fetched_ids_populated_on_load(self):
        """A file without rec_fetched_ids should get it added as empty list."""
        data = {"ignore_movies": [1]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            result = load_json(path)
            assert "rec_fetched_ids" in result
            assert result["rec_fetched_ids"] == []
        finally:
            os.unlink(path)

    def test_rec_fetched_ids_preserved_on_load(self):
        """Existing rec_fetched_ids should be preserved."""
        data = {"rec_fetched_ids": [100, 200, 300]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            result = load_json(path)
            assert result["rec_fetched_ids"] == [100, 200, 300]
        finally:
            os.unlink(path)

    def test_all_default_keys_present(self):
        expected = {
            "ignore_movies", "ignore_movies_meta", "ignore_franchises", "ignore_directors",
            "ignore_actors", "wishlist_movies", "rec_fetched_ids", "letterboxd_urls"
        }
        assert expected == set(DEFAULT.keys())