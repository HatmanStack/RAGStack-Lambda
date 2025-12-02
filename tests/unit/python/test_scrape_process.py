"""Unit tests for scrape_process Lambda handler."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_scrape_process_module():
    """Load scrape_process module using importlib (avoids 'lambda' keyword issue)."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src/lambda/scrape_process/index.py"
    )
    spec = importlib.util.spec_from_file_location("scrape_process_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["scrape_process_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def _mock_env(monkeypatch):
    """Set up environment variables for tests (underscore prefix for side-effect fixture)."""
    monkeypatch.setenv("SCRAPE_JOBS_TABLE", "test-jobs-table")
    monkeypatch.setenv("SCRAPE_URLS_TABLE", "test-urls-table")
    monkeypatch.setenv("INPUT_BUCKET", "test-input-bucket")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


class TestScrapeProcessHandler:
    """Tests for scrape_process lambda_handler."""

    def test_missing_jobs_table_env(self, monkeypatch):
        """Test error when SCRAPE_JOBS_TABLE is missing."""
        monkeypatch.delenv("SCRAPE_JOBS_TABLE", raising=False)
        monkeypatch.setenv("SCRAPE_URLS_TABLE", "test-urls-table")
        monkeypatch.setenv("INPUT_BUCKET", "test-input-bucket")

        module = _load_scrape_process_module()

        with pytest.raises(ValueError, match="SCRAPE_JOBS_TABLE"):
            module.lambda_handler({"Records": []}, None)

    def test_sqs_message_parsing(self, _mock_env):
        """Test SQS message parsing from event."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            # Mock DynamoDB tables
            mock_jobs_table = MagicMock()
            mock_urls_table = MagicMock()
            mock_jobs_table.get_item.return_value = {
                "Item": {"job_id": "test-job-123", "status": "processing"}
            }

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.side_effect = lambda name: (
                mock_jobs_table if "jobs" in name else mock_urls_table
            )
            mock_resource.return_value = mock_dynamodb

            # Mock S3
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            module = _load_scrape_process_module()

            event = {
                "Records": [
                    {
                        "body": json.dumps({
                            "job_id": "test-job-123",
                            "url": "https://example.com/page1",
                            "depth": 0,
                        })
                    }
                ]
            }

            result = module.lambda_handler(event, None)

            assert result["processed"] == 1
            assert result["failed"] == 0
            # Verify S3 put was called
            mock_s3.put_object.assert_called_once()

    def test_processed_count_increment(self, _mock_env):
        """Test that processed_count is incremented on success."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            mock_jobs_table = MagicMock()
            mock_urls_table = MagicMock()
            mock_jobs_table.get_item.return_value = {
                "Item": {"job_id": "test-job-123", "status": "processing"}
            }

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.side_effect = lambda name: (
                mock_jobs_table if "jobs" in name else mock_urls_table
            )
            mock_resource.return_value = mock_dynamodb
            mock_client.return_value = MagicMock()

            module = _load_scrape_process_module()

            event = {
                "Records": [
                    {
                        "body": json.dumps({
                            "job_id": "test-job-123",
                            "url": "https://example.com/page1",
                            "depth": 0,
                        })
                    }
                ]
            }

            module.lambda_handler(event, None)

            # Verify update_item was called to increment processed_count
            update_calls = mock_jobs_table.update_item.call_args_list
            assert len(update_calls) > 0
            # Check that processed_count is in the update expression
            found_processed_update = any(
                "processed_count" in str(call) for call in update_calls
            )
            assert found_processed_update

    def test_job_cancelled_skips_processing(self, _mock_env):
        """Test that cancelled jobs skip URL processing."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            mock_jobs_table = MagicMock()
            mock_urls_table = MagicMock()
            mock_jobs_table.get_item.return_value = {
                "Item": {"job_id": "test-job-123", "status": "cancelled"}
            }

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.side_effect = lambda name: (
                mock_jobs_table if "jobs" in name else mock_urls_table
            )
            mock_resource.return_value = mock_dynamodb
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            module = _load_scrape_process_module()

            event = {
                "Records": [
                    {
                        "body": json.dumps({
                            "job_id": "test-job-123",
                            "url": "https://example.com/page1",
                            "depth": 0,
                        })
                    }
                ]
            }

            result = module.lambda_handler(event, None)

            assert result["processed"] == 0
            # S3 should not be touched for cancelled jobs
            mock_s3.put_object.assert_not_called()

    def test_s3_write_creates_markdown_file(self, _mock_env):
        """Test that S3 write creates .scraped.md file."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            mock_jobs_table = MagicMock()
            mock_urls_table = MagicMock()
            mock_jobs_table.get_item.return_value = {
                "Item": {"job_id": "test-job-123", "status": "processing"}
            }

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.side_effect = lambda name: (
                mock_jobs_table if "jobs" in name else mock_urls_table
            )
            mock_resource.return_value = mock_dynamodb

            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            module = _load_scrape_process_module()

            event = {
                "Records": [
                    {
                        "body": json.dumps({
                            "job_id": "test-job-123",
                            "url": "https://example.com/page1",
                            "depth": 0,
                        })
                    }
                ]
            }

            module.lambda_handler(event, None)

            # Verify S3 put_object was called with correct parameters
            call_args = mock_s3.put_object.call_args
            assert call_args is not None
            # Check the key ends with .scraped.md
            s3_key = call_args.kwargs.get("Key") or call_args[1].get("Key")
            assert s3_key.endswith(".scraped.md")
            # Check content type
            content_type = call_args.kwargs.get("ContentType") or call_args[1].get("ContentType")
            assert content_type == "text/markdown"


class TestUrlStatusUpdates:
    """Tests for URL status updates."""

    def test_updates_url_status_to_completed(self, _mock_env):
        """Test that URL status is updated to completed on success."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            mock_jobs_table = MagicMock()
            mock_urls_table = MagicMock()
            mock_jobs_table.get_item.return_value = {
                "Item": {"job_id": "test-job-123", "status": "processing"}
            }

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.side_effect = lambda name: (
                mock_jobs_table if "jobs" in name else mock_urls_table
            )
            mock_resource.return_value = mock_dynamodb
            mock_client.return_value = MagicMock()

            module = _load_scrape_process_module()

            event = {
                "Records": [
                    {
                        "body": json.dumps({
                            "job_id": "test-job-123",
                            "url": "https://example.com/page1",
                            "depth": 0,
                        })
                    }
                ]
            }

            module.lambda_handler(event, None)

            # Verify URL status was updated to completed
            update_calls = mock_urls_table.update_item.call_args_list
            assert len(update_calls) >= 1
            # Should have a call setting status to completed
            found_completed = any("completed" in str(call) for call in update_calls)
            assert found_completed
