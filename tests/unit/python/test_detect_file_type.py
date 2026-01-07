"""Unit tests for DetectFileType Lambda."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws


def _load_detect_file_type_module():
    """Load detect_file_type module using importlib (avoids 'lambda' keyword issue)."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src/lambda/detect_file_type/index.py"
    )
    spec = importlib.util.spec_from_file_location("detect_file_type_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["detect_file_type_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def lambda_context():
    """Create mock Lambda context."""
    context = MagicMock()
    context.function_name = "DetectFileType"
    context.memory_limit_in_mb = 256
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:DetectFileType"
    return context


@pytest.fixture
def base_event():
    """Create base Lambda event."""
    return {
        "document_id": "test-doc-123",
        "input_s3_uri": "s3://test-bucket/input/test-doc-123/document.html",
        "output_s3_prefix": "s3://test-bucket/output/test-doc-123/",
    }


class TestDetectFileTypeLambda:
    """Test DetectFileType Lambda handler."""

    @mock_aws
    def test_detect_html_file(self, lambda_context, base_event):
        """Test HTML file detection routes to text path."""
        html_content = b"""<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Hello</h1></body>
</html>"""

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-doc-123/document.html",
            Body=html_content,
        )

        module = _load_detect_file_type_module()
        result = module.lambda_handler(base_event, lambda_context)

        assert result["document_id"] == "test-doc-123"
        assert result["input_s3_uri"] == base_event["input_s3_uri"]
        assert result["output_s3_prefix"] == base_event["output_s3_prefix"]
        assert result["fileType"] == "text"
        assert result["detectedType"] == "html"

    @mock_aws
    def test_detect_csv_file(self, lambda_context):
        """Test CSV file detection routes to text path."""
        event = {
            "document_id": "test-csv-123",
            "input_s3_uri": "s3://test-bucket/input/test-csv-123/data.csv",
            "output_s3_prefix": "s3://test-bucket/output/test-csv-123/",
        }

        csv_content = b"""name,age,city
Alice,30,New York
Bob,25,San Francisco
Charlie,35,Chicago"""

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-csv-123/data.csv",
            Body=csv_content,
        )

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "text"
        assert result["detectedType"] == "csv"

    @mock_aws
    def test_detect_json_file(self, lambda_context):
        """Test JSON file detection routes to text path."""
        event = {
            "document_id": "test-json-123",
            "input_s3_uri": "s3://test-bucket/input/test-json-123/config.json",
            "output_s3_prefix": "s3://test-bucket/output/test-json-123/",
        }

        json_content = b'{"name": "test", "value": 123}'

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-json-123/config.json",
            Body=json_content,
        )

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "text"
        assert result["detectedType"] == "json"

    @mock_aws
    def test_detect_xml_file(self, lambda_context):
        """Test XML file detection routes to text path."""
        event = {
            "document_id": "test-xml-123",
            "input_s3_uri": "s3://test-bucket/input/test-xml-123/data.xml",
            "output_s3_prefix": "s3://test-bucket/output/test-xml-123/",
        }

        xml_content = b'<?xml version="1.0"?><root><item>Test</item></root>'

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-xml-123/data.xml",
            Body=xml_content,
        )

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "text"
        assert result["detectedType"] == "xml"

    @mock_aws
    def test_detect_plain_text_file(self, lambda_context):
        """Test plain text file detection routes to text path."""
        event = {
            "document_id": "test-txt-123",
            "input_s3_uri": "s3://test-bucket/input/test-txt-123/notes.txt",
            "output_s3_prefix": "s3://test-bucket/output/test-txt-123/",
        }

        text_content = b"This is a plain text document.\nIt has multiple lines."

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-txt-123/notes.txt",
            Body=text_content,
        )

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "text"
        assert result["detectedType"] == "txt"

    @mock_aws
    def test_detect_markdown_passthrough(self, lambda_context):
        """Test markdown file detection routes to passthrough path."""
        event = {
            "document_id": "test-md-123",
            "input_s3_uri": "s3://test-bucket/input/test-md-123/readme.md",
            "output_s3_prefix": "s3://test-bucket/output/test-md-123/",
        }

        # Note: Markdown detection doesn't need S3 content - just checks extension
        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "passthrough"
        assert result["detectedType"] == "markdown"

    @mock_aws
    def test_detect_scraped_markdown_passthrough(self, lambda_context):
        """Test scraped markdown file detection routes to passthrough path."""
        event = {
            "document_id": "test-scraped-123",
            "input_s3_uri": "s3://test-bucket/input/test-scraped-123/page.scraped.md",
            "output_s3_prefix": "s3://test-bucket/output/test-scraped-123/",
        }

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "passthrough"
        assert result["detectedType"] == "markdown"

    @mock_aws
    def test_detect_pdf_file(self, lambda_context):
        """Test PDF file detection routes to OCR path."""
        event = {
            "document_id": "test-pdf-123",
            "input_s3_uri": "s3://test-bucket/input/test-pdf-123/document.pdf",
            "output_s3_prefix": "s3://test-bucket/output/test-pdf-123/",
        }

        # PDF magic bytes
        pdf_content = b"%PDF-1.4 fake pdf content"

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-pdf-123/document.pdf",
            Body=pdf_content,
        )

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "ocr"
        assert result["detectedType"] == "pdf"

    @mock_aws
    def test_detect_jpeg_image(self, lambda_context):
        """Test JPEG image detection routes to OCR path."""
        event = {
            "document_id": "test-jpg-123",
            "input_s3_uri": "s3://test-bucket/input/test-jpg-123/photo.jpg",
            "output_s3_prefix": "s3://test-bucket/output/test-jpg-123/",
        }

        # JPEG magic bytes (FFD8FF)
        jpeg_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-jpg-123/photo.jpg",
            Body=jpeg_content,
        )

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "ocr"
        assert result["detectedType"] == "image"

    @mock_aws
    def test_detect_png_image(self, lambda_context):
        """Test PNG image detection routes to OCR path."""
        event = {
            "document_id": "test-png-123",
            "input_s3_uri": "s3://test-bucket/input/test-png-123/image.png",
            "output_s3_prefix": "s3://test-bucket/output/test-png-123/",
        }

        # PNG magic bytes
        png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-png-123/image.png",
            Body=png_content,
        )

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "ocr"
        assert result["detectedType"] == "image"

    @mock_aws
    def test_detect_email_file(self, lambda_context):
        """Test email file detection routes to text path."""
        event = {
            "document_id": "test-eml-123",
            "input_s3_uri": "s3://test-bucket/input/test-eml-123/message.eml",
            "output_s3_prefix": "s3://test-bucket/output/test-eml-123/",
        }

        eml_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Test Email
