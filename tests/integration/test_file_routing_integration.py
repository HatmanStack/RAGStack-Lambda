"""Integration tests for file type routing with mocked AWS services."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws


def _load_detect_file_type_module():
    """Load detect_file_type module using importlib (avoids 'lambda' keyword issue)."""
    module_path = Path(__file__).parent.parent.parent / "src/lambda/detect_file_type/index.py"
    spec = importlib.util.spec_from_file_location("detect_file_type_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["detect_file_type_index"] = module
    spec.loader.exec_module(module)
    return module


def _load_process_text_module():
    """Load process_text module using importlib (avoids 'lambda' keyword issue)."""
    module_path = Path(__file__).parent.parent.parent / "src/lambda/process_text/index.py"
    spec = importlib.util.spec_from_file_location("process_text_index", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["process_text_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables."""
    monkeypatch.setenv("TRACKING_TABLE", "test-tracking-table")
    monkeypatch.setenv("GRAPHQL_ENDPOINT", "https://test.appsync.amazonaws.com/graphql")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def lambda_context():
    """Create mock Lambda context."""
    context = MagicMock()
    context.function_name = "DetectFileType"
    context.memory_limit_in_mb = 256
    return context


def setup_mocked_aws():
    """Set up mocked S3 and DynamoDB resources."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName="test-tracking-table",
        KeySchema=[{"AttributeName": "document_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "document_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    return s3, dynamodb


@pytest.mark.integration
class TestFileRoutingIntegration:
    """Integration tests for file type routing logic."""

    @mock_aws
    def test_html_routes_to_text_path(self, mock_env, lambda_context):
        """Test HTML file detection and routing to text path."""
        s3, _ = setup_mocked_aws()

        html_content = b"""<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Hello World</h1></body>
</html>"""

        document_id = "route-test-html"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/page.html",
            Body=html_content,
        )

        event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/page.html",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
        }

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "text"
        assert result["detectedType"] == "html"
        assert result["document_id"] == document_id

    @mock_aws
    def test_pdf_routes_to_ocr_path(self, mock_env, lambda_context):
        """Test PDF file detection and routing to OCR path."""
        s3, _ = setup_mocked_aws()

        # PDF magic bytes
        pdf_content = b"%PDF-1.4 fake pdf content for testing"

        document_id = "route-test-pdf"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/document.pdf",
            Body=pdf_content,
        )

        event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/document.pdf",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
        }

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "ocr"
        assert result["detectedType"] == "pdf"

    @mock_aws
    def test_markdown_routes_to_passthrough(self, mock_env, lambda_context):
        """Test markdown file detection and routing to passthrough path."""
        s3, _ = setup_mocked_aws()

        # Markdown files don't need content check - extension is sufficient
        event = {
            "document_id": "route-test-md",
            "input_s3_uri": "s3://test-bucket/input/route-test-md/readme.md",
            "output_s3_prefix": "s3://test-bucket/output/route-test-md/",
        }

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "passthrough"
        assert result["detectedType"] == "markdown"

    @mock_aws
    def test_csv_routes_to_text_path(self, mock_env, lambda_context):
        """Test CSV file detection and routing to text path."""
        s3, _ = setup_mocked_aws()

        csv_content = b"""name,age,city
Alice,30,NYC
Bob,25,LA"""

        document_id = "route-test-csv"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/data.csv",
            Body=csv_content,
        )

        event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/data.csv",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
        }

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "text"
        assert result["detectedType"] == "csv"

    @mock_aws
    def test_json_routes_to_text_path(self, mock_env, lambda_context):
        """Test JSON file detection and routing to text path."""
        s3, _ = setup_mocked_aws()

        json_content = b'{"key": "value", "number": 42}'

        document_id = "route-test-json"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/config.json",
            Body=json_content,
        )

        event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/config.json",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
        }

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "text"
        assert result["detectedType"] == "json"

    @mock_aws
    def test_image_routes_to_ocr_path(self, mock_env, lambda_context):
        """Test image file detection and routing to OCR path."""
        s3, _ = setup_mocked_aws()

        # JPEG magic bytes
        jpeg_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100

        document_id = "route-test-jpg"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/photo.jpg",
            Body=jpeg_content,
        )

        event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/photo.jpg",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
        }

        module = _load_detect_file_type_module()
        result = module.lambda_handler(event, lambda_context)

        assert result["fileType"] == "ocr"
        assert result["detectedType"] == "image"


@pytest.mark.integration
class TestEndToEndTextProcessing:
    """End-to-end tests simulating full Step Functions flow."""

    @mock_aws
    def test_html_detection_then_processing(self, mock_env, lambda_context):
        """Test complete flow: DetectFileType -> ProcessText for HTML."""
        s3, dynamodb = setup_mocked_aws()

        html_content = b"""<!DOCTYPE html>
