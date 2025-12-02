"""Unit tests for scrape_discover Lambda handler."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_scrape_discover_module():
    """Load scrape_discover module using importlib (avoids 'lambda' keyword issue)."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src/lambda/scrape_discover/index.py"
    )
    spec = importlib.util.spec_from_file_location("scrape_discover_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["scrape_discover_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def _mock_env(monkeypatch):
    """Set up environment variables for tests (underscore prefix for side-effect fixture)."""
    monkeypatch.setenv("SCRAPE_JOBS_TABLE", "test-jobs-table")
    monkeypatch.setenv("SCRAPE_URLS_TABLE", "test-urls-table")
    monkeypatch.setenv("SCRAPE_DISCOVERY_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/disc")
    monkeypatch.setenv("SCRAPE_PROCESSING_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/proc")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


class TestScrapeDiscoverHandler:
    """Tests for scrape_discover lambda_handler."""

    def test_missing_jobs_table_env(self, monkeypatch):
        """Test error when SCRAPE_JOBS_TABLE is missing."""
        monkeypatch.delenv("SCRAPE_JOBS_TABLE", raising=False)
        monkeypatch.setenv("SCRAPE_URLS_TABLE", "test-urls-table")
        monkeypatch.setenv("SCRAPE_DISCOVERY_QUEUE_URL", "https://sqs.example.com/disc")
        monkeypatch.setenv("SCRAPE_PROCESSING_QUEUE_URL", "https://sqs.example.com/proc")

        module = _load_scrape_discover_module()

        with pytest.raises(ValueError, match="SCRAPE_JOBS_TABLE"):
            module.lambda_handler({"Records": []}, None)

    def test_sqs_message_parsing(self, _mock_env):
        """Test SQS message parsing from event."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            # Mock DynamoDB tables
            mock_jobs_table = MagicMock()
            mock_urls_table = MagicMock()
            mock_jobs_table.get_item.return_value = {
                "Item": {
                    "job_id": "test-job-123",
                    "status": "discovering",
                    "config": {"max_depth": 3},
                }
            }
            mock_urls_table.get_item.return_value = {}  # URL not visited yet

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.side_effect = lambda name: (
                mock_jobs_table if "jobs" in name else mock_urls_table
            )
            mock_resource.return_value = mock_dynamodb

            # Mock SQS
            mock_sqs = MagicMock()
            mock_client.return_value = mock_sqs

            module = _load_scrape_discover_module()

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
            # Verify URL was marked as visited
            mock_urls_table.put_item.assert_called_once()

    def test_duplicate_url_handling(self, _mock_env):
        """Test that already-visited URLs are skipped."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            mock_jobs_table = MagicMock()
            mock_urls_table = MagicMock()
            mock_jobs_table.get_item.return_value = {
                "Item": {"job_id": "test-job-123", "status": "discovering"}
            }
            # URL already exists
            mock_urls_table.get_item.return_value = {
                "Item": {"job_id": "test-job-123", "url": "https://example.com/page1"}
            }

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.side_effect = lambda name: (
                mock_jobs_table if "jobs" in name else mock_urls_table
            )
            mock_resource.return_value = mock_dynamodb
            mock_client.return_value = MagicMock()

            module = _load_scrape_discover_module()

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

            # Skipped because URL already exists
            assert result["skipped"] == 1
            assert result["processed"] == 0

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
            mock_client.return_value = MagicMock()

            module = _load_scrape_discover_module()

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

            assert result["skipped"] == 1
            # URL table should not be touched for cancelled jobs
            mock_urls_table.put_item.assert_not_called()

    def test_job_not_found(self, _mock_env):
        """Test handling when job doesn't exist."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            mock_jobs_table = MagicMock()
            mock_urls_table = MagicMock()
            mock_jobs_table.get_item.return_value = {}  # Job not found

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.side_effect = lambda name: (
                mock_jobs_table if "jobs" in name else mock_urls_table
            )
            mock_resource.return_value = mock_dynamodb
            mock_client.return_value = MagicMock()

            module = _load_scrape_discover_module()

            event = {
                "Records": [
                    {
                        "body": json.dumps({
                            "job_id": "nonexistent-job",
                            "url": "https://example.com/page1",
                            "depth": 0,
                        })
                    }
                ]
            }

            result = module.lambda_handler(event, None)

            # Should continue without error when job not found
            assert result["processed"] == 0


class TestJobCounterUpdates:
    """Tests for job counter updates."""

    def test_increments_total_urls(self, _mock_env):
        """Test that total_urls counter is incremented."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            mock_jobs_table = MagicMock()
            mock_urls_table = MagicMock()
            mock_jobs_table.get_item.return_value = {
                "Item": {
                    "job_id": "test-job-123",
                    "status": "discovering",
                    "config": {"max_depth": 3},
                }
            }
            mock_urls_table.get_item.return_value = {}

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.side_effect = lambda name: (
                mock_jobs_table if "jobs" in name else mock_urls_table
            )
            mock_resource.return_value = mock_dynamodb
            mock_client.return_value = MagicMock()

            module = _load_scrape_discover_module()

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

            # Verify update_item was called to increment counter
            mock_jobs_table.update_item.assert_called()
            call_args = mock_jobs_table.update_item.call_args
            assert "total_urls" in str(call_args)
