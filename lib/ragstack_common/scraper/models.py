"""
Data models for web scraping pipeline.

These models represent scrape jobs and pages as they flow through the pipeline:
start -> discovery -> processing -> ingestion
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ScrapeStatus(str, Enum):
    """Processing status for scrape jobs."""

    PENDING = "pending"
    DISCOVERING = "discovering"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UrlStatus(str, Enum):
    """Processing status for individual URLs."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ScrapeScope(str, Enum):
    """URL scope enforcement for crawling."""

    SUBPAGES = "subpages"  # Only URLs under the base path
    HOSTNAME = "hostname"  # Any URL on the same hostname
    DOMAIN = "domain"  # Any URL on the same domain (includes subdomains)


@dataclass
class ScrapeConfig:
    """
    Configuration for a scrape job.

    Attributes:
        max_pages: Maximum number of pages to scrape
        max_depth: Maximum crawl depth from base URL
        scope: URL scope enforcement level
        request_delay_ms: Delay between requests in milliseconds
        include_patterns: Glob patterns for URLs to include
        exclude_patterns: Glob patterns for URLs to exclude
        cookies: Optional cookies for authenticated sites
        headers: Optional custom headers
    """

    max_pages: int = 1000
    max_depth: int = 3
    scope: ScrapeScope = ScrapeScope.SUBPAGES
    request_delay_ms: int = 500
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage."""
        return {
            "max_pages": self.max_pages,
            "max_depth": self.max_depth,
            "scope": self.scope.value,
            "request_delay_ms": self.request_delay_ms,
            "include_patterns": self.include_patterns,
            "exclude_patterns": self.exclude_patterns,
            "cookies": self.cookies,
            "headers": self.headers,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScrapeConfig":
        """Create ScrapeConfig from dictionary."""
        return cls(
            max_pages=data.get("max_pages", 1000),
            max_depth=data.get("max_depth", 3),
            scope=ScrapeScope(data.get("scope", "subpages")),
            request_delay_ms=data.get("request_delay_ms", 500),
            include_patterns=data.get("include_patterns", []),
            exclude_patterns=data.get("exclude_patterns", []),
            cookies=data.get("cookies", {}),
            headers=data.get("headers", {}),
        )


@dataclass
class ScrapeJob:
    """
    Main scrape job container tracking state through the pipeline.

    Attributes:
        job_id: Unique identifier (UUID)
        base_url: Starting URL for the scrape
        status: Current processing status
        config: Job configuration
        title: Job name (extracted from page title)
        total_urls: Total discovered URLs
        processed_count: Successfully processed URLs
        failed_count: Failed URLs
        failed_urls: List of failed URL strings with errors
        step_function_arn: Step Functions execution ARN
        created_at: Job creation timestamp
        updated_at: Last update timestamp
    """

    job_id: str
    base_url: str
    status: ScrapeStatus = ScrapeStatus.PENDING
    config: ScrapeConfig = field(default_factory=ScrapeConfig)
    title: str | None = None
    total_urls: int = 0
    processed_count: int = 0
    failed_count: int = 0
    failed_urls: list[dict[str, str]] = field(default_factory=list)
    step_function_arn: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage."""
        data = {
            "job_id": self.job_id,
            "base_url": self.base_url,
            "status": self.status.value,
            "config": self.config.to_dict(),
            "total_urls": self.total_urls,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "failed_urls": self.failed_urls,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

        if self.title:
            data["title"] = self.title
        if self.step_function_arn:
            data["step_function_arn"] = self.step_function_arn

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScrapeJob":
        """Create ScrapeJob from DynamoDB record."""
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")

        return cls(
            job_id=data["job_id"],
            base_url=data["base_url"],
            status=ScrapeStatus(data.get("status", "pending")),
            config=ScrapeConfig.from_dict(data.get("config", {})),
            title=data.get("title"),
            total_urls=data.get("total_urls", 0),
            processed_count=data.get("processed_count", 0),
            failed_count=data.get("failed_count", 0),
            failed_urls=data.get("failed_urls", []),
            step_function_arn=data.get("step_function_arn"),
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.now(UTC),
            updated_at=datetime.fromisoformat(updated_at) if updated_at else datetime.now(UTC),
        )


@dataclass
class ScrapePage:
    """
    Represents a single scraped page.

    Attributes:
        job_id: Parent scrape job ID
        url: Full URL of the page
        status: Processing status
        depth: Crawl depth from base URL
        content_hash: SHA-256 hash of extracted content
        document_id: UUID of created document (after S3 upload)
        title: Page title
        error: Error message if failed
        discovered_at: When URL was discovered
        processed_at: When page was processed
    """

    job_id: str
    url: str
    status: UrlStatus = UrlStatus.PENDING
    depth: int = 0
    content_hash: str | None = None
    document_id: str | None = None
    title: str | None = None
    error: str | None = None
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage."""
        data = {
            "job_id": self.job_id,
            "url": self.url,
            "status": self.status.value,
            "depth": self.depth,
            "discovered_at": self.discovered_at.isoformat(),
        }

        if self.content_hash:
            data["content_hash"] = self.content_hash
        if self.document_id:
            data["document_id"] = self.document_id
        if self.title:
            data["title"] = self.title
        if self.error:
            data["error"] = self.error
        if self.processed_at:
            data["processed_at"] = self.processed_at.isoformat()

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScrapePage":
        """Create ScrapePage from DynamoDB record."""
        discovered_at = data.get("discovered_at")
        processed_at = data.get("processed_at")

        return cls(
            job_id=data["job_id"],
            url=data["url"],
            status=UrlStatus(data.get("status", "pending")),
            depth=data.get("depth", 0),
            content_hash=data.get("content_hash"),
            document_id=data.get("document_id"),
            title=data.get("title"),
            error=data.get("error"),
            discovered_at=(
                datetime.fromisoformat(discovered_at) if discovered_at else datetime.now(UTC)
            ),
            processed_at=datetime.fromisoformat(processed_at) if processed_at else None,
        )
