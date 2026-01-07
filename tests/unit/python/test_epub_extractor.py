"""Unit tests for EPUB extractor."""

import io

import pytest

try:
    from ebooklib import epub
except ImportError:
    epub = None

from ragstack_common.text_extractors.base import ExtractionResult
from ragstack_common.text_extractors.epub_extractor import EpubExtractor


def create_minimal_epub(
    title: str = "Test Book",
    author: str = "Test Author",
    chapters: list[tuple[str, str]] | None = None,
) -> bytes:
    """Create a minimal EPUB file for testing."""
    if epub is None:
        pytest.skip("ebooklib not installed")

    book = epub.EpubBook()
    book.set_identifier("test-id-12345")
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    if chapters is None:
        chapters = [
            ("Chapter 1", "<h1>Chapter 1</h1><p>First chapter content.</p>"),
            ("Chapter 2", "<h1>Chapter 2</h1><p>Second chapter content.</p>"),
        ]

    spine = ["nav"]
    for i, (chapter_title, content) in enumerate(chapters):
        chapter = epub.EpubHtml(title=chapter_title, file_name=f"chap_{i + 1}.xhtml", lang="en")
        chapter.content = f"<html><body>{content}</body></html>"
        book.add_item(chapter)
        spine.append(chapter)

    # Add navigation
    book.toc = [
        epub.Link(f"chap_{i + 1}.xhtml", title, f"chap{i + 1}")
        for i, (title, _) in enumerate(chapters)
    ]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    # Write to bytes
    buffer = io.BytesIO()
    epub.write_epub(buffer, book)
    return buffer.getvalue()


@pytest.fixture
def minimal_epub() -> bytes:
    """Fixture for minimal EPUB file."""
    return create_minimal_epub()


@pytest.fixture
def corrupted_epub() -> bytes:
    """Fixture for corrupted EPUB (invalid ZIP)."""
    return b"not a valid zip file"


class TestEpubExtractor:
    """Tests for EpubExtractor."""

    def test_extracts_epub(self, minimal_epub):
        """Test extraction of EPUB file."""
        extractor = EpubExtractor()
        result = extractor.extract(minimal_epub, "book.epub")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "epub"

    def test_extracts_title(self, minimal_epub):
        """Test extraction of book title."""
        extractor = EpubExtractor()
        result = extractor.extract(minimal_epub, "book.epub")

        assert result.title == "Test Book"

    def test_extracts_author(self, minimal_epub):
        """Test extraction of author."""
        extractor = EpubExtractor()
        result = extractor.extract(minimal_epub, "book.epub")

        assert result.structural_metadata.get("author") == "Test Author"

    def test_extracts_chapters(self, minimal_epub):
        """Test extraction of chapter content."""
        extractor = EpubExtractor()
        result = extractor.extract(minimal_epub, "book.epub")

        assert "Chapter 1" in result.markdown
        assert "Chapter 2" in result.markdown

    def test_extracts_chapter_content(self, minimal_epub):
        """Test that chapter content is extracted."""
        extractor = EpubExtractor()
        result = extractor.extract(minimal_epub, "book.epub")

        assert "First chapter content" in result.markdown
        assert "Second chapter content" in result.markdown

    def test_generates_frontmatter(self, minimal_epub):
        """Test that frontmatter is generated correctly."""
        extractor = EpubExtractor()
        result = extractor.extract(minimal_epub, "book.epub")

        assert result.markdown.startswith("---\n")
        assert "source_file: book.epub" in result.markdown
        assert "file_type: epub" in result.markdown

    def test_structural_metadata_includes_chapter_count(self, minimal_epub):
        """Test structural metadata includes chapter count."""
        extractor = EpubExtractor()
        result = extractor.extract(minimal_epub, "book.epub")

        assert "chapter_count" in result.structural_metadata
        # Chapter count includes nav documents, so >= 2 content chapters
        assert result.structural_metadata["chapter_count"] >= 2

    def test_corrupted_epub_falls_back(self, corrupted_epub):
        """Test that corrupted EPUB falls back with warning."""
        extractor = EpubExtractor()
        result = extractor.extract(corrupted_epub, "broken.epub")

        assert isinstance(result, ExtractionResult)
        assert result.parse_warning is not None

    def test_custom_book(self):
        """Test extraction of custom book."""
        epub_bytes = create_minimal_epub(
            title="Custom Title",
            author="Custom Author",
            chapters=[
                ("Introduction", "<p>Welcome to the book.</p>"),
                ("Main Content", "<p>This is the main content.</p>"),
                ("Conclusion", "<p>The end.</p>"),
            ],
        )
        extractor = EpubExtractor()
        result = extractor.extract(epub_bytes, "custom.epub")

        assert result.title == "Custom Title"
        assert result.structural_metadata.get("author") == "Custom Author"
        # Chapter count includes nav documents, so >= 3 content chapters
        assert result.structural_metadata.get("chapter_count") >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
