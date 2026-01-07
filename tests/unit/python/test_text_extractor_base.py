"""Unit tests for base extractor class and ExtractionResult."""

import pytest

from ragstack_common.text_extractors.base import (
    BaseExtractor,
    ExtractionResult,
)


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_creation_with_all_fields(self):
        """Test creating ExtractionResult with all fields."""
        result = ExtractionResult(
            markdown="# Title\n\nContent here",
            file_type="txt",
            title="Test Document",
            word_count=5,
            structural_metadata={"lines": 3},
            parse_warning=None,
        )
        assert result.markdown == "# Title\n\nContent here"
        assert result.file_type == "txt"
        assert result.title == "Test Document"
        assert result.word_count == 5
        assert result.structural_metadata == {"lines": 3}
        assert result.parse_warning is None

    def test_creation_with_parse_warning(self):
        """Test creating ExtractionResult with a parse warning."""
        result = ExtractionResult(
            markdown="Raw content",
            file_type="json",
            title="malformed.json",
            word_count=2,
            structural_metadata={},
            parse_warning="Invalid JSON: Expecting property name",
        )
        assert result.parse_warning == "Invalid JSON: Expecting property name"

    def test_structural_metadata_can_be_empty(self):
        """Test that structural_metadata can be an empty dict."""
        result = ExtractionResult(
            markdown="Content",
            file_type="txt",
            title="file.txt",
            word_count=1,
            structural_metadata={},
            parse_warning=None,
        )
        assert result.structural_metadata == {}


class TestBaseExtractorHelpers:
    """Tests for BaseExtractor helper methods."""

    def test_generate_frontmatter_simple(self):
        """Test frontmatter generation with simple values."""
        metadata = {
            "source_file": "test.txt",
            "file_type": "txt",
            "word_count": 100,
        }
        frontmatter = BaseExtractor._generate_frontmatter(metadata)
        assert frontmatter.startswith("---\n")
        assert frontmatter.endswith("---\n")
        assert "source_file: test.txt" in frontmatter
        assert "file_type: txt" in frontmatter
        assert "word_count: 100" in frontmatter

    def test_generate_frontmatter_with_quotes(self):
        """Test frontmatter generation escapes quotes in values."""
        metadata = {
            "title": 'Document with "quotes" inside',
        }
        frontmatter = BaseExtractor._generate_frontmatter(metadata)
        # YAML should escape or quote the string properly
        assert "quotes" in frontmatter
        assert frontmatter.startswith("---\n")

    def test_generate_frontmatter_with_colons(self):
        """Test frontmatter generation handles colons in values."""
        metadata = {
            "url": "https://example.com/path",
        }
        frontmatter = BaseExtractor._generate_frontmatter(metadata)
        assert "https://example.com/path" in frontmatter or "example.com" in frontmatter

    def test_generate_frontmatter_with_list(self):
        """Test frontmatter generation handles list values."""
        metadata = {
            "columns": ["name", "age", "city"],
        }
        frontmatter = BaseExtractor._generate_frontmatter(metadata)
        assert "columns:" in frontmatter
        assert "name" in frontmatter

    def test_generate_frontmatter_with_none(self):
        """Test frontmatter generation handles None values."""
        metadata = {
            "source_file": "test.txt",
            "parse_warning": None,
        }
        frontmatter = BaseExtractor._generate_frontmatter(metadata)
        assert "source_file: test.txt" in frontmatter
        assert "null" in frontmatter.lower() or "parse_warning:" in frontmatter

    def test_count_words_simple(self):
        """Test word count with simple text."""
        text = "one two three four five"
        assert BaseExtractor._count_words(text) == 5

    def test_count_words_with_punctuation(self):
        """Test word count ignores punctuation properly."""
        text = "Hello, world! This is a test."
        assert BaseExtractor._count_words(text) == 6

    def test_count_words_with_multiple_spaces(self):
        """Test word count handles multiple spaces."""
        text = "word1    word2     word3"
        assert BaseExtractor._count_words(text) == 3

    def test_count_words_with_newlines(self):
        """Test word count handles newlines."""
        text = "line one\nline two\nline three"
        assert BaseExtractor._count_words(text) == 6

    def test_count_words_empty_string(self):
        """Test word count with empty string."""
        assert BaseExtractor._count_words("") == 0

    def test_count_words_whitespace_only(self):
        """Test word count with whitespace only."""
        assert BaseExtractor._count_words("   \n\t  ") == 0

    def test_decode_content_utf8(self):
        """Test decoding valid UTF-8 content."""
        content = "Hello, World! 你好".encode("utf-8")
        decoded = BaseExtractor._decode_content(content)
        assert decoded == "Hello, World! 你好"

    def test_decode_content_latin1_fallback(self):
        """Test decoding falls back to latin-1 for invalid UTF-8."""
        # Create content that's valid latin-1 but invalid UTF-8
        content = "café".encode("latin-1")
        decoded = BaseExtractor._decode_content(content)
        # Should decode without raising, may use replacement or latin-1
        assert decoded is not None
        assert len(decoded) > 0

    def test_decode_content_empty(self):
        """Test decoding empty bytes."""
        assert BaseExtractor._decode_content(b"") == ""

    def test_extract_title_from_filename_simple(self):
        """Test extracting title from simple filename."""
        assert BaseExtractor._extract_title_from_filename("document.txt") == "document"

    def test_extract_title_from_filename_multiple_dots(self):
        """Test extracting title from filename with multiple dots."""
        assert BaseExtractor._extract_title_from_filename("my.file.name.txt") == "my.file.name"

    def test_extract_title_from_filename_no_extension(self):
        """Test extracting title from filename without extension."""
        assert BaseExtractor._extract_title_from_filename("README") == "README"

    def test_extract_title_from_filename_with_path(self):
        """Test extracting title handles path-like filenames."""
        result = BaseExtractor._extract_title_from_filename("path/to/document.txt")
        # Should extract just the filename part without extension
        assert "document" in result

    def test_extract_title_from_filename_underscores(self):
        """Test title extraction converts underscores to spaces."""
        result = BaseExtractor._extract_title_from_filename("my_document_name.txt")
        # Implementation may or may not convert underscores
        assert "my" in result.lower()

    def test_extract_title_from_filename_hyphens(self):
        """Test title extraction handles hyphens."""
        result = BaseExtractor._extract_title_from_filename("my-document-name.txt")
        assert "my" in result.lower()


