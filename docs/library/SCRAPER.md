# Web Scraper Module

Web scraping for ingesting documentation sites into the knowledge base.

## scraper/

```python
from ragstack_common.scraper import ScrapeJob, ScrapeConfig, ScrapeStatus, ScrapeScope

class ScrapeStatus(str, Enum):
    PENDING, DISCOVERING, PROCESSING, COMPLETED, COMPLETED_WITH_ERRORS, FAILED, CANCELLED

class ScrapeScope(str, Enum):
    SUBPAGES  # Only paths under starting URL
    HOSTNAME  # Same subdomain
    DOMAIN    # All subdomains

@dataclass
class ScrapeConfig:
    max_pages: int = 100
    max_depth: int = 3
    scope: ScrapeScope = ScrapeScope.SUBPAGES
    include_patterns: list[str] = None
    exclude_patterns: list[str] = None
    scrape_mode: str = "auto"  # auto, fast, full
    cookies: str | None = None
    force_rescrape: bool = False

@dataclass
class ScrapeJob:
    job_id: str
    base_url: str
    status: ScrapeStatus
    config: ScrapeConfig
    total_urls: int
    processed_count: int
    failed_count: int
```

**Architecture:** Discovery via SQS, HTTP-first fetching with Playwright fallback, SHA-256 content deduplication.

## Overview

The scraper module enables ingesting entire documentation sites or website sections into the knowledge base. It crawls pages, extracts content as markdown, and handles deduplication. Designed for technical documentation, blogs, and knowledge bases.

## Data Models

### ScrapeStatus

```python
class ScrapeStatus(str, Enum):
    PENDING = "PENDING"               # Job created, not started
    DISCOVERING = "DISCOVERING"       # Finding URLs to scrape
    PROCESSING = "PROCESSING"         # Scraping pages
    COMPLETED = "COMPLETED"           # All pages processed successfully
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"  # Some pages failed
    FAILED = "FAILED"                # Job failed completely
    CANCELLED = "CANCELLED"          # User cancelled job
```

### ScrapeScope

```python
class ScrapeScope(str, Enum):
    SUBPAGES = "SUBPAGES"   # Only URLs under starting path
    HOSTNAME = "HOSTNAME"   # Same subdomain (e.g., docs.example.com)
    DOMAIN = "DOMAIN"       # All subdomains (e.g., *.example.com)
```

**Examples:**

Starting URL: `https://docs.example.com/api/`

| Scope | Includes | Excludes |
|-------|----------|----------|
| SUBPAGES | `docs.example.com/api/*` | `docs.example.com/blog/*` |
| HOSTNAME | `docs.example.com/*` | `www.example.com/*` |
| DOMAIN | `*.example.com/*` | `other-site.com/*` |

### ScrapeConfig

```python
@dataclass
class ScrapeConfig:
    max_pages: int = 100
    max_depth: int = 3
    scope: ScrapeScope = ScrapeScope.SUBPAGES
    include_patterns: list[str] = None      # Regex patterns to include
    exclude_patterns: list[str] = None      # Regex patterns to exclude
    scrape_mode: str = "auto"               # auto, fast, full
    cookies: str | None = None              # Cookie string for auth
    force_rescrape: bool = False            # Ignore cached content
```

**scrape_mode:**
- `auto`: HTTP first, fallback to Playwright for dynamic content
- `fast`: HTTP only (faster, may miss dynamic content)
- `full`: Always use Playwright (slower, handles JavaScript)

### ScrapeJob

```python
@dataclass
class ScrapeJob:
    job_id: str              # Unique job identifier
    base_url: str            # Starting URL
    status: ScrapeStatus     # Current job status
    config: ScrapeConfig     # Scraping configuration
    total_urls: int          # Total URLs discovered
    processed_count: int     # URLs successfully processed
    failed_count: int        # URLs that failed
```

## Usage

### Basic Scraping

