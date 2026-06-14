"""
Unit tests for return_prevention/taxonomy/taxonomy_loader.py

Validates:
- Loading from a valid JSON fixture yields all entries with correct types
- Missing file raises RuntimeError containing file path
- Malformed JSON raises RuntimeError containing parse failure reason
- Subcategory lookup miss returns None (not an exception)

Requirements: 3.4, 3.7
"""

import json

import pytest

from return_prevention.taxonomy.taxonomy_loader import (
    TaxonomyEntry,
    load_taxonomy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


VALID_TAXONOMY_DATA = [
    {"category": "Apparel", "subcategory": "Women's Shoes", "category_return_rate": 0.3200, "has_size_ambiguity": True},
    {"category": "Apparel", "subcategory": "Men's Jeans", "category_return_rate": 0.2800, "has_size_ambiguity": True},
    {"category": "Apparel", "subcategory": "T-Shirts", "category_return_rate": 0.1500, "has_size_ambiguity": False},
    {"category": "Apparel", "subcategory": "Rings", "category_return_rate": 0.2000, "has_size_ambiguity": True},
    {"category": "Electronics", "subcategory": "Smartphones", "category_return_rate": 0.0800, "has_size_ambiguity": False},
    {"category": "Electronics", "subcategory": "Earphones", "category_return_rate": 0.1200, "has_size_ambiguity": False},
    {"category": "Electronics", "subcategory": "Tablets", "category_return_rate": 0.0900, "has_size_ambiguity": False},
    {"category": "Home", "subcategory": "Blenders", "category_return_rate": 0.0500, "has_size_ambiguity": False},
    {"category": "Home", "subcategory": "Coffee Makers", "category_return_rate": 0.0600, "has_size_ambiguity": False},
    {"category": "Books", "subcategory": "Novels", "category_return_rate": 0.0300, "has_size_ambiguity": False},
    {"category": "Books", "subcategory": "Textbooks", "category_return_rate": 0.0400, "has_size_ambiguity": False},
]


@pytest.fixture
def valid_taxonomy_file(tmp_path):
    """Create a valid taxonomy JSON file with 11 entries."""
    file_path = tmp_path / "taxonomy.json"
    file_path.write_text(json.dumps(VALID_TAXONOMY_DATA), encoding="utf-8")
    return str(file_path)


@pytest.fixture
def malformed_json_file(tmp_path):
    """Create a file with invalid JSON content."""
    file_path = tmp_path / "bad_taxonomy.json"
    file_path.write_text("{not valid json: [}", encoding="utf-8")
    return str(file_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadFromValidJSON:
    """Load from valid JSON fixture → assert all entries present with correct types."""

    def test_loads_all_entries(self, valid_taxonomy_file):
        result = load_taxonomy(valid_taxonomy_file)
        assert len(result) == 11

    def test_keys_are_subcategory_strings(self, valid_taxonomy_file):
        result = load_taxonomy(valid_taxonomy_file)
        for key in result:
            assert isinstance(key, str)
        # Spot-check specific subcategories
        assert "Women's Shoes" in result
        assert "Smartphones" in result
        assert "Novels" in result

    def test_values_are_taxonomy_entry_instances(self, valid_taxonomy_file):
        result = load_taxonomy(valid_taxonomy_file)
        for entry in result.values():
            assert isinstance(entry, TaxonomyEntry)

    def test_entry_field_types(self, valid_taxonomy_file):
        result = load_taxonomy(valid_taxonomy_file)
        for entry in result.values():
            assert isinstance(entry.category, str)
            assert isinstance(entry.subcategory, str)
            assert isinstance(entry.category_return_rate, float)
            assert isinstance(entry.has_size_ambiguity, bool)

    def test_entry_values_correct(self, valid_taxonomy_file):
        result = load_taxonomy(valid_taxonomy_file)
        shoes = result["Women's Shoes"]
        assert shoes.category == "Apparel"
        assert shoes.subcategory == "Women's Shoes"
        assert shoes.category_return_rate == pytest.approx(0.3200)
        assert shoes.has_size_ambiguity is True

        phones = result["Smartphones"]
        assert phones.category == "Electronics"
        assert phones.category_return_rate == pytest.approx(0.0800)
        assert phones.has_size_ambiguity is False


class TestMissingFile:
    """Missing file → raises RuntimeError containing file path."""

    def test_raises_runtime_error(self, tmp_path):
        nonexistent = str(tmp_path / "does_not_exist.json")
        with pytest.raises(RuntimeError) as exc_info:
            load_taxonomy(nonexistent)
        assert nonexistent in str(exc_info.value)

    def test_error_message_contains_path(self, tmp_path):
        missing_path = str(tmp_path / "missing_taxonomy.json")
        with pytest.raises(RuntimeError, match="missing_taxonomy.json"):
            load_taxonomy(missing_path)


class TestMalformedJSON:
    """Malformed JSON → raises RuntimeError containing parse failure reason."""

    def test_raises_runtime_error(self, malformed_json_file):
        with pytest.raises(RuntimeError):
            load_taxonomy(malformed_json_file)

    def test_error_contains_file_path(self, malformed_json_file):
        with pytest.raises(RuntimeError) as exc_info:
            load_taxonomy(malformed_json_file)
        assert "bad_taxonomy.json" in str(exc_info.value)

    def test_error_mentions_parse_failure(self, malformed_json_file):
        with pytest.raises(RuntimeError) as exc_info:
            load_taxonomy(malformed_json_file)
        # Should contain some indication of JSON parse failure
        error_msg = str(exc_info.value).lower()
        assert "json" in error_msg or "parse" in error_msg or "malformed" in error_msg


class TestSubcategoryLookupMiss:
    """Subcategory lookup miss returns None (not an exception)."""

    def test_dict_get_returns_none_for_missing_key(self, valid_taxonomy_file):
        result = load_taxonomy(valid_taxonomy_file)
        # .get() on the dict for a nonexistent subcategory returns None
        assert result.get("Nonexistent Subcategory") is None

    def test_does_not_raise_on_missing_subcategory(self, valid_taxonomy_file):
        result = load_taxonomy(valid_taxonomy_file)
        # This should NOT raise a KeyError or any exception
        value = result.get("Unknown Category XYZ")
        assert value is None
