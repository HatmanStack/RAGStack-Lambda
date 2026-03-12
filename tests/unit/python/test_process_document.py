"""Unit tests for ProcessDocument Lambda."""

import importlib.util
import os
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
def _mock_env(monkeypatch):
    """Set up environment variables for tests (underscore prefix for side-effect fixture)."""
    monkeypatch.setenv("TRACKING_TABLE", "test-tracking-table")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


class TestMarkdownPassthrough:
    """Tests for scraped markdown passthrough logic."""

    def test_parse_s3_uri(self, _mock_env):
        """Test S3 URI parsing via module import."""
        module = _load_process_document_module()

        bucket, key = module.parse_s3_uri("s3://my-bucket/path/to/file.txt")
        assert bucket == "my-bucket"
        assert key == "path/to/file.txt"

    def test_parse_s3_uri_invalid(self, _mock_env):
        """Test S3 URI parsing with invalid URI."""
        module = _load_process_document_module()

        with pytest.raises(ValueError, match="Invalid S3 URI"):
            module.parse_s3_uri("http://not-s3/path/file.txt")

    def test_scraped_md_passthrough(self, _mock_env):
        """Test that .scraped.md files skip OCR."""
        with (
            patch("boto3.client") as mock_boto3_client,
            patch("boto3.resource") as mock_boto3_resource,
        ):
            # Mock S3 client
            mock_s3 = MagicMock()
            mock_s3.get_object.return_value = {
                "Body": MagicMock(read=lambda: b"# Test Content\n\nThis is markdown."),
                "Metadata": {"title": "Test Page", "source_url": "https://example.com/page"},
            }
            mock_boto3_client.return_value = mock_s3

            # Mock DynamoDB resource
            mock_dynamodb = MagicMock()
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3_resource.return_value = mock_dynamodb

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

            # Verify DynamoDB update with created_at, filename, input_s3_uri, type
            mock_table.update_item.assert_called_once()
            call_kwargs = mock_table.update_item.call_args[1]
            assert "created_at" in call_kwargs["UpdateExpression"]
            assert "filename" in call_kwargs["UpdateExpression"]
            assert "#type" in call_kwargs["UpdateExpression"]
            assert ":filename" in call_kwargs["ExpressionAttributeValues"]
            assert call_kwargs["ExpressionAttributeValues"][":filename"] == "Test Page"
            assert call_kwargs["ExpressionAttributeValues"][":type"] == "scraped"


class TestS3UriParsing:
    """Tests for S3 URI parsing edge cases."""

    def test_parse_uri_with_nested_path(self, _mock_env):
        """Test parsing URI with deeply nested path."""
        module = _load_process_document_module()

        bucket, key = module.parse_s3_uri("s3://bucket/a/b/c/d/file.txt")
        assert bucket == "bucket"
        assert key == "a/b/c/d/file.txt"

    def test_parse_uri_with_special_chars(self, _mock_env):
        """Test parsing URI with special characters."""
        module = _load_process_document_module()

        bucket, key = module.parse_s3_uri("s3://my-bucket/path/file-name_v2.txt")
        assert bucket == "my-bucket"
        assert key == "path/file-name_v2.txt"


