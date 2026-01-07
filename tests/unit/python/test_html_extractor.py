"""Unit tests for HTML extractor."""

import pytest

from ragstack_common.text_extractors.base import ExtractionResult
from ragstack_common.text_extractors.html_extractor import HtmlExtractor
from tests.fixtures.text_extractor_samples import (
    FULL_HTML_PAGE,
    HTML_EMPTY,
    HTML_FRAGMENT,
    HTML_SCRIPTS_ONLY,
    HTML_WITH_CODE,
)


class TestHtmlExtractor:
    """Tests for HtmlExtractor."""

    def test_extracts_full_html_page(self):
        """Test extraction of full HTML page."""
        extractor = HtmlExtractor()
        result = extractor.extract(FULL_HTML_PAGE.encode(), "page.html")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "html"
        assert "Main Heading" in result.markdown
        assert "main content of the page" in result.markdown.lower()

    def test_extracts_title_from_og_title(self):
        """Test title extraction uses og:title first."""
        extractor = HtmlExtractor()
        result = extractor.extract(FULL_HTML_PAGE.encode(), "page.html")

        assert result.title == "OG Title for Testing"

    def test_removes_nav_and_footer(self):
        """Test that navigation and footer are removed."""
        extractor = HtmlExtractor()
        result = extractor.extract(FULL_HTML_PAGE.encode(), "page.html")

        # Nav content should be removed
        assert "Home" not in result.markdown
        assert "About" not in result.markdown
        # Footer content should be removed
        assert "Copyright 2024" not in result.markdown

    def test_removes_scripts_and_styles(self):
        """Test that scripts and styles are removed."""
        extractor = HtmlExtractor()
        result = extractor.extract(FULL_HTML_PAGE.encode(), "page.html")

        assert "alert" not in result.markdown
        assert "display: none" not in result.markdown

    def test_extracts_html_fragment(self):
        """Test extraction of HTML fragment without html/head/body."""
        extractor = HtmlExtractor()
        result = extractor.extract(HTML_FRAGMENT.encode(), "fragment.html")

        assert "Fragment Heading" in result.markdown
        assert "HTML fragment" in result.markdown

    def test_preserves_code_blocks(self):
        """Test that code blocks are preserved."""
        extractor = HtmlExtractor()
        result = extractor.extract(HTML_WITH_CODE.encode(), "code.html")

        assert "print" in result.markdown
        assert "Hello, World" in result.markdown

    def test_handles_empty_html(self):
        """Test handling of empty HTML document."""
        extractor = HtmlExtractor()
        result = extractor.extract(HTML_EMPTY.encode(), "empty.html")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "html"

    def test_handles_scripts_only_html(self):
        """Test handling of HTML with only scripts (no content)."""
        extractor = HtmlExtractor()
        result = extractor.extract(HTML_SCRIPTS_ONLY.encode(), "scripts.html")

        # Scripts should be removed, leaving minimal content
        assert isinstance(result, ExtractionResult)
        assert "console.log" not in result.markdown

    def test_generates_frontmatter(self):
        """Test that frontmatter is generated correctly."""
        extractor = HtmlExtractor()
        result = extractor.extract(FULL_HTML_PAGE.encode(), "page.html")

        assert result.markdown.startswith("---\n")
        assert "source_file: page.html" in result.markdown
        assert "file_type: html" in result.markdown

    def test_structural_metadata(self):
        """Test structural metadata includes relevant fields."""
        extractor = HtmlExtractor()
        result = extractor.extract(FULL_HTML_PAGE.encode(), "page.html")

        assert "has_main_element" in result.structural_metadata
        assert "original_size" in result.structural_metadata

    def test_converts_headings_to_markdown(self):
        """Test that HTML headings are converted to markdown headings."""
        extractor = HtmlExtractor()
        result = extractor.extract(FULL_HTML_PAGE.encode(), "page.html")

        # Should have markdown headings
        assert "# " in result.markdown or "## " in result.markdown

    def test_converts_lists_to_markdown(self):
        """Test that HTML lists are converted to markdown lists."""
        extractor = HtmlExtractor()
        result = extractor.extract(FULL_HTML_PAGE.encode(), "page.html")

        # Should have markdown list items
        assert "- " in result.markdown or "* " in result.markdown

    def test_title_fallback_to_title_tag(self):
        """Test title falls back to title tag when no og:title."""
        html_no_og = """<!DOCTYPE html>
        <html>
        <head><title>Title Tag Title</title></head>
        <body><main><p>Content</p></main></body>
        </html>"""
        extractor = HtmlExtractor()
        result = extractor.extract(html_no_og.encode(), "page.html")

        assert result.title == "Title Tag Title"

    def test_title_fallback_to_h1(self):
        """Test title falls back to h1 when no title tag."""
        html_h1_only = """<!DOCTYPE html>
        <html>
        <head></head>
        <body><main><h1>H1 Heading Title</h1><p>Content</p></main></body>
        </html>"""
        extractor = HtmlExtractor()
        result = extractor.extract(html_h1_only.encode(), "page.html")

        assert result.title == "H1 Heading Title"

    def test_title_fallback_to_filename(self):
        """Test title falls back to filename when no title found."""
        html_no_title = """<div><p>Just content, no title</p></div>"""
        extractor = HtmlExtractor()
        result = extractor.extract(html_no_title.encode(), "document.html")

        assert result.title == "document"

    def test_parse_warning_is_none_for_valid_html(self):
        """Test parse_warning is None for valid HTML."""
        extractor = HtmlExtractor()
        result = extractor.extract(FULL_HTML_PAGE.encode(), "page.html")

        assert result.parse_warning is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
