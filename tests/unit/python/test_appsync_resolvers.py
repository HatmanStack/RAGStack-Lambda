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


# =============================================================================
# Generate Caption Resolver Tests
# =============================================================================


class TestGenerateCaption:
    """Tests for generateCaption resolver."""

    def test_generate_caption_success(self, mock_env, mock_boto3):
        """Test successful caption generation."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        # Mock S3 get_object
        mock_body = MagicMock()
        mock_body.read.return_value = b"\x89PNG\r\n\x1a\n" + b"fake image data"
        mock_boto3["s3"].get_object.return_value = {
            "Body": mock_body,
            "ContentType": "image/png",
        }

        # Mock bedrock_runtime.converse
        mock_bedrock = MagicMock()
        mock_bedrock.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "A beautiful sunset over the ocean with clouds."}]
                }
            }
        }
        module.bedrock_runtime = mock_bedrock

        event = {
            "info": {"fieldName": "generateCaption"},
            "arguments": {"imageS3Uri": "s3://test-data-bucket/images/123/image.png"},
        }

        result = module.lambda_handler(event, None)

        assert result["caption"] == "A beautiful sunset over the ocean with clouds."
        assert result["error"] is None

        # Verify S3 was called correctly
        mock_boto3["s3"].get_object.assert_called_once_with(
            Bucket="test-data-bucket", Key="images/123/image.png"
        )

        # Verify Bedrock Converse was called
        mock_bedrock.converse.assert_called_once()

    def test_generate_caption_invalid_s3_uri_format(self, mock_env, mock_boto3):
        """Test rejection of invalid S3 URI format."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "generateCaption"},
            "arguments": {"imageS3Uri": "https://example.com/image.png"},
        }

        result = module.lambda_handler(event, None)

        assert result["caption"] is None
        assert "Invalid S3 URI" in result["error"]

    def test_generate_caption_empty_s3_uri(self, mock_env, mock_boto3):
        """Test rejection of empty S3 URI."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "generateCaption"},
            "arguments": {"imageS3Uri": ""},
        }

        result = module.lambda_handler(event, None)

        assert result["caption"] is None
        assert "Invalid S3 URI" in result["error"]

    def test_generate_caption_wrong_bucket(self, mock_env, mock_boto3):
        """Test rejection of image from unauthorized bucket."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "generateCaption"},
            "arguments": {"imageS3Uri": "s3://other-bucket/images/123/image.png"},
        }

        result = module.lambda_handler(event, None)

        assert result["caption"] is None
        assert "configured data bucket" in result["error"]

    def test_generate_caption_s3_not_found(self, mock_env, mock_boto3):
        """Test handling of S3 NoSuchKey error."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        # Mock S3 to raise NoSuchKey
        from botocore.exceptions import ClientError

        mock_boto3["s3"].get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
        )

        event = {
            "info": {"fieldName": "generateCaption"},
            "arguments": {"imageS3Uri": "s3://test-data-bucket/images/123/image.png"},
        }

        result = module.lambda_handler(event, None)

        assert result["caption"] is None
        assert "not found" in result["error"]

    def test_generate_caption_bedrock_error(self, mock_env, mock_boto3):
        """Test handling of Bedrock API error."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        # Mock S3 get_object
        mock_body = MagicMock()
        mock_body.read.return_value = b"\x89PNG\r\n\x1a\n" + b"fake image data"
        mock_boto3["s3"].get_object.return_value = {
            "Body": mock_body,
            "ContentType": "image/png",
        }

        # Mock bedrock_runtime to raise error
        from botocore.exceptions import ClientError

        mock_bedrock = MagicMock()
        mock_bedrock.converse.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Model error"}},
            "Converse",
        )
        module.bedrock_runtime = mock_bedrock

        event = {
            "info": {"fieldName": "generateCaption"},
            "arguments": {"imageS3Uri": "s3://test-data-bucket/images/123/image.png"},
        }

        result = module.lambda_handler(event, None)

        assert result["caption"] is None
        assert "Model error" in result["error"]


