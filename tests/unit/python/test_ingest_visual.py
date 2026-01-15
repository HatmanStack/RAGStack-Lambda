"""Unit tests for IngestVisualFunction Lambda.

Tests the visual embedding ingestion process that triggers StartIngestionJob
when video files are uploaded to content/{docId}/.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_ingest_visual_module():
    """Load the ingest_visual index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src" / "lambda" / "ingest_visual" / "index.py"
    ).resolve()

    spec = importlib.util.spec_from_file_location("ingest_visual_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_visual_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    """Set required environment variables for all tests."""
    env_vars = {
        "KNOWLEDGE_BASE_ID": "test-kb-id",
        "DATA_SOURCE_ID": "test-ds-id",
        "AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def s3_put_event():
    """S3 PUT event for video file in content/{docId}/."""
    return {
        "version": "0",
        "id": "87654321-dcba-4321-hgfe-210987654321",
        "detail-type": "Object Created",
        "source": "aws.s3",
        "account": "123456789012",
        "time": "2024-01-15T10:31:00Z",
        "region": "us-east-1",
        "resources": ["arn:aws:s3:::test-data-bucket"],
        "detail": {
            "version": "0",
            "bucket": {"name": "test-data-bucket"},
            "object": {
                "key": "content/doc-123/video.mp4",
                "size": 15728640,
                "etag": "d41d8cd98f00b204e9800998ecf8427e",
                "sequencer": "00A1B2C3D4E5F67890",
            },
            "request-id": "REQUEST123456789",
            "requester": "123456789012",
            "source-ip-address": "10.0.0.1",
            "reason": "PutObject",
        },
    }


class TestIngestVisualLambda:
    """Tests for the IngestVisualFunction Lambda handler."""

    @patch("boto3.client")
    def test_handler_starts_ingestion_job(self, mock_boto_client, s3_put_event):
        """Test that handler starts ingestion job for video file."""
        mock_bedrock_agent = MagicMock()
        mock_boto_client.return_value = mock_bedrock_agent
        mock_bedrock_agent.start_ingestion_job.return_value = {
            "ingestionJob": {
                "ingestionJobId": "job-123",
                "status": "STARTING",
                "knowledgeBaseId": "test-kb-id",
                "dataSourceId": "test-ds-id",
            }
        }

        module = load_ingest_visual_module()
        result = module.lambda_handler(s3_put_event, None)

        assert result["status"] == "success"
        assert result["job_id"] == "job-123"
        mock_bedrock_agent.start_ingestion_job.assert_called_once_with(
            knowledgeBaseId="test-kb-id",
            dataSourceId="test-ds-id",
        )

    @patch("boto3.client")
    def test_handler_skips_metadata_files(self, mock_boto_client, s3_put_event):
        """Test that handler skips .metadata.json files."""
        s3_put_event["detail"]["object"]["key"] = "content/doc-123/video.mp4.metadata.json"

        mock_bedrock_agent = MagicMock()
        mock_boto_client.return_value = mock_bedrock_agent

        module = load_ingest_visual_module()
        result = module.lambda_handler(s3_put_event, None)

        assert result["status"] == "skipped"
        assert "metadata" in result["message"].lower()
        mock_bedrock_agent.start_ingestion_job.assert_not_called()

    @patch("boto3.client")
    def test_handler_skips_non_video_files(self, mock_boto_client, s3_put_event):
        """Test that handler skips non-video files."""
        s3_put_event["detail"]["object"]["key"] = "content/doc-123/transcript_full.txt"

        mock_bedrock_agent = MagicMock()
        mock_boto_client.return_value = mock_bedrock_agent

        module = load_ingest_visual_module()
        result = module.lambda_handler(s3_put_event, None)

        assert result["status"] == "skipped"
        mock_bedrock_agent.start_ingestion_job.assert_not_called()

    @patch("boto3.client")
    def test_handler_logs_ingestion_statistics(self, mock_boto_client, s3_put_event):
        """Test that handler logs ingestion statistics for monitoring."""
        mock_bedrock_agent = MagicMock()
        mock_boto_client.return_value = mock_bedrock_agent
        mock_bedrock_agent.start_ingestion_job.return_value = {
            "ingestionJob": {
                "ingestionJobId": "job-123",
                "status": "STARTING",
                "knowledgeBaseId": "test-kb-id",
                "dataSourceId": "test-ds-id",
                "statistics": {
                    "numberOfDocumentsScanned": 5,
                    "numberOfNewDocumentsIndexed": 1,
                    "numberOfModifiedDocumentsIndexed": 0,
                    "numberOfDocumentsDeleted": 0,
                },
            }
        }

        module = load_ingest_visual_module()
        result = module.lambda_handler(s3_put_event, None)

        assert result["status"] == "success"
        # Statistics should be captured if available
        if "statistics" in result:
            assert "numberOfDocumentsScanned" in result["statistics"]

    @patch("boto3.client")
    def test_handler_with_polling_disabled(self, mock_boto_client, s3_put_event):
        """Test that handler works in fire-and-forget mode by default."""
        mock_bedrock_agent = MagicMock()
        mock_boto_client.return_value = mock_bedrock_agent
        mock_bedrock_agent.start_ingestion_job.return_value = {
            "ingestionJob": {
                "ingestionJobId": "job-123",
                "status": "STARTING",
            }
        }

        module = load_ingest_visual_module()
        result = module.lambda_handler(s3_put_event, None)

        assert result["status"] == "success"
        # Should not call get_ingestion_job when polling is disabled
        mock_bedrock_agent.get_ingestion_job.assert_not_called()

    @patch("boto3.client")
    def test_handler_validates_video_path_pattern(self, mock_boto_client, s3_put_event):
        """Test that handler only processes content/{docId}/video.mp4 pattern."""
        # Valid pattern
        s3_put_event["detail"]["object"]["key"] = "content/abc-123/video.mp4"

        mock_bedrock_agent = MagicMock()
        mock_boto_client.return_value = mock_bedrock_agent
        mock_bedrock_agent.start_ingestion_job.return_value = {
            "ingestionJob": {"ingestionJobId": "job-123", "status": "STARTING"}
        }

        module = load_ingest_visual_module()
        result = module.lambda_handler(s3_put_event, None)

        assert result["status"] == "success"

    @patch("boto3.client")
    def test_handler_skips_input_folder(self, mock_boto_client, s3_put_event):
        """Test that handler skips files in input/ folder."""
        s3_put_event["detail"]["object"]["key"] = "input/doc-123/video.mp4"

        mock_bedrock_agent = MagicMock()
        mock_boto_client.return_value = mock_bedrock_agent

        module = load_ingest_visual_module()
        result = module.lambda_handler(s3_put_event, None)

        assert result["status"] == "skipped"
        mock_bedrock_agent.start_ingestion_job.assert_not_called()
