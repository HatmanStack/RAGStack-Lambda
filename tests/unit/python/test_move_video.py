"""Unit tests for MoveVideoFunction Lambda.

Tests the video move process that copies video from input/ to content/{docId}/
and creates metadata for KB visual embeddings.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_move_video_module():
    """Load the move_video index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src" / "lambda" / "move_video" / "index.py"
    ).resolve()

    spec = importlib.util.spec_from_file_location("move_video_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["move_video_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    """Set required environment variables for all tests."""
    env_vars = {
        "TRACKING_TABLE": "test-tracking-table",
        "DATA_BUCKET": "test-data-bucket",
        "AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def step_functions_event():
    """Step Functions success event for media pipeline."""
    return {
        "version": "0",
        "id": "12345678-abcd-1234-efgh-123456789012",
        "detail-type": "Step Functions Execution Status Change",
        "source": "aws.states",
        "account": "123456789012",
        "time": "2024-01-15T10:30:00Z",
        "region": "us-east-1",
        "resources": [
            "arn:aws:states:us-east-1:123456789012:execution:test-ProcessingPipeline:test-exec"
        ],
        "detail": {
            "executionArn": "arn:aws:states:us-east-1:123456789012:execution:test-Pipeline:test",
            "stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:test-Pipeline",
            "name": "test-execution-id",
            "status": "SUCCEEDED",
            "startDate": 1705313400000,
            "stopDate": 1705313460000,
            "input": json.dumps(
                {
                    "document_id": "input/doc-123/sample-video.mp4",
                    "input_s3_uri": "s3://test-data-bucket/input/doc-123/sample-video.mp4",
                    "output_s3_prefix": "s3://test-data-bucket/content/doc-123",
                }
            ),
            "output": json.dumps(
                {
                    "document_id": "doc-123",
                    "status": "completed",
                    "message": "Document successfully processed",
                }
            ),
            "inputDetails": {"included": True},
            "outputDetails": {"included": True},
        },
    }


class TestMoveVideoLambda:
    """Tests for the MoveVideoFunction Lambda handler."""

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_handler_moves_video_successfully(
        self, mock_boto_client, mock_boto_resource, step_functions_event
    ):
        """Test that handler moves video from input/ to content/{docId}/."""
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.head_object.return_value = {"ContentLength": 1024}
        mock_s3.copy_object.return_value = {"CopyObjectResult": {"ETag": "test-etag"}}

        # Mock DynamoDB
        mock_dynamodb = MagicMock()
        mock_boto_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "doc-123",
                "filename": "sample-video.mp4",
                "type": "media",
                "input_s3_uri": "s3://test-data-bucket/input/doc-123/sample-video.mp4",
            }
        }

        module = load_move_video_module()
        result = module.lambda_handler(step_functions_event, None)

        assert result["status"] == "success"
        assert "doc-123" in result["new_s3_uri"]
        assert "video.mp4" in result["new_s3_uri"]

        # Verify metadata was uploaded before copy
        put_calls = [
            call for call in mock_s3.put_object.call_args_list if ".metadata.json" in str(call)
        ]
        assert len(put_calls) == 1

        # Verify copy was called
        mock_s3.copy_object.assert_called_once()

        # Verify original was deleted
        mock_s3.delete_object.assert_called_once()

        # Verify tracking table was updated
        mock_table.update_item.assert_called_once()

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_handler_skips_non_video_files(
        self, mock_boto_client, mock_boto_resource, step_functions_event
    ):
        """Test that handler skips non-video files (type != media)."""
        # Mock DynamoDB with non-media type
        mock_dynamodb = MagicMock()
        mock_boto_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "doc-123",
                "filename": "document.pdf",
                "type": "document",  # Not media
            }
        }

        module = load_move_video_module()
        result = module.lambda_handler(step_functions_event, None)

        assert result["status"] == "skipped"
        msg = result["message"].lower()
        assert "not a video" in msg or "not media" in msg

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_handler_is_idempotent(
        self, mock_boto_client, mock_boto_resource, step_functions_event
    ):
        """Test that re-running handler when video already moved doesn't fail."""
        # Mock S3 client - video doesn't exist at source
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        from botocore.exceptions import ClientError

        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )

        # Mock DynamoDB
        mock_dynamodb = MagicMock()
        mock_boto_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "doc-123",
                "filename": "sample-video.mp4",
                "type": "media",
                "input_s3_uri": "s3://test-data-bucket/content/doc-123/video.mp4",
            }
        }

        module = load_move_video_module()
        result = module.lambda_handler(step_functions_event, None)

        assert result["status"] == "skipped"
        # Should not try to copy or delete
        mock_s3.copy_object.assert_not_called()
        mock_s3.delete_object.assert_not_called()

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_handler_does_not_delete_on_copy_failure(
        self, mock_boto_client, mock_boto_resource, step_functions_event
    ):
        """Test that original is not deleted if copy fails."""
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.head_object.return_value = {"ContentLength": 1024}
        from botocore.exceptions import ClientError

        mock_s3.copy_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal Error"}}, "CopyObject"
        )

        # Mock DynamoDB
        mock_dynamodb = MagicMock()
        mock_boto_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "doc-123",
                "filename": "sample-video.mp4",
                "type": "media",
                "input_s3_uri": "s3://test-data-bucket/input/doc-123/sample-video.mp4",
            }
        }

        module = load_move_video_module()

        with pytest.raises(ClientError):
            module.lambda_handler(step_functions_event, None)

        # Should NOT delete original on copy failure
        mock_s3.delete_object.assert_not_called()

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_metadata_file_structure(
        self, mock_boto_client, mock_boto_resource, step_functions_event
    ):
        """Test that metadata file has correct structure."""
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.head_object.return_value = {"ContentLength": 1024}
        mock_s3.copy_object.return_value = {"CopyObjectResult": {"ETag": "test-etag"}}

        # Mock DynamoDB
        mock_dynamodb = MagicMock()
        mock_boto_resource.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "doc-123",
                "filename": "sample-video.mp4",
                "type": "media",
                "input_s3_uri": "s3://test-data-bucket/input/doc-123/sample-video.mp4",
            }
        }

        module = load_move_video_module()
        module.lambda_handler(step_functions_event, None)

        # Get the metadata that was uploaded
        put_calls = mock_s3.put_object.call_args_list
        metadata_call = [c for c in put_calls if ".metadata.json" in str(c.kwargs.get("Key", ""))]
        assert len(metadata_call) == 1

        metadata_body = json.loads(metadata_call[0].kwargs["Body"])
        assert "metadataAttributes" in metadata_body
        attrs = metadata_body["metadataAttributes"]
        assert attrs["content_type"] == "visual"
        assert attrs["document_id"] == "doc-123"
        assert attrs["media_type"] == "video"
        assert attrs["filename"] == "sample-video.mp4"