Date: Mon, 1 Jan 2024 12:00:00 +0000

This is the email body."""

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-eml-123/message.eml",
            Body=eml_content,
        )

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "text"
        assert result["detectedType"] == "eml"

    @mock_aws
    def test_wrong_extension_content_sniffing(self, lambda_context):
        """Test that content sniffing corrects wrong extension."""
        event = {
            "document_id": "test-wrong-ext",
            "input_s3_uri": "s3://test-bucket/input/test-wrong-ext/data.txt",
            "output_s3_prefix": "s3://test-bucket/output/test-wrong-ext/",
        }

        # JSON content with .txt extension
        json_content = b'{"name": "test", "values": [1, 2, 3]}'

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-wrong-ext/data.txt",
            Body=json_content,
        )

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        # Should detect as JSON despite .txt extension
        assert result["fileType"] == "text"
        assert result["detectedType"] == "json"

    @mock_aws
    def test_unknown_file_defaults_to_text(self, lambda_context):
        """Test unknown file type defaults to text path (txt fallback)."""
        event = {
            "document_id": "test-unknown-123",
            "input_s3_uri": "s3://test-bucket/input/test-unknown-123/data.bin",
            "output_s3_prefix": "s3://test-bucket/output/test-unknown-123/",
        }

        # Content that looks like text but doesn't match any specific format
        text_content = b"Some random content that doesn't match any format."

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-unknown-123/data.bin",
            Body=text_content,
        )

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        # Unknown text content falls back to txt, which routes to text path
        assert result["fileType"] == "text"
        assert result["detectedType"] == "txt"

    @mock_aws
    def test_file_not_found(self, lambda_context, base_event):
        """Test error handling when file not found."""
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        # Don't put any object

        module = _load_detect_file_type_module()

        with pytest.raises(module.s3_client.exceptions.NoSuchKey):
            module.lambda_handler(base_event, lambda_context)


class TestHelperFunctions:
    """Test helper functions in detect_file_type module."""

    def test_parse_s3_uri(self):
        """Test S3 URI parsing."""
        module = _load_detect_file_type_module()

        bucket, key = module._parse_s3_uri("s3://my-bucket/path/to/file.txt")
        assert bucket == "my-bucket"
        assert key == "path/to/file.txt"

    def test_parse_s3_uri_invalid(self):
        """Test S3 URI parsing with invalid URI."""
        module = _load_detect_file_type_module()

        with pytest.raises(ValueError, match="Invalid S3 URI"):
            module._parse_s3_uri("http://not-s3/path/file.txt")

    def test_extract_filename(self):
        """Test filename extraction from S3 URI."""
        module = _load_detect_file_type_module()

        filename = module._extract_filename("s3://bucket/path/to/document.html")
        assert filename == "document.html"

    def test_get_routing_category_text_types(self):
        """Test routing category for text types."""
        module = _load_detect_file_type_module()

        for file_type in ["html", "txt", "csv", "json", "xml", "eml", "epub", "docx", "xlsx"]:
            assert module._get_routing_category(file_type) == "text"

    def test_get_routing_category_passthrough(self):
        """Test routing category for passthrough types."""
        module = _load_detect_file_type_module()

        assert module._get_routing_category("markdown") == "passthrough"

    def test_get_routing_category_ocr(self):
        """Test routing category for OCR types."""
        module = _load_detect_file_type_module()

        for file_type in ["pdf", "image", "binary", "unknown"]:
            assert module._get_routing_category(file_type) == "ocr"

    def test_is_markdown_file(self):
        """Test markdown file detection."""
        module = _load_detect_file_type_module()

        assert module._is_markdown_file("readme.md") is True
        assert module._is_markdown_file("README.MD") is True
        assert module._is_markdown_file("doc.markdown") is True
        assert module._is_markdown_file("page.scraped.md") is True
        assert module._is_markdown_file("file.txt") is False
        assert module._is_markdown_file("file.html") is False

    def test_is_pdf_or_image(self):
        """Test PDF/image detection by extension and magic bytes."""
        module = _load_detect_file_type_module()

        # By extension
        assert module._is_pdf_or_image("doc.pdf", b"anything") is True
        assert module._is_pdf_or_image("photo.jpg", b"anything") is True
        assert module._is_pdf_or_image("image.PNG", b"anything") is True

        # By magic bytes
        assert module._is_pdf_or_image("unknown", b"%PDF-1.4") is True
        assert module._is_pdf_or_image("unknown", b"\xff\xd8\xff\xe0") is True
        assert module._is_pdf_or_image("unknown", b"\x89PNG\r\n") is True

        # Not PDF/image
        assert module._is_pdf_or_image("file.txt", b"plain text") is False
        assert module._is_pdf_or_image("file.html", b"<html>") is False
