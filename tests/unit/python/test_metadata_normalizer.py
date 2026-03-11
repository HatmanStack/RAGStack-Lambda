"""Tests for metadata_normalizer module."""

from ragstack_common.metadata_normalizer import (
    DEFAULT_CORE_METADATA_KEYS,
    MAX_ARRAY_ITEMS,
    expand_to_searchable_array,
    normalize_metadata_for_s3,
    reduce_metadata,
)


class TestExpandToSearchableArray:
    """Tests for expand_to_searchable_array function."""

    def test_simple_string(self):
        """Single word returns array with just that word."""
        result = expand_to_searchable_array("genealogy")
        assert result == ["genealogy"]

    def test_comma_separated(self):
        """Comma-separated values are split into elements, tokens before phrases."""
        result = expand_to_searchable_array("chicago, illinois")
        assert "chicago" in result
        assert "illinois" in result
        assert "chicago, illinois" in result
        # Words before phrases
        assert result.index("chicago") < result.index("chicago, illinois")

    def test_space_separated_words(self):
        """Words are split and included if >= 3 chars, tokens before original."""
        result = expand_to_searchable_array("jack wilson")
        assert "jack" in result
        assert "wilson" in result
        assert "jack wilson" in result
        # Tokens before phrase
        assert result.index("jack") < result.index("jack wilson")
        assert result.index("wilson") < result.index("jack wilson")

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
        """List values are expanded with word tokens prioritized over phrases."""
        metadata = {"people_mentioned": ["jack wilson", "mary jones"]}
        result = normalize_metadata_for_s3(metadata)

        assert isinstance(result["people_mentioned"], list)
        # Word tokens appear before phrases (tokens-first ordering)
        assert "jack" in result["people_mentioned"]
        assert "wilson" in result["people_mentioned"]
        assert "mary" in result["people_mentioned"]
        assert "jones" in result["people_mentioned"]
        # Full phrases still included when budget allows
        assert "jack wilson" in result["people_mentioned"]
        assert "mary jones" in result["people_mentioned"]
        # Words come before phrases
        word_indices = [
            result["people_mentioned"].index(w) for w in ["jack", "wilson", "mary", "jones"]
        ]
        phrase_indices = [
            result["people_mentioned"].index(p) for p in ["jack wilson", "mary jones"]
        ]
        assert max(word_indices) < min(phrase_indices)

    def test_list_tokens_first_under_budget_pressure(self):
        """With many list items, word tokens are kept even when budget is tight."""
        # 10 names would fill MAX_ARRAY_ITEMS with just originals in old code
        metadata = {
            "people_mentioned": [
                "dwight sheldon tillotson",
                "charles m. tillotson",
                "rudy valle",
                "edwin i. thompson",
                "j. k. tillotson",
                "hugh a. thompson",
                "harry d. van roop",
                "k. maurin b. thomas",
                "billy c. sucher",
                "everett j. tarr",
            ]
        }
        result = normalize_metadata_for_s3(metadata)
        values = result["people_mentioned"]

        assert len(values) <= MAX_ARRAY_ITEMS
        # Individual name tokens must be present for $eq filtering
        assert "dwight" in values
        assert "tillotson" in values
        assert "thompson" in values
        # Words should appear before any multi-word phrases
        words = [v for v in values if " " not in v]
        phrases = [v for v in values if " " in v]
        assert len(words) > 0
        if phrases:
            first_phrase_idx = values.index(phrases[0])
            last_word_idx = max(values.index(w) for w in words)
            assert last_word_idx < first_phrase_idx

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

    def test_list_with_falsy_values_preserved(self):
        """Falsy values (0, False) in lists are preserved, not dropped."""
        metadata = {"counts": [0, 1, 2], "flags": [False, True, "active"]}
        result = normalize_metadata_for_s3(metadata)

        # 0 should be preserved as "0"
        assert "counts" in result
        assert "0" in result["counts"]
        assert "1" in result["counts"]
        assert "2" in result["counts"]

        # False should be preserved as "false"
        assert "flags" in result
        assert "false" in result["flags"]
        assert "true" in result["flags"]
        assert "active" in result["flags"]

    def test_list_with_none_excluded(self):
        """None values in lists are excluded, but other values preserved."""
        metadata = {"items": ["valid", None, "also valid", ""]}
        result = normalize_metadata_for_s3(metadata)

        assert "items" in result
        assert "valid" in result["items"]
        assert "also valid" in result["items"]
        # Empty string should be excluded after normalization
        # None should not appear

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


class TestReduceMetadata:
    """Tests for reduce_metadata function."""

    def test_level_1_preserves_all(self):
        """Level 1 preserves all metadata unchanged."""
        metadata = {
            "content_type": "document",
            "author": "John Smith",
            "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
        }
        result = reduce_metadata(metadata, reduction_level=1)
        assert result == metadata

    def test_level_2_truncates_lists(self):
        """Level 2 truncates lists to 3 items but keeps scalars."""
        metadata = {
            "content_type": "document",
            "author": "John Smith",
            "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
        }
        result = reduce_metadata(metadata, reduction_level=2)
        assert result["content_type"] == "document"
        assert result["author"] == "John Smith"  # Scalar preserved
        assert result["tags"] == ["tag1", "tag2", "tag3"]  # Truncated to 3

    def test_level_2_preserves_scalars(self):
        """Level 2 preserves scalar values (regression test for bug fix)."""
        metadata = {
            "content_type": "document",
            "title": "My Document",
            "year": 2024,
            "is_public": True,
        }
        result = reduce_metadata(metadata, reduction_level=2)
        assert result["content_type"] == "document"
        assert result["title"] == "My Document"
        assert result["year"] == 2024
        assert result["is_public"] is True

    def test_level_3_keeps_only_core_keys(self):
        """Level 3 keeps only core metadata keys."""
        metadata = {
            "content_type": "document",
            "document_id": "abc123",
            "author": "John Smith",
            "custom_field": "should be dropped",
        }
        result = reduce_metadata(metadata, reduction_level=3)
        assert "content_type" in result
        assert "document_id" in result
        assert "author" not in result
        assert "custom_field" not in result

    def test_default_core_keys(self):
        """Default core keys are used when not specified."""
        assert "content_type" in DEFAULT_CORE_METADATA_KEYS
        assert "document_id" in DEFAULT_CORE_METADATA_KEYS
        assert "filename" in DEFAULT_CORE_METADATA_KEYS

    def test_custom_core_keys(self):
        """Custom core keys can be specified."""
        metadata = {
            "content_type": "document",
            "my_key": "important",
            "other_key": "also important",
        }
        custom_core = frozenset({"my_key"})
        result = reduce_metadata(metadata, reduction_level=3, core_keys=custom_core)
        assert "my_key" in result
        assert "content_type" not in result  # Not in custom core keys
