"""Tests for sync_coordinator Lambda."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables."""
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "test-kb-id")
    monkeypatch.setenv("DATA_SOURCE_ID", "test-ds-id")
    monkeypatch.setenv("TRACKING_TABLE", "test-tracking-table")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


def import_sync_coordinator():
    """Import sync_coordinator module (handles 'lambda' in path)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "sync_coordinator",
        "src/lambda/sync_coordinator/index.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_coordinator"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_bedrock_agent():
    """Mock bedrock-agent client."""
    with patch("boto3.client") as mock_client:
        mock_agent = MagicMock()
        mock_client.return_value = mock_agent
        yield mock_agent


@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB resource."""
    with patch("boto3.resource") as mock_resource:
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.Table.return_value = mock_table
        mock_resource.return_value = mock_db
        yield mock_table


class TestWaitForSyncCompletion:
    """Tests for wait_for_sync_completion function."""

    def test_no_jobs_returns_true(self, mock_env, mock_bedrock_agent):
        """Returns True when no ingestion jobs exist."""
        mock_bedrock_agent.list_ingestion_jobs.return_value = {"ingestionJobSummaries": []}

        module = import_sync_coordinator()
        result = module.wait_for_sync_completion("kb-id", "ds-id", max_wait=5)
        assert result is True

    def test_completed_job_returns_true(self, mock_env, mock_bedrock_agent):
        """Returns True when latest job is completed."""
        mock_bedrock_agent.list_ingestion_jobs.return_value = {
            "ingestionJobSummaries": [{"ingestionJobId": "job-1", "status": "COMPLETE"}]
        }

        module = import_sync_coordinator()
        result = module.wait_for_sync_completion("kb-id", "ds-id", max_wait=5)
        assert result is True

    def test_failed_job_returns_true(self, mock_env, mock_bedrock_agent):
        """Returns True when latest job failed (safe to start new)."""
        mock_bedrock_agent.list_ingestion_jobs.return_value = {
            "ingestionJobSummaries": [{"ingestionJobId": "job-1", "status": "FAILED"}]
        }

        module = import_sync_coordinator()
        result = module.wait_for_sync_completion("kb-id", "ds-id", max_wait=5)
        assert result is True

    def test_in_progress_waits_then_completes(self, mock_env, mock_bedrock_agent):
        """Waits for in-progress job then returns True when complete."""
        # First call: IN_PROGRESS, second call: COMPLETE
        mock_bedrock_agent.list_ingestion_jobs.side_effect = [
            {"ingestionJobSummaries": [{"ingestionJobId": "job-1", "status": "IN_PROGRESS"}]},
            {"ingestionJobSummaries": [{"ingestionJobId": "job-1", "status": "COMPLETE"}]},
        ]

        module = import_sync_coordinator()
        with patch.object(module.time, "sleep"):
            result = module.wait_for_sync_completion("kb-id", "ds-id", max_wait=60)

        assert result is True
        assert mock_bedrock_agent.list_ingestion_jobs.call_count == 2


class TestStartSyncJob:
    """Tests for start_sync_job function."""

    def test_successful_start(self, mock_env, mock_bedrock_agent):
        """Successfully starts ingestion job."""
        with patch(
            "ragstack_common.ingestion.start_ingestion_with_retry"
        ) as mock_start:
            mock_start.return_value = {"ingestionJob": {"ingestionJobId": "new-job-123"}}

            module = import_sync_coordinator()
            result = module.start_sync_job("kb-id", "ds-id")

            assert result is not None
            assert result["ingestionJobId"] == "new-job-123"

    def test_failed_start_returns_none(self, mock_env, mock_bedrock_agent):
        """Returns None when start fails after retries exhausted."""
        with patch(
            "ragstack_common.ingestion.start_ingestion_with_retry"
        ) as mock_start:
            mock_start.side_effect = ClientError(
                {"Error": {"Code": "ConflictException", "Message": "Another job running"}},
                "StartIngestionJob",
            )

            module = import_sync_coordinator()
            result = module.start_sync_job("kb-id", "ds-id")
            assert result is None


class TestLambdaHandler:
    """Tests for sync_coordinator lambda_handler."""

    def test_successful_sync(self, mock_env, mock_bedrock_agent, mock_dynamodb):
        """Successfully processes sync request."""
        # No running jobs
        mock_bedrock_agent.list_ingestion_jobs.return_value = {"ingestionJobSummaries": []}

        with patch(
            "ragstack_common.ingestion.start_ingestion_with_retry"
        ) as mock_start:
            mock_start.return_value = {"ingestionJob": {"ingestionJobId": "new-job-123"}}

            module = import_sync_coordinator()
            event = {
                "Records": [
                    {
                        "body": json.dumps(
                            {
                                "kb_id": "test-kb",
                                "ds_id": "test-ds",
                                "document_ids": ["doc-1", "doc-2"],
                                "source": "process_image",
                            }
                        )
                    }
                ]
            }

            result = module.lambda_handler(event, None)

            assert result["status"] == "SYNC_STARTED"
            assert result["job_id"] == "new-job-123"
            assert result["documents_affected"] == 2

    def test_sync_start_failure_updates_status(self, mock_env, mock_bedrock_agent, mock_dynamodb):
        """Updates document status to INGESTION_FAILED when sync fails to start."""
        # No running jobs
        mock_bedrock_agent.list_ingestion_jobs.return_value = {"ingestionJobSummaries": []}

        with patch(
            "ragstack_common.ingestion.start_ingestion_with_retry"
        ) as mock_start:
            # Start fails after retries exhausted
            mock_start.side_effect = ClientError(
                {"Error": {"Code": "ValidationException", "Message": "Invalid request"}},
                "StartIngestionJob",
            )

            module = import_sync_coordinator()
            event = {
                "Records": [
                    {
                        "body": json.dumps(
                            {
                                "kb_id": "test-kb",
                                "ds_id": "test-ds",
                                "document_ids": ["doc-1"],
                                "source": "process_image",
                            }
                        )
                    }
                ]
            }

            result = module.lambda_handler(event, None)

            assert result["status"] == "FAILED"
            # Verify status update was called
            mock_dynamodb.update_item.assert_called()

    def test_missing_env_vars_raises(self, monkeypatch):
        """Raises error when required env vars missing."""
        monkeypatch.delenv("KNOWLEDGE_BASE_ID", raising=False)
        monkeypatch.delenv("DATA_SOURCE_ID", raising=False)

        module = import_sync_coordinator()
        with pytest.raises(ValueError, match="KNOWLEDGE_BASE_ID and DATA_SOURCE_ID are required"):
            module.lambda_handler({"Records": []}, None)
