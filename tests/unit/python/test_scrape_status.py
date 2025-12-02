"""Unit tests for scrape_status Lambda handler."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_scrape_status_module():
    """Load scrape_status module using importlib (avoids 'lambda' keyword issue)."""
    module_path = Path(__file__).parent.parent.parent.parent / "src/lambda/scrape_status/index.py"
    spec = importlib.util.spec_from_file_location("scrape_status_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["scrape_status_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables for tests."""
    monkeypatch.setenv("SCRAPE_JOBS_TABLE", "test-jobs-table")
    monkeypatch.setenv("SCRAPE_DISCOVERY_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/disc")
    monkeypatch.setenv("SCRAPE_PROCESSING_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/proc")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


class TestScrapeStatusHandler:
    """Tests for scrape_status lambda_handler."""

    def test_missing_jobs_table_env(self, monkeypatch):
        """Test error when SCRAPE_JOBS_TABLE is missing."""
        monkeypatch.delenv("SCRAPE_JOBS_TABLE", raising=False)

        module = _load_scrape_status_module()

        with pytest.raises(ValueError, match="SCRAPE_JOBS_TABLE"):
            module.lambda_handler({"job_id": "test-job"}, None)

    def test_missing_job_id(self, mock_env):
        """Test error when job_id is missing."""
        module = _load_scrape_status_module()

        with pytest.raises(ValueError, match="job_id is required"):
            module.lambda_handler({}, None)

    def test_job_not_found(self, mock_env):
        """Test error when job doesn't exist."""
        with patch("boto3.resource") as mock_resource:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {}
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            module = _load_scrape_status_module()

            with pytest.raises(ValueError, match="Job not found"):
                module.lambda_handler({"job_id": "nonexistent-job"}, None)

    def test_successful_status_check(self, mock_env):
        """Test successful status check."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "job_id": "test-job-123",
                    "status": "processing",
                    "total_urls": 10,
                    "processed_count": 5,
                    "failed_count": 1,
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            # Mock SQS
            mock_sqs = MagicMock()
            mock_sqs.get_queue_attributes.return_value = {
                "Attributes": {
                    "ApproximateNumberOfMessages": "0",
                    "ApproximateNumberOfMessagesNotVisible": "0",
                }
            }
            mock_client.return_value = mock_sqs

            module = _load_scrape_status_module()

            result = module.lambda_handler({"job_id": "test-job-123"}, None)

            assert result["job_id"] == "test-job-123"
            assert result["status"] == "processing"
            assert result["total_urls"] == 10
            assert result["processed_count"] == 5
            assert result["failed_count"] == 1
            assert result["discovery_complete"] is True
            assert result["processing_complete"] is True

    def test_failure_threshold_exceeded(self, mock_env):
        """Test failure threshold detection."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "job_id": "test-job-456",
                    "status": "processing",
                    "total_urls": 100,
                    "processed_count": 50,
                    "failed_count": 20,  # 20% failure rate > 10% threshold
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            mock_sqs = MagicMock()
            mock_sqs.get_queue_attributes.return_value = {
                "Attributes": {
                    "ApproximateNumberOfMessages": "0",
                    "ApproximateNumberOfMessagesNotVisible": "0",
                }
            }
            mock_client.return_value = mock_sqs

            module = _load_scrape_status_module()

            result = module.lambda_handler({"job_id": "test-job-456"}, None)

            assert result["failure_threshold_exceeded"] is True

    def test_queues_not_empty(self, mock_env):
        """Test detection of non-empty queues."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "job_id": "test-job-789",
                    "status": "processing",
                    "total_urls": 10,
                    "processed_count": 5,
                    "failed_count": 0,
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            mock_sqs = MagicMock()
            mock_sqs.get_queue_attributes.return_value = {
                "Attributes": {
                    "ApproximateNumberOfMessages": "5",  # Messages still in queue
                    "ApproximateNumberOfMessagesNotVisible": "0",
                }
            }
            mock_client.return_value = mock_sqs

            module = _load_scrape_status_module()

            result = module.lambda_handler({"job_id": "test-job-789"}, None)

            # Queues not empty means not complete
            assert result["discovery_complete"] is False
            assert result["is_complete"] is False
