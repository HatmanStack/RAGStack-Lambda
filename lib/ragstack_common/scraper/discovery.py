"""
URL discovery logic for web scraping.

Handles recursive URL discovery with scope enforcement, link extraction,
and visited URL tracking to avoid cycles.
"""

import fnmatch
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ragstack_common.scraper.models import ScrapeConfig, ScrapeScope


def normalize_url(url: str) -> str:
    """
    Normalize URL for deduplication.

    Removes fragments, normalizes trailing slashes, lowercases hostname.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL string
    """
    parsed = urlparse(url)

    # Lowercase hostname
    netloc = parsed.netloc.lower()

    # Remove trailing slash from path (except for root)
    path = parsed.path
    if path and path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Reconstruct without fragment, keep query params
    normalized = f"{parsed.scheme}://{netloc}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"

    return normalized


def extract_links(html: str, page_url: str) -> list[str]:
    """
    Extract all links from HTML content.

    Args:
        html: HTML content to parse
        page_url: URL of the page (for resolving relative links)

    Returns:
        List of absolute URLs found in the page
    """
    soup = BeautifulSoup(html, "lxml")
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Skip fragment-only links
        if href.startswith("#"):
            continue

        # Skip javascript: and mailto: links
        if href.startswith(("javascript:", "mailto:", "tel:", "data:")):
            continue

        # Resolve relative URLs
        absolute = urljoin(page_url, href)

        # Only include http/https URLs
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue

        # Normalize and add
        normalized = normalize_url(absolute)
        if normalized not in links:
            links.append(normalized)

    return links


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
    # First check if URL is within scope
    if not _is_in_scope(url, base_url, config.scope):
        return False

    # Check include patterns (if specified, URL must match at least one)
    if config.include_patterns and not matches_patterns(url, config.include_patterns):
        return False

    # Check exclude patterns (URL must not match any)
    return not (config.exclude_patterns and matches_patterns(url, config.exclude_patterns))


def _is_in_scope(url: str, base_url: str, scope: ScrapeScope) -> bool:
    """
    Check if URL is within the crawl scope.

    Args:
        url: URL to check
        base_url: Base URL of the scrape job
        scope: Scope enforcement level

    Returns:
        True if URL is within scope
    """
    url_parsed = urlparse(url)
    base_parsed = urlparse(base_url)

    url_host = url_parsed.netloc.lower()
    base_host = base_parsed.netloc.lower()

    if scope == ScrapeScope.SUBPAGES:
        # URL must have same hostname and path must start with base path
        if url_host != base_host:
            return False

        base_path = base_parsed.path.rstrip("/")
        url_path = url_parsed.path

        # If base has a path, URL path must start with it
        if base_path:
            return url_path == base_path or url_path.startswith(f"{base_path}/")
        return True

    if scope == ScrapeScope.HOSTNAME:
        # URL hostname must exactly match base hostname
        return url_host == base_host

    if scope == ScrapeScope.DOMAIN:
        # URL hostname must be same domain or subdomain
        # Extract domain (last two parts, e.g., example.com from sub.example.com)
        base_domain = _get_domain(base_host)
        url_domain = _get_domain(url_host)
        return url_domain == base_domain

    return False


def _get_domain(hostname: str) -> str:
    """
    Extract domain from hostname (e.g., 'sub.example.com' -> 'example.com').

    For simple TLDs, this extracts the last two parts.
    """
    parts = hostname.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return hostname


def matches_patterns(url: str, patterns: list[str]) -> bool:
    """
    Check if URL matches any of the glob patterns.

    Args:
        url: URL to check
        patterns: List of glob patterns

    Returns:
        True if URL matches at least one pattern
    """
    return any(fnmatch.fnmatch(url, pattern) for pattern in patterns)


def get_url_depth(url: str, base_url: str) -> int:
    """
    Calculate the depth of a URL relative to the base URL.

    Args:
        url: URL to check
        base_url: Base URL of the scrape job

    Returns:
        Depth as integer (0 for base URL)
    """
    url_parsed = urlparse(url)
    base_parsed = urlparse(base_url)

    # Different hostname means we can't calculate depth meaningfully
    if url_parsed.netloc.lower() != base_parsed.netloc.lower():
        return 0

    base_path = base_parsed.path.rstrip("/").split("/")
    url_path = url_parsed.path.rstrip("/").split("/")

    # Filter out empty segments
    base_path = [p for p in base_path if p]
    url_path = [p for p in url_path if p]

    # Depth is the number of additional path segments
    if len(url_path) >= len(base_path):
        # Check if base path is a prefix
        for i, segment in enumerate(base_path):
            if i >= len(url_path) or url_path[i] != segment:
                return len(url_path)
        return len(url_path) - len(base_path)

    return 0


def filter_discovered_urls(
    urls: list[str],
    base_url: str,
    config: ScrapeConfig,
    visited: set[str],
) -> list[str]:
    """
    Filter a list of discovered URLs based on scope, patterns, and visited set.

    Args:
        urls: List of discovered URLs to filter
        base_url: Base URL of the scrape job
        config: Scrape configuration
        visited: Set of already visited URLs

    Returns:
        Filtered list of URLs to crawl
    """
    filtered = []

    for url in urls:
        # Skip if already visited
        if url in visited:
            continue

        # Check if should crawl based on scope and patterns
        if not should_crawl(url, base_url, config):
            continue

        filtered.append(url)

    return filtered
