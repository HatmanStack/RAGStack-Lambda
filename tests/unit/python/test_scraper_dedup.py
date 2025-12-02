"""Unit tests for content deduplication."""

import pytest

from ragstack_common.scraper.dedup import compute_content_hash, should_skip_page


class TestComputeContentHash:
    """Tests for compute_content_hash function."""

    def test_returns_sha256_hex(self):
        content = "Hello, World!"
        hash_value = compute_content_hash(content)
        # SHA-256 produces 64 hex characters
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_same_content_same_hash(self):
        content = "Test content"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        hash1 = compute_content_hash("Content A")
        hash2 = compute_content_hash("Content B")
        assert hash1 != hash2

    def test_empty_content(self):
        hash_value = compute_content_hash("")
        # SHA-256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert hash_value == expected


class TestShouldSkipPage:
    """Tests for should_skip_page function."""

    def test_new_page_not_skipped(self):
        assert should_skip_page("abc123", None) is False

    def test_same_hash_skipped(self):
        assert should_skip_page("abc123", "abc123") is True

    def test_different_hash_not_skipped(self):
        assert should_skip_page("abc123", "def456") is False


class TestNormalizeUrlForHash:
    """Tests for normalize_url_for_hash function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_removes_fragments(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_removes_query_params(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_normalizes_case(self):
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