class TestLambdaHandler:
    """Tests for lambda_handler orchestration."""

    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.ocr.OcrService")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("ragstack_common.storage.update_item")
    @patch("boto3.resource")
    @patch("boto3.client")
    def test_pdf_happy_path(
        self,
        mock_boto3_client,
        mock_boto3_resource,
        mock_update_item,
        mock_config_class,
        mock_ocr_class,
        mock_publish,
        _mock_env,
    ):
        """Test processing a normal PDF document."""
        mock_boto3_client.return_value = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_config = MagicMock()
        mock_config.get_parameter.side_effect = lambda key, default=None: {
            "ocr_backend": "textract",
            "bedrock_ocr_model_id": "model-id",
        }.get(key, default)
        mock_config_class.return_value = mock_config

        mock_page = MagicMock()
        mock_page.page_number = 1
        mock_page.text = "Page 1 text"
        mock_page.ocr_backend = "textract"

        mock_doc = MagicMock()
        mock_doc.status.value = "ocr_complete"
        mock_doc.total_pages = 3
        mock_doc.is_text_native = True
        mock_doc.output_s3_uri = "s3://bucket/content/doc-123/full_text.txt"
        mock_doc.pages = [mock_page]

        mock_ocr = MagicMock()
        mock_ocr.process_document.return_value = mock_doc
        mock_ocr_class.return_value = mock_ocr

        module = _load_process_document_module()
        with (
            patch.object(module, "s3_client", MagicMock()),
            patch.object(module, "dynamodb", mock_dynamodb),
            patch.object(module, "_config_manager", mock_config),
        ):
            # Use Status.FAILED to test the if condition
            from ragstack_common.models import Status

            mock_doc.status = Status.OCR_COMPLETE

            result = module.lambda_handler(
                {
                    "document_id": "doc-123",
                    "input_s3_uri": "s3://bucket/input/doc-123/report.pdf",
                    "output_s3_prefix": "s3://bucket/content/doc-123/",
                },
                None,
            )

        assert result["document_id"] == "doc-123"
        assert result["status"] == "ocr_complete"
        assert result["total_pages"] == 3

    def test_missing_tracking_table_raises(self, monkeypatch):
        """Test that missing TRACKING_TABLE raises ValueError."""
        monkeypatch.setenv("TRACKING_TABLE", "")
        monkeypatch.setenv("AWS_REGION", "us-east-1")

        module = _load_process_document_module()
        with pytest.raises(ValueError, match="TRACKING_TABLE"):
            module.lambda_handler(
                {
                    "document_id": "doc-1",
                    "input_s3_uri": "s3://bucket/input/doc-1/file.pdf",
                    "output_s3_prefix": "s3://bucket/content/doc-1/",
                },
                None,
            )

    def test_skips_generated_output_files(self, _mock_env):
        """Test that generated output files are skipped."""
        module = _load_process_document_module()

        result = module.lambda_handler(
            {
                "document_id": "doc-1",
                "input_s3_uri": "s3://bucket/input/doc-1/extracted_text.txt",
                "output_s3_prefix": "s3://bucket/content/doc-1/",
            },
            None,
        )

        assert result["status"] == "skipped"

    def test_skips_full_text_file(self, _mock_env):
        """Test that full_text.txt is skipped."""
        module = _load_process_document_module()

        result = module.lambda_handler(
            {
                "document_id": "doc-1",
                "input_s3_uri": "s3://bucket/input/doc-1/full_text.txt",
                "output_s3_prefix": "s3://bucket/content/doc-1/",
            },
            None,
        )

        assert result["status"] == "skipped"

    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.ocr.OcrService")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("ragstack_common.storage.update_item")
    @patch("boto3.resource")
    @patch("boto3.client")
    def test_ocr_failure_updates_status(
        self,
        mock_boto3_client,
        mock_boto3_resource,
        mock_update_item,
        mock_config_class,
        mock_ocr_class,
        mock_publish,
        _mock_env,
    ):
        """Test that OCR failure updates DynamoDB with failed status."""
        mock_boto3_client.return_value = MagicMock()
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_config = MagicMock()
        mock_config.get_parameter.return_value = "textract"
        mock_config_class.return_value = mock_config

        from ragstack_common.models import Status

        mock_doc = MagicMock()
        mock_doc.status = Status.FAILED
        mock_doc.error_message = "OCR processing failed"

        mock_ocr = MagicMock()
        mock_ocr.process_document.return_value = mock_doc
        mock_ocr_class.return_value = mock_ocr

        module = _load_process_document_module()
        with (
            patch.object(module, "s3_client", MagicMock()),
            patch.object(module, "dynamodb", mock_dynamodb),
            patch.object(module, "_config_manager", mock_config),
            pytest.raises(Exception, match="OCR processing failed"),
        ):
            module.lambda_handler(
                {
                    "document_id": "doc-1",
                    "input_s3_uri": "s3://bucket/input/doc-1/file.pdf",
                    "output_s3_prefix": "s3://bucket/content/doc-1/",
                },
                None,
            )

        # Should update tracking with failed status
        mock_update_item.assert_called()

    def test_document_id_extraction_from_path(self, _mock_env):
        """Test that document_id is extracted from input/uuid/filename format."""
        module = _load_process_document_module()

        # This file is skipped but we can verify the document_id parsing
        result = module.lambda_handler(
            {
                "document_id": "input/abc-uuid/extracted_text.txt",
                "input_s3_uri": "s3://bucket/input/abc-uuid/extracted_text.txt",
                "output_s3_prefix": "s3://bucket/content/input/abc-uuid/extracted_text.txt/",
            },
            None,
        )

        assert result["document_id"] == "abc-uuid"
        assert result["status"] == "skipped"

    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.ocr.OcrService")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("ragstack_common.storage.update_item")
    @patch("boto3.resource")
    @patch("boto3.client")
    def test_webp_forces_bedrock_backend(
        self,
        mock_boto3_client,
        mock_boto3_resource,
        mock_update_item,
        mock_config_class,
        mock_ocr_class,
        mock_publish,
        _mock_env,
    ):
        """Test that .webp files force bedrock OCR backend."""
        mock_boto3_client.return_value = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = MagicMock()
        mock_boto3_resource.return_value = mock_dynamodb

        mock_config = MagicMock()
        mock_config.get_parameter.side_effect = lambda key, default=None: {
            "ocr_backend": "textract",
            "bedrock_ocr_model_id": "model-id",
        }.get(key, default)
        mock_config_class.return_value = mock_config

        from ragstack_common.models import Status

        mock_doc = MagicMock()
        mock_doc.status = Status.OCR_COMPLETE
        mock_doc.total_pages = 1
        mock_doc.is_text_native = False
        mock_doc.output_s3_uri = "s3://bucket/content/doc-1/full_text.txt"
        mock_doc.pages = []

        mock_ocr = MagicMock()
        mock_ocr.process_document.return_value = mock_doc
        mock_ocr_class.return_value = mock_ocr

        module = _load_process_document_module()
        with (
            patch.object(module, "s3_client", MagicMock()),
            patch.object(module, "dynamodb", mock_dynamodb),
            patch.object(module, "_config_manager", mock_config),
        ):
            module.lambda_handler(
                {
                    "document_id": "doc-1",
                    "input_s3_uri": "s3://bucket/input/doc-1/image.webp",
                    "output_s3_prefix": "s3://bucket/content/doc-1/",
                },
                None,
            )

        # OcrService should be initialized with bedrock backend
        mock_ocr_class.assert_called_once()
        call_kwargs = mock_ocr_class.call_args[1]
        assert call_kwargs["backend"] == "bedrock"
