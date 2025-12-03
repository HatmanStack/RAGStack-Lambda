"""Unit tests for scrape_discover Lambda handler."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_scrape_discover_module():
    """Load scrape_discover module using importlib (avoids 'lambda' keyword issue)."""
    module_path = Path(__file__).parent.parent.parent.parent / "src/lambda/scrape_discover/index.py"
    spec = importlib.util.spec_from_file_location("scrape_discover_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["scrape_discover_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def _mock_env(monkeypatch):
    """Set up environment variables for tests."""
    monkeypatch.setenv("SCRAPE_JOBS_TABLE", "test-jobs-table")
    monkeypatch.setenv("SCRAPE_URLS_TABLE", "test-urls-table")
    monkeypatch.setenv("SCRAPE_DISCOVERY_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/disc")
    monkeypatch.setenv(
        "SCRAPE_PROCESSING_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/proc"
    )
    monkeypatch.setenv("REQUEST_DELAY_MS", "0")  # No delay for tests
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def mock_aws(_mock_env):
    """Set up AWS mocks for DynamoDB and SQS."""
    with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
        # Mock DynamoDB tables
        mock_jobs_table = MagicMock()
        mock_urls_table = MagicMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.side_effect = lambda name: (
            mock_jobs_table if "jobs" in name else mock_urls_table
        )
        mock_resource.return_value = mock_dynamodb

        # Mock SQS
        mock_sqs = MagicMock()
        mock_client.return_value = mock_sqs

        yield {
            "jobs_table": mock_jobs_table,
            "urls_table": mock_urls_table,
            "sqs": mock_sqs,
        }


@pytest.fixture
def _mock_fetcher():
    """Mock the HTTP fetcher (fixture provides side-effect patching)."""
    with patch("ragstack_common.scraper.fetcher.HttpFetcher") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.fetch.return_value = MagicMock(
            error=None,
            is_html=True,
            content="<html><body><h1>Test</h1></body></html>",
            status_code=200,
        )
        mock_cls.return_value = mock_instance
        yield mock_instance


class TestScrapeDiscoverHandler:
    """Tests for scrape_discover lambda_handler."""

    def test_missing_jobs_table_env(self, monkeypatch):
        """Test error when SCRAPE_JOBS_TABLE is missing."""
        monkeypatch.delenv("SCRAPE_JOBS_TABLE", raising=False)
        monkeypatch.setenv("SCRAPE_URLS_TABLE", "test-urls-table")
        monkeypatch.setenv("SCRAPE_DISCOVERY_QUEUE_URL", "https://sqs.example.com/disc")
        monkeypatch.setenv("SCRAPE_PROCESSING_QUEUE_URL", "https://sqs.example.com/proc")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

        module = _load_scrape_discover_module()

        with pytest.raises(ValueError, match="SCRAPE_JOBS_TABLE"):
            module.lambda_handler({"Records": []}, None)

    def test_sqs_message_parsing(self, mock_aws, _mock_fetcher):
        """Test SQS message parsing from event."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-123",
                "status": "running",
                "base_url": "https://example.com",
                "config": {"max_depth": 3, "max_pages": 100},
                "total_urls": 0,
            }
        }
        mock_aws["urls_table"].get_item.return_value = {}  # URL not visited yet

        module = _load_scrape_discover_module()

        event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "job_id": "test-job-123",
                            "url": "https://example.com/page1",
                            "depth": 0,
                        }
                    )
                }
            ]
        }

        result = module.lambda_handler(event, None)

        assert result["processed"] == 1
        mock_aws["urls_table"].put_item.assert_called_once()

    def test_duplicate_url_handling(self, mock_aws, _mock_fetcher):
        """Test that already-visited URLs are skipped."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {"job_id": "test-job-123", "status": "running"}
        }
        mock_aws["urls_table"].get_item.return_value = {
            "Item": {"job_id": "test-job-123", "url": "https://example.com/page1"}
        }

        module = _load_scrape_discover_module()

        event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "job_id": "test-job-123",
                            "url": "https://example.com/page1",
                            "depth": 0,
                        }
                    )
                }
            ]
        }

        result = module.lambda_handler(event, None)

        assert result["skipped"] == 1
        assert result["processed"] == 0

    def test_job_cancelled_skips_processing(self, mock_aws, _mock_fetcher):
        """Test that cancelled jobs skip URL processing."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {"job_id": "test-job-123", "status": "cancelled"}
        }

        module = _load_scrape_discover_module()

        event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "job_id": "test-job-123",
                            "url": "https://example.com/page1",
                            "depth": 0,
                        }
                    )
                }
            ]
        }

        result = module.lambda_handler(event, None)

        assert result["skipped"] == 1
        mock_aws["urls_table"].put_item.assert_not_called()

    def test_job_not_found(self, mock_aws, _mock_fetcher):
        """Test handling when job doesn't exist."""
        mock_aws["jobs_table"].get_item.return_value = {}

        module = _load_scrape_discover_module()

        event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "job_id": "nonexistent-job",
                            "url": "https://example.com/page1",
                            "depth": 0,
                        }
                    )
                }
            ]
        }

        result = module.lambda_handler(event, None)

        assert result["processed"] == 0


class TestJobCounterUpdates:
    """Tests for job counter updates."""

    def test_increments_total_urls(self, mock_aws, _mock_fetcher):
        """Test that total_urls counter is incremented."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-123",
                "status": "running",
                "base_url": "https://example.com",
                "config": {"max_depth": 3, "max_pages": 100},
                "total_urls": 0,
            }
        }
        mock_aws["urls_table"].get_item.return_value = {}

        module = _load_scrape_discover_module()

        event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "job_id": "test-job-123",
                            "url": "https://example.com/page1",
                            "depth": 0,
                        }
                    )
                }
            ]
        }

        module.lambda_handler(event, None)

        mock_aws["jobs_table"].update_item.assert_called()
        call_args = mock_aws["jobs_table"].update_item.call_args
        assert "total_urls" in str(call_args)


class TestUrlDiscovery:
    """Tests for URL discovery from page content."""

    def test_discovers_links_from_content(self, mock_aws, _mock_fetcher):
        """Test that links are extracted from fetched content."""
        _mock_fetcher.fetch.return_value = MagicMock(
            error=None,
            is_html=True,
            content="""
            <html>
                <body>
                    <a href="/page2">Link 1</a>
                    <a href="/page3">Link 2</a>
                </body>
            </html>
            """,
            status_code=200,
        )

        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-123",
                "status": "running",
                "base_url": "https://example.com",
                "config": {"max_depth": 3, "max_pages": 100, "scope": "hostname"},
                "total_urls": 0,
            }
        }
        mock_aws["urls_table"].get_item.return_value = {}

        module = _load_scrape_discover_module()

        event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "job_id": "test-job-123",
                            "url": "https://example.com/",
                            "depth": 0,
                        }
                    )
                }
            ]
        }

        result = module.lambda_handler(event, None)

        # Should discover at least 2 new URLs
        assert result["discovered"] >= 2
        # Should send messages to discovery queue
        mock_aws["sqs"].send_message.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