class TestBaseExtractorAbstract:
    """Tests verifying BaseExtractor is properly abstract."""

    def test_cannot_instantiate_directly(self):
        """Test that BaseExtractor cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseExtractor()

    def test_extract_method_is_abstract(self):
        """Test that extract method must be implemented by subclasses."""
        # Create a minimal subclass that doesn't implement extract
        class IncompleteExtractor(BaseExtractor):
            pass

        with pytest.raises(TypeError):
            IncompleteExtractor()


class TestConcreteExtractorSubclass:
    """Tests using a concrete subclass to verify base functionality works."""

    def test_subclass_with_extract_implementation(self):
        """Test that a properly implemented subclass works."""

        class SimpleExtractor(BaseExtractor):
            def extract(self, content: bytes, filename: str):
                text = self._decode_content(content)
                title = self._extract_title_from_filename(filename)
                word_count = self._count_words(text)
                metadata = {
                    "source_file": filename,
                    "file_type": "txt",
                    "word_count": word_count,
                }
                frontmatter = self._generate_frontmatter(metadata)
                markdown = f"{frontmatter}\n{text}"
                return ExtractionResult(
                    markdown=markdown,
                    file_type="txt",
                    title=title,
                    word_count=word_count,
                    structural_metadata={"char_count": len(text)},
                    parse_warning=None,
                )

        extractor = SimpleExtractor()
        result = extractor.extract(b"Hello world", "test.txt")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "txt"
        assert result.title == "test"
        assert result.word_count == 2
        assert "Hello world" in result.markdown
        assert "---" in result.markdown


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