<html>
<head><title>End-to-End Test</title></head>
<body>
<h1>Welcome</h1>
<p>This tests the full pipeline flow.</p>
</body>
</html>"""

        document_id = "e2e-test-html"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/page.html",
            Body=html_content,
        )

        initial_event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/page.html",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
        }

        # Step 1: DetectFileType
        detect_module = _load_detect_file_type_module()
        routing_result = detect_module.lambda_handler(initial_event, lambda_context)

        assert routing_result["fileType"] == "text"
        assert routing_result["detectedType"] == "html"

        # Step 2: ProcessText (using routing result as input)
        with patch("ragstack_common.appsync.publish_document_update"):
            process_module = _load_process_text_module()
            process_result = process_module.lambda_handler(routing_result, lambda_context)

        # Verify final result
        assert process_result["status"] == "ocr_complete"
        assert process_result["is_text_native"] is True
        assert "output_s3_uri" in process_result

        # Verify S3 output exists
        output = s3.get_object(
            Bucket="test-bucket",
            Key=f"output/{document_id}/full_text.txt",
        )
        output_content = output["Body"].read().decode("utf-8")
        assert "End-to-End Test" in output_content or "Welcome" in output_content

        # Verify DynamoDB tracking
        table = dynamodb.Table("test-tracking-table")
        item = table.get_item(Key={"document_id": document_id})["Item"]
        assert item["status"] == "ocr_complete"

    @mock_aws
    def test_csv_detection_then_processing(self, mock_env, lambda_context):
        """Test complete flow: DetectFileType -> ProcessText for CSV."""
        s3, dynamodb = setup_mocked_aws()

        csv_content = b"""product,price,stock
Widget A,19.99,100
Widget B,29.99,50
Widget C,39.99,25"""

        document_id = "e2e-test-csv"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/inventory.csv",
            Body=csv_content,
        )

        initial_event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/inventory.csv",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
        }

        # Step 1: DetectFileType
        detect_module = _load_detect_file_type_module()
        routing_result = detect_module.lambda_handler(initial_event, lambda_context)

        assert routing_result["fileType"] == "text"
        assert routing_result["detectedType"] == "csv"

        # Step 2: ProcessText
        with patch("ragstack_common.appsync.publish_document_update"):
            process_module = _load_process_text_module()
            process_result = process_module.lambda_handler(routing_result, lambda_context)

        assert process_result["status"] == "ocr_complete"

        # Verify output contains smart extraction
        output = s3.get_object(
            Bucket="test-bucket",
            Key=f"output/{document_id}/full_text.txt",
        )
        output_content = output["Body"].read().decode("utf-8")
        assert "product" in output_content or "Widget" in output_content

    @mock_aws
    def test_multiple_file_types_routing(self, mock_env, lambda_context):
        """Test routing decisions for multiple file types."""
        s3, _ = setup_mocked_aws()

        test_cases = [
            ("test.html", b"<html><body>HTML</body></html>", "text", "html"),
            ("test.txt", b"Plain text content", "text", "txt"),
            ("test.csv", b"a,b,c\n1,2,3\n4,5,6", "text", "csv"),
            ("test.json", b'{"key": "value"}', "text", "json"),
            ("test.xml", b'<?xml version="1.0"?><root/>', "text", "xml"),
            ("test.pdf", b"%PDF-1.4 fake pdf", "ocr", "pdf"),
            ("test.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 20, "ocr", "image"),
            ("test.md", b"# Markdown", "passthrough", "markdown"),
        ]

        detect_module = _load_detect_file_type_module()

        for filename, content, expected_route, expected_type in test_cases:
            document_id = f"route-multi-{filename.replace('.', '-')}"

            # Skip content upload for markdown (extension-based detection)
            if expected_type != "markdown":
                s3.put_object(
                    Bucket="test-bucket",
                    Key=f"input/{document_id}/{filename}",
                    Body=content,
                )

            event = {
                "document_id": document_id,
                "input_s3_uri": f"s3://test-bucket/input/{document_id}/{filename}",
                "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
            }

            result = detect_module.lambda_handler(event, lambda_context)

            assert result["fileType"] == expected_route, f"Failed for {filename}"
            assert result["detectedType"] == expected_type, f"Failed for {filename}"
