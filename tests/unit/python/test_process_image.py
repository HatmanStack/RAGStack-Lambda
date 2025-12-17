"""Unit tests for process_image Lambda handler."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_process_image_module():
    """Load process_image module using importlib (avoids 'lambda' keyword issue)."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src/lambda/process_image/index.py"
    )
    spec = importlib.util.spec_from_file_location("process_image_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["process_image_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables for tests."""
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "test-kb-id")
    monkeypatch.setenv("DATA_SOURCE_ID", "test-ds-id")
    monkeypatch.setenv("TRACKING_TABLE", "test-tracking-table")
    monkeypatch.setenv("GRAPHQL_ENDPOINT", "https://test.appsync.amazonaws.com/graphql")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


@pytest.fixture
def mock_boto3():
    """Set up mocked boto3 clients and resources."""
    with (
        patch("boto3.client") as mock_client,
        patch("boto3.resource") as mock_resource,
    ):
        # Mock Bedrock Agent client
        mock_bedrock_agent = MagicMock()
        mock_bedrock_agent.ingest_knowledge_base_documents.return_value = {
            "documentDetails": [{"status": "STARTING"}]
        }

        # Mock S3 client
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {
            "ContentType": "image/png",
            "ContentLength": 12345,
        }
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(
                    return_value=json.dumps(
                        {
                            "caption": "Test caption",
                            "userCaption": "User caption",
                            "aiCaption": "AI caption",
                            "filename": "test.png",
                        }
                    ).encode()
                )
            )
        }

        # Mock DynamoDB resource
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "test-image-id",
                "filename": "test.png",
                "caption": "Test caption",
                "type": "image",
                "status": "PROCESSING",
                "input_s3_uri": "s3://test-bucket/images/test-image-id/test.png",
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        def client_factory(service):
            if service == "bedrock-agent":
                return mock_bedrock_agent
            if service == "s3":
                return mock_s3
            return MagicMock()

        mock_client.side_effect = client_factory
        mock_resource.return_value = mock_dynamodb

        yield {
            "bedrock_agent": mock_bedrock_agent,
            "s3": mock_s3,
            "dynamodb": mock_dynamodb,
            "table": mock_table,
        }


class TestProcessImage:
    """Tests for process_image Lambda handler."""

    def test_process_image_success(self, mock_env, mock_boto3):
        """Test successful image processing."""
        module = _load_process_image_module()

        # Reinitialize module clients
        module.bedrock_agent = mock_boto3["bedrock_agent"]
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "image_id": "test-image-id",
            "input_s3_uri": "s3://test-bucket/images/test-image-id/test.png",
        }

        # Mock publish_image_update
        with patch.object(module, "publish_image_update"):
            result = module.lambda_handler(event, None)

        assert result["image_id"] == "test-image-id"
        assert result["status"] == "INDEXED"
        assert result["knowledge_base_id"] == "test-kb-id"

        # Verify S3 text file was created
        mock_boto3["s3"].put_object.assert_called()

        # Verify Bedrock ingestion was called
        mock_boto3["bedrock_agent"].ingest_knowledge_base_documents.assert_called_once()

        # Verify DynamoDB was updated
        mock_boto3["table"].update_item.assert_called()

    def test_process_image_not_found_in_table(self, mock_env, mock_boto3):
        """Test error when image not in tracking table."""
        module = _load_process_image_module()
        module.bedrock_agent = mock_boto3["bedrock_agent"]
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        # Return empty item
        mock_boto3["table"].get_item.return_value = {}

        event = {
            "image_id": "nonexistent-id",
            "input_s3_uri": "s3://test-bucket/images/nonexistent-id/test.png",
        }

        with pytest.raises(ValueError, match="not found"):
            module.lambda_handler(event, None)

    def test_process_image_not_image_type(self, mock_env, mock_boto3):
        """Test error when record is not an image type."""
        module = _load_process_image_module()
        module.bedrock_agent = mock_boto3["bedrock_agent"]
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        # Return document type instead of image
        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "document_id": "test-id",
                "type": "document",  # Not image
                "status": "UPLOADED",
            }
        }

        event = {
            "image_id": "test-id",
            "input_s3_uri": "s3://test-bucket/input/test-id/doc.pdf",
        }

        with pytest.raises(ValueError, match="not an image"):
            module.lambda_handler(event, None)

    def test_process_image_missing_image_id(self, mock_env, mock_boto3):
        """Test error when image_id is missing."""
        module = _load_process_image_module()

        event = {"input_s3_uri": "s3://test-bucket/images/test-id/test.png"}

        with pytest.raises(ValueError, match="required"):
            module.lambda_handler(event, None)

    def test_process_image_missing_s3_uri_in_tracking(self, mock_env, mock_boto3):
        """Test error when tracking record has no input_s3_uri."""
        module = _load_process_image_module()
        module.bedrock_agent = mock_boto3["bedrock_agent"]
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        # Return item without input_s3_uri
        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "document_id": "test-image-id",
                "filename": "test.png",
                "type": "image",
                "status": "PROCESSING",
                # No input_s3_uri
            }
        }

        event = {"image_id": "test-image-id"}

        with pytest.raises(ValueError, match="No input_s3_uri"):
            module.lambda_handler(event, None)

    def test_process_image_s3_file_not_found(self, mock_env, mock_boto3):
        """Test error when image file not in S3."""
        from botocore.exceptions import ClientError

        module = _load_process_image_module()
        module.bedrock_agent = mock_boto3["bedrock_agent"]
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        # S3 raises 404
        mock_boto3["s3"].head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )

        event = {
            "image_id": "test-image-id",
            "input_s3_uri": "s3://test-bucket/images/test-image-id/test.png",
        }

        with pytest.raises(ValueError, match="not found in S3"):
            module.lambda_handler(event, None)

    def test_process_image_missing_env_vars(self, monkeypatch):
        """Test error when environment variables are missing."""
        monkeypatch.delenv("KNOWLEDGE_BASE_ID", raising=False)
        monkeypatch.delenv("DATA_SOURCE_ID", raising=False)
        monkeypatch.setenv("TRACKING_TABLE", "test-table")

        module = _load_process_image_module()

        event = {
            "image_id": "test-image-id",
            "input_s3_uri": "s3://test-bucket/images/test-image-id/test.png",
        }

        with pytest.raises(ValueError, match="required"):
            module.lambda_handler(event, None)


class TestBuildIngestionText:
    """Tests for build_ingestion_text helper function."""

    def test_build_ingestion_text_with_all_captions(self, mock_env, mock_boto3):
        """Test text building with user and AI captions."""
        module = _load_process_image_module()

        text = module.build_ingestion_text(
            image_id="test-id",
            filename="vacation.png",
            caption="My vacation photo. A sunset over the ocean.",
            metadata={
                "userCaption": "My vacation photo",
                "aiCaption": "A sunset over the ocean",
            },
        )

        assert "image_id: test-id" in text
        assert "filename: vacation.png" in text
        assert "type: image" in text
        assert "user_caption: My vacation photo" in text
        assert "ai_caption: A sunset over the ocean" in text
        assert "My vacation photo. A sunset over the ocean." in text

    def test_build_ingestion_text_caption_only(self, mock_env, mock_boto3):
        """Test text building with only combined caption."""
        module = _load_process_image_module()

        text = module.build_ingestion_text(
            image_id="test-id",
            filename="image.jpg",
            caption="A simple caption",
            metadata={},
        )

        assert "A simple caption" in text
        assert "image_id: test-id" in text

    def test_build_ingestion_text_empty_caption(self, mock_env, mock_boto3):
        """Test text building with no caption."""
        module = _load_process_image_module()

        text = module.build_ingestion_text(
            image_id="test-id",
            filename="image.jpg",
            caption="",
            metadata={},
        )

        # Should still have frontmatter
        assert "image_id: test-id" in text
        assert "type: image" in text
