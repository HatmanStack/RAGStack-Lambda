"""Unit tests for JSON extractor."""

import pytest

from ragstack_common.text_extractors.json_extractor import JsonExtractor
from ragstack_common.text_extractors.base import ExtractionResult
from tests.fixtures.text_extractor_samples import (
    JSON_SIMPLE_OBJECT,
    JSON_SIMPLE_ARRAY,
    JSON_ARRAY_OF_OBJECTS,
    JSON_NESTED,
    JSON_DEEPLY_NESTED,
    JSON_ALL_TYPES,
    JSON_EMPTY_OBJECT,
    JSON_EMPTY_ARRAY,
    JSON_MALFORMED,
)


class TestJsonExtractor:
    """Tests for JsonExtractor."""

    def test_extracts_simple_object(self):
        """Test extraction of simple JSON object."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_SIMPLE_OBJECT.encode(), "config.json")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "json"
        assert "name" in result.markdown.lower()

    def test_extracts_simple_array(self):
        """Test extraction of JSON array."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_SIMPLE_ARRAY.encode(), "numbers.json")

        assert result.file_type == "json"
        assert result.structural_metadata.get("structure_type") == "array"

    def test_extracts_array_of_objects(self):
        """Test extraction of JSON array of objects."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_ARRAY_OF_OBJECTS.encode(), "users.json")

        assert result.file_type == "json"
        assert result.structural_metadata.get("structure_type") == "array"
        assert result.structural_metadata.get("item_count") == 3

    def test_extracts_nested_json(self):
        """Test extraction of nested JSON structure."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_NESTED.encode(), "config.json")

        assert result.file_type == "json"
        assert "database" in result.markdown.lower()
        assert "cache" in result.markdown.lower()

    def test_handles_deeply_nested(self):
        """Test handling of deeply nested JSON (should truncate)."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_DEEPLY_NESTED.encode(), "deep.json")

        # Should not raise, should produce output
        assert isinstance(result, ExtractionResult)

    def test_handles_all_types(self):
        """Test handling of all JSON types."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_ALL_TYPES.encode(), "types.json")

        assert result.file_type == "json"
        # Should handle string, number, boolean, null, array, object

    def test_handles_empty_object(self):
        """Test handling of empty JSON object."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_EMPTY_OBJECT.encode(), "empty.json")

        assert isinstance(result, ExtractionResult)
        assert result.structural_metadata.get("structure_type") == "object"

    def test_handles_empty_array(self):
        """Test handling of empty JSON array."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_EMPTY_ARRAY.encode(), "empty.json")

        assert isinstance(result, ExtractionResult)
        assert result.structural_metadata.get("structure_type") == "array"

    def test_malformed_json_falls_back(self):
        """Test that malformed JSON falls back with warning."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_MALFORMED.encode(), "broken.json")

        assert isinstance(result, ExtractionResult)
        assert result.parse_warning is not None

    def test_generates_frontmatter(self):
        """Test that frontmatter is generated correctly."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_SIMPLE_OBJECT.encode(), "config.json")

        assert result.markdown.startswith("---\n")
        assert "source_file: config.json" in result.markdown
        assert "file_type: json" in result.markdown

    def test_structural_metadata_for_object(self):
        """Test structural metadata includes expected fields for objects."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_SIMPLE_OBJECT.encode(), "config.json")

        assert "structure_type" in result.structural_metadata
        assert "top_level_keys" in result.structural_metadata
        assert result.structural_metadata["structure_type"] == "object"

    def test_structural_metadata_for_array(self):
        """Test structural metadata includes expected fields for arrays."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_SIMPLE_ARRAY.encode(), "numbers.json")

        assert "structure_type" in result.structural_metadata
        assert "item_count" in result.structural_metadata
        assert result.structural_metadata["structure_type"] == "array"
        assert result.structural_metadata["item_count"] == 5

    def test_describes_top_level_keys(self):
        """Test that top-level keys are described in output."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_NESTED.encode(), "config.json")

        assert "database" in result.markdown
        assert "cache" in result.markdown

    def test_title_extracted_from_filename(self):
        """Test title is extracted from filename."""
        extractor = JsonExtractor()
        result = extractor.extract(JSON_SIMPLE_OBJECT.encode(), "app_config.json")

        assert result.title == "app_config"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