```python
from ragstack_common.scraper import ScrapeJob, ScrapeConfig, ScrapeScope, ScrapeStatus

# Create config
config = ScrapeConfig(
    max_pages=50,
    max_depth=2,
    scope=ScrapeScope.SUBPAGES,
    scrape_mode="auto"
)

# Create job
job = ScrapeJob(
    job_id="scrape-123",
    base_url="https://docs.example.com/api/",
    status=ScrapeStatus.PENDING,
    config=config,
    total_urls=0,
    processed_count=0,
    failed_count=0
)
```

### Scope Examples

#### Subpages Only

```python
config = ScrapeConfig(
    scope=ScrapeScope.SUBPAGES,
    max_pages=100
)

# Starting URL: https://docs.example.com/api/
# Scrapes: /api/overview, /api/authentication, /api/endpoints/...
# Skips: /blog/, /about/, /pricing/
```

#### Same Subdomain

```python
config = ScrapeConfig(
    scope=ScrapeScope.HOSTNAME,
    max_pages=200
)

# Starting URL: https://docs.example.com/api/
# Scrapes: /api/*, /guides/*, /tutorials/*
# Skips: www.example.com/*, blog.example.com/*
```

#### All Subdomains

```python
config = ScrapeConfig(
    scope=ScrapeScope.DOMAIN,
    max_pages=500
)

# Starting URL: https://docs.example.com/
# Scrapes: docs.example.com/*, blog.example.com/*, www.example.com/*
# Skips: other-domain.com/*
```

### URL Filtering

#### Include Patterns

```python
config = ScrapeConfig(
    include_patterns=[
        r"/api/.*",           # Include all API docs
        r"/guides/.*",        # Include all guides
        r".*\.html$"          # Include only HTML files
    ]
)
```

#### Exclude Patterns

```python
config = ScrapeConfig(
    exclude_patterns=[
        r".*/archive/.*",     # Skip archived pages
        r".*/draft/.*",       # Skip draft pages
        r".*\.pdf$",          # Skip PDFs
        r".*/comments.*"      # Skip comment sections
    ]
)
```

#### Combined Filtering

```python
config = ScrapeConfig(
    scope=ScrapeScope.HOSTNAME,
    include_patterns=[r"/docs/.*"],
    exclude_patterns=[r".*/v1/.*", r".*/deprecated/.*"],
    max_pages=200
)

# Scrapes: /docs/api/, /docs/guides/
# Skips: /docs/v1/*, /docs/deprecated/*, /blog/*
```

### Scrape Modes

#### Auto Mode (Recommended)

```python
config = ScrapeConfig(scrape_mode="auto")

# Tries HTTP first (fast)
# Falls back to Playwright if:
# - Content is JavaScript-rendered
# - Page requires browser features
# - HTTP fetch fails
```

#### Fast Mode

```python
config = ScrapeConfig(scrape_mode="fast")

# HTTP only
# Pros: 5-10x faster, lower resource usage
# Cons: Misses JavaScript-rendered content
# Use for: Static sites, server-rendered docs
```

#### Full Mode

```python
config = ScrapeConfig(scrape_mode="full")

# Always uses Playwright browser
# Pros: Handles all dynamic content
# Cons: Slower, higher resource usage
# Use for: Single-page apps, heavily dynamic sites
```

### Authentication

```python
config = ScrapeConfig(
    cookies="session=abc123; auth_token=xyz789"
)

# Passes cookies to all requests
# Use for: Authenticated documentation, private wikis
```

**Note:** Cookie format is standard HTTP cookie string (semicolon-separated)

### Force Rescrape

```python
config = ScrapeConfig(force_rescrape=True)

# Ignores content hash cache
# Scrapes even if content unchanged
# Use for: Testing, forcing updates
```

## Content Deduplication

The scraper uses SHA-256 content hashing to prevent duplicate ingestion:

```python
# Content hash computed from:
# - Main content text (excludes navigation, footer, etc.)
# - URL path (normalized)

# Example:
# URL 1: https://docs.example.com/api/authentication
# URL 2: https://docs.example.com/api/authentication?utm_source=email
# If content identical → only scrapes once
```

**Deduplication rules:**
- Same content, different URLs → scrapes once, uses canonical URL
- Same URL, different content → rescrapes if hash differs
- `force_rescrape=True` → bypasses hash check

