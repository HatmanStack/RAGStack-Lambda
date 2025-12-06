"""Unit tests for URL discovery logic."""

import pytest

from ragstack_common.scraper.discovery import (
    extract_links,
    filter_discovered_urls,
    get_url_depth,
    matches_patterns,
    normalize_url,
    should_crawl,
)
from ragstack_common.scraper.models import ScrapeConfig, ScrapeScope


class TestNormalizeUrl:
    """Tests for normalize_url function."""

    def test_removes_fragments(self):
        url = "https://example.com/page#section"
        assert normalize_url(url) == "https://example.com/page"

    def test_normalizes_trailing_slash(self):
        url = "https://example.com/page/"
        assert normalize_url(url) == "https://example.com/page"

    def test_preserves_root_trailing_slash(self):
        # Root path should keep its form
        url = "https://example.com/"
        result = normalize_url(url)
        # Either https://example.com/ or https://example.com is acceptable
        assert result in ("https://example.com/", "https://example.com")

    def test_lowercases_hostname(self):
        url = "https://EXAMPLE.COM/Page"
        result = normalize_url(url)
        assert "example.com" in result
        # Path case should be preserved
        assert "/Page" in result

    def test_preserves_query_params(self):
        url = "https://example.com/page?foo=bar"
        assert normalize_url(url) == "https://example.com/page?foo=bar"

    def test_complex_url(self):
        url = "https://EXAMPLE.COM/path/to/page/?query=value#fragment"
        result = normalize_url(url)
        assert result == "https://example.com/path/to/page?query=value"


class TestExtractLinks:
    """Tests for extract_links function."""

    def test_extracts_anchor_hrefs(self):
        html = '<html><body><a href="https://example.com/page1">Link</a></body></html>'
        links = extract_links(html, "https://example.com/")
        assert "https://example.com/page1" in links

    def test_resolves_relative_links(self):
        html = '<html><body><a href="/page">Link</a></body></html>'
        links = extract_links(html, "https://example.com/base/")
        assert "https://example.com/page" in links

    def test_resolves_relative_paths(self):
        html = '<html><body><a href="subpage">Link</a></body></html>'
        links = extract_links(html, "https://example.com/docs/")
        assert "https://example.com/docs/subpage" in links

    def test_ignores_fragment_only_links(self):
        html = '<html><body><a href="#section">Link</a></body></html>'
        links = extract_links(html, "https://example.com/")
        assert len(links) == 0

    def test_ignores_javascript_links(self):
        html = '<html><body><a href="javascript:void(0)">Link</a></body></html>'
        links = extract_links(html, "https://example.com/")
        assert len(links) == 0

    def test_ignores_mailto_links(self):
        html = '<html><body><a href="mailto:test@example.com">Link</a></body></html>'
        links = extract_links(html, "https://example.com/")
        assert len(links) == 0

    def test_extracts_multiple_links(self):
        html = """
        <html><body>
            <a href="/page1">Link 1</a>
            <a href="/page2">Link 2</a>
            <a href="https://other.com">External</a>
        </body></html>
        """
        links = extract_links(html, "https://example.com/")
        assert len(links) == 3
        assert "https://example.com/page1" in links
        assert "https://example.com/page2" in links
        assert "https://other.com" in links

    def test_deduplicates_links(self):
        html = """
        <html><body>
            <a href="/page">Link 1</a>
            <a href="/page">Link 2</a>
            <a href="/page/">Link 3</a>
        </body></html>
        """
        links = extract_links(html, "https://example.com/")
        # All three should normalize to the same URL
        assert links.count("https://example.com/page") == 1

    def test_empty_html(self):
        links = extract_links("", "https://example.com/")
        assert links == []


