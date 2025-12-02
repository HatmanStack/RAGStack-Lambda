"""
URL discovery logic for web scraping.

Handles recursive URL discovery with scope enforcement, link extraction,
and visited URL tracking to avoid cycles.
"""

from ragstack_common.scraper.models import ScrapeConfig


def should_crawl(url: str, base_url: str, config: ScrapeConfig) -> bool:
    """
    Determine if a URL should be crawled based on scope and patterns.

    Args:
        url: URL to check
        base_url: Base URL of the scrape job
        config: Scrape configuration with scope and patterns

    Returns:
        True if URL should be crawled, False otherwise
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("URL scope checking not yet implemented")


def extract_links(html: str, page_url: str) -> list[str]:
    """
    Extract all links from HTML content.

    Args:
        html: HTML content to parse
        page_url: URL of the page (for resolving relative links)

    Returns:
        List of absolute URLs found in the page
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("Link extraction not yet implemented")


def normalize_url(url: str) -> str:
    """
    Normalize a URL for deduplication.

    Removes fragments, normalizes trailing slashes, lowercases hostname.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL string
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("URL normalization not yet implemented")


def get_url_depth(url: str, base_url: str) -> int:
    """
    Calculate the depth of a URL relative to the base URL.

    Args:
        url: URL to check
        base_url: Base URL of the scrape job

    Returns:
        Depth as integer (0 for base URL)
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("URL depth calculation not yet implemented")
