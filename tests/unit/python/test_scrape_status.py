"""Unit tests for scrape_status Lambda handler."""

import importlib.util
import json
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
def _mock_env(monkeypatch):
    """Set up environment variables for tests."""
    monkeypatch.setenv("SCRAPE_JOBS_TABLE", "test-jobs-table")
    monkeypatch.setenv("SCRAPE_URLS_TABLE", "test-urls-table")
    monkeypatch.setenv("SCRAPE_DISCOVERY_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/disc")
    monkeypatch.setenv(
        "SCRAPE_PROCESSING_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/proc"
    )
    monkeypatch.setenv("TRACKING_TABLE", "test-tracking-table")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def mock_aws(_mock_env):
    """Set up AWS mocks for DynamoDB and SQS."""
    with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
        mock_jobs_table = MagicMock()
        mock_urls_table = MagicMock()
        mock_tracking_table = MagicMock()

        def table_factory(name):
            if "jobs" in name:
                return mock_jobs_table
            if "urls" in name:
                return mock_urls_table
            return mock_tracking_table

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.side_effect = table_factory
        mock_resource.return_value = mock_dynamodb

        mock_sqs = MagicMock()
        mock_sqs.get_queue_attributes.return_value = {
            "Attributes": {
                "ApproximateNumberOfMessages": "0",
                "ApproximateNumberOfMessagesNotVisible": "0",
            }
        }
        mock_client.return_value = mock_sqs

        yield {
            "jobs_table": mock_jobs_table,
            "urls_table": mock_urls_table,
            "tracking_table": mock_tracking_table,
            "sqs": mock_sqs,
        }


class TestScrapeStatusHandler:
    """Tests for scrape_status lambda_handler."""

    def test_missing_jobs_table_env(self, monkeypatch):
        """Test error when SCRAPE_JOBS_TABLE is missing."""
        monkeypatch.delenv("SCRAPE_JOBS_TABLE", raising=False)
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

        module = _load_scrape_status_module()

        with pytest.raises(ValueError, match="SCRAPE_JOBS_TABLE"):
            module.lambda_handler({"job_id": "test-job"}, None)

    def test_missing_job_id(self, mock_aws):  # noqa: ARG002
        """Test error when job_id is missing from Step Functions event."""
        module = _load_scrape_status_module()

        with pytest.raises(ValueError, match="job_id is required"):
            module.lambda_handler({}, None)

    def test_job_not_found(self, mock_aws):
        """Test error when job doesn't exist."""
        mock_aws["jobs_table"].get_item.return_value = {}

        module = _load_scrape_status_module()

        with pytest.raises(ValueError, match="Job not found"):
            module.lambda_handler({"job_id": "nonexistent-job"}, None)

    def test_successful_status_check(self, mock_aws):
        """Test successful status check."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-123",
                "status": "running",
                "total_urls": 10,
                "processed_count": 5,
                "failed_count": 1,
            }
        }

        module = _load_scrape_status_module()

        result = module.lambda_handler({"job_id": "test-job-123"}, None)

        assert result["job_id"] == "test-job-123"
        assert result["status"] == "running"
        assert result["total_urls"] == 10
        assert result["processed_count"] == 5
        assert result["failed_count"] == 1
        assert result["discovery_complete"] is True
        assert result["processing_complete"] is True

    def test_failure_threshold_exceeded(self, mock_aws):
        """Test failure threshold detection."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-456",
                "status": "running",
                "total_urls": 100,
                "processed_count": 50,
                "failed_count": 20,  # 20% failure rate > 10% threshold
            }
        }

        module = _load_scrape_status_module()

        result = module.lambda_handler({"job_id": "test-job-456"}, None)

        assert result["failure_threshold_exceeded"] is True

    def test_queues_not_empty(self, mock_aws):
        """Test detection of non-empty queues."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-789",
                "status": "running",
                "total_urls": 10,
                "processed_count": 5,
                "failed_count": 0,
            }
        }
        mock_aws["sqs"].get_queue_attributes.return_value = {
            "Attributes": {
                "ApproximateNumberOfMessages": "5",
                "ApproximateNumberOfMessagesNotVisible": "0",
            }
        }

        module = _load_scrape_status_module()

        result = module.lambda_handler({"job_id": "test-job-789"}, None)

        assert result["discovery_complete"] is False
        assert result["is_complete"] is False


class TestApiGatewayRequests:
    """Tests for API Gateway HTTP requests."""

    def test_api_get_status(self, mock_aws):
        """Test GET request for job status."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-123",
                "status": "running",
                "base_url": "https://example.com",
                "total_urls": 10,
                "processed_count": 5,
                "failed_count": 1,
                "config": {"max_depth": 3},
            }
        }

        module = _load_scrape_status_module()

        event = {
            "httpMethod": "GET",
            "pathParameters": {"job_id": "test-job-123"},
            "queryStringParameters": None,
            "resource": "/scrape/{job_id}",
        }

        result = module.lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["job_id"] == "test-job-123"
        assert body["status"] == "running"
        assert "progress" in body

    def test_api_get_urls(self, mock_aws):
        """Test GET request for job URLs."""
        mock_aws["urls_table"].query.return_value = {
            "Items": [
                {"url": "https://example.com/page1", "status": "completed", "depth": 0},
                {"url": "https://example.com/page2", "status": "pending", "depth": 1},
            ]
        }

        module = _load_scrape_status_module()

        event = {
            "httpMethod": "GET",
            "pathParameters": {"job_id": "test-job-123"},
            "queryStringParameters": {"limit": "50"},
            "resource": "/scrape/{job_id}/urls",
        }

        result = module.lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["count"] == 2
        assert len(body["urls"]) == 2

    def test_api_cancel_job(self, mock_aws):
        """Test DELETE request to cancel job."""
        mock_aws["jobs_table"].get_item.return_value = {
            "Item": {
                "job_id": "test-job-123",
                "status": "discovering",  # Use valid status from ScrapeStatus enum
            }
        }

        module = _load_scrape_status_module()

        event = {
            "httpMethod": "DELETE",
            "pathParameters": {"job_id": "test-job-123"},
            "queryStringParameters": None,
            "resource": "/scrape/{job_id}",
        }

        result = module.lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "cancelled"
        mock_aws["jobs_table"].update_item.assert_called_once()

    def test_api_missing_job_id(self, mock_aws):  # noqa: ARG002
        """Test API request missing job_id."""
        module = _load_scrape_status_module()

        event = {
            "httpMethod": "GET",
            "pathParameters": {},
            "queryStringParameters": None,
            "resource": "/scrape/{job_id}",
        }

        result = module.lambda_handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "error" in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
