"""
Integration tests for web scraping pipeline.

These tests require running against real AWS resources or LocalStack.
Run with: pytest -m integration
"""

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestScrapeDiscoveryIntegration:
    """Integration tests for URL discovery."""

    def test_discovery_extracts_links_from_live_page(self):
        """Test that discovery correctly extracts links from a test page."""
        from ragstack_common.scraper.discovery import extract_links, normalize_url
        from ragstack_common.scraper.fetcher import HttpFetcher

        # Use a stable public page for testing
        test_url = "https://example.com"

        fetcher = HttpFetcher(delay_ms=0)
        result = fetcher.fetch(test_url)

        assert result.error is None, f"Fetch failed: {result.error}"
        assert result.is_html

        # Extract links
        links = extract_links(result.content, test_url)

        # example.com has at least one link to IANA
        assert len(links) >= 1


class TestContentExtractionIntegration:
    """Integration tests for content extraction."""

    def test_extraction_from_live_page(self):
        """Test full extraction pipeline on a live page."""
        from ragstack_common.scraper.extractor import extract_content
        from ragstack_common.scraper.fetcher import HttpFetcher

        test_url = "https://example.com"

        fetcher = HttpFetcher(delay_ms=0)
        result = fetcher.fetch(test_url)

        assert result.error is None

        extracted = extract_content(result.content, test_url)

        assert extracted.title is not None
        assert "example" in extracted.title.lower()
        assert extracted.word_count > 0
        assert "source_url: https://example.com" in extracted.markdown


class TestDeduplicationIntegration:
    """Integration tests for deduplication."""

    def test_content_hash_consistency(self):
        """Test that content hashing is consistent across runs."""
        from ragstack_common.scraper.dedup import (
            compute_content_hash,
            normalize_content_for_hash,
        )

        content = """---
source_url: https://example.com
scraped_at: 2024-01-01T00:00:00Z
---

# Test Title

Some content here.
"""
        normalized1 = normalize_content_for_hash(content)
        hash1 = compute_content_hash(normalized1)

        # Same content, different scraped_at
        content2 = content.replace("2024-01-01", "2024-12-31")
        normalized2 = normalize_content_for_hash(content2)
        hash2 = compute_content_hash(normalized2)

        # Hashes should be equal (frontmatter removed)
        assert hash1 == hash2


class TestEndToEndPipeline:
    """End-to-end integration tests."""

    def test_full_scrape_single_page(self):
        """Test complete scrape pipeline for a single page."""
        from ragstack_common.scraper.dedup import compute_content_hash, normalize_content_for_hash
        from ragstack_common.scraper.extractor import extract_content
        from ragstack_common.scraper.fetcher import fetch_auto

        test_url = "https://example.com"

        # Step 1: Fetch
        result = fetch_auto(test_url, delay_ms=0)
        assert result.error is None
        assert result.is_html

        # Step 2: Extract
        extracted = extract_content(result.content, test_url)
        assert extracted.title is not None
        assert extracted.markdown is not None
        assert len(extracted.markdown) > 100

        # Step 3: Compute hash for dedup
        normalized = normalize_content_for_hash(extracted.markdown)
        content_hash = compute_content_hash(normalized)
        assert len(content_hash) == 64

        # Verify markdown has frontmatter
        assert "---" in extracted.markdown
        assert "source_url:" in extracted.markdown


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
