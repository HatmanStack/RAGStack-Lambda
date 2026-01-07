"""Unit tests for plain text extractor."""

import pytest

from ragstack_common.text_extractors.base import ExtractionResult
from ragstack_common.text_extractors.text_extractor import TextExtractor
from tests.fixtures.text_extractor_samples import (
    EMPTY_TEXT,
    SIMPLE_TEXT,
    SINGLE_LINE_TEXT,
    UNICODE_TEXT,
    WHITESPACE_ONLY_TEXT,
)


class TestTextExtractor:
    """Tests for TextExtractor."""

    def test_extracts_simple_text(self):
        """Test extraction of simple text."""
        extractor = TextExtractor()
        result = extractor.extract(SIMPLE_TEXT.encode(), "notes.txt")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "txt"
        assert result.title == "notes"
        assert "This is a simple text file" in result.markdown
        assert result.word_count > 0

    def test_extracts_unicode_text(self):
        """Test extraction preserves Unicode content."""
        extractor = TextExtractor()
        result = extractor.extract(UNICODE_TEXT.encode(), "unicode.txt")

        assert "🎉" in result.markdown  # Emoji preserved
        assert "café" in result.markdown  # Accented characters
        assert "你好" in result.markdown  # CJK characters

    def test_handles_empty_file(self):
        """Test extraction of empty file."""
        extractor = TextExtractor()
        result = extractor.extract(EMPTY_TEXT.encode(), "empty.txt")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "txt"
        assert result.word_count == 0

    def test_handles_whitespace_only(self):
        """Test extraction of whitespace-only file."""
        extractor = TextExtractor()
        result = extractor.extract(WHITESPACE_ONLY_TEXT.encode(), "whitespace.txt")

        assert isinstance(result, ExtractionResult)
        assert result.word_count == 0

    def test_extracts_single_line(self):
        """Test extraction of single-line file."""
        extractor = TextExtractor()
        result = extractor.extract(SINGLE_LINE_TEXT.encode(), "oneline.txt")

        assert result.word_count > 0
        assert "one line" in result.markdown.lower()

    def test_generates_frontmatter(self):
        """Test that frontmatter is generated correctly."""
        extractor = TextExtractor()
        result = extractor.extract(SIMPLE_TEXT.encode(), "document.txt")

        assert result.markdown.startswith("---\n")
        assert "source_file: document.txt" in result.markdown
        assert "file_type: txt" in result.markdown

    def test_structural_metadata_includes_counts(self):
        """Test that structural metadata includes line, word, char counts."""
        extractor = TextExtractor()
        result = extractor.extract(SIMPLE_TEXT.encode(), "test.txt")

        assert "line_count" in result.structural_metadata
        assert "word_count" in result.structural_metadata
        assert "char_count" in result.structural_metadata
        assert result.structural_metadata["line_count"] == 3
        assert result.structural_metadata["word_count"] > 0

    def test_handles_binary_content_gracefully(self):
        """Test handling of content that can't be decoded as text."""
        extractor = TextExtractor()
        # Content with invalid UTF-8 that falls back to latin-1
        content = b"\xff\xfe\x00\x01Hello"
        result = extractor.extract(content, "binary.txt")

        # Should not raise, should produce output
        assert isinstance(result, ExtractionResult)

    def test_title_extracted_from_filename(self):
        """Test title is extracted from filename without extension."""
        extractor = TextExtractor()
        result = extractor.extract(b"content", "My Document File.txt")

        assert result.title == "My Document File"

    def test_parse_warning_is_none_for_valid_text(self):
        """Test parse_warning is None for valid text files."""
        extractor = TextExtractor()
        result = extractor.extract(SIMPLE_TEXT.encode(), "test.txt")

        assert result.parse_warning is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
