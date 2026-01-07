"""Integration tests for ProcessText Lambda with mocked AWS services."""

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
    context.function_name = "ProcessText"
    context.memory_limit_in_mb = 1024
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


class TestProcessTextIntegration:
    """Full integration tests for ProcessText Lambda."""

    @mock_aws
    def test_html_document_full_flow(self, mock_env, lambda_context):
        """Test complete flow for HTML document processing."""
        s3, dynamodb = setup_mocked_aws()

        html_content = b"""<!DOCTYPE html>
<html>
<head><title>Integration Test Document</title></head>
<body>
<h1>Welcome</h1>
<p>This is a test document for integration testing.</p>
<ul>
    <li>Item 1</li>
    <li>Item 2</li>
    <li>Item 3</li>
</ul>
</body>
</html>"""

        # Upload document
        document_id = "int-test-html-001"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/document.html",
            Body=html_content,
        )

        event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/document.html",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
            "fileType": "text",
            "detectedType": "html",
        }

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            result = module.lambda_handler(event, lambda_context)

        # Verify Lambda result
        assert result["document_id"] == document_id
        assert result["status"] == "ocr_complete"
        assert result["is_text_native"] is True

        # Verify S3 output
        output = s3.get_object(
            Bucket="test-bucket",
            Key=f"output/{document_id}/full_text.txt",
        )
        output_content = output["Body"].read().decode("utf-8")
        assert "Integration Test Document" in output_content or "Welcome" in output_content

        # Verify DynamoDB tracking
        table = dynamodb.Table("test-tracking-table")
        item = table.get_item(Key={"document_id": document_id})["Item"]
        assert item["status"] == "ocr_complete"
        assert item["detected_file_type"] == "html"

    @mock_aws
    def test_csv_document_full_flow(self, mock_env, lambda_context):
        """Test complete flow for CSV document processing with smart extraction."""
        s3, dynamodb = setup_mocked_aws()

        csv_content = b"""product_id,name,price,quantity
P001,Widget A,19.99,100
P002,Widget B,29.99,50
P003,Widget C,39.99,25
P004,Widget D,49.99,10"""

        document_id = "int-test-csv-001"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/inventory.csv",
            Body=csv_content,
        )

        event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/inventory.csv",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
            "fileType": "text",
            "detectedType": "csv",
        }

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            result = module.lambda_handler(event, lambda_context)

        # Verify Lambda result
        assert result["document_id"] == document_id
        assert result["status"] == "ocr_complete"

        # Verify S3 output contains smart extraction
        output = s3.get_object(
            Bucket="test-bucket",
            Key=f"output/{document_id}/full_text.txt",
        )
        output_content = output["Body"].read().decode("utf-8")

        # CSV extractor should include column names and table structure
        assert "product_id" in output_content or "name" in output_content
        assert "Widget" in output_content

    @mock_aws
    def test_json_document_full_flow(self, mock_env, lambda_context):
        """Test complete flow for JSON document processing with structure analysis."""
        s3, dynamodb = setup_mocked_aws()

        json_content = json.dumps(
            {
                "api_version": "1.0",
                "endpoints": [
                    {"path": "/users", "method": "GET"},
                    {"path": "/users/{id}", "method": "GET"},
                    {"path": "/users", "method": "POST"},
                ],
                "auth": {"type": "bearer", "header": "Authorization"},
            }
        ).encode("utf-8")

        document_id = "int-test-json-001"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/api_config.json",
            Body=json_content,
        )

        event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/api_config.json",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
            "fileType": "text",
            "detectedType": "json",
        }

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            result = module.lambda_handler(event, lambda_context)

        # Verify Lambda result
        assert result["document_id"] == document_id
        assert result["status"] == "ocr_complete"

        # Verify S3 output contains structure analysis
        output = s3.get_object(
            Bucket="test-bucket",
            Key=f"output/{document_id}/full_text.txt",
        )
        output_content = output["Body"].read().decode("utf-8")

        # JSON extractor should analyze structure
        assert "api_version" in output_content or "endpoints" in output_content

    @mock_aws
    def test_xml_document_full_flow(self, mock_env, lambda_context):
        """Test complete flow for XML document processing."""
        s3, dynamodb = setup_mocked_aws()

        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<catalog>
    <book id="1">
        <title>Python Cookbook</title>
        <author>David Beazley</author>
        <price>49.99</price>
    </book>
    <book id="2">
        <title>Effective Python</title>
        <author>Brett Slatkin</author>
        <price>39.99</price>
    </book>
