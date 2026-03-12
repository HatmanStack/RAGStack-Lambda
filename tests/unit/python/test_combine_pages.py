"""Unit tests for combine_pages Lambda."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


def load_combine_pages_module():
    """Load the combine_pages index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src" / "lambda" / "combine_pages" / "index.py"
    ).resolve()

    if "combine_pages_index" in sys.modules:
        del sys.modules["combine_pages_index"]

    spec = importlib.util.spec_from_file_location("combine_pages_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["combine_pages_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    with patch.dict(
        os.environ,
        {
            "TRACKING_TABLE": "test-tracking-table",
            "INGEST_TO_KB_FUNCTION_ARN": "arn:aws:lambda:us-east-1:123:function:IngestToKB",
        },
    ):
        yield


@pytest.fixture
def base_event():
    return {
        "document_id": "doc-123",
        "output_s3_prefix": "s3://bucket/content/doc-123/",
        "total_pages": 20,
        "batch_results": [
            {
                "page_start": 1,
                "page_end": 10,
                "partial_output_uri": "s3://bucket/content/doc-123/pages_1-10.txt",
            },
            {
                "page_start": 11,
                "page_end": 20,
                "partial_output_uri": "s3://bucket/content/doc-123/pages_11-20.txt",
            },
        ],
    }


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.storage.write_s3_text")
    @patch("ragstack_common.storage.read_s3_text")
    @patch("ragstack_common.storage.delete_s3_object")
    @patch("ragstack_common.appsync.publish_document_update")
    def test_happy_path_combines_batches(
        self,
        mock_publish,
        mock_delete,
        mock_read,
        mock_write,
        mock_resource,
        mock_client,
        base_event,
    ):
        mock_read.side_effect = ["Page 1-10 text", "Page 11-20 text"]
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"filename": "report.pdf"}}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        mock_lambda = MagicMock()
        mock_client.return_value = mock_lambda

        module = load_combine_pages_module()
        result = module.lambda_handler(base_event, None)

        assert result["document_id"] == "doc-123"
        assert result["status"] == "ocr_complete"
        assert result["total_pages"] == 20
        assert "extracted_text.txt" in result["output_s3_uri"]

        # Verify text was combined
        mock_write.assert_called_once()
        written_text = mock_write.call_args[0][1]
        assert "Page 1-10 text" in written_text
        assert "Page 11-20 text" in written_text

        # Verify partial files cleaned up
        assert mock_delete.call_count == 2

        # Verify IngestToKB invoked
        mock_lambda.invoke.assert_called_once()

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.storage.write_s3_text")
    @patch("ragstack_common.storage.read_s3_text")
    @patch("ragstack_common.storage.delete_s3_object")
    @patch("ragstack_common.appsync.publish_document_update")
    def test_single_batch(
        self, mock_publish, mock_delete, mock_read, mock_write, mock_resource, mock_client
    ):
        mock_read.return_value = "Single page text"
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        mock_client.return_value = MagicMock()

        event = {
            "document_id": "doc-1",
            "output_s3_prefix": "s3://bucket/content/doc-1/",
            "total_pages": 5,
            "batch_results": [
                {
                    "page_start": 1,
                    "page_end": 5,
                    "partial_output_uri": "s3://bucket/content/doc-1/pages_1-5.txt",
                }
            ],
        }

        module = load_combine_pages_module()
        result = module.lambda_handler(event, None)

        assert result["document_id"] == "doc-1"
        mock_write.assert_called_once()

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.storage.write_s3_text")
    @patch("ragstack_common.storage.read_s3_text")
    @patch("ragstack_common.storage.delete_s3_object")
    @patch("ragstack_common.appsync.publish_document_update")
    def test_no_batch_results_lists_s3(
        self, mock_publish, mock_delete, mock_read, mock_write, mock_resource, mock_client
    ):
        """When no batch_results in event, lists S3 for partial files."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "content/doc-1/pages_1-10.txt"},
                {"Key": "content/doc-1/pages_11-20.txt"},
            ],
            "IsTruncated": False,
        }
        mock_client.return_value = mock_s3

        mock_read.side_effect = ["Text A", "Text B"]
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb

        event = {
            "document_id": "doc-1",
            "output_s3_prefix": "s3://bucket/content/doc-1/",
            "total_pages": 20,
        }

        module = load_combine_pages_module()
        result = module.lambda_handler(event, None)

        assert result["document_id"] == "doc-1"
        mock_s3.list_objects_v2.assert_called()

    def test_missing_tracking_table_raises(self):
        with patch.dict(os.environ, {"TRACKING_TABLE": ""}):
            module = load_combine_pages_module()
            with pytest.raises(ValueError, match="TRACKING_TABLE"):
                module.lambda_handler(
                    {
                        "document_id": "doc-1",
                        "output_s3_prefix": "s3://bucket/content/",
                        "total_pages": 10,
                    },
                    None,
                )

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.storage.write_s3_text")
    @patch("ragstack_common.storage.read_s3_text")
    @patch("ragstack_common.storage.delete_s3_object")
    @patch("ragstack_common.appsync.publish_document_update")
    def test_no_partial_files_raises(
        self, mock_publish, mock_delete, mock_read, mock_write, mock_resource, mock_client
    ):
        mock_resource.return_value = MagicMock()
        # Empty list is falsy, so handler goes to _list_partial_files
        # which calls boto3.client("s3") internally -- mock returns no Contents
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {"Contents": [], "IsTruncated": False}
        mock_client.return_value = mock_s3

        event = {
            "document_id": "doc-1",
            "output_s3_prefix": "s3://bucket/content/doc-1/",
            "total_pages": 10,
            # batch_results intentionally omitted (not empty list) -- empty list is falsy
        }

        module = load_combine_pages_module()
        with pytest.raises(ValueError, match="No partial files"):
            module.lambda_handler(event, None)

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.storage.write_s3_text")
    @patch("ragstack_common.storage.read_s3_text")
    @patch("ragstack_common.storage.delete_s3_object")
    @patch("ragstack_common.appsync.publish_document_update")
    def test_s3_read_failure_raises(
        self, mock_publish, mock_delete, mock_read, mock_write, mock_resource, mock_client
    ):
        mock_read.side_effect = Exception("S3 read failed")
        mock_resource.return_value = MagicMock()
        mock_client.return_value = MagicMock()

        event = {
            "document_id": "doc-1",
            "output_s3_prefix": "s3://bucket/content/doc-1/",
            "total_pages": 10,
            "batch_results": [
                {
                    "page_start": 1,
                    "page_end": 10,
                    "partial_output_uri": "s3://bucket/content/doc-1/pages_1-10.txt",
                }
            ],
        }

        module = load_combine_pages_module()
        with pytest.raises(Exception, match="S3 read failed"):
            module.lambda_handler(event, None)

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.storage.write_s3_text")
    @patch("ragstack_common.storage.read_s3_text")
    @patch("ragstack_common.storage.delete_s3_object")
    @patch("ragstack_common.appsync.publish_document_update")
    def test_delete_failure_non_fatal(
        self, mock_publish, mock_delete, mock_read, mock_write, mock_resource, mock_client
    ):
        """Partial file deletion failure should not crash the handler."""
        mock_read.return_value = "Page text"
        mock_delete.side_effect = Exception("Delete failed")
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        mock_client.return_value = MagicMock()

        event = {
            "document_id": "doc-1",
            "output_s3_prefix": "s3://bucket/content/doc-1/",
            "total_pages": 5,
            "batch_results": [
                {
                    "page_start": 1,
                    "page_end": 5,
                    "partial_output_uri": "s3://bucket/content/doc-1/pages_1-5.txt",
                }
            ],
        }

        module = load_combine_pages_module()
        result = module.lambda_handler(event, None)
        assert result["status"] == "ocr_complete"

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.storage.write_s3_text")
    @patch("ragstack_common.storage.read_s3_text")
    @patch("ragstack_common.storage.delete_s3_object")
    @patch("ragstack_common.appsync.publish_document_update")
    def test_no_ingest_arn_skips_invocation(
        self, mock_publish, mock_delete, mock_read, mock_write, mock_resource, mock_client
    ):
        mock_read.return_value = "Text"
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        mock_lambda = MagicMock()
        mock_client.return_value = mock_lambda

        event = {
            "document_id": "doc-1",
            "output_s3_prefix": "s3://bucket/content/doc-1/",
            "total_pages": 5,
            "batch_results": [
                {
                    "page_start": 1,
                    "page_end": 5,
                    "partial_output_uri": "s3://bucket/content/doc-1/pages_1-5.txt",
                }
            ],
        }

        with patch.dict(os.environ, {"INGEST_TO_KB_FUNCTION_ARN": ""}):
            module = load_combine_pages_module()
            result = module.lambda_handler(event, None)

        assert result["status"] == "ocr_complete"
        mock_lambda.invoke.assert_not_called()