# =============================================================================
# Submit Image Resolver Tests
# =============================================================================


class TestSubmitImage:
    """Tests for submitImage resolver."""

    def test_submit_image_success(self, mock_env, mock_boto3):
        """Test successful image submission with both captions."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        # Setup DynamoDB mocks
        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "document_id": "12345678-1234-1234-1234-123456789012",
                "filename": "test.png",
                "input_s3_uri": "s3://test-data-bucket/images/12345678-1234-1234-1234-123456789012/test.png",
                "status": "PENDING",
                "type": "image",
                "created_at": "2025-01-01T00:00:00Z",
            }
        }

        # Setup S3 mocks
        mock_boto3["s3"].head_object.return_value = {
            "ContentType": "image/png",
            "ContentLength": 12345,
        }

        event = {
            "info": {"fieldName": "submitImage"},
            "arguments": {
                "input": {
                    "imageId": "12345678-1234-1234-1234-123456789012",
                    "userCaption": "My vacation photo",
                    "aiCaption": "A sunset over the ocean",
                }
            },
        }

        result = module.lambda_handler(event, None)

        # Verify result structure
        assert result["imageId"] == "12345678-1234-1234-1234-123456789012"
        assert result["status"] == "PENDING"  # From mock return

        # Verify S3 metadata was written
        mock_boto3["s3"].put_object.assert_called_once()
        put_call = mock_boto3["s3"].put_object.call_args
        assert put_call.kwargs["Key"].endswith("metadata.json")

        # Verify DynamoDB was updated
        mock_boto3["table"].update_item.assert_called_once()

    def test_submit_image_user_caption_only(self, mock_env, mock_boto3):
        """Test submission with only user caption."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "document_id": "12345678-1234-1234-1234-123456789012",
                "filename": "test.png",
                "input_s3_uri": "s3://test-data-bucket/images/12345678-1234-1234-1234-123456789012/test.png",
                "status": "PENDING",
                "type": "image",
            }
        }

        mock_boto3["s3"].head_object.return_value = {
            "ContentType": "image/png",
            "ContentLength": 12345,
        }

        event = {
            "info": {"fieldName": "submitImage"},
            "arguments": {
                "input": {
                    "imageId": "12345678-1234-1234-1234-123456789012",
                    "userCaption": "Just a user caption",
                }
            },
        }

        result = module.lambda_handler(event, None)
        assert "imageId" in result

    def test_submit_image_not_found(self, mock_env, mock_boto3):
        """Test rejection when image not found."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].get_item.return_value = {}  # No Item

        event = {
            "info": {"fieldName": "submitImage"},
            "arguments": {
                "input": {
                    "imageId": "12345678-1234-1234-1234-123456789012",
                }
            },
        }

        with pytest.raises(ValueError, match="not found"):
            module.lambda_handler(event, None)

    def test_submit_image_not_image_type(self, mock_env, mock_boto3):
        """Test rejection when record is not an image type."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "document_id": "12345678-1234-1234-1234-123456789012",
                "filename": "document.pdf",
                "input_s3_uri": "s3://test-data-bucket/input/123/document.pdf",
                "status": "UPLOADED",
                "type": "document",  # Not an image
            }
        }

        event = {
            "info": {"fieldName": "submitImage"},
            "arguments": {
                "input": {
                    "imageId": "12345678-1234-1234-1234-123456789012",
                }
            },
        }

        with pytest.raises(ValueError, match="not an image"):
            module.lambda_handler(event, None)

    def test_submit_image_wrong_status(self, mock_env, mock_boto3):
        """Test rejection when image not in PENDING status."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "document_id": "12345678-1234-1234-1234-123456789012",
                "filename": "test.png",
                "input_s3_uri": "s3://test-data-bucket/images/123/test.png",
                "status": "PROCESSING",  # Already processing
                "type": "image",
            }
        }

        event = {
            "info": {"fieldName": "submitImage"},
            "arguments": {
                "input": {
                    "imageId": "12345678-1234-1234-1234-123456789012",
                }
            },
        }

        with pytest.raises(ValueError, match="PENDING"):
            module.lambda_handler(event, None)

    def test_submit_image_s3_file_not_found(self, mock_env, mock_boto3):
        """Test rejection when image file not in S3."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "document_id": "12345678-1234-1234-1234-123456789012",
                "filename": "test.png",
                "input_s3_uri": "s3://test-data-bucket/images/123/test.png",
                "status": "PENDING",
                "type": "image",
            }
        }

        # Mock S3 to raise NoSuchKey
        from botocore.exceptions import ClientError

        mock_boto3["s3"].head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "HeadObject"
        )

        event = {
            "info": {"fieldName": "submitImage"},
            "arguments": {
                "input": {
                    "imageId": "12345678-1234-1234-1234-123456789012",
                    "userCaption": "Test caption",
                }
            },
        }

        with pytest.raises(ValueError, match="not found in S3"):
            module.lambda_handler(event, None)

    def test_submit_image_missing_image_id(self, mock_env, mock_boto3):
        """Test rejection when imageId is missing."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "submitImage"},
            "arguments": {"input": {}},
        }

        with pytest.raises(ValueError, match="required"):
            module.lambda_handler(event, None)

    def test_submit_image_invalid_uuid(self, mock_env, mock_boto3):
        """Test rejection when imageId is not a valid UUID."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "submitImage"},
            "arguments": {
                "input": {
                    "imageId": "not-a-uuid",
                }
            },
        }

        with pytest.raises(ValueError, match="Invalid"):
            module.lambda_handler(event, None)