class TestShouldCrawl:
    """Tests for should_crawl function."""

    def test_same_hostname_allowed(self):
        config = ScrapeConfig(scope=ScrapeScope.HOSTNAME)
        assert should_crawl(
            "https://example.com/page",
            "https://example.com/",
            config,
        )

    def test_different_hostname_blocked(self):
        config = ScrapeConfig(scope=ScrapeScope.HOSTNAME)
        assert not should_crawl(
            "https://other.com/page",
            "https://example.com/",
            config,
        )

    def test_subpages_scope_same_path(self):
        config = ScrapeConfig(scope=ScrapeScope.SUBPAGES)
        assert should_crawl(
            "https://example.com/docs/page",
            "https://example.com/docs/",
            config,
        )

    def test_subpages_scope_different_path(self):
        config = ScrapeConfig(scope=ScrapeScope.SUBPAGES)
        assert not should_crawl(
            "https://example.com/blog/post",
            "https://example.com/docs/",
            config,
        )

    def test_subpages_scope_exact_base(self):
        config = ScrapeConfig(scope=ScrapeScope.SUBPAGES)
        assert should_crawl(
            "https://example.com/docs",
            "https://example.com/docs",
            config,
        )

    def test_domain_scope_includes_subdomains(self):
        config = ScrapeConfig(scope=ScrapeScope.DOMAIN)
        assert should_crawl(
            "https://blog.example.com/post",
            "https://example.com/",
            config,
        )

    def test_domain_scope_different_domain(self):
        config = ScrapeConfig(scope=ScrapeScope.DOMAIN)
        assert not should_crawl(
            "https://other.com/page",
            "https://example.com/",
            config,
        )

    def test_include_patterns(self):
        config = ScrapeConfig(
            scope=ScrapeScope.HOSTNAME,
            include_patterns=["*/docs/*"],
        )
        assert should_crawl(
            "https://example.com/docs/page",
            "https://example.com/",
            config,
        )
        assert not should_crawl(
            "https://example.com/blog/page",
            "https://example.com/",
            config,
        )

    def test_exclude_patterns(self):
        config = ScrapeConfig(
            scope=ScrapeScope.HOSTNAME,
            exclude_patterns=["*/login*", "*/admin/*"],
        )
        assert should_crawl(
            "https://example.com/docs/page",
            "https://example.com/",
            config,
        )
        assert not should_crawl(
            "https://example.com/login",
            "https://example.com/",
            config,
        )
        assert not should_crawl(
            "https://example.com/admin/dashboard",
            "https://example.com/",
            config,
        )


class TestMatchesPatterns:
    """Tests for matches_patterns function."""

    def test_matches_glob_star(self):
        assert matches_patterns("https://example.com/docs/page", ["*/docs/*"])

    def test_matches_exact(self):
        assert matches_patterns("https://example.com/page", ["https://example.com/page"])

    def test_no_match(self):
        assert not matches_patterns("https://example.com/page", ["*/other/*"])

    def test_multiple_patterns(self):
        patterns = ["*/docs/*", "*/api/*"]
        assert matches_patterns("https://example.com/api/v1", patterns)


class TestGetUrlDepth:
    """Tests for get_url_depth function."""

    def test_base_url_depth_zero(self):
        assert get_url_depth("https://example.com/", "https://example.com/") == 0

    def test_subpage_depth(self):
        assert get_url_depth("https://example.com/docs", "https://example.com/") == 1
        assert get_url_depth("https://example.com/docs/page", "https://example.com/") == 2

    def test_depth_relative_to_base(self):
        assert (
            get_url_depth(
                "https://example.com/docs/api/v1",
                "https://example.com/docs",
            )
            == 2
        )

    def test_different_hostname_zero_depth(self):
        assert get_url_depth("https://other.com/page", "https://example.com/") == 0


class TestFilterDiscoveredUrls:
    """Tests for filter_discovered_urls function."""

    def test_filters_visited(self):
        config = ScrapeConfig(scope=ScrapeScope.HOSTNAME)
        urls = ["https://example.com/page1", "https://example.com/page2"]
        visited = {"https://example.com/page1"}

        filtered = filter_discovered_urls(urls, "https://example.com/", config, visited)
        assert "https://example.com/page1" not in filtered
        assert "https://example.com/page2" in filtered

    def test_filters_out_of_scope(self):
        config = ScrapeConfig(scope=ScrapeScope.HOSTNAME)
        urls = ["https://example.com/page", "https://other.com/page"]

        filtered = filter_discovered_urls(urls, "https://example.com/", config, set())
        assert "https://example.com/page" in filtered
        assert "https://other.com/page" not in filtered

    def test_empty_urls(self):
        config = ScrapeConfig()
        filtered = filter_discovered_urls([], "https://example.com/", config, set())
        assert filtered == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
