"""
EPUB extractor using ebooklib.

Extracts ebook content including metadata and chapter content,
converting HTML chapters to markdown.
"""

import tempfile
from typing import Any

import ebooklib
from ebooklib import epub

from .base import BaseExtractor, ExtractionResult
from .html_extractor import HtmlExtractor


class EpubExtractor(BaseExtractor):
    """Extract content from EPUB files.

    Features:
    - Extract title, author, language metadata
    - Extract chapters in reading order
    - Convert chapter HTML to markdown
    """

    def __init__(self) -> None:
        """Initialize extractor with HTML converter."""
        self._html_extractor = HtmlExtractor()

    def extract(self, content: bytes, filename: str) -> ExtractionResult:
        """Extract text content from EPUB file bytes.

        Args:
            content: Raw EPUB content as bytes.
            filename: Original filename.

        Returns:
            ExtractionResult with markdown content and metadata.
        """
        title = self._extract_title_from_filename(filename)

        # EPUB needs to be read from a file-like object or file
        try:
            book = self._read_epub(content)
        except Exception as e:
            # Fall back to plain text with warning
            return self._create_fallback_result(content, filename, title, str(e))

        # Extract metadata
        book_title = self._get_metadata(book, "title") or title
        author = self._get_metadata(book, "creator")
        language = self._get_metadata(book, "language") or "unknown"
        publisher = self._get_metadata(book, "publisher")

        # Extract chapters
        chapters = self._extract_chapters(book)
        chapter_count = len(chapters)

        # Build structural metadata
        structural_metadata: dict[str, Any] = {
            "title": book_title,
            "chapter_count": chapter_count,
            "language": language,
        }
        if author:
            structural_metadata["author"] = author
        if publisher:
            structural_metadata["publisher"] = publisher

        # Generate markdown
        markdown_body = self._generate_markdown(book_title, author, language, chapters)
        word_count = self._count_words(markdown_body)

        # Build frontmatter metadata
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "epub",
            "title": book_title,
            "chapter_count": chapter_count,
            "language": language,
        }
        if author:
            frontmatter_metadata["author"] = author
        if publisher:
            frontmatter_metadata["publisher"] = publisher

        frontmatter = self._generate_frontmatter(frontmatter_metadata)

        # Combine frontmatter and content
        markdown = f"{frontmatter}\n{markdown_body}"

        return ExtractionResult(
            markdown=markdown,
            file_type="epub",
            title=book_title,
            word_count=word_count,
            structural_metadata=structural_metadata,
            parse_warning=None,
        )

    def _read_epub(self, content: bytes) -> epub.EpubBook:
        """Read EPUB from bytes using temp file."""
        # ebooklib requires a file path, so we use a temp file
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=True) as tmp:
            tmp.write(content)
            tmp.flush()
            return epub.read_epub(tmp.name)

    def _get_metadata(self, book: epub.EpubBook, key: str) -> str | None:
        """Get metadata value from EPUB."""
        try:
            values = book.get_metadata("DC", key)
            if values:
                # Returns list of (value, attributes) tuples
                return values[0][0] if values[0] else None
        except Exception:
            pass
        return None

    def _extract_chapters(self, book: epub.EpubBook) -> list[tuple[str, str]]:
        """Extract chapters as (title, content) tuples."""
        chapters = []

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                # Get chapter content
                content = item.get_content()
                if isinstance(content, bytes):
                    try:
                        html = content.decode("utf-8")
                    except UnicodeDecodeError:
                        html = content.decode("latin-1")
                else:
                    html = str(content)

                # Extract title from item or content
                chapter_title = item.get_name() or f"Chapter {len(chapters) + 1}"

                # Convert HTML to markdown (simplified)
                text = self._html_to_markdown(html)

                if text.strip():  # Only include non-empty chapters
                    chapters.append((chapter_title, text))

        return chapters

    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML chapter content to markdown."""
        # Use the HTML extractor's sanitize and convert logic
        # For simplicity, we do basic conversion here
        import re

        # Remove script and style elements
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

        # Convert headings
        for i in range(1, 7):
            pattern = rf"<h{i}[^>]*>(.*?)</h{i}>"
            repl = "#" * i + r" \1\n"
            text = re.sub(pattern, repl, text, flags=re.DOTALL | re.IGNORECASE)

        # Convert paragraphs
        text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text, flags=re.DOTALL | re.IGNORECASE)

        # Convert line breaks
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

        # Remove remaining tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities
        import html as html_module

        text = html_module.unescape(text)

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _generate_markdown(
        self,
        title: str,
        author: str | None,
        language: str,
        chapters: list[tuple[str, str]],
    ) -> str:
        """Generate markdown from EPUB content."""
        lines = []

        # Title
        lines.append(f"# {title}")
        lines.append("")

        # Metadata
        if author:
            lines.append(f"**Author:** {author}")
        lines.append(f"**Language:** {language}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Chapters
        for chapter_title, content in chapters:
            # Add chapter heading if not already in content
            if not content.startswith("#"):
                lines.append(f"## {chapter_title}")
                lines.append("")
            lines.append(content)
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def _create_fallback_result(
        self, content: bytes, filename: str, title: str, error: str
    ) -> ExtractionResult:
        """Create fallback result when EPUB parsing fails."""
        text = self._decode_content(content)
        word_count = self._count_words(text)
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "epub",
            "parse_warning": f"EPUB parsing failed: {error}",
        }
        frontmatter = self._generate_frontmatter(frontmatter_metadata)
        markdown = f"{frontmatter}\nFailed to parse EPUB: {error}"

        return ExtractionResult(
            markdown=markdown,
            file_type="epub",
            title=title,
            word_count=word_count,
            structural_metadata={},
            parse_warning=f"EPUB parsing failed: {error}",
        )
