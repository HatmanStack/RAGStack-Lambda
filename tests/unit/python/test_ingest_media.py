"""Unit tests for IngestMedia Lambda.

Tests the media ingestion process that handles dual embeddings
(text transcripts and visual segments).

Note: Since 'lambda' is a Python keyword, we use importlib to load the module.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_ingest_media_module():
    """Load the ingest_media index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src"
        / "lambda"
        / "ingest_media"
        / "index.py"
    ).resolve()

    spec = importlib.util.spec_from_file_location("ingest_media_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_media_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    """Set required environment variables for all tests."""
    env_vars = {
        "KNOWLEDGE_BASE_ID": "test-kb-id",
        "DATA_SOURCE_ID": "test-ds-id",
        "TRACKING_TABLE": "test-tracking-table",
        "GRAPHQL_ENDPOINT": "https://test-api.appsync.amazonaws.com/graphql",
        "VECTOR_BUCKET": "test-vector-bucket",
        "AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def sample_media_event():
    """Sample media ingestion event."""
    return {
        "document_id": "media-123",
        "output_s3_uri": "s3://test-bucket/content/media-123/transcript_full.txt",
        "media_type": "video",
        "duration_seconds": 120,
        "total_segments": 4,
        "visual_segments": [
            {
                "segment_index": 0,
                "timestamp_start": 0,
                "timestamp_end": 30,
                "s3_uri": "s3://test-bucket/segments/media-123/segment_000.mp4",
            },
            {
                "segment_index": 1,
                "timestamp_start": 30,
                "timestamp_end": 60,
                "s3_uri": "s3://test-bucket/segments/media-123/segment_001.mp4",
            },
        ],
        "transcript_segments": [
            {
                "segment_index": 0,
                "timestamp_start": 0,
                "timestamp_end": 30,
                "text": "Welcome to the video",
                "word_count": 4,
            },
        ],
    }


class TestIngestMediaLambda:
    """Tests for the IngestMedia Lambda handler."""

    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.storage.read_s3_text")
    @patch("boto3.resource")
    @patch("boto3.client")
    def test_handler_ingests_text_to_kb(
        self,
        mock_boto_client,
        mock_boto_resource,
        mock_read_s3,
        mock_publish,
        sample_media_event,
    ):
        """Test that handler ingests text content to knowledge base."""
        mock_read_s3.return_value = "Test transcript content"

        # Mock S3 client
        mock_s3 = MagicMock()

        # Mock Bedrock Agent client
        mock_bedrock_agent = MagicMock()
        mock_bedrock_agent.ingest_knowledge_base_documents.return_value = {
            "documentDetails": [{"status": "STARTING"}]
        }

        # Mock DynamoDB
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {"document_id": "media-123", "filename": "video.mp4"}
        }

        def client_factory(service_name, **kwargs):
            if service_name == "bedrock-agent":
                return mock_bedrock_agent
            if service_name == "s3":
                return mock_s3
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        # Load and execute
        module = load_ingest_media_module()
        result = module.lambda_handler(sample_media_event, None)

        assert result["status"] == "indexed"
        assert result["document_id"] == "media-123"

    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.storage.read_s3_text")
    @patch("ragstack_common.nova_embeddings.NovaEmbeddingsClient")
    @patch("boto3.resource")
    @patch("boto3.client")
    def test_handler_creates_visual_embeddings(
        self,
        mock_boto_client,
        mock_boto_resource,
        mock_nova_client_class,
        mock_read_s3,
        mock_publish,
        sample_media_event,
    ):
        """Test that handler creates embeddings for visual segments."""
        mock_read_s3.return_value = "Test content"

        # Mock Nova embeddings client
        mock_nova_client = MagicMock()
        mock_nova_client.embed_from_s3.return_value = {"embedding": [0.1] * 1024}
        mock_nova_client_class.return_value = mock_nova_client

        mock_s3 = MagicMock()
        mock_bedrock_agent = MagicMock()
        mock_bedrock_agent.ingest_knowledge_base_documents.return_value = {
            "documentDetails": [{"status": "STARTING"}]
        }

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": {"document_id": "media-123"}}

        def client_factory(service_name, **kwargs):
            if service_name == "bedrock-agent":
                return mock_bedrock_agent
            if service_name == "s3":
                return mock_s3
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        module = load_ingest_media_module()
        result = module.lambda_handler(sample_media_event, None)

        assert "visual_segments_indexed" in result

    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.storage.read_s3_text")
    @patch("boto3.resource")
    @patch("boto3.client")
    def test_handler_updates_tracking_status(
        self,
        mock_boto_client,
        mock_boto_resource,
        mock_read_s3,
        mock_publish,
        sample_media_event,
    ):
        """Test that handler updates DynamoDB tracking status."""
        mock_read_s3.return_value = "Test transcript"

        mock_s3 = MagicMock()
        mock_bedrock_agent = MagicMock()
        mock_bedrock_agent.ingest_knowledge_base_documents.return_value = {
            "documentDetails": [{"status": "STARTING"}]
        }

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": {"document_id": "media-123"}}

        mock_boto_client.side_effect = lambda svc, **_kw: {
            "bedrock-agent": mock_bedrock_agent,
            "s3": mock_s3,
        }.get(svc, MagicMock())

        module = load_ingest_media_module()
        module.lambda_handler(sample_media_event, None)

        # Verify status was updated
        mock_table.update_item.assert_called()

    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.storage.read_s3_text")
    @patch("boto3.resource")
    @patch("boto3.client")
    def test_handler_handles_no_visual_segments(
        self,
        mock_boto_client,
        mock_boto_resource,
        mock_read_s3,
        mock_publish,
    ):
        """Test handler works when no visual segments are provided."""
        event = {
            "document_id": "media-456",
            "output_s3_uri": "s3://test-bucket/transcript.txt",
            "media_type": "audio",
            "visual_segments": [],
        }

        mock_read_s3.return_value = "Test transcript"

        mock_s3 = MagicMock()
        mock_bedrock_agent = MagicMock()
        mock_bedrock_agent.ingest_knowledge_base_documents.return_value = {
            "documentDetails": [{"status": "STARTING"}]
        }

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table
        mock_table.get_item.return_value = {"Item": {"document_id": "media-456"}}

        mock_boto_client.side_effect = lambda svc, **_kw: {
            "bedrock-agent": mock_bedrock_agent,
            "s3": mock_s3,
        }.get(svc, MagicMock())

        module = load_ingest_media_module()
        result = module.lambda_handler(event, None)

        assert result["status"] == "indexed"
        assert result.get("visual_segments_indexed", 0) == 0


class TestIngestMediaValidation:
    """Tests for input validation."""

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_handler_requires_document_id(
        self, mock_boto_client, mock_boto_resource
    ):
        """Test that handler requires document_id."""
        event = {"output_s3_uri": "s3://bucket/key"}

        module = load_ingest_media_module()

        with pytest.raises(ValueError, match="document_id"):
            module.lambda_handler(event, None)

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_handler_requires_output_s3_uri(
        self, mock_boto_client, mock_boto_resource
    ):
        """Test that handler requires output_s3_uri."""
        event = {"document_id": "media-123"}

        module = load_ingest_media_module()

        with pytest.raises(ValueError, match="output_s3_uri"):
            module.lambda_handler(event, None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
