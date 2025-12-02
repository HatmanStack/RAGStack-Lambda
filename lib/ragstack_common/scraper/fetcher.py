"""
HTTP and Playwright fetching for web scraping.

Implements HTTP-first fetching with automatic Playwright fallback
for SPAs that require JavaScript rendering.
"""


async def fetch_page(
    url: str, cookies: dict | None = None, headers: dict | None = None
) -> tuple[str, int]:
    """
    Fetch a page using HTTP, falling back to Playwright if needed.

    Args:
        url: URL to fetch
        cookies: Optional cookies for authenticated sites
        headers: Optional custom headers

    Returns:
        Tuple of (html_content, status_code)

    Raises:
        FetchError: If fetching fails after retries
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("Page fetching not yet implemented")


async def fetch_with_http(
    url: str, cookies: dict | None = None, headers: dict | None = None
) -> tuple[str, int]:
    """
    Fetch a page using httpx.

    Args:
        url: URL to fetch
        cookies: Optional cookies
        headers: Optional headers

    Returns:
        Tuple of (html_content, status_code)
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("HTTP fetching not yet implemented")


async def fetch_with_playwright(url: str, cookies: dict | None = None) -> tuple[str, int]:
    """
    Fetch a page using Playwright for JavaScript rendering.

    Args:
        url: URL to fetch
        cookies: Optional cookies

    Returns:
        Tuple of (html_content, status_code)
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("Playwright fetching not yet implemented")


def is_spa(html: str) -> bool:
    """
    Detect if HTML indicates a Single Page Application.

    Heuristics:
    - Content length < 1000 chars after sanitization
    - Script tag count > 5
    - Presence of framework indicators (__NEXT_DATA__, window.__NUXT__, ng-app)

    Args:
        html: HTML content to check

    Returns:
        True if SPA detected, False otherwise
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("SPA detection not yet implemented")


class FetchError(Exception):
    """Error during page fetching."""

    def __init__(self, url: str, message: str, status_code: int | None = None):
        self.url = url
        self.status_code = status_code
        super().__init__(f"Failed to fetch {url}: {message}")