## Discovery Architecture

```
User initiates scrape
    ↓
Discovery Lambda
    ├─ Fetch starting URL
    ├─ Extract links
    ├─ Apply scope/filters
    └─ Send URLs to SQS queue
         ↓
Processing Lambda (parallel)
    ├─ Fetch page content
    ├─ Extract markdown
    ├─ Check content hash
    ├─ Save to S3
    └─ Update job progress
```

**Benefits:**
- Parallel processing (10-100 concurrent fetches)
- Resilient to failures (SQS retries)
- Scalable (handles 1,000+ page sites)

## Complete Example

```python
from ragstack_common.scraper import ScrapeJob, ScrapeConfig, ScrapeScope, ScrapeStatus

def scrape_documentation_site():
    """
    Scrape Python documentation site.
    """
    config = ScrapeConfig(
        # Limit to 500 pages
        max_pages=500,

        # Depth 3 from starting URL
        max_depth=3,

        # Stay within docs.python.org
        scope=ScrapeScope.HOSTNAME,

        # Include only current version docs
        include_patterns=[r"/3/.*"],

        # Exclude tutorials and archives
        exclude_patterns=[r".*/tutorial/.*", r".*/archive/.*"],

        # Auto mode for optimal speed/completeness
        scrape_mode="auto",

        # Don't force rescrape (use cache)
        force_rescrape=False
    )

    job = ScrapeJob(
        job_id="scrape-python-docs",
        base_url="https://docs.python.org/3/",
        status=ScrapeStatus.PENDING,
        config=config,
        total_urls=0,
        processed_count=0,
        failed_count=0
    )

    return job
```

## Progress Tracking

```python
# Check job progress
if job.status == ScrapeStatus.PROCESSING:
    progress = job.processed_count / job.total_urls
    print(f"Progress: {progress:.1%} ({job.processed_count}/{job.total_urls})")
    print(f"Failed: {job.failed_count}")

# Check completion
if job.status == ScrapeStatus.COMPLETED:
    print(f"Scrape complete: {job.processed_count} pages")
elif job.status == ScrapeStatus.COMPLETED_WITH_ERRORS:
    print(f"Scrape complete with {job.failed_count} failures")
elif job.status == ScrapeStatus.FAILED:
    print("Scrape failed")
```

## Error Handling

```python
from ragstack_common.scraper import ScrapeJob, ScrapeStatus

# Partial failures
if job.status == ScrapeStatus.COMPLETED_WITH_ERRORS:
    success_rate = job.processed_count / (job.processed_count + job.failed_count)
    if success_rate > 0.9:
        print("Scrape mostly successful")
    else:
        print(f"High failure rate: {job.failed_count} of {job.total_urls}")

# Complete failure
if job.status == ScrapeStatus.FAILED:
    # Check if base URL accessible
    # Check scope settings (too restrictive?)
    # Check authentication (cookies expired?)
    pass
```

**Common issues:**
- **0 pages scraped**: Scope too restrictive, include patterns too narrow
- **High failure rate**: Site blocking bot traffic, rate limiting
- **Missing content**: `scrape_mode="fast"` on JavaScript-heavy site

## Best Practices

1. **Start Small**: Test with `max_pages=10` before full scrape
2. **Scope Appropriately**: Use SUBPAGES for documentation subsections
3. **Use Patterns**: Combine include/exclude patterns for precise control
4. **Choose Mode Wisely**: Use `auto` unless you know site is static or fully dynamic
5. **Monitor Progress**: Track `processed_count` and `failed_count`
6. **Handle Errors**: Expect some failures on large sites (broken links, 404s)
7. **Respect Rate Limits**: Use reasonable `max_pages` to avoid overwhelming sites
8. **Cache**: Set `force_rescrape=False` to leverage content hashing

## See Also

- [STORAGE.md](./STORAGE.md) - S3 storage for scraped content
- [TEXT_EXTRACTORS.md](./TEXT_EXTRACTORS.md) - HTML to markdown conversion
- [appsync.py](./UTILITIES.md#appsync) - Scrape job progress updates
