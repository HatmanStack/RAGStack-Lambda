"""
HTML extractor.

Extracts content from HTML files, reusing patterns from the web scraper module.
"""

from ..scraper.extractor import (
    extract_title,
    find_main_content,
    html_to_markdown,
    sanitize_html,
)
from .base import BaseExtractor, ExtractionResult


class HtmlExtractor(BaseExtractor):
    """Extract content from HTML files.

    Reuses the proven HTML sanitization and markdown conversion
    logic from the web scraper module.
    """

    def extract(self, content: bytes, filename: str) -> ExtractionResult:
        """Extract text content from HTML file bytes.

        Args:
            content: Raw HTML content as bytes.
            filename: Original filename.

        Returns:
            ExtractionResult with markdown content and metadata.
        """
        # Decode content
        html = self._decode_content(content)
        original_size = len(content)

        # Extract title (must happen before sanitization as title is in <head>)
        title = extract_title(html)
        if not title:
            title = self._extract_title_from_filename(filename)

        # Sanitize HTML (remove scripts, styles, nav, footer, etc.)
        soup = sanitize_html(html)

        # Find main content area
        main_content = find_main_content(soup)
        has_main_element = main_content.name == "main" if main_content else False

        # Convert to markdown
        markdown_body = html_to_markdown(str(main_content))

        # Count words
        word_count = self._count_words(markdown_body)

        # Build structural metadata
        structural_metadata = {
            "has_main_element": has_main_element,
            "original_size": original_size,
            "word_count": word_count,
        }

        # Build frontmatter metadata
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "html",
            "title": title,
            "word_count": word_count,
        }
        frontmatter = self._generate_frontmatter(frontmatter_metadata)

        # Combine frontmatter and content
        markdown = f"{frontmatter}\n{markdown_body}"

        return ExtractionResult(
            markdown=markdown,
            file_type="html",
            title=title,
            word_count=word_count,
            structural_metadata=structural_metadata,
            parse_warning=None,
        )