# =============================================================================
# Get Image Resolver Tests
# =============================================================================


class TestGetImage:
    """Tests for getImage resolver."""

    def test_get_image_success(self, mock_env, mock_boto3):
        """Test successful image retrieval."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "document_id": "12345678-1234-1234-1234-123456789012",
                "filename": "test.png",
                "caption": "Test caption",
                "input_s3_uri": "s3://test-bucket/images/123/test.png",
                "status": "INDEXED",
                "type": "image",
            }
        }

        event = {
            "info": {"fieldName": "getImage"},
            "arguments": {"imageId": "12345678-1234-1234-1234-123456789012"},
        }

        result = module.lambda_handler(event, None)

        assert result["imageId"] == "12345678-1234-1234-1234-123456789012"
        assert result["filename"] == "test.png"
        assert result["caption"] == "Test caption"

    def test_get_image_not_found(self, mock_env, mock_boto3):
        """Test image not found returns None."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].get_item.return_value = {}

        event = {
            "info": {"fieldName": "getImage"},
            "arguments": {"imageId": "12345678-1234-1234-1234-123456789012"},
        }

        result = module.lambda_handler(event, None)
        assert result is None

    def test_get_image_not_image_type(self, mock_env, mock_boto3):
        """Test returns None for non-image type."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "document_id": "12345678-1234-1234-1234-123456789012",
                "type": "document",  # Not image
            }
        }

        event = {
            "info": {"fieldName": "getImage"},
            "arguments": {"imageId": "12345678-1234-1234-1234-123456789012"},
        }

        result = module.lambda_handler(event, None)
        assert result is None

    def test_get_image_invalid_uuid(self, mock_env, mock_boto3):
        """Test rejection of invalid UUID."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "getImage"},
            "arguments": {"imageId": "not-a-uuid"},
        }

        with pytest.raises(ValueError, match="Invalid"):
            module.lambda_handler(event, None)


# =============================================================================
# List Images Resolver Tests
# =============================================================================


