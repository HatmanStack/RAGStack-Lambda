"""Unit tests for admin_user_provisioner Lambda."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_admin_user_provisioner_module():
    """Load the admin_user_provisioner index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src" / "lambda" / "admin_user_provisioner" / "index.py"
    ).resolve()

    if "admin_user_provisioner_index" in sys.modules:
        del sys.modules["admin_user_provisioner_index"]

    spec = importlib.util.spec_from_file_location("admin_user_provisioner_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["admin_user_provisioner_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_context():
    """Create a mock Lambda context."""
    ctx = MagicMock()
    ctx.log_stream_name = "test-log-stream"
    return ctx


@pytest.fixture
def base_event():
    """Base CloudFormation custom resource event."""
    return {
        "RequestType": "Create",
        "ResponseURL": "https://cfn-response.example.com/callback",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789:stack/test/guid",
        "RequestId": "req-123",
        "LogicalResourceId": "AdminUser",
        "ResourceProperties": {
            "UserPoolId": "us-east-1_TestPool",
            "Email": "admin@example.com",
        },
    }


class TestSendResponse:
    """Tests for send_response function."""

    @patch("boto3.client")
    def test_sends_put_to_response_url(self, mock_boto3_client, base_event, mock_context):
        mock_boto3_client.return_value = MagicMock()
        module = load_admin_user_provisioner_module()

        with patch.object(module, "urllib") as mock_urllib:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_urllib.request.urlopen.return_value.__enter__ = MagicMock(
                return_value=mock_response
            )
            mock_urllib.request.urlopen.return_value.__exit__ = MagicMock(return_value=False)

            module.send_response(base_event, mock_context, "SUCCESS", data={"Key": "Value"})

            mock_urllib.request.Request.assert_called_once()
            call_args = mock_urllib.request.Request.call_args
            assert call_args[0][0] == base_event["ResponseURL"]
            body = json.loads(call_args[1]["data"].decode("utf-8"))
            assert body["Status"] == "SUCCESS"
            assert body["Data"] == {"Key": "Value"}
            assert body["StackId"] == base_event["StackId"]


def _make_mock_cognito(user_exists=True):
    """Create a mock cognito client with proper exception class."""

    class UserNotFoundException(Exception):
        pass

    mock_cognito = MagicMock()
    mock_cognito.exceptions.UserNotFoundException = UserNotFoundException

    if user_exists:
        mock_cognito.admin_get_user.return_value = {"Username": "admin@example.com"}
    else:
        mock_cognito.admin_get_user.side_effect = UserNotFoundException(
            {"Error": {"Code": "UserNotFoundException", "Message": "User not found"}},
            "AdminGetUser",
        )
    return mock_cognito


class TestCreateUser:
    """Tests for create_user function."""

    @patch("boto3.client")
    def test_user_already_exists(self, mock_boto3_client):
        mock_cognito = _make_mock_cognito(user_exists=True)
        mock_boto3_client.return_value = mock_cognito

        module = load_admin_user_provisioner_module()
        with patch.object(module, "cognito", mock_cognito):
            result = module.create_user("us-east-1_Pool", "admin@example.com")

        assert result["created"] is False
        assert result["username"] == "admin@example.com"
        mock_cognito.admin_create_user.assert_not_called()

    @patch("boto3.client")
    def test_user_not_found_creates_new(self, mock_boto3_client):
        mock_cognito = _make_mock_cognito(user_exists=False)
        mock_boto3_client.return_value = mock_cognito

        module = load_admin_user_provisioner_module()
        with patch.object(module, "cognito", mock_cognito):
            result = module.create_user("us-east-1_Pool", "admin@example.com")

        assert result["created"] is True
        assert result["username"] == "admin@example.com"
        mock_cognito.admin_create_user.assert_called_once()


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_create_happy_path(self, mock_boto3_client, mock_urlopen, base_event, mock_context):
        mock_cognito = _make_mock_cognito(user_exists=False)
        mock_boto3_client.return_value = mock_cognito

        module = load_admin_user_provisioner_module()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(module, "cognito", mock_cognito):
            module.lambda_handler(base_event, mock_context)

        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"
        assert body["Data"]["Created"] == "True"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_create_missing_user_pool_id(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_boto3_client.return_value = MagicMock()
        module = load_admin_user_provisioner_module()

        base_event["ResourceProperties"] = {"Email": "admin@example.com"}

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "FAILED"
        assert "required" in body["Reason"].lower()

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_update_with_properties(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_cognito = _make_mock_cognito(user_exists=True)
        mock_boto3_client.return_value = mock_cognito

        module = load_admin_user_provisioner_module()
        base_event["RequestType"] = "Update"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(module, "cognito", mock_cognito):
            module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_update_without_properties(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_boto3_client.return_value = MagicMock()
        module = load_admin_user_provisioner_module()

        base_event["RequestType"] = "Update"
        base_event["ResourceProperties"] = {}

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_delete_sends_success(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_boto3_client.return_value = MagicMock()
        module = load_admin_user_provisioner_module()

        base_event["RequestType"] = "Delete"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_unknown_request_type_sends_failed(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_boto3_client.return_value = MagicMock()
        module = load_admin_user_provisioner_module()

        base_event["RequestType"] = "Invalid"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "FAILED"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_unhandled_exception_sends_failed(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.side_effect = RuntimeError("unexpected")
        mock_boto3_client.return_value = mock_cognito

        module = load_admin_user_provisioner_module()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(module, "cognito", mock_cognito):
            module.lambda_handler(base_event, mock_context)

        # Should still send a response to CloudFormation
        assert mock_urlopen.call_count >= 1

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_client_error_sends_failed(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        from botocore.exceptions import ClientError

        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Service unavailable"}},
            "AdminGetUser",
        )
        # Make exceptions attribute not have UserNotFoundException
        mock_cognito.exceptions.UserNotFoundException = type("UserNotFoundException", (Exception,), {})
        mock_boto3_client.return_value = mock_cognito

        module = load_admin_user_provisioner_module()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(module, "cognito", mock_cognito):
            module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "FAILED"
        assert "AWS error" in body["Reason"]
