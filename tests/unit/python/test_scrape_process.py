"""Unit tests for scrape_process Lambda handler."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_scrape_process_module():
    """Load scrape_process module using importlib (avoids 'lambda' keyword issue)."""
    module_path = Path(__file__).parent.parent.parent.parent / "src/lambda/scrape_process/index.py"
    spec = importlib.util.spec_from_file_location("scrape_process_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["scrape_process_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def _mock_env(monkeypatch):
    """Set up environment variables for tests."""
    monkeypatch.setenv("SCRAPE_JOBS_TABLE", "test-jobs-table")
    monkeypatch.setenv("SCRAPE_URLS_TABLE", "test-urls-table")
    monkeypatch.setenv("DATA_BUCKET", "test-data-bucket")
    monkeypatch.setenv("REQUEST_DELAY_MS", "0")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def mock_aws(_mock_env):
    """Set up AWS mocks for DynamoDB and S3."""
    with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
        # Mock DynamoDB tables
        mock_jobs_table = MagicMock()
        mock_urls_table = MagicMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.side_effect = lambda name: (
            mock_jobs_table if "jobs" in name else mock_urls_table
        )
        mock_resource.return_value = mock_dynamodb

        # Mock S3
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3

        yield {
            "jobs_table": mock_jobs_table,
            "urls_table": mock_urls_table,
            "s3": mock_s3,
        }


@pytest.fixture
def _mock_fetcher():
    """Mock the fetch_auto function (fixture provides side-effect patching)."""
    with patch("ragstack_common.scraper.fetcher.fetch_auto") as mock_fetch:
        test_html = (
            "<html><head><title>Test Page</title></head>"
            "<body><h1>Test</h1><p>Content here</p></body></html>"
        )
        mock_fetch.return_value = MagicMock(
            error=None,
            is_html=True,
            content=test_html,
            status_code=200,
        )
        yield mock_fetch


@pytest.fixture
def _mock_dedup():
    """Mock the deduplication service (fixture provides side-effect patching)."""
    with patch("ragstack_common.scraper.dedup.DeduplicationService") as mock_cls:
        mock_service = MagicMock()
        mock_service.is_content_changed.return_value = True  # Content is new
        mock_service.get_content_hash.return_value = "abc123"
        mock_cls.return_value = mock_service
        yield mock_service


class TestScrapeProcessHandler:
    """Tests for scrape_process lambda_handler."""

    def test_missing_jobs_table_env(self, monkeypatch):
        """Test error when SCRAPE_JOBS_TABLE is missing."""
        monkeypatch.delenv("SCRAPE_JOBS_TABLE", raising=False)
        monkeypatch.setenv("SCRAPE_URLS_TABLE", "test-urls-table")
        monkeypatch.setenv("DATA_BUCKET", "test-data-bucket")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

        module = _load_scrape_process_module()

        with pytest.raises(ValueError, match="SCRAPE_JOBS_TABLE"):
            module.lambda_handler({"Records": []}, None)

    def test_sqs_message_parsing(self, mock_aws, _mock_fetcher, _mock_dedup):
        """Test SQS message parsing from event."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-123",
                "status": "running",
                "config": {},
            }
        }

        module = _load_scrape_process_module()

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
        assert result["failed"] == 0
        # Now writes 2 files: content + metadata.json
        assert mock_aws["s3"].put_object.call_count == 2

    def test_processed_count_increment(self, mock_aws, _mock_fetcher, _mock_dedup):
        """Test that processed_count is incremented on success."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-123",
                "status": "running",
                "config": {},
            }
        }

        module = _load_scrape_process_module()

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

        update_calls = mock_aws["jobs_table"].update_item.call_args_list
        assert len(update_calls) > 0
        found_processed_update = any("processed_count" in str(call) for call in update_calls)
        assert found_processed_update

    def test_job_cancelled_skips_processing(self, mock_aws, _mock_fetcher, _mock_dedup):
        """Test that cancelled jobs skip URL processing."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {"job_id": "test-job-123", "status": "cancelled"}
        }

        module = _load_scrape_process_module()

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

        assert result["processed"] == 0
        mock_aws["s3"].put_object.assert_not_called()

    def test_s3_write_creates_markdown_file(self, mock_aws, _mock_fetcher, _mock_dedup):
        """Test that S3 write creates .scraped.md file."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-123",
                "status": "running",
                "config": {},
            }
        }

        module = _load_scrape_process_module()

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

        # Now writes 2 files: first is markdown, second is metadata.json
        call_args_list = mock_aws["s3"].put_object.call_args_list
        assert len(call_args_list) == 2

        # First call should be the markdown file (content/{job_id}/{slug}.md)
        md_call = call_args_list[0]
        s3_key = md_call.kwargs.get("Key") or md_call[1].get("Key")
        assert s3_key.startswith("content/test-job-123/")
        assert s3_key.endswith(".md")
        content_type = md_call.kwargs.get("ContentType") or md_call[1].get("ContentType")
        assert content_type == "text/markdown"

        # Second call should be the metadata file
        meta_call = call_args_list[1]
        meta_key = meta_call.kwargs.get("Key") or meta_call[1].get("Key")
        assert meta_key.endswith(".metadata.json")


class TestUrlStatusUpdates:
    """Tests for URL status updates."""

    def test_updates_url_status_to_completed(self, mock_aws, _mock_fetcher, _mock_dedup):
        """Test that URL status is updated to completed on success."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-123",
                "status": "running",
                "config": {},
            }
        }

        module = _load_scrape_process_module()

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

        update_calls = mock_aws["urls_table"].update_item.call_args_list
        assert len(update_calls) >= 1
        found_completed = any("completed" in str(call) for call in update_calls)
        assert found_completed


class TestDeduplication:
    """Tests for content deduplication."""

    def test_skips_unchanged_content(self, mock_aws, _mock_fetcher, _mock_dedup):
        """Test that unchanged content is skipped."""
        _mock_dedup.is_content_changed.return_value = False  # Content unchanged

        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-123",
                "status": "running",
                "config": {},
            }
        }

        module = _load_scrape_process_module()

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
        mock_aws["s3"].put_object.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
