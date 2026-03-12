"""Unit tests for enqueue_batches Lambda."""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_enqueue_batches_module():
    """Load the enqueue_batches index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src"
        / "lambda"
        / "enqueue_batches"
        / "index.py"
    ).resolve()

    if "enqueue_batches_index" in sys.modules:
        del sys.modules["enqueue_batches_index"]

    spec = importlib.util.spec_from_file_location("enqueue_batches_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["enqueue_batches_index"] = module
    spec.loader.exec_module(module)
    return module


def _make_event(num_batches):
    """Create an event with the given number of batches."""
    return {
        "document_id": "doc-123",
        "input_s3_uri": "s3://bucket/input/doc-123/report.pdf",
        "output_s3_prefix": "s3://bucket/content/doc-123/",
        "total_pages": num_batches * 10,
        "batches": [
            {"page_start": i * 10 + 1, "page_end": (i + 1) * 10} for i in range(num_batches)
        ],
    }


@pytest.fixture(autouse=True)
def set_env_vars():
    """Set required environment variables for all tests."""
    with patch.dict(
        os.environ,
        {
            "TRACKING_TABLE": "test-tracking-table",
            "BATCH_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/test-queue",
        },
    ):
        yield


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_happy_path_3_batches(self, mock_resource, mock_client):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"filename": "report.pdf"}}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb

        mock_sqs = MagicMock()
        mock_client.return_value = mock_sqs

        module = load_enqueue_batches_module()
        result = module.lambda_handler(_make_event(3), None)

        assert result["document_id"] == "doc-123"
        assert result["status"] == "batches_enqueued"
        assert result["total_batches"] == 3
        mock_sqs.send_message_batch.assert_called_once()
        mock_table.update_item.assert_called_once()

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_exactly_10_batches_single_sqs_call(self, mock_resource, mock_client):
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb

        mock_sqs = MagicMock()
        mock_client.return_value = mock_sqs

        module = load_enqueue_batches_module()
        module.lambda_handler(_make_event(10), None)

        # Exactly 10 entries = 1 send_message_batch call
        assert mock_sqs.send_message_batch.call_count == 1

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_11_batches_two_sqs_calls(self, mock_resource, mock_client):
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb

        mock_sqs = MagicMock()
        mock_client.return_value = mock_sqs

        module = load_enqueue_batches_module()
        module.lambda_handler(_make_event(11), None)

        # 11 entries = 2 calls (10 + 1)
        assert mock_sqs.send_message_batch.call_count == 2

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_20_batches_two_sqs_calls(self, mock_resource, mock_client):
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb

        mock_sqs = MagicMock()
        mock_client.return_value = mock_sqs

        module = load_enqueue_batches_module()
        module.lambda_handler(_make_event(20), None)

        # 20 entries = 2 calls (10 + 10)
        assert mock_sqs.send_message_batch.call_count == 2

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_dynamodb_tracking_initialized(self, mock_resource, mock_client):
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        mock_client.return_value = MagicMock()

        module = load_enqueue_batches_module()
        module.lambda_handler(_make_event(5), None)

        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["ExpressionAttributeValues"][":total"] == 5
        assert call_kwargs["ExpressionAttributeValues"][":remaining"] == 5
        assert call_kwargs["ExpressionAttributeValues"][":zero"] == 0

    def test_missing_tracking_table_raises(self):
        with patch.dict(os.environ, {"TRACKING_TABLE": ""}):
            module = load_enqueue_batches_module()
            with pytest.raises(ValueError, match="TRACKING_TABLE"):
                module.lambda_handler(_make_event(1), None)

    def test_missing_batch_queue_url_raises(self):
        with patch.dict(os.environ, {"BATCH_QUEUE_URL": ""}):
            module = load_enqueue_batches_module()
            with pytest.raises(ValueError, match="BATCH_QUEUE_URL"):
                module.lambda_handler(_make_event(1), None)

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_graphql_endpoint_publishes_update(self, mock_resource, mock_client):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"filename": "report.pdf"}}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        mock_client.return_value = MagicMock()

        module = load_enqueue_batches_module()
        with (
            patch.dict(os.environ, {"GRAPHQL_ENDPOINT": "https://test.appsync.com/graphql"}),
            patch("ragstack_common.appsync.publish_document_update") as mock_publish,
        ):
            module.lambda_handler(_make_event(1), None)
            mock_publish.assert_called_once()

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_no_graphql_endpoint_skips_publish(self, mock_resource, mock_client):
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        mock_client.return_value = MagicMock()

        module = load_enqueue_batches_module()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GRAPHQL_ENDPOINT", None)
            result = module.lambda_handler(_make_event(1), None)
            assert result["status"] == "batches_enqueued"

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_graphql_publish_failure_non_fatal(self, mock_resource, mock_client):
        mock_table = MagicMock()
        mock_table.get_item.side_effect = Exception("DynamoDB error")
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        mock_client.return_value = MagicMock()

        module = load_enqueue_batches_module()
        with patch.dict(os.environ, {"GRAPHQL_ENDPOINT": "https://test.appsync.com/graphql"}):
            # Should not raise even if publish fails
            result = module.lambda_handler(_make_event(1), None)
            assert result["status"] == "batches_enqueued"
