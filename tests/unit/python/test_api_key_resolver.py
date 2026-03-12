"""Unit tests for api_key_resolver Lambda."""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


def load_api_key_resolver_module():
    """Load the api_key_resolver index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src"
        / "lambda"
        / "api_key_resolver"
        / "index.py"
    ).resolve()

    if "api_key_resolver_index" in sys.modules:
        del sys.modules["api_key_resolver_index"]

    spec = importlib.util.spec_from_file_location("api_key_resolver_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["api_key_resolver_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    """Set required environment variables for all tests."""
    with patch.dict(os.environ, {"APPSYNC_API_ID": "test-api-id"}):
        yield


class TestGetApiKey:
    """Tests for getApiKey operation."""

    @patch("boto3.client")
    def test_get_api_key_returns_newest(self, mock_boto3_client):
        mock_appsync = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "apiKeys": [
                    {"id": "key-old", "expires": 1000000},
                    {"id": "key-new", "expires": 2000000},
                ]
            }
        ]
        mock_appsync.get_paginator.return_value = paginator
        mock_boto3_client.return_value = mock_appsync

        module = load_api_key_resolver_module()
        with patch.object(module, "appsync", mock_appsync):
            result = module.lambda_handler({"info": {"fieldName": "getApiKey"}}, None)

        assert result["apiKey"] == "key-new"
        assert result["id"] == "key-new"
        assert result["error"] is None

    @patch("boto3.client")
    def test_get_api_key_no_keys(self, mock_boto3_client):
        mock_appsync = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [{"apiKeys": []}]
        mock_appsync.get_paginator.return_value = paginator
        mock_boto3_client.return_value = mock_appsync

        module = load_api_key_resolver_module()
        with patch.object(module, "appsync", mock_appsync):
            result = module.lambda_handler({"info": {"fieldName": "getApiKey"}}, None)

        assert result["apiKey"] == ""
        assert "No API key found" in result["error"]

    @patch("boto3.client")
    def test_get_api_key_client_error(self, mock_boto3_client):
        mock_appsync = MagicMock()
        paginator = MagicMock()
        paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "Not found"}},
            "ListApiKeys",
        )
        mock_appsync.get_paginator.return_value = paginator
        mock_boto3_client.return_value = mock_appsync

        module = load_api_key_resolver_module()
        with patch.object(module, "appsync", mock_appsync):
            result = module.lambda_handler({"info": {"fieldName": "getApiKey"}}, None)

        assert result["apiKey"] == ""
        assert result["error"] != ""


class TestRegenerateApiKey:
    """Tests for regenerateApiKey operation."""

    @patch("boto3.client")
    def test_regenerate_creates_and_deletes(self, mock_boto3_client):
        mock_appsync = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [{"apiKeys": [{"id": "old-key", "expires": 1000000}]}]
        mock_appsync.get_paginator.return_value = paginator
        mock_appsync.create_api_key.return_value = {"apiKey": {"id": "new-key-id"}}
        mock_boto3_client.return_value = mock_appsync

        module = load_api_key_resolver_module()
        with patch.object(module, "appsync", mock_appsync):
            result = module.lambda_handler({"info": {"fieldName": "regenerateApiKey"}}, None)

        assert result["apiKey"] == "new-key-id"
        assert result["error"] is None
        mock_appsync.delete_api_key.assert_called_once_with(apiId="test-api-id", id="old-key")

    @patch("boto3.client")
    def test_regenerate_delete_failure_non_fatal(self, mock_boto3_client):
        mock_appsync = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [{"apiKeys": [{"id": "old-key", "expires": 1000000}]}]
        mock_appsync.get_paginator.return_value = paginator
        mock_appsync.create_api_key.return_value = {"apiKey": {"id": "new-key"}}
        mock_appsync.delete_api_key.side_effect = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "Not found"}},
            "DeleteApiKey",
        )
        mock_boto3_client.return_value = mock_appsync

        module = load_api_key_resolver_module()
        with patch.object(module, "appsync", mock_appsync):
            result = module.lambda_handler({"info": {"fieldName": "regenerateApiKey"}}, None)

        # Should succeed even if old key deletion fails
        assert result["apiKey"] == "new-key"
        assert result["error"] is None


class TestLambdaHandlerGeneral:
    """Tests for general handler behavior."""

    @patch("boto3.client")
    def test_missing_api_id(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_api_key_resolver_module()

        with patch.dict(os.environ, {"APPSYNC_API_ID": ""}):
            result = module.lambda_handler({"info": {"fieldName": "getApiKey"}}, None)

        assert "not configured" in result["error"]

    @patch("boto3.client")
    def test_unsupported_operation(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_api_key_resolver_module()

        result = module.lambda_handler({"info": {"fieldName": "unknownOp"}}, None)

        assert result["error"] != ""
        assert "Unsupported" in result["error"]
