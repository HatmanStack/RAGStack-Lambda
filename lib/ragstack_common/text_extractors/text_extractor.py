"""
Plain text extractor.

Simple extractor for .txt files that preserves content with basic metadata.
"""

from .base import BaseExtractor, ExtractionResult


class TextExtractor(BaseExtractor):
    """Extract content from plain text files.

    The simplest extractor - decodes content, counts basic metrics,
    and wraps in markdown format with frontmatter.
    """

    def extract(self, content: bytes, filename: str) -> ExtractionResult:
        """Extract text content from file bytes.

        Args:
            content: Raw file content as bytes.
            filename: Original filename.

        Returns:
            ExtractionResult with markdown content and metadata.
        """
        # Decode content
        text = self._decode_content(content)

        # Extract metadata
        title = self._extract_title_from_filename(filename)
        lines = text.split("\n")
        line_count = len(lines)
        word_count = self._count_words(text)
        char_count = len(text)

        # Build structural metadata
        structural_metadata = {
            "line_count": line_count,
            "word_count": word_count,
            "char_count": char_count,
        }

        # Build frontmatter metadata
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "txt",
            "word_count": word_count,
            "line_count": line_count,
        }
        frontmatter = self._generate_frontmatter(frontmatter_metadata)

        # Combine frontmatter and content
        markdown = f"{frontmatter}\n{text}"

        return ExtractionResult(
            markdown=markdown,
            file_type="txt",
            title=title,
            word_count=word_count,
            structural_metadata=structural_metadata,
            parse_warning=None,
        )
