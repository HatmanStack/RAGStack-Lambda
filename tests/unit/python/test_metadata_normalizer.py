"""Tests for metadata_normalizer module."""

import pytest

from ragstack_common.metadata_normalizer import (
    MAX_ARRAY_ITEMS,
    expand_to_searchable_array,
    normalize_metadata_for_s3,
)


class TestExpandToSearchableArray:
    """Tests for expand_to_searchable_array function."""

    def test_simple_string(self):
        """Single word returns array with just that word."""
        result = expand_to_searchable_array("genealogy")
        assert result == ["genealogy"]

    def test_comma_separated(self):
        """Comma-separated values are split into elements."""
        result = expand_to_searchable_array("chicago, illinois")
        assert "chicago, illinois" in result  # Original
        assert "chicago" in result
        assert "illinois" in result

    def test_space_separated_words(self):
        """Words are split and included if >= 3 chars."""
        result = expand_to_searchable_array("jack wilson")
        assert "jack wilson" in result  # Original
        assert "jack" in result
        assert "wilson" in result

    def test_short_words_excluded(self):
        """Words shorter than 3 chars are excluded."""
        result = expand_to_searchable_array("judy f")
        assert "judy f" in result  # Original
        assert "judy" in result
        assert "f" not in result  # Too short

    def test_year_extraction(self):
        """4-digit years are extracted from date strings."""
        result = expand_to_searchable_array("2016-01-15")
        assert "2016-01-15" in result  # Original
        assert "2016" in result

    def test_empty_string(self):
        """Empty string returns empty list."""
        assert expand_to_searchable_array("") == []
        assert expand_to_searchable_array("   ") == []

    def test_lowercase_normalization(self):
        """All values are lowercased."""
        result = expand_to_searchable_array("CHICAGO, ILLINOIS")
        assert all(v.islower() for v in result)

    def test_max_items_limit(self):
        """Output is limited to MAX_ARRAY_ITEMS."""
        # Create a string that would expand to many items
        long_value = ", ".join(f"item{i}" for i in range(20))
        result = expand_to_searchable_array(long_value)
        assert len(result) <= MAX_ARRAY_ITEMS


class TestNormalizeMetadataForS3:
    """Tests for normalize_metadata_for_s3 function."""

    def test_string_values_expanded(self):
        """String values are expanded to arrays."""
        metadata = {"author": "judy f", "topic": "genealogy"}
        result = normalize_metadata_for_s3(metadata)

        assert isinstance(result["author"], list)
        assert "judy f" in result["author"]
        assert "judy" in result["author"]

        assert isinstance(result["topic"], list)
        assert "genealogy" in result["topic"]

    def test_list_values_expanded(self):
        """List values are expanded with components."""
        metadata = {"people_mentioned": ["jack wilson", "mary jones"]}
        result = normalize_metadata_for_s3(metadata)

        assert isinstance(result["people_mentioned"], list)
        assert "jack wilson" in result["people_mentioned"]
        assert "mary jones" in result["people_mentioned"]
        assert "jack" in result["people_mentioned"]
        assert "wilson" in result["people_mentioned"]

    def test_boolean_preserved(self):
        """Boolean values are preserved as-is."""
        metadata = {"is_active": True}
        result = normalize_metadata_for_s3(metadata)
        assert result["is_active"] is True

    def test_number_to_array(self):
        """Numbers become single-item arrays."""
        metadata = {"year": 2016}
        result = normalize_metadata_for_s3(metadata)
        assert result["year"] == ["2016"]

    def test_none_values_excluded(self):
        """None values are excluded from output."""
        metadata = {"topic": "genealogy", "empty": None}
        result = normalize_metadata_for_s3(metadata)
        assert "empty" not in result

    def test_complex_metadata(self):
        """Full metadata object is normalized correctly."""
        metadata = {
            "author": "judy f",
            "location": "chicago, illinois",
            "people_mentioned": ["jack wilson", "mary jones"],
            "date": "2016-01-15",
            "document_type": "letter",
            "content_type": "document",
        }
        result = normalize_metadata_for_s3(metadata)

        # All values should be lists (except booleans)
        for key, value in result.items():
            assert isinstance(value, list), f"{key} should be a list"

        # Check specific expansions
        assert "judy" in result["author"]
        assert "chicago" in result["location"]
        assert "illinois" in result["location"]
        assert "2016" in result["date"]
