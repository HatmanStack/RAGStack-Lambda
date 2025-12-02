"""Unit tests for HTTP/Playwright fetcher."""

import pytest


class TestFetchPage:
    """Tests for fetch_page function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_successful_fetch(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_handles_404(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_retries_on_timeout(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_fallback_to_playwright(self):
        pass


class TestFetchWithHttp:
    """Tests for fetch_with_http function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_passes_cookies(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_passes_headers(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_follows_redirects(self):
        pass


class TestIsSpa:
    """Tests for is_spa detection function."""

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_detects_nextjs(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_detects_nuxt(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_detects_angular(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_static_html_not_spa(self):
        pass

    @pytest.mark.skip(reason="Not implemented - Phase 2")
    def test_many_scripts_is_spa(self):
        pass


class TestFetchError:
    """Tests for FetchError exception."""

    def test_error_message(self):
        from ragstack_common.scraper.fetcher import FetchError

        error = FetchError("https://example.com", "Connection refused")
        assert "https://example.com" in str(error)
        assert "Connection refused" in str(error)
        assert error.url == "https://example.com"

    def test_with_status_code(self):
        from ragstack_common.scraper.fetcher import FetchError

        error = FetchError("https://example.com", "Not found", status_code=404)
        assert error.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
