"""Tests for process_zip Lambda function."""

import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_process_zip_module():
    """Load process_zip module using importlib (avoids 'lambda' keyword issue)."""
    module_path = Path(__file__).parent.parent.parent.parent / "src/lambda/process_zip/index.py"
    spec = importlib.util.spec_from_file_location("process_zip_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["process_zip_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables."""
    monkeypatch.setenv("TRACKING_TABLE", "test-tracking-table")
    monkeypatch.setenv("DATA_BUCKET", "test-data-bucket")
    monkeypatch.setenv("GRAPHQL_ENDPOINT", "https://test-graphql.example.com")
    monkeypatch.setenv("CAPTION_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")


@pytest.fixture
def mock_boto3():
    """Set up mocked boto3 clients and resources."""
    with (
        patch("boto3.client") as mock_client,
        patch("boto3.resource") as mock_resource,
    ):
        # Mock S3 client
        mock_s3 = MagicMock()
        # Mock head_object to return a valid ContentLength (10MB by default)
        mock_s3.head_object.return_value = {"ContentLength": 10 * 1024 * 1024}

        # Mock Bedrock runtime client
        mock_bedrock = MagicMock()

        # Mock DynamoDB resource and table
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        def client_factory(service_name, *args, **kwargs):
            if service_name == "s3":
                return mock_s3
            if service_name == "bedrock-runtime":
                return mock_bedrock
            return MagicMock()

        def resource_factory(service_name, *args, **kwargs):
            if service_name == "dynamodb":
                return mock_dynamodb
            return MagicMock()

        mock_client.side_effect = client_factory
        mock_resource.side_effect = resource_factory

        yield {
            "s3": mock_s3,
            "bedrock": mock_bedrock,
            "dynamodb": mock_dynamodb,
            "table": mock_table,
        }


@pytest.fixture
def mock_publish():
    """Mock publish_image_update function."""
    with patch("ragstack_common.appsync.publish_image_update") as mock:
        yield mock


def create_test_zip(files: dict[str, bytes | str]) -> bytes:
    """Create a test ZIP file in memory."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(filename, content)
    return buffer.getvalue()


class TestProcessZip:
    """Tests for process_zip Lambda handler."""

    def test_process_zip_with_captions_json(self, mock_env, mock_boto3, mock_publish):
        """Test processing ZIP with captions.json manifest."""
        module = _load_process_zip_module()

        # Create test ZIP with captions
        captions = {
            "image1.png": "A beautiful sunset",
            "image2.jpg": "A mountain landscape",
        }
        zip_content = create_test_zip(
            {
                "image1.png": b"\x89PNG\r\n\x1a\n" + b"fake image data 1",
                "image2.jpg": b"\xff\xd8\xff\xe0" + b"fake image data 2",
                "captions.json": json.dumps(captions),
            }
        )

        # Mock S3 get_object to return ZIP
        mock_boto3["s3"].get_object.return_value = {"Body": io.BytesIO(zip_content)}

        event = {
            "upload_id": "test-upload-123",
            "bucket": "test-bucket",
            "key": "uploads/test-upload-123/archive.zip",
            "generate_captions": False,
        }

        result = module.lambda_handler(event, None)

        assert result["status"] == "COMPLETED"
        assert result["total_images"] == 2
        assert result["processed_images"] == 2
        assert result["failed_images"] == 0
        assert len(result["errors"]) == 0

        # Verify tracking records were created
        assert mock_boto3["table"].put_item.call_count == 2

    def test_process_zip_without_captions_json(self, mock_env, mock_boto3, mock_publish):
        """Test processing ZIP without captions.json."""
        module = _load_process_zip_module()

        # Create test ZIP without captions
        zip_content = create_test_zip(
            {
                "photo.png": b"\x89PNG\r\n\x1a\n" + b"fake image data",
            }
        )

        mock_boto3["s3"].get_object.return_value = {"Body": io.BytesIO(zip_content)}

        event = {
            "upload_id": "test-upload-456",
            "bucket": "test-bucket",
            "key": "uploads/test-upload-456/archive.zip",
            "generate_captions": False,
        }

        result = module.lambda_handler(event, None)

        assert result["status"] == "COMPLETED"
        assert result["total_images"] == 1
        assert result["processed_images"] == 1

        # Verify image was processed without caption
        put_call = mock_boto3["table"].put_item.call_args
        item = put_call[1]["Item"]
        assert item["caption"] == ""

    def test_process_zip_with_ai_caption_generation(self, mock_env, mock_boto3, mock_publish):
        """Test processing ZIP with AI caption generation enabled."""
        module = _load_process_zip_module()

        # Mock Bedrock response
        mock_boto3["bedrock"].invoke_model.return_value = {
            "body": io.BytesIO(
                json.dumps(
                    {"content": [{"type": "text", "text": "AI generated description of image"}]}
                ).encode()
            )
        }

        # Create test ZIP
        zip_content = create_test_zip(
            {
                "photo.png": b"\x89PNG\r\n\x1a\n" + b"fake image data",
            }
        )

        mock_boto3["s3"].get_object.return_value = {"Body": io.BytesIO(zip_content)}

        event = {
            "upload_id": "test-upload-789",
            "bucket": "test-bucket",
            "key": "uploads/test-upload-789/archive.zip",
            "generate_captions": True,
        }

        result = module.lambda_handler(event, None)

        assert result["status"] == "COMPLETED"
        assert result["processed_images"] == 1

        # Verify Bedrock was called
        assert mock_boto3["bedrock"].invoke_model.call_count == 1

        # Verify AI caption was applied
        put_call = mock_boto3["table"].put_item.call_args
        item = put_call[1]["Item"]
        assert "AI generated description" in item["caption"]

    def test_process_zip_combines_user_and_ai_captions(self, mock_env, mock_boto3, mock_publish):
        """Test that user caption comes first, AI appends."""
        module = _load_process_zip_module()

        # Mock Bedrock response
        mock_boto3["bedrock"].invoke_model.return_value = {
            "body": io.BytesIO(
                json.dumps({"content": [{"type": "text", "text": "AI description"}]}).encode()
            )
        }

        # Create test ZIP with user caption
        captions = {"photo.png": "User provided caption"}
        zip_content = create_test_zip(
            {
                "photo.png": b"\x89PNG\r\n\x1a\n" + b"fake image data",
                "captions.json": json.dumps(captions),
            }
        )

        mock_boto3["s3"].get_object.return_value = {"Body": io.BytesIO(zip_content)}

        event = {
            "upload_id": "test-upload-combo",
            "bucket": "test-bucket",
            "key": "uploads/test-upload-combo/archive.zip",
            "generate_captions": True,
        }

        result = module.lambda_handler(event, None)

        assert result["status"] == "COMPLETED"

        # Verify combined caption (user first)
        put_call = mock_boto3["table"].put_item.call_args
        item = put_call[1]["Item"]
        assert item["caption"] == "User provided caption. AI description"
        assert item["user_caption"] == "User provided caption"
        assert item["ai_caption"] == "AI description"

    def test_process_zip_skips_non_image_files(self, mock_env, mock_boto3, mock_publish):
        """Test that non-image files are skipped."""
        module = _load_process_zip_module()

        # Create test ZIP with mixed content
        zip_content = create_test_zip(
            {
                "photo.png": b"\x89PNG\r\n\x1a\n" + b"fake image data",
                "readme.txt": "This is a text file",
                "data.csv": "col1,col2\n1,2",
                "nested/image.jpg": b"\xff\xd8\xff\xe0" + b"nested image",
            }
        )

        mock_boto3["s3"].get_object.return_value = {"Body": io.BytesIO(zip_content)}

        event = {
            "upload_id": "test-upload-mixed",
            "bucket": "test-bucket",
            "key": "uploads/test-upload-mixed/archive.zip",
            "generate_captions": False,
        }

        result = module.lambda_handler(event, None)

        assert result["status"] == "COMPLETED"
        assert result["total_images"] == 2  # Only PNG and JPG
        assert result["processed_images"] == 2

    def test_process_zip_skips_macosx_folder(self, mock_env, mock_boto3, mock_publish):
        """Test that __MACOSX folder is skipped."""
        module = _load_process_zip_module()

        # Create test ZIP with macOS resource fork files
        zip_content = create_test_zip(
            {
                "photo.png": b"\x89PNG\r\n\x1a\n" + b"fake image data",
                "__MACOSX/._photo.png": b"resource fork data",
            }
        )

        mock_boto3["s3"].get_object.return_value = {"Body": io.BytesIO(zip_content)}

        event = {
            "upload_id": "test-upload-macos",
            "bucket": "test-bucket",
            "key": "uploads/test-upload-macos/archive.zip",
            "generate_captions": False,
        }

        result = module.lambda_handler(event, None)

        assert result["status"] == "COMPLETED"
        assert result["total_images"] == 1  # Only real image

    def test_process_zip_empty_archive(self, mock_env, mock_boto3, mock_publish):
        """Test processing empty ZIP file."""
        module = _load_process_zip_module()

        # Create empty test ZIP
        zip_content = create_test_zip({})

        mock_boto3["s3"].get_object.return_value = {"Body": io.BytesIO(zip_content)}

        event = {
            "upload_id": "test-upload-empty",
            "bucket": "test-bucket",
            "key": "uploads/test-upload-empty/archive.zip",
            "generate_captions": False,
        }

        result = module.lambda_handler(event, None)

        assert result["status"] == "COMPLETED"
        assert result["total_images"] == 0
        assert result["processed_images"] == 0

    def test_process_zip_invalid_zip_file(self, mock_env, mock_boto3):
        """Test handling invalid ZIP file."""
        module = _load_process_zip_module()

        # Return invalid ZIP data
        mock_boto3["s3"].get_object.return_value = {"Body": io.BytesIO(b"not a zip file")}

        event = {
            "upload_id": "test-upload-invalid",
            "bucket": "test-bucket",
            "key": "uploads/test-upload-invalid/archive.zip",
            "generate_captions": False,
        }

        result = module.lambda_handler(event, None)

        assert result["status"] == "FAILED"
        assert any("Invalid ZIP file" in e for e in result["errors"])

    def test_process_zip_malformed_captions_json(self, mock_env, mock_boto3, mock_publish):
        """Test handling malformed captions.json."""
        module = _load_process_zip_module()

        # Create test ZIP with invalid JSON
        zip_content = create_test_zip(
            {
                "photo.png": b"\x89PNG\r\n\x1a\n" + b"fake image data",
                "captions.json": "{ invalid json }",
            }
        )

        mock_boto3["s3"].get_object.return_value = {"Body": io.BytesIO(zip_content)}

        event = {
            "upload_id": "test-upload-badjson",
            "bucket": "test-bucket",
            "key": "uploads/test-upload-badjson/archive.zip",
            "generate_captions": False,
        }

        result = module.lambda_handler(event, None)

        # Should still process images, just log warning about JSON
        assert result["status"] in ("COMPLETED", "COMPLETED_WITH_ERRORS")
        assert result["total_images"] == 1

    def test_process_zip_missing_required_params(self, mock_env, mock_boto3):
        """Test error handling for missing parameters."""
        module = _load_process_zip_module()

        event = {"upload_id": "test-123"}  # Missing bucket and key

        with pytest.raises(ValueError, match="bucket.*key.*required"):
            module.lambda_handler(event, None)


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_is_supported_image(self, mock_env, mock_boto3):
        """Test image extension validation."""
        module = _load_process_zip_module()

        assert module.is_supported_image("photo.png") is True
        assert module.is_supported_image("photo.PNG") is True
        assert module.is_supported_image("photo.jpg") is True
        assert module.is_supported_image("photo.jpeg") is True
        assert module.is_supported_image("photo.gif") is True
        assert module.is_supported_image("photo.webp") is True
        assert module.is_supported_image("photo.txt") is False
        assert module.is_supported_image("photo.pdf") is False
        assert module.is_supported_image("photo") is False

    def test_combine_captions(self, mock_env, mock_boto3):
        """Test caption combination logic."""
        module = _load_process_zip_module()

        # User only
        assert module.combine_captions("User caption", None) == "User caption"

        # AI only
        assert module.combine_captions(None, "AI caption") == "AI caption"

        # Both (user first)
        assert module.combine_captions("User caption", "AI caption") == "User caption. AI caption"

        # Neither
        assert module.combine_captions(None, None) == ""

        # With whitespace
        assert module.combine_captions("  User  ", "  AI  ") == "User. AI"
