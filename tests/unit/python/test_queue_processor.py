"""Unit tests for queue_processor Lambda."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


def load_queue_processor_module():
    """Load the queue_processor index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src" / "lambda" / "queue_processor" / "index.py"
    ).resolve()

    if "queue_processor_index" in sys.modules:
        del sys.modules["queue_processor_index"]

    spec = importlib.util.spec_from_file_location("queue_processor_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["queue_processor_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    """Set required environment variables for all tests."""
    with patch.dict(
        os.environ,
        {
            "STATE_MACHINE_ARN": "arn:aws:states:us-east-1:123456789:stateMachine:test",
            "CONFIGURATION_TABLE_NAME": "test-config-table",
        },
    ):
        yield


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.aws_request_id = "request-123456"
    return ctx


@pytest.fixture
def sqs_event():
    """Sample SQS event with one record."""
    return {
        "Records": [
            {
                "messageId": "msg-abc123",
                "body": json.dumps({
                    "document_id": "input/doc-uuid/report.pdf",
                    "input_s3_uri": "s3://bucket/input/doc-uuid/report.pdf",
                }),
            }
        ]
    }


class TestCheckReindexLock:
    """Tests for check_reindex_lock function."""

    def test_no_config_table_returns_without_error(self):
        module = load_queue_processor_module()
        with patch.dict(os.environ, {"CONFIGURATION_TABLE_NAME": ""}):
            module.check_reindex_lock()  # Should not raise

    @patch("boto3.resource")
    def test_lock_not_present(self, mock_boto3_resource):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        module = load_queue_processor_module()
        module.check_reindex_lock()  # Should not raise

    @patch("boto3.resource")
    def test_lock_present_and_locked_raises(self, mock_boto3_resource):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {"is_locked": True, "started_at": "2026-01-01T00:00:00"}
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        module = load_queue_processor_module()
        with pytest.raises(RuntimeError, match="reindex is in progress"):
            module.check_reindex_lock()

    @patch("boto3.resource")
    def test_dynamodb_error_logs_warning(self, mock_boto3_resource):
        mock_table = MagicMock()
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "oops"}},
            "GetItem",
        )
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        module = load_queue_processor_module()
        module.check_reindex_lock()  # Should not raise


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_single_record_starts_execution(
        self, mock_boto3_client, mock_boto3_resource, sqs_event, mock_context
    ):
        mock_sfn = MagicMock()
        mock_boto3_client.return_value = mock_sfn

        # Mock check_reindex_lock to not find a lock
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        module = load_queue_processor_module()
        result = module.lambda_handler(sqs_event, mock_context)

        mock_sfn.start_execution.assert_called_once()
        call_kwargs = mock_sfn.start_execution.call_args[1]
        assert call_kwargs["stateMachineArn"] == os.environ["STATE_MACHINE_ARN"]
        assert result["statusCode"] == 200

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_multiple_records(self, mock_boto3_client, mock_boto3_resource, mock_context):
        mock_sfn = MagicMock()
        mock_boto3_client.return_value = mock_sfn

        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        event = {
            "Records": [
                {"messageId": f"msg-{i}", "body": json.dumps({"document_id": f"doc-{i}"})}
                for i in range(3)
            ]
        }

        module = load_queue_processor_module()
        module.lambda_handler(event, mock_context)

        assert mock_sfn.start_execution.call_count == 3

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_execution_name_sanitized(
        self, mock_boto3_client, mock_boto3_resource, mock_context
    ):
        mock_sfn = MagicMock()
        mock_boto3_client.return_value = mock_sfn

        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        event = {
            "Records": [
                {
                    "messageId": "msg-123",
                    "body": json.dumps({"document_id": "input/doc uuid/file!.pdf"}),
                }
            ]
        }

        module = load_queue_processor_module()
        module.lambda_handler(event, mock_context)

        call_kwargs = mock_sfn.start_execution.call_args[1]
        name = call_kwargs["name"]
        # Should not contain spaces or exclamation marks
        assert " " not in name
        assert "!" not in name
        assert len(name) <= 80

    @patch("boto3.resource")
    @patch("boto3.client")
    def test_reindex_lock_active_raises(
        self, mock_boto3_client, mock_boto3_resource, mock_context, sqs_event
    ):
        mock_sfn = MagicMock()
        mock_boto3_client.return_value = mock_sfn

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {"is_locked": True, "started_at": "2026-01-01"}
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        module = load_queue_processor_module()
        with pytest.raises(RuntimeError, match="reindex is in progress"):
            module.lambda_handler(sqs_event, mock_context)

        mock_sfn.start_execution.assert_not_called()
