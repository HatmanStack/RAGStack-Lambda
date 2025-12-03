"""Unit tests for scraper data models."""

from datetime import UTC, datetime

from ragstack_common.scraper import (
    ScrapeConfig,
    ScrapeJob,
    ScrapePage,
    ScrapeScope,
    ScrapeStatus,
    UrlStatus,
)


class TestScrapeStatus:
    """Tests for ScrapeStatus enum."""

    def test_enum_values(self):
        assert ScrapeStatus.PENDING.value == "pending"
        assert ScrapeStatus.DISCOVERING.value == "discovering"
        assert ScrapeStatus.PROCESSING.value == "processing"
        assert ScrapeStatus.COMPLETED.value == "completed"
        assert ScrapeStatus.COMPLETED_WITH_ERRORS.value == "completed_with_errors"
        assert ScrapeStatus.FAILED.value == "failed"
        assert ScrapeStatus.CANCELLED.value == "cancelled"

    def test_string_conversion(self):
        # str(Enum) inherits from str, so direct equality works
        assert ScrapeStatus.PENDING == "pending"
        assert ScrapeStatus.COMPLETED == "completed"


class TestUrlStatus:
    """Tests for UrlStatus enum."""

    def test_enum_values(self):
        assert UrlStatus.PENDING.value == "pending"
        assert UrlStatus.PROCESSING.value == "processing"
        assert UrlStatus.COMPLETED.value == "completed"
        assert UrlStatus.FAILED.value == "failed"
        assert UrlStatus.SKIPPED.value == "skipped"


class TestScrapeScope:
    """Tests for ScrapeScope enum."""

    def test_enum_values(self):
        assert ScrapeScope.SUBPAGES.value == "subpages"
        assert ScrapeScope.HOSTNAME.value == "hostname"
        assert ScrapeScope.DOMAIN.value == "domain"


class TestScrapeConfig:
    """Tests for ScrapeConfig dataclass."""

    def test_default_values(self):
        config = ScrapeConfig()
        assert config.max_pages == 1000
        assert config.max_depth == 3
        assert config.scope == ScrapeScope.SUBPAGES
        assert config.request_delay_ms == 500
        assert config.include_patterns == []
        assert config.exclude_patterns == []
        assert config.cookies == {}
        assert config.headers == {}

    def test_custom_values(self):
        config = ScrapeConfig(
            max_pages=500,
            max_depth=5,
            scope=ScrapeScope.HOSTNAME,
            request_delay_ms=1000,
            include_patterns=["*/docs/*"],
            exclude_patterns=["*/blog/*"],
            cookies={"session": "abc123"},
            headers={"Authorization": "Bearer token"},
        )
        assert config.max_pages == 500
        assert config.max_depth == 5
        assert config.scope == ScrapeScope.HOSTNAME
        assert config.request_delay_ms == 1000
        assert config.include_patterns == ["*/docs/*"]
        assert config.exclude_patterns == ["*/blog/*"]
        assert config.cookies == {"session": "abc123"}
        assert config.headers == {"Authorization": "Bearer token"}

    def test_to_dict(self):
        config = ScrapeConfig(max_pages=100, scope=ScrapeScope.DOMAIN)
        data = config.to_dict()
        assert data["max_pages"] == 100
        assert data["scope"] == "domain"
        assert data["max_depth"] == 3
        assert data["request_delay_ms"] == 500

    def test_from_dict(self):
        data = {
            "max_pages": 200,
            "max_depth": 4,
            "scope": "hostname",
            "request_delay_ms": 750,
            "include_patterns": ["*/api/*"],
            "exclude_patterns": [],
            "cookies": {},
            "headers": {"X-Custom": "value"},
        }
        config = ScrapeConfig.from_dict(data)
        assert config.max_pages == 200
        assert config.max_depth == 4
        assert config.scope == ScrapeScope.HOSTNAME
        assert config.request_delay_ms == 750
        assert config.headers == {"X-Custom": "value"}

    def test_from_dict_defaults(self):
        config = ScrapeConfig.from_dict({})
        assert config.max_pages == 1000
        assert config.max_depth == 3
        assert config.scope == ScrapeScope.SUBPAGES


