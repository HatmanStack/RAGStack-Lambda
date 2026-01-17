"""Tests for ragstack_common.ingestion module."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from ragstack_common.ingestion import (
    ingest_documents_with_retry,
    start_ingestion_with_retry,
)


class TestStartIngestionWithRetry:
    """Tests for start_ingestion_with_retry function."""

    def test_success_first_attempt(self):
        """Successful start on first attempt."""
        mock_client = MagicMock()
        mock_client.start_ingestion_job.return_value = {
            "ingestionJob": {"ingestionJobId": "job-123"}
        }

        result = start_ingestion_with_retry("kb-id", "ds-id", max_retries=3, client=mock_client)

        assert result["ingestionJob"]["ingestionJobId"] == "job-123"
        assert mock_client.start_ingestion_job.call_count == 1

    def test_retry_on_ongoing_validation_error(self):
        """Retries on 'ongoing' validation error."""
        mock_client = MagicMock()
        # First call fails with ongoing error, second succeeds
        mock_client.start_ingestion_job.side_effect = [
            ClientError(
                {"Error": {"Code": "ValidationException", "Message": "ongoing ingestion job"}},
                "StartIngestionJob",
            ),
            {"ingestionJob": {"ingestionJobId": "job-123"}},
        ]

        with patch("ragstack_common.ingestion.time.sleep"):
            result = start_ingestion_with_retry(
                "kb-id", "ds-id", max_retries=3, base_delay=0.1, client=mock_client
            )

        assert result["ingestionJob"]["ingestionJobId"] == "job-123"
        assert mock_client.start_ingestion_job.call_count == 2

    def test_raises_non_retryable_error(self):
        """Raises immediately on non-retryable errors."""
        mock_client = MagicMock()
        mock_client.start_ingestion_job.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "KB not found"}},
            "StartIngestionJob",
        )

        with pytest.raises(ClientError) as exc_info:
            start_ingestion_with_retry("kb-id", "ds-id", max_retries=3, client=mock_client)

        assert exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"
        assert mock_client.start_ingestion_job.call_count == 1


class TestIngestDocumentsWithRetry:
    """Tests for ingest_documents_with_retry function."""

    def test_success_first_attempt(self):
        """Successful ingestion on first attempt."""
        mock_client = MagicMock()
        mock_client.ingest_knowledge_base_documents.return_value = {
            "documentDetails": [{"status": "STARTING"}]
        }

        documents = [{"content": {"dataSourceType": "S3"}}]
        result = ingest_documents_with_retry(
            "kb-id", "ds-id", documents, max_retries=3, client=mock_client
        )

        assert result["documentDetails"][0]["status"] == "STARTING"
        assert mock_client.ingest_knowledge_base_documents.call_count == 1

    def test_retry_on_conflict_exception(self):
        """Retries on ConflictException (sync running)."""
        mock_client = MagicMock()
        # First call fails with conflict, second succeeds
        mock_client.ingest_knowledge_base_documents.side_effect = [
            ClientError(
                {"Error": {"Code": "ConflictException", "Message": "Sync job running"}},
                "IngestKnowledgeBaseDocuments",
            ),
            {"documentDetails": [{"status": "STARTING"}]},
        ]

        documents = [{"content": {"dataSourceType": "S3"}}]

        with patch("ragstack_common.ingestion.time.sleep"):
            result = ingest_documents_with_retry(
                "kb-id", "ds-id", documents, max_retries=3, base_delay=0.1, client=mock_client
            )

        assert result["documentDetails"][0]["status"] == "STARTING"
        assert mock_client.ingest_knowledge_base_documents.call_count == 2

    def test_retry_on_validation_ongoing(self):
        """Retries on ValidationException with 'ongoing' in message."""
        mock_client = MagicMock()
        mock_client.ingest_knowledge_base_documents.side_effect = [
            ClientError(
                {"Error": {"Code": "ValidationException", "Message": "ongoing API call"}},
                "IngestKnowledgeBaseDocuments",
            ),
            {"documentDetails": [{"status": "STARTING"}]},
        ]

        documents = [{"content": {"dataSourceType": "S3"}}]

        with patch("ragstack_common.ingestion.time.sleep"):
            result = ingest_documents_with_retry(
                "kb-id", "ds-id", documents, max_retries=3, base_delay=0.1, client=mock_client
            )

        assert result["documentDetails"][0]["status"] == "STARTING"
        assert mock_client.ingest_knowledge_base_documents.call_count == 2

    def test_retry_on_service_unavailable(self):
        """Retries on ServiceUnavailableException."""
        mock_client = MagicMock()
        mock_client.ingest_knowledge_base_documents.side_effect = [
            ClientError(
                {"Error": {"Code": "ServiceUnavailableException", "Message": "Service busy"}},
                "IngestKnowledgeBaseDocuments",
            ),
            {"documentDetails": [{"status": "STARTING"}]},
        ]

        documents = [{"content": {"dataSourceType": "S3"}}]

        with patch("ragstack_common.ingestion.time.sleep"):
            result = ingest_documents_with_retry(
                "kb-id", "ds-id", documents, max_retries=3, base_delay=0.1, client=mock_client
            )

        assert result["documentDetails"][0]["status"] == "STARTING"
        assert mock_client.ingest_knowledge_base_documents.call_count == 2

    def test_raises_non_retryable_error(self):
        """Raises immediately on non-retryable errors."""
        mock_client = MagicMock()
        mock_client.ingest_knowledge_base_documents.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid document format"}},
            "IngestKnowledgeBaseDocuments",
        )

        documents = [{"content": {"dataSourceType": "S3"}}]

        with pytest.raises(ClientError) as exc_info:
            ingest_documents_with_retry(
                "kb-id", "ds-id", documents, max_retries=3, client=mock_client
            )

        assert exc_info.value.response["Error"]["Code"] == "ValidationException"
        # Should raise immediately without retry (no "ongoing" in message)
        assert mock_client.ingest_knowledge_base_documents.call_count == 1

    def test_exhausts_retries(self):
        """Raises after exhausting all retries."""
        mock_client = MagicMock()
        # All calls fail with conflict
        mock_client.ingest_knowledge_base_documents.side_effect = ClientError(
            {"Error": {"Code": "ConflictException", "Message": "Sync running"}},
            "IngestKnowledgeBaseDocuments",
        )

        documents = [{"content": {"dataSourceType": "S3"}}]

        with (
            patch("ragstack_common.ingestion.time.sleep"),
            pytest.raises(ClientError) as exc_info,
        ):
            ingest_documents_with_retry(
                "kb-id", "ds-id", documents, max_retries=2, base_delay=0.1, client=mock_client
            )

        assert exc_info.value.response["Error"]["Code"] == "ConflictException"
        # Initial attempt + 2 retries = 3 calls
        assert mock_client.ingest_knowledge_base_documents.call_count == 3

    def test_exponential_backoff(self):
        """Uses exponential backoff between retries."""
        mock_client = MagicMock()
        mock_client.ingest_knowledge_base_documents.side_effect = [
            ClientError(
                {"Error": {"Code": "ConflictException", "Message": "Sync running"}},
                "IngestKnowledgeBaseDocuments",
            ),
            ClientError(
                {"Error": {"Code": "ConflictException", "Message": "Sync running"}},
                "IngestKnowledgeBaseDocuments",
            ),
            {"documentDetails": [{"status": "STARTING"}]},
        ]

        documents = [{"content": {"dataSourceType": "S3"}}]
        sleep_calls = []

        def record_sleep(x):
            sleep_calls.append(x)

        with patch("ragstack_common.ingestion.time.sleep", side_effect=record_sleep):
            ingest_documents_with_retry(
                "kb-id", "ds-id", documents, max_retries=3, base_delay=1.0, client=mock_client
            )

        # First retry: 1.0 * 2^0 = 1.0
        # Second retry: 1.0 * 2^1 = 2.0
        assert sleep_calls == [1.0, 2.0]
