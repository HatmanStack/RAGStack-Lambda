"""Unit tests for initial_sync Lambda."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


def load_initial_sync_module():
    """Load the initial_sync index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src" / "lambda" / "initial_sync" / "index.py"
    ).resolve()

    if "initial_sync_index" in sys.modules:
        del sys.modules["initial_sync_index"]

    spec = importlib.util.spec_from_file_location("initial_sync_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["initial_sync_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.log_stream_name = "test-log-stream"
    return ctx


@pytest.fixture
def base_event():
    return {
        "RequestType": "Create",
        "ResponseURL": "https://cfn-response.example.com/callback",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789:stack/test/guid",
        "RequestId": "req-123",
        "LogicalResourceId": "InitialSync",
        "ResourceProperties": {
            "KnowledgeBaseId": "kb-123",
            "DataSourceId": "ds-456",
        },
    }


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_create_happy_path(self, mock_boto3_client, mock_urlopen, base_event, mock_context):
        mock_bedrock = MagicMock()
        mock_bedrock.start_ingestion_job.return_value = {
            "ingestionJob": {"ingestionJobId": "job-789"}
        }
        mock_boto3_client.return_value = mock_bedrock

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module = load_initial_sync_module()
        with patch.object(module, "bedrock_agent", mock_bedrock):
            module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"
        assert body["Data"]["IngestionJobId"] == "job-789"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_create_missing_kb_id(self, mock_boto3_client, mock_urlopen, base_event, mock_context):
        mock_boto3_client.return_value = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        base_event["ResourceProperties"] = {"DataSourceId": "ds-456"}

        module = load_initial_sync_module()
        module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "FAILED"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_create_missing_ds_id(self, mock_boto3_client, mock_urlopen, base_event, mock_context):
        mock_boto3_client.return_value = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        base_event["ResourceProperties"] = {"KnowledgeBaseId": "kb-123"}

        module = load_initial_sync_module()
        module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "FAILED"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_create_client_error_sends_success(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        """ClientError from bedrock-agent sends SUCCESS to not fail deployment."""
        mock_bedrock = MagicMock()
        mock_bedrock.start_ingestion_job.side_effect = ClientError(
            {"Error": {"Code": "ServiceError", "Message": "Service unavailable"}},
            "StartIngestionJob",
        )
        mock_boto3_client.return_value = mock_bedrock

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module = load_initial_sync_module()
        with patch.object(module, "bedrock_agent", mock_bedrock):
            module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"
        assert "skipped" in body["Reason"].lower()

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_update_sends_success(self, mock_boto3_client, mock_urlopen, base_event, mock_context):
        mock_boto3_client.return_value = MagicMock()
        base_event["RequestType"] = "Update"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module = load_initial_sync_module()
        module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_delete_sends_success(self, mock_boto3_client, mock_urlopen, base_event, mock_context):
        mock_boto3_client.return_value = MagicMock()
        base_event["RequestType"] = "Delete"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module = load_initial_sync_module()
        module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_unknown_request_type(self, mock_boto3_client, mock_urlopen, base_event, mock_context):
        mock_boto3_client.return_value = MagicMock()
        base_event["RequestType"] = "Invalid"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module = load_initial_sync_module()
        module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "FAILED"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_unexpected_exception_sends_failed(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_bedrock = MagicMock()
        mock_bedrock.start_ingestion_job.side_effect = RuntimeError("unexpected")
        mock_boto3_client.return_value = mock_bedrock

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module = load_initial_sync_module()
        with patch.object(module, "bedrock_agent", mock_bedrock):
            module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "FAILED"