</catalog>"""

        document_id = "int-test-xml-001"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/books.xml",
            Body=xml_content,
        )

        event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/books.xml",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
            "fileType": "text",
            "detectedType": "xml",
        }

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            result = module.lambda_handler(event, lambda_context)

        # Verify Lambda result
        assert result["document_id"] == document_id
        assert result["status"] == "ocr_complete"

        # Verify S3 output
        output = s3.get_object(
            Bucket="test-bucket",
            Key=f"output/{document_id}/full_text.txt",
        )
        output_content = output["Body"].read().decode("utf-8")
        assert "catalog" in output_content or "book" in output_content

    @mock_aws
    def test_email_document_full_flow(self, mock_env, lambda_context):
        """Test complete flow for email (EML) document processing."""
        s3, dynamodb = setup_mocked_aws()

        eml_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Integration Test Email
Date: Mon, 1 Jan 2024 12:00:00 +0000
Content-Type: text/plain; charset=utf-8

Hello,

This is a test email for integration testing.

Best regards,
The Test Team"""

        document_id = "int-test-eml-001"
        s3.put_object(
            Bucket="test-bucket",
            Key=f"input/{document_id}/message.eml",
            Body=eml_content,
        )

        event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/message.eml",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
            "fileType": "text",
            "detectedType": "eml",
        }

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            result = module.lambda_handler(event, lambda_context)

        # Verify Lambda result
        assert result["document_id"] == document_id
        assert result["status"] == "ocr_complete"

        # Verify S3 output contains email headers and body
        output = s3.get_object(
            Bucket="test-bucket",
            Key=f"output/{document_id}/full_text.txt",
        )
        output_content = output["Body"].read().decode("utf-8")
        assert "sender@example.com" in output_content or "Integration Test Email" in output_content

    @mock_aws
    def test_error_handling_file_not_found(self, mock_env, lambda_context):
        """Test error handling when source file doesn't exist."""
        s3, dynamodb = setup_mocked_aws()

        document_id = "int-test-error-001"

        event = {
            "document_id": document_id,
            "input_s3_uri": f"s3://test-bucket/input/{document_id}/missing.html",
            "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
            "fileType": "text",
            "detectedType": "html",
        }

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()
            with pytest.raises(module.s3_client.exceptions.NoSuchKey):
                module.lambda_handler(event, lambda_context)

        # Verify tracking table shows failed status
        table = dynamodb.Table("test-tracking-table")
        item = table.get_item(Key={"document_id": document_id})["Item"]
        assert item["status"] == "failed"
        assert "error_message" in item

    @mock_aws
    def test_multiple_documents_sequential(self, mock_env, lambda_context):
        """Test processing multiple documents sequentially."""
        s3, dynamodb = setup_mocked_aws()

        documents = [
            ("doc1.txt", b"This is document 1.", "txt"),
            ("doc2.html", b"<html><body><p>Document 2</p></body></html>", "html"),
            ("doc3.json", b'{"name": "Document 3"}', "json"),
        ]

        with patch("ragstack_common.appsync.publish_document_update"):
            module = _load_process_text_module()

            for i, (filename, content, file_type) in enumerate(documents):
                document_id = f"int-test-multi-{i:03d}"
                s3.put_object(
                    Bucket="test-bucket",
                    Key=f"input/{document_id}/{filename}",
                    Body=content,
                )

                event = {
                    "document_id": document_id,
                    "input_s3_uri": f"s3://test-bucket/input/{document_id}/{filename}",
                    "output_s3_prefix": f"s3://test-bucket/output/{document_id}/",
                    "fileType": "text",
                    "detectedType": file_type,
                }

                result = module.lambda_handler(event, lambda_context)
                assert result["status"] == "ocr_complete"

        # Verify all documents processed
        table = dynamodb.Table("test-tracking-table")
        for i in range(len(documents)):
            document_id = f"int-test-multi-{i:03d}"
            item = table.get_item(Key={"document_id": document_id})["Item"]
            assert item["status"] == "ocr_complete"
