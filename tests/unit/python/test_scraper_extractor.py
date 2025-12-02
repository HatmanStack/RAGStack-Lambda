"""Unit tests for content extraction."""

import pytest


class TestExtractContent:
    """Tests for extract_content function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_adds_frontmatter(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_converts_to_markdown(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_preserves_code_blocks(self):
        pass


class TestSanitizeHtml:
    """Tests for sanitize_html function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_removes_script_tags(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_removes_style_tags(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_removes_nav(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_removes_footer(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_preserves_main_content(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_preserves_article(self):
        pass


class TestHtmlToMarkdown:
    """Tests for html_to_markdown function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_converts_headings(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_converts_lists(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_converts_links(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_converts_code_blocks(self):
        pass


class TestExtractTitle:
    """Tests for extract_title function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_extracts_title_tag(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_returns_none_if_missing(self):
        pass


class TestAddFrontmatter:
    """Tests for add_frontmatter function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_adds_source_url(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_adds_title_if_provided(self):
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
