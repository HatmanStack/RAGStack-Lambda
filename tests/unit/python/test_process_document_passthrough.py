"""Unit tests for ProcessDocument markdown passthrough."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_process_document_module():
    """Load process_document module using importlib (avoids 'lambda' keyword issue)."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src/lambda/process_document/index.py"
    )
    spec = importlib.util.spec_from_file_location("process_document_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["process_document_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables for tests."""
    monkeypatch.setenv("TRACKING_TABLE", "test-tracking-table")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


class TestMarkdownPassthrough:
    """Tests for scraped markdown passthrough logic."""

    def test_parse_s3_uri(self, mock_env):
        """Test S3 URI parsing."""
        module = _load_process_document_module()

        bucket, key = module._parse_s3_uri("s3://my-bucket/path/to/file.txt")
        assert bucket == "my-bucket"
        assert key == "path/to/file.txt"

    def test_parse_s3_uri_invalid(self, mock_env):
        """Test S3 URI parsing with invalid URI."""
        module = _load_process_document_module()

        with pytest.raises(ValueError, match="Invalid S3 URI"):
            module._parse_s3_uri("http://not-s3/path/file.txt")

    def test_scraped_md_passthrough(self, mock_env):
        """Test that .scraped.md files skip OCR."""
        with patch("boto3.client") as mock_boto3_client:
            # Mock S3
            mock_s3 = MagicMock()
            mock_s3.get_object.return_value = {
                "Body": MagicMock(read=lambda: b"# Test Content\n\nThis is markdown.")
            }
            mock_boto3_client.return_value = mock_s3

            # Mock update_item at module level
            with patch(
                "ragstack_common.storage.update_item"
            ) as mock_update:
                module = _load_process_document_module()

                event = {
                    "document_id": "test-doc-123",
                    "input_s3_uri": "s3://input-bucket/doc/test.scraped.md",
                    "output_s3_prefix": "s3://output-bucket/processed/test-doc-123/",
                }

                result = module.lambda_handler(event, None)

                # Verify result
                assert result["document_id"] == "test-doc-123"
                assert result["status"] == "ocr_complete"
                assert result["total_pages"] == 1
                assert result["is_text_native"] is True
                assert "passthrough" in result["pages"][0]["ocr_backend"]

                # Verify S3 operations
                mock_s3.get_object.assert_called_once()
                mock_s3.put_object.assert_called_once()

                # Verify DynamoDB update
                mock_update.assert_called_once()


class TestS3UriParsing:
    """Tests for S3 URI parsing edge cases."""

    def test_parse_uri_with_nested_path(self, mock_env):
        """Test parsing URI with deeply nested path."""
        module = _load_process_document_module()

        bucket, key = module._parse_s3_uri("s3://bucket/a/b/c/d/file.txt")
        assert bucket == "bucket"
        assert key == "a/b/c/d/file.txt"

    def test_parse_uri_with_special_chars(self, mock_env):
        """Test parsing URI with special characters."""
        module = _load_process_document_module()

        bucket, key = module._parse_s3_uri("s3://my-bucket/path/file-name_v2.txt")
        assert bucket == "my-bucket"
        assert key == "path/file-name_v2.txt"
