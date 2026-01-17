"""Unit tests for scrape_start Lambda handler."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_scrape_start_module():
    """Load scrape_start module using importlib (avoids 'lambda' keyword issue)."""
    module_path = Path(__file__).parent.parent.parent.parent / "src/lambda/scrape_start/index.py"
    spec = importlib.util.spec_from_file_location("scrape_start_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["scrape_start_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def _mock_env(monkeypatch):
    """Set up environment variables for tests (underscore prefix for side-effect fixture)."""
    monkeypatch.setenv("SCRAPE_JOBS_TABLE", "test-jobs-table")
    monkeypatch.setenv(
        "SCRAPE_DISCOVERY_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/queue"
    )
    monkeypatch.setenv("SCRAPE_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123:stateMachine:test")
    monkeypatch.setenv("TRACKING_TABLE", "test-tracking-table")
    monkeypatch.setenv("DATA_BUCKET", "test-data-bucket")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


class TestScrapeStartHandler:
    """Tests for scrape_start lambda_handler."""

    def test_missing_jobs_table_env(self, monkeypatch):
        """Test error when SCRAPE_JOBS_TABLE is missing."""
        monkeypatch.delenv("SCRAPE_JOBS_TABLE", raising=False)
        monkeypatch.setenv("SCRAPE_DISCOVERY_QUEUE_URL", "https://sqs.example.com/queue")
        monkeypatch.setenv("SCRAPE_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123:sm:test")

        module = _load_scrape_start_module()

        with pytest.raises(ValueError, match="SCRAPE_JOBS_TABLE"):
            module.lambda_handler({"base_url": "https://example.com"}, None)

    def test_missing_base_url(self, _mock_env):
        """Test error when base_url is missing."""
        module = _load_scrape_start_module()

        with pytest.raises(ValueError, match="base_url is required"):
            module.lambda_handler({}, None)

    def test_invalid_url_format(self, _mock_env):
        """Test error when URL doesn't start with http/https."""
        module = _load_scrape_start_module()

        with pytest.raises(ValueError, match="must start with http"):
            module.lambda_handler({"base_url": "ftp://example.com"}, None)

    def test_successful_job_creation(self, _mock_env):
        """Test successful job creation."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            # Mock DynamoDB
            mock_table = MagicMock()
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            # Mock SQS and Step Functions
            mock_sqs = MagicMock()
            mock_sfn = MagicMock()
            mock_sfn.start_execution.return_value = {
                "executionArn": "arn:aws:states:us-east-1:123:exec:test"
            }

            def client_factory(service, **kwargs):
                if service == "sqs":
                    return mock_sqs
                return mock_sfn

            mock_client.side_effect = client_factory

            module = _load_scrape_start_module()

            event = {
                "base_url": "https://docs.example.com",
                "config": {"max_pages": 100},
            }

            result = module.lambda_handler(event, None)

            assert "job_id" in result
            assert result["base_url"] == "https://docs.example.com"
            assert result["status"] == "discovering"

            # Verify DynamoDB put was called twice (jobs table + tracking table)
            assert mock_table.put_item.call_count == 2

            # Verify SQS message was sent
            mock_sqs.send_message.assert_called_once()


class TestConfigParsing:
    """Tests for config parsing."""

    def test_default_config_values(self, _mock_env):
        """Test that default config values are used."""
        with patch("boto3.resource") as mock_resource, patch("boto3.client") as mock_client:
            mock_table = MagicMock()
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            mock_sqs = MagicMock()
            mock_sfn = MagicMock()
            mock_sfn.start_execution.return_value = {"executionArn": "arn:test"}

            def client_factory(service, **kwargs):
                if service == "sqs":
                    return mock_sqs
                return mock_sfn

            mock_client.side_effect = client_factory

            module = _load_scrape_start_module()

            event = {"base_url": "https://example.com"}
            module.lambda_handler(event, None)

            # Verify job was created with default config (first put_item call)
            call_args = mock_table.put_item.call_args_list[0]
            job_data = call_args.kwargs.get("Item") or call_args[1].get("Item")

            assert job_data["config"]["max_pages"] == 1000
            assert job_data["config"]["max_depth"] == 3
            assert job_data["config"]["scope"] == "subpages"
