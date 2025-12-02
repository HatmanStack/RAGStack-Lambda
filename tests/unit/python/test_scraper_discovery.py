"""Unit tests for URL discovery logic."""

import pytest


class TestShouldCrawl:
    """Tests for should_crawl function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_same_hostname_allowed(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_different_hostname_blocked(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_subpages_scope(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_domain_scope_includes_subdomains(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_include_patterns(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_exclude_patterns(self):
        pass


class TestExtractLinks:
    """Tests for extract_links function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_extracts_anchor_hrefs(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_resolves_relative_links(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_ignores_fragment_only_links(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_ignores_javascript_links(self):
        pass


class TestNormalizeUrl:
    """Tests for normalize_url function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_removes_fragments(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_normalizes_trailing_slash(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_lowercases_hostname(self):
        pass


class TestGetUrlDepth:
    """Tests for get_url_depth function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_base_url_depth_zero(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_subpage_depth(self):
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
