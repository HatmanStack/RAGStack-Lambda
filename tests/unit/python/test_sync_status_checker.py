"""Tests for sync_status_checker Lambda."""

import importlib.util
import sys
from unittest.mock import MagicMock, patch

import pytest


def import_sync_status_checker():
    """Import sync_status_checker module (handles 'lambda' in path)."""
    spec = importlib.util.spec_from_file_location(
        "sync_status_checker",
        "src/lambda/sync_status_checker/index.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_status_checker"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables."""
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "test-kb-id")
    monkeypatch.setenv("DATA_SOURCE_ID", "test-ds-id")
    monkeypatch.setenv("TRACKING_TABLE", "test-tracking-table")
    monkeypatch.setenv("GRAPHQL_ENDPOINT", "https://test.appsync.amazonaws.com/graphql")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB resource."""
    with patch("boto3.resource") as mock_resource:
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.Table.return_value = mock_table
        mock_resource.return_value = mock_db
        yield mock_table


class TestGetSyncQueuedDocuments:
    """Tests for get_sync_queued_documents function."""

    def test_returns_sync_queued_documents(self, mock_env, mock_dynamodb):
        """Returns documents with SYNC_QUEUED status."""
        mock_dynamodb.scan.return_value = {
            "Items": [
                {
                    "document_id": "doc-1",
                    "status": "SYNC_QUEUED",
                    "caption_s3_uri": "s3://bucket/doc1.txt",
                },
                {
                    "document_id": "doc-2",
                    "status": "SYNC_QUEUED",
                    "caption_s3_uri": "s3://bucket/doc2.txt",
                },
            ]
        }

        module = import_sync_status_checker()
        result = module.get_sync_queued_documents("test-table")

        assert len(result) == 2
        assert result[0]["document_id"] == "doc-1"

    def test_returns_empty_when_no_documents(self, mock_env, mock_dynamodb):
        """Returns empty list when no SYNC_QUEUED documents."""
        mock_dynamodb.scan.return_value = {"Items": []}

        module = import_sync_status_checker()
        result = module.get_sync_queued_documents("test-table")

        assert result == []


class TestUpdateDocumentStatus:
    """Tests for update_document_status function."""

    def test_updates_status_to_indexed(self, mock_env, mock_dynamodb):
        """Updates document status to INDEXED."""
        module = import_sync_status_checker()
        module.update_document_status("test-table", "doc-1", "INDEXED")

        mock_dynamodb.update_item.assert_called_once()
        call_kwargs = mock_dynamodb.update_item.call_args[1]
        assert call_kwargs["Key"] == {"document_id": "doc-1"}
        assert ":status" in call_kwargs["ExpressionAttributeValues"]
        assert call_kwargs["ExpressionAttributeValues"][":status"] == "INDEXED"

    def test_updates_status_with_error_message(self, mock_env, mock_dynamodb):
        """Includes error message when updating to failed status."""
        module = import_sync_status_checker()
        module.update_document_status("test-table", "doc-1", "INGESTION_FAILED", "KB sync failed")

        mock_dynamodb.update_item.assert_called_once()
        call_kwargs = mock_dynamodb.update_item.call_args[1]
        assert ":error" in call_kwargs["ExpressionAttributeValues"]
        assert call_kwargs["ExpressionAttributeValues"][":error"] == "KB sync failed"


class TestLambdaHandler:
    """Tests for sync_status_checker lambda_handler."""

    def test_no_documents_to_check(self, mock_env, mock_dynamodb):
        """Returns early when no SYNC_QUEUED documents."""
        mock_dynamodb.scan.return_value = {"Items": []}

        module = import_sync_status_checker()
        result = module.lambda_handler({}, None)

        assert result["checked"] == 0
        assert result["updated"] == 0

    def test_updates_indexed_documents(self, mock_env, mock_dynamodb):
        """Updates status when KB reports INDEXED."""
        mock_dynamodb.scan.return_value = {
            "Items": [
                {
                    "document_id": "doc-1",
                    "status": "SYNC_QUEUED",
                    "caption_s3_uri": "s3://bucket/content/doc-1/caption.txt",
                    "type": "image",
                    "filename": "test.jpg",
                },
            ]
        }

        with patch("ragstack_common.ingestion.batch_check_document_statuses") as mock_batch_check:
            mock_batch_check.return_value = {"s3://bucket/content/doc-1/caption.txt": "INDEXED"}

            module = import_sync_status_checker()

            # Also mock the publish function
            with patch.object(module, "publish_image_update"):
                result = module.lambda_handler({}, None)

        assert result["checked"] == 1
        assert result["updated"] == 1
        assert result["indexed"] == 1
        assert result["failed"] == 0

    def test_updates_failed_documents(self, mock_env, mock_dynamodb):
        """Updates status when KB reports FAILED."""
        mock_dynamodb.scan.return_value = {
            "Items": [
                {
                    "document_id": "doc-1",
                    "status": "SYNC_QUEUED",
                    "caption_s3_uri": "s3://bucket/content/doc-1/caption.txt",
                    "type": "image",
                    "filename": "test.jpg",
                },
            ]
        }

        with patch("ragstack_common.ingestion.batch_check_document_statuses") as mock_batch_check:
            mock_batch_check.return_value = {"s3://bucket/content/doc-1/caption.txt": "FAILED"}

            module = import_sync_status_checker()

            with patch.object(module, "publish_image_update"):
                result = module.lambda_handler({}, None)

        assert result["checked"] == 1
        assert result["updated"] == 1
        assert result["indexed"] == 0
        assert result["failed"] == 1

    def test_leaves_in_progress_documents(self, mock_env, mock_dynamodb):
        """Leaves status unchanged for documents still processing."""
        mock_dynamodb.scan.return_value = {
            "Items": [
                {
                    "document_id": "doc-1",
                    "status": "SYNC_QUEUED",
                    "caption_s3_uri": "s3://bucket/content/doc-1/caption.txt",
                },
            ]
        }

        with patch("ragstack_common.ingestion.batch_check_document_statuses") as mock_batch_check:
            mock_batch_check.return_value = {"s3://bucket/content/doc-1/caption.txt": "IN_PROGRESS"}

            module = import_sync_status_checker()
            result = module.lambda_handler({}, None)

        assert result["checked"] == 1
        assert result["updated"] == 0  # Not updated because still processing

    def test_missing_env_vars_raises(self, monkeypatch):
        """Raises error when required env vars missing."""
        monkeypatch.delenv("KNOWLEDGE_BASE_ID", raising=False)
        monkeypatch.delenv("DATA_SOURCE_ID", raising=False)
        monkeypatch.delenv("TRACKING_TABLE", raising=False)

        module = import_sync_status_checker()
        with pytest.raises(ValueError):
            module.lambda_handler({}, None)
