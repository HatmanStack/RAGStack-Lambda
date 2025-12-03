"""
HTTP and Playwright fetching for web scraping.

Implements HTTP-first fetching with automatic Playwright fallback
for SPAs that require JavaScript rendering.
"""

import logging
import time
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class FetchError(Exception):
    """Error during page fetching."""

    def __init__(self, url: str, message: str, status_code: int | None = None):
        self.url = url
        self.status_code = status_code
        super().__init__(f"Failed to fetch {url}: {message}")


@dataclass
class FetchResult:
    """Result of a page fetch operation."""

    url: str
    status_code: int
    content: str
    content_type: str
    is_html: bool
    error: str | None = None


class HttpFetcher:
    """HTTP fetcher with retry logic and configurable delays."""

    # User agent identifying as a respectful bot
    USER_AGENT = "RAGStack-Scraper/1.0 (+https://github.com/ragstack)"

    # Retryable status codes
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        delay_ms: int = 500,
        cookies: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ):
        """
        Initialize HTTP fetcher.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for retryable errors
            delay_ms: Delay between requests in milliseconds
            cookies: Optional cookies for authenticated sites
            headers: Optional custom headers
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay_ms = delay_ms
        self.cookies = cookies or {}
        self.headers = headers or {}

    def fetch(self, url: str) -> FetchResult:
        """
        Fetch URL with retries and delay.

        Args:
            url: URL to fetch

        Returns:
            FetchResult with content or error
        """
        # Apply request delay
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)

        last_error = None
        last_status = None

        for attempt in range(self.max_retries):
            try:
                return self._do_fetch(url)
            except httpx.HTTPStatusError as e:
                last_status = e.response.status_code
                last_error = str(e)

                if not self._should_retry(last_status):
                    # Non-retryable error
                    return FetchResult(
                        url=url,
                        status_code=last_status,
                        content="",
                        content_type="",
                        is_html=False,
                        error=f"HTTP {last_status}: {e.response.reason_phrase}",
                    )

                # Exponential backoff for retryable errors
                backoff = (2**attempt) * 1.0
                if last_status == 429:
                    # Longer backoff for rate limiting
                    backoff *= 2
                logger.warning(
                    f"Retry {attempt + 1}/{self.max_retries} for {url} "
                    f"(status={last_status}, backoff={backoff}s)"
                )
                time.sleep(backoff)

            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
                backoff = (2**attempt) * 1.0
                logger.warning(
                    f"Retry {attempt + 1}/{self.max_retries} for {url} "
                    f"(timeout, backoff={backoff}s)"
                )
                time.sleep(backoff)

            except httpx.RequestError as e:
                last_error = f"Request error: {e}"
                backoff = (2**attempt) * 1.0
                logger.warning(
                    f"Retry {attempt + 1}/{self.max_retries} for {url} "
                    f"(error={e}, backoff={backoff}s)"
                )
                time.sleep(backoff)

        # All retries exhausted
        return FetchResult(
            url=url,
            status_code=last_status or 0,
            content="",
            content_type="",
            is_html=False,
            error=last_error,
        )

    def _do_fetch(self, url: str) -> FetchResult:
        """Perform the actual HTTP fetch."""
        request_headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            **self.headers,
        }

        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            cookies=self.cookies,
        ) as client:
            response = client.get(url, headers=request_headers)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            is_html = "text/html" in content_type or "application/xhtml" in content_type

            return FetchResult(
                url=str(response.url),  # May differ from request URL due to redirects
                status_code=response.status_code,
                content=response.text,
                content_type=content_type,
                is_html=is_html,
            )

    def _should_retry(self, status_code: int) -> bool:
        """Check if status code is retryable."""
        return status_code in self.RETRYABLE_STATUS_CODES


def is_spa(html: str) -> bool:
    """
    Detect if HTML indicates a Single Page Application.

    Heuristics:
    - Content length < 500 chars after sanitization
    - Script tag count > 5
    - Presence of framework indicators (__NEXT_DATA__, window.__NUXT__, ng-app)

    Args:
        html: HTML content to check

    Returns:
        True if SPA detected, False otherwise
    """
    soup = BeautifulSoup(html, "lxml")

    # Count scripts before removing them
    script_count = len(soup.find_all("script"))

    # Remove script/style for content measurement
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text_content = soup.get_text(strip=True)

    # Framework indicators in original HTML
    indicators = [
        len(text_content) < 500,
        script_count > 5,
        "__NEXT_DATA__" in html,
        "window.__NUXT__" in html,
        "ng-app" in html,
        "data-reactroot" in html and len(text_content) < 1000,
        'id="__next"' in html and len(text_content) < 1000,
    ]

    # SPA if at least 2 indicators match
    return sum(indicators) >= 2


def fetch_with_playwright(url: str, cookies: dict[str, str] | None = None) -> FetchResult:
    """
    Fetch URL using Playwright for JavaScript rendering.

    Args:
        url: URL to fetch
        cookies: Optional cookies

    Returns:
        FetchResult with rendered content
    """
    try:
        # Import only when needed (Playwright layer may not be available)
        from playwright.sync_api import sync_playwright
    except ImportError:
        return FetchResult(
            url=url,
            status_code=0,
            content="",
            content_type="",
            is_html=False,
            error="Playwright not available - install playwright package",
        )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HttpFetcher.USER_AGENT,
            )

            if cookies:
                # Convert cookies dict to Playwright format
                cookie_list = [{"name": k, "value": v, "url": url} for k, v in cookies.items()]
                context.add_cookies(cookie_list)

            page = context.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=60000)

            content = page.content()
            status_code = response.status if response else 200

            browser.close()

            return FetchResult(
                url=url,
                status_code=status_code,
                content=content,
                content_type="text/html",
                is_html=True,
            )

    except Exception as e:
        logger.error(f"Playwright fetch failed for {url}: {e}")
        return FetchResult(
            url=url,
            status_code=0,
            content="",
            content_type="",
            is_html=False,
            error=f"Playwright error: {e}",
        )


def fetch_auto(
    url: str,
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    force_playwright: bool = False,
    delay_ms: int = 500,
) -> FetchResult:
    """
    Fetch with auto-detection: try HTTP first, fall back to Playwright if SPA.

    Args:
        url: URL to fetch
        cookies: Optional cookies
        headers: Optional headers
        force_playwright: Skip HTTP and use Playwright directly
        delay_ms: Delay between requests in milliseconds

    Returns:
        FetchResult with content or error
    """
    if force_playwright:
        return fetch_with_playwright(url, cookies)

    # Try HTTP first
    fetcher = HttpFetcher(cookies=cookies, headers=headers, delay_ms=delay_ms)
    result = fetcher.fetch(url)

    if result.error:
        return result

    if result.is_html and is_spa(result.content):
        logger.info(f"SPA detected for {url}, retrying with Playwright")
        playwright_result = fetch_with_playwright(url, cookies)

        # Only use Playwright result if successful
        if not playwright_result.error:
            return playwright_result

        # Fall back to HTTP result if Playwright fails
        logger.warning(
            f"Playwright fallback failed for {url}, using HTTP result: {playwright_result.error}"
        )

    return result


# Async variants for future use
async def fetch_with_http(
    url: str, cookies: dict | None = None, headers: dict | None = None
) -> tuple[str, int]:
    """
    Fetch a page using httpx async client.

    Args:
        url: URL to fetch
        cookies: Optional cookies
        headers: Optional headers

    Returns:
        Tuple of (html_content, status_code)
    """
    request_headers = {
        "User-Agent": HttpFetcher.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        **(headers or {}),
    }

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        cookies=cookies,
    ) as client:
        response = await client.get(url, headers=request_headers)
        response.raise_for_status()
        return response.text, response.status_code


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
    result = fetch_auto(url, cookies=cookies, headers=headers)
    if result.error:
        raise FetchError(url, result.error, result.status_code)
    return result.content, result.status_code