class TestListImages:
    """Tests for listImages resolver."""

    def test_list_images_success(self, mock_env, mock_boto3):
        """Test successful image listing."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].scan.return_value = {
            "Items": [
                {
                    "document_id": "image-1",
                    "filename": "test1.png",
                    "type": "image",
                    "status": "INDEXED",
                    "input_s3_uri": "s3://test/1.png",
                },
                {
                    "document_id": "image-2",
                    "filename": "test2.jpg",
                    "type": "image",
                    "status": "PENDING",
                    "input_s3_uri": "s3://test/2.jpg",
                },
            ]
        }

        event = {
            "info": {"fieldName": "listImages"},
            "arguments": {"limit": 10},
        }

        result = module.lambda_handler(event, None)

        assert len(result["items"]) == 2
        assert result["items"][0]["imageId"] == "image-1"
        assert result["items"][1]["imageId"] == "image-2"

    def test_list_images_with_pagination(self, mock_env, mock_boto3):
        """Test listing with pagination token."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].scan.return_value = {
            "Items": [
                {
                    "document_id": "image-3",
                    "filename": "test3.png",
                    "type": "image",
                    "status": "INDEXED",
                    "input_s3_uri": "s3://test/3.png",
                }
            ],
            "LastEvaluatedKey": {"document_id": "image-3"},
        }

        event = {
            "info": {"fieldName": "listImages"},
            "arguments": {"limit": 10, "nextToken": '{"document_id": "image-2"}'},
        }

        result = module.lambda_handler(event, None)

        assert len(result["items"]) == 1
        assert "nextToken" in result

    def test_list_images_invalid_limit(self, mock_env, mock_boto3):
        """Test rejection of invalid limit."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "listImages"},
            "arguments": {"limit": 200},  # Over max
        }

        with pytest.raises(ValueError, match="must be between"):
            module.lambda_handler(event, None)


# =============================================================================
# Delete Image Resolver Tests
# =============================================================================


class TestDeleteImage:
    """Tests for deleteImage resolver."""

    def test_delete_image_success(self, mock_env, mock_boto3):
        """Test successful image deletion."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "document_id": "12345678-1234-1234-1234-123456789012",
                "filename": "test.png",
                "input_s3_uri": "s3://test-bucket/images/123/test.png",
                "type": "image",
            }
        }

        event = {
            "info": {"fieldName": "deleteImage"},
            "arguments": {"imageId": "12345678-1234-1234-1234-123456789012"},
        }

        result = module.lambda_handler(event, None)

        assert result is True

        # Verify S3 objects were deleted
        assert mock_boto3["s3"].delete_object.called

        # Verify DynamoDB delete was called
        mock_boto3["table"].delete_item.assert_called_once()

    def test_delete_image_not_found(self, mock_env, mock_boto3):
        """Test error when image not found."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].get_item.return_value = {}

        event = {
            "info": {"fieldName": "deleteImage"},
            "arguments": {"imageId": "12345678-1234-1234-1234-123456789012"},
        }

        with pytest.raises(ValueError, match="not found"):
            module.lambda_handler(event, None)

    def test_delete_image_not_image_type(self, mock_env, mock_boto3):
        """Test error when record is not an image."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "document_id": "12345678-1234-1234-1234-123456789012",
                "type": "document",
            }
        }

        event = {
            "info": {"fieldName": "deleteImage"},
            "arguments": {"imageId": "12345678-1234-1234-1234-123456789012"},
        }

        with pytest.raises(ValueError, match="not an image"):
            module.lambda_handler(event, None)

    def test_delete_image_missing_id(self, mock_env, mock_boto3):
        """Test error when imageId is missing."""
        module = _load_appsync_resolvers_module()
        module.s3 = mock_boto3["s3"]
        module.dynamodb = mock_boto3["dynamodb"]

        event = {
            "info": {"fieldName": "deleteImage"},
            "arguments": {},
        }

        with pytest.raises(ValueError, match="required"):
            module.lambda_handler(event, None)
