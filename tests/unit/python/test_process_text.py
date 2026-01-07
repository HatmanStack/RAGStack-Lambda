"""Unit tests for ProcessText Lambda."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws


def _load_process_text_module():
    """Load process_text module using importlib (avoids 'lambda' keyword issue)."""
    module_path = Path(__file__).parent.parent.parent.parent / "src/lambda/process_text/index.py"
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
    context.function_name = "ProcessText"
    context.memory_limit_in_mb = 1024
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:ProcessText"
    return context


@pytest.fixture
def sample_event():
    """Create sample Lambda event."""
    return {
        "document_id": "test-doc-123",
        "input_s3_uri": "s3://test-bucket/input/test-doc-123/document.html",
        "output_s3_prefix": "s3://test-bucket/output/test-doc-123/",
        "fileType": "text",
        "detectedType": "html",
    }


@pytest.fixture
def html_content():
    """Sample HTML content for testing."""
    return b"""<!DOCTYPE html>
<html>
<head><title>Test Document</title></head>
<body>
<h1>Hello World</h1>
<p>This is a test document for text extraction.</p>
</body>
</html>"""


@pytest.fixture
def csv_content():
    """Sample CSV content for testing."""
    return b"""name,age,city
Alice,30,New York
Bob,25,San Francisco
Charlie,35,Chicago"""


class TestProcessTextLambda:
    """Test ProcessText Lambda handler."""

    @mock_aws
    def test_process_text_html_success(self, mock_env, lambda_context, sample_event, html_content):
        """Test successful HTML extraction."""
        # Set up S3
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-doc-123/document.html",
            Body=html_content,
        )

        # Set up DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-tracking-table",
            KeySchema=[{"AttributeName": "document_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "document_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Mock AppSync publish
        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            result = module.lambda_handler(sample_event, lambda_context)

        # Verify result
        assert result["document_id"] == "test-doc-123"
        assert result["status"] == "ocr_complete"
        assert result["total_pages"] == 1
        assert result["is_text_native"] is True
        assert "output_s3_uri" in result
        assert result["output_s3_uri"].endswith("full_text.txt")

        # Verify S3 output
        output = s3.get_object(
            Bucket="test-bucket",
            Key="output/test-doc-123/full_text.txt",
        )
        output_content = output["Body"].read().decode("utf-8")
        assert "Test Document" in output_content or "Hello World" in output_content

        # Verify DynamoDB update
        table = dynamodb.Table("test-tracking-table")
        item = table.get_item(Key={"document_id": "test-doc-123"})["Item"]
        assert item["status"] == "ocr_complete"
        assert item["is_text_native"] is True
        assert item["detected_file_type"] == "html"

    @mock_aws
    def test_process_text_csv_success(self, mock_env, lambda_context, csv_content):
        """Test successful CSV extraction."""
        event = {
            "document_id": "test-csv-123",
            "input_s3_uri": "s3://test-bucket/input/test-csv-123/data.csv",
            "output_s3_prefix": "s3://test-bucket/output/test-csv-123/",
            "fileType": "text",
            "detectedType": "csv",
        }

        # Set up S3
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-csv-123/data.csv",
            Body=csv_content,
        )

        # Set up DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-tracking-table",
            KeySchema=[{"AttributeName": "document_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "document_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            result = module.lambda_handler(event, lambda_context)

        assert result["document_id"] == "test-csv-123"
        assert result["status"] == "ocr_complete"

        # Verify S3 output contains CSV summary
        output = s3.get_object(
            Bucket="test-bucket",
            Key="output/test-csv-123/full_text.txt",
        )
        output_content = output["Body"].read().decode("utf-8")
        # CSV extractor creates markdown with table
        assert "name" in output_content or "Alice" in output_content

    @mock_aws
    def test_process_text_plain_text(self, mock_env, lambda_context):
        """Test plain text extraction."""
        event = {
            "document_id": "test-txt-123",
            "input_s3_uri": "s3://test-bucket/input/test-txt-123/notes.txt",
            "output_s3_prefix": "s3://test-bucket/output/test-txt-123/",
            "fileType": "text",
            "detectedType": "txt",
        }

        content = b"This is a simple plain text document.\nIt has multiple lines.\n"

        # Set up S3
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-txt-123/notes.txt",
            Body=content,
        )

        # Set up DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-tracking-table",
            KeySchema=[{"AttributeName": "document_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "document_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            result = module.lambda_handler(event, lambda_context)

        assert result["document_id"] == "test-txt-123"
        assert result["status"] == "ocr_complete"

    @mock_aws
    def test_process_text_json_file(self, mock_env, lambda_context):
        """Test JSON file extraction."""
        event = {
            "document_id": "test-json-123",
            "input_s3_uri": "s3://test-bucket/input/test-json-123/config.json",
            "output_s3_prefix": "s3://test-bucket/output/test-json-123/",
            "fileType": "text",
            "detectedType": "json",
        }

        content = json.dumps(
            {"name": "Test Config", "settings": {"debug": True, "timeout": 30}}
        ).encode("utf-8")

        # Set up S3
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-json-123/config.json",
            Body=content,
        )

        # Set up DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-tracking-table",
            KeySchema=[{"AttributeName": "document_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "document_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            result = module.lambda_handler(event, lambda_context)

        assert result["document_id"] == "test-json-123"
        assert result["status"] == "ocr_complete"

    @mock_aws
    def test_process_text_s3_not_found(self, mock_env, lambda_context, sample_event):
        """Test error handling when file not found in S3."""
        # Set up S3 without the file
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")

        # Set up DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-tracking-table",
            KeySchema=[{"AttributeName": "document_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "document_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            with pytest.raises(module.s3_client.exceptions.NoSuchKey):
                module.lambda_handler(sample_event, lambda_context)

        # Verify status updated to failed
        table = dynamodb.Table("test-tracking-table")
        item = table.get_item(Key={"document_id": "test-doc-123"})["Item"]
        assert item["status"] == "failed"
        assert "error_message" in item

    def test_process_text_missing_env_var(self, lambda_context, sample_event, monkeypatch):
        """Test error when TRACKING_TABLE not set."""
        monkeypatch.delenv("TRACKING_TABLE", raising=False)

        module = _load_process_text_module()

        with pytest.raises(ValueError, match="TRACKING_TABLE"):
            module.lambda_handler(sample_event, lambda_context)

    @mock_aws
    def test_process_text_publishes_updates(
        self, mock_env, lambda_context, sample_event, html_content
    ):
        """Test that AppSync updates are published."""
        # Set up S3
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-doc-123/document.html",
            Body=html_content,
        )

        # Set up DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-tracking-table",
            KeySchema=[{"AttributeName": "document_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "document_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        with patch("ragstack_common.appsync.publish_document_update") as mock_publish:
            module = _load_process_text_module()
            module.lambda_handler(sample_event, lambda_context)

        # Verify publish was called for PROCESSING and OCR_COMPLETE
        assert mock_publish.call_count >= 2
        statuses = [call.args[3] for call in mock_publish.call_args_list]
        assert "PROCESSING" in statuses
        assert "OCR_COMPLETE" in statuses

    @mock_aws
    def test_process_text_output_format(self, mock_env, lambda_context, sample_event, html_content):
        """Test that output format matches process_document format."""
        # Set up S3
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(
            Bucket="test-bucket",
            Key="input/test-doc-123/document.html",
            Body=html_content,
        )

        # Set up DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-tracking-table",
            KeySchema=[{"AttributeName": "document_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "document_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            result = module.lambda_handler(sample_event, lambda_context)

        # Verify all required fields are present
        assert "document_id" in result
        assert "status" in result
        assert "total_pages" in result
        assert "is_text_native" in result
        assert "output_s3_uri" in result
        assert "pages" in result

        # Verify pages structure
        assert len(result["pages"]) == 1
        page = result["pages"][0]
        assert "page_number" in page
        assert "text" in page
        assert "ocr_backend" in page
        assert page["ocr_backend"] == "text_extraction"


class TestHelperFunctions:
    """Test helper functions in process_text module."""

    def test_parse_s3_uri(self, mock_env):
        """Test S3 URI parsing."""
        module = _load_process_text_module()

        bucket, key = module._parse_s3_uri("s3://my-bucket/path/to/file.txt")
        assert bucket == "my-bucket"
        assert key == "path/to/file.txt"

    def test_parse_s3_uri_invalid(self, mock_env):
        """Test S3 URI parsing with invalid URI."""
        module = _load_process_text_module()

        with pytest.raises(ValueError, match="Invalid S3 URI"):
            module._parse_s3_uri("http://not-s3/path/file.txt")

    def test_extract_filename(self, mock_env):
        """Test filename extraction from S3 URI."""
        module = _load_process_text_module()

        filename = module._extract_filename("s3://bucket/path/to/document.html")
        assert filename == "document.html"

        filename = module._extract_filename("s3://bucket/file.csv")
        assert filename == "file.csv"