class TestScrapeJob:
    """Tests for ScrapeJob dataclass."""

    def test_creation_minimal(self):
        job = ScrapeJob(job_id="job-123", base_url="https://example.com")
        assert job.job_id == "job-123"
        assert job.base_url == "https://example.com"
        assert job.status == ScrapeStatus.PENDING
        assert job.total_urls == 0
        assert job.processed_count == 0
        assert job.failed_count == 0
        assert job.failed_urls == []
        assert job.title is None
        assert job.step_function_arn is None
        assert isinstance(job.config, ScrapeConfig)

    def test_creation_full(self):
        config = ScrapeConfig(max_pages=50)
        job = ScrapeJob(
            job_id="job-456",
            base_url="https://docs.example.com",
            status=ScrapeStatus.PROCESSING,
            config=config,
            title="Example Docs",
            total_urls=100,
            processed_count=50,
            failed_count=2,
            failed_urls=[{"url": "https://example.com/404", "error": "Not found"}],
            step_function_arn="arn:aws:states:us-east-1:123456:execution:xyz",
        )
        assert job.status == ScrapeStatus.PROCESSING
        assert job.title == "Example Docs"
        assert job.config.max_pages == 50
        assert len(job.failed_urls) == 1

    def test_to_dict(self):
        job = ScrapeJob(
            job_id="job-789",
            base_url="https://example.com",
            status=ScrapeStatus.COMPLETED,
            title="Test Job",
        )
        data = job.to_dict()
        assert data["job_id"] == "job-789"
        assert data["base_url"] == "https://example.com"
        assert data["status"] == "completed"
        assert data["title"] == "Test Job"
        assert "created_at" in data
        assert "updated_at" in data
        assert isinstance(data["config"], dict)

    def test_to_dict_excludes_none(self):
        job = ScrapeJob(job_id="job-abc", base_url="https://example.com")
        data = job.to_dict()
        assert "title" not in data
        assert "step_function_arn" not in data

    def test_from_dict(self):
        now = datetime.now(UTC)
        data = {
            "job_id": "job-xyz",
            "base_url": "https://example.com/docs",
            "status": "processing",
            "config": {"max_pages": 75},
            "title": "Documentation",
            "total_urls": 30,
            "processed_count": 10,
            "failed_count": 1,
            "failed_urls": [],
            "step_function_arn": "arn:aws:states:us-east-1:123:exec:abc",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        job = ScrapeJob.from_dict(data)
        assert job.job_id == "job-xyz"
        assert job.status == ScrapeStatus.PROCESSING
        assert job.config.max_pages == 75
        assert job.title == "Documentation"
        assert job.step_function_arn == "arn:aws:states:us-east-1:123:exec:abc"

    def test_from_dict_defaults(self):
        data = {"job_id": "job-min", "base_url": "https://example.com"}
        job = ScrapeJob.from_dict(data)
        assert job.status == ScrapeStatus.PENDING
        assert job.total_urls == 0
        assert job.config.max_pages == 1000


class TestScrapePage:
    """Tests for ScrapePage dataclass."""

    def test_creation_minimal(self):
        page = ScrapePage(job_id="job-123", url="https://example.com/page1")
        assert page.job_id == "job-123"
        assert page.url == "https://example.com/page1"
        assert page.status == UrlStatus.PENDING
        assert page.depth == 0
        assert page.content_hash is None
        assert page.document_id is None
        assert page.title is None
        assert page.error is None
        assert page.processed_at is None

    def test_creation_full(self):
        now = datetime.now(UTC)
        page = ScrapePage(
            job_id="job-456",
            url="https://example.com/page2",
            status=UrlStatus.COMPLETED,
            depth=2,
            content_hash="abc123def456",
            document_id="doc-789",
            title="Page Title",
            processed_at=now,
        )
        assert page.status == UrlStatus.COMPLETED
        assert page.depth == 2
        assert page.content_hash == "abc123def456"
        assert page.document_id == "doc-789"
        assert page.title == "Page Title"
        assert page.processed_at == now

    def test_to_dict(self):
        page = ScrapePage(
            job_id="job-abc",
            url="https://example.com/docs/intro",
            status=UrlStatus.COMPLETED,
            content_hash="hash123",
            document_id="doc-456",
            title="Introduction",
        )
        data = page.to_dict()
        assert data["job_id"] == "job-abc"
        assert data["url"] == "https://example.com/docs/intro"
        assert data["status"] == "completed"
        assert data["content_hash"] == "hash123"
        assert data["document_id"] == "doc-456"
        assert data["title"] == "Introduction"

    def test_to_dict_excludes_none(self):
        page = ScrapePage(job_id="job-xyz", url="https://example.com")
        data = page.to_dict()
        assert "content_hash" not in data
        assert "document_id" not in data
        assert "title" not in data
        assert "error" not in data
        assert "processed_at" not in data

    def test_from_dict(self):
        now = datetime.now(UTC)
        data = {
            "job_id": "job-from",
            "url": "https://example.com/test",
            "status": "failed",
            "depth": 3,
            "error": "Connection timeout",
            "discovered_at": now.isoformat(),
        }
        page = ScrapePage.from_dict(data)
        assert page.job_id == "job-from"
        assert page.status == UrlStatus.FAILED
        assert page.depth == 3
        assert page.error == "Connection timeout"

    def test_from_dict_defaults(self):
        data = {"job_id": "job-min", "url": "https://example.com/minimal"}
        page = ScrapePage.from_dict(data)
        assert page.status == UrlStatus.PENDING
        assert page.depth == 0


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
