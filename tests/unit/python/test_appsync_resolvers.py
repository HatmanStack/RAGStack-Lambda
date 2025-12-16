"""Unit tests for AppSync resolver Lambda handlers."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_appsync_resolvers_module():
    """Load appsync_resolvers module using importlib (avoids 'lambda' keyword issue)."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src/lambda/appsync_resolvers/index.py"
    )
    spec = importlib.util.spec_from_file_location("appsync_resolvers_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["appsync_resolvers_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables for tests."""
    monkeypatch.setenv("TRACKING_TABLE", "test-tracking-table")
    monkeypatch.setenv("DATA_BUCKET", "test-data-bucket")
    monkeypatch.setenv("STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123:stateMachine:test")


@pytest.fixture
def mock_boto3():
    """Set up mocked boto3 clients and resources."""
    with patch("boto3.client") as mock_client, patch("boto3.resource") as mock_resource:
        # Mock S3 client
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_post.return_value = {
            "url": "https://test-bucket.s3.amazonaws.com/",
            "fields": {"key": "test-key", "policy": "test-policy"},
        }

        # Mock DynamoDB resource
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        def client_factory(service):
            if service == "s3":
                return mock_s3
            if service == "stepfunctions":
                return MagicMock()
            return MagicMock()

        mock_client.side_effect = client_factory
        mock_resource.return_value = mock_dynamodb

        yield {
            "s3": mock_s3,
            "dynamodb": mock_dynamodb,
            "table": mock_table,
        }


# =============================================================================
# Image Upload URL Resolver Tests
# =============================================================================


class TestCreateImageUploadUrl:
    """Tests for createImageUploadUrl resolver."""

    def test_create_image_upload_url_png(self, mock_env, mock_boto3):
        """Test successful image upload URL creation for PNG file."""
        module = _load_appsync_resolvers_module()

        # Reinitialize module-level variables with mocked values
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": "test-image.png"},
        }

        result = module.lambda_handler(event, None)

        # Verify response structure
        assert "uploadUrl" in result
        assert "imageId" in result
        assert "fields" in result
        assert result["uploadUrl"] == "https://test-bucket.s3.amazonaws.com/"

        # Verify S3 presigned URL was requested with images/ prefix
        mock_boto3["s3"].generate_presigned_post.assert_called_once()
        call_kwargs = mock_boto3["s3"].generate_presigned_post.call_args.kwargs
        assert call_kwargs["Key"].startswith("images/")
        assert call_kwargs["Key"].endswith("/test-image.png")

        # Verify DynamoDB record was created
        mock_boto3["table"].put_item.assert_called_once()
        put_args = mock_boto3["table"].put_item.call_args.kwargs["Item"]
        assert put_args["type"] == "image"
        assert put_args["status"] == "PENDING"
        assert put_args["filename"] == "test-image.png"

    def test_create_image_upload_url_jpg(self, mock_env, mock_boto3):
        """Test successful image upload URL creation for JPG file."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": "photo.jpg"},
        }

        result = module.lambda_handler(event, None)

        assert "imageId" in result
        call_kwargs = mock_boto3["s3"].generate_presigned_post.call_args.kwargs
        assert call_kwargs["Key"].endswith("/photo.jpg")

    def test_create_image_upload_url_gif(self, mock_env, mock_boto3):
        """Test successful image upload URL creation for GIF file."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": "animation.gif"},
        }

        result = module.lambda_handler(event, None)
        assert "imageId" in result

    def test_create_image_upload_url_webp(self, mock_env, mock_boto3):
        """Test successful image upload URL creation for WebP file."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": "modern.webp"},
        }

        result = module.lambda_handler(event, None)
        assert "imageId" in result

    def test_create_image_upload_url_reject_pdf(self, mock_env, mock_boto3):
        """Test rejection of non-image file (PDF)."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": "document.pdf"},
        }

        with pytest.raises(ValueError, match="Unsupported"):
            module.lambda_handler(event, None)

    def test_create_image_upload_url_reject_doc(self, mock_env, mock_boto3):
        """Test rejection of non-image file (DOC)."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": "document.doc"},
        }

        with pytest.raises(ValueError, match="Unsupported"):
            module.lambda_handler(event, None)

    def test_create_image_upload_url_reject_path_traversal(self, mock_env, mock_boto3):
        """Test rejection of filename with path traversal."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": "../../../etc/passwd.png"},
        }

        with pytest.raises(ValueError, match="invalid path"):
            module.lambda_handler(event, None)

    def test_create_image_upload_url_reject_forward_slash(self, mock_env, mock_boto3):
        """Test rejection of filename with forward slash."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": "path/to/image.png"},
        }

        with pytest.raises(ValueError, match="invalid path"):
            module.lambda_handler(event, None)

    def test_create_image_upload_url_reject_long_filename(self, mock_env, mock_boto3):
        """Test rejection of filename exceeding max length."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        long_filename = "a" * 256 + ".png"
        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": long_filename},
        }

        with pytest.raises(ValueError, match="255 characters"):
            module.lambda_handler(event, None)

    def test_create_image_upload_url_reject_empty_filename(self, mock_env, mock_boto3):
        """Test rejection of empty filename."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": ""},
        }

        with pytest.raises(ValueError, match="must be between"):
            module.lambda_handler(event, None)

    def test_create_image_upload_url_case_insensitive(self, mock_env, mock_boto3):
        """Test that file extension check is case insensitive."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": "UPPERCASE.PNG"},
        }

        result = module.lambda_handler(event, None)
        assert "imageId" in result

    def test_create_image_upload_url_jpeg_extension(self, mock_env, mock_boto3):
        """Test successful image upload URL creation for JPEG extension."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "createImageUploadUrl"},
            "arguments": {"filename": "photo.jpeg"},
        }

        result = module.lambda_handler(event, None)
        assert "imageId" in result
