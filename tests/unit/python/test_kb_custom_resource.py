"""Unit tests for kb_custom_resource Lambda."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


def load_kb_custom_resource_module():
    """Load the kb_custom_resource index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src" / "lambda" / "kb_custom_resource" / "index.py"
    ).resolve()

    if "kb_custom_resource_index" in sys.modules:
        del sys.modules["kb_custom_resource_index"]

    spec = importlib.util.spec_from_file_location("kb_custom_resource_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["kb_custom_resource_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.log_stream_name = "test-log-stream"
    return ctx


@pytest.fixture
def base_properties():
    return {
        "KnowledgeBaseName": "test-kb",
        "RoleArn": "arn:aws:iam::123:role/KBRole",
        "VectorBucket": "test-vector-bucket",
        "EmbedModelArn": "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-v2:0",
        "DataBucket": "test-data-bucket",
        "ProjectName": "test-project",
    }


@pytest.fixture
def base_event(base_properties):
    return {
        "RequestType": "Create",
        "ResponseURL": "https://cfn-response.example.com/callback",
        "StackId": "arn:aws:cloudformation:us-east-1:123:stack/test/guid",
        "RequestId": "req-123",
        "LogicalResourceId": "KnowledgeBase",
        "ResourceProperties": base_properties,
    }


class TestLambdaHandlerCreate:
    """Tests for Create request type."""

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_create_happy_path(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_bedrock = MagicMock()
        mock_s3vectors = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789"}
        mock_ssm = MagicMock()

        mock_bedrock.create_knowledge_base.return_value = {
            "knowledgeBase": {
                "knowledgeBaseId": "kb-123",
                "knowledgeBaseArn": "arn:aws:bedrock:us-east-1:123:knowledge-base/kb-123",
            }
        }
        mock_bedrock.create_data_source.return_value = {
            "dataSource": {"dataSourceId": "ds-456"}
        }

        def client_factory(svc, **kwargs):
            return {
                "bedrock-agent": mock_bedrock,
                "s3vectors": mock_s3vectors,
                "sts": mock_sts,
                "ssm": mock_ssm,
            }.get(svc, MagicMock())

        mock_boto3_client.side_effect = client_factory

        module = load_kb_custom_resource_module()
        with (
            patch.object(module, "bedrock_agent", mock_bedrock),
            patch.object(module, "ssm", mock_ssm),
            patch("time.sleep"),  # Skip the 10s wait
        ):
            module.lambda_handler(base_event, mock_context)

        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"
        assert body["Data"]["KnowledgeBaseId"] == "kb-123"
        assert body["Data"]["DataSourceId"] == "ds-456"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_create_s3vectors_already_exists(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_bedrock = MagicMock()
        mock_s3vectors = MagicMock()
        mock_s3vectors.create_vector_bucket.side_effect = ClientError(
            {"Error": {"Code": "ConflictException", "Message": "Already exists"}},
            "CreateVectorBucket",
        )
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789"}
        mock_ssm = MagicMock()

        mock_bedrock.create_knowledge_base.return_value = {
            "knowledgeBase": {
                "knowledgeBaseId": "kb-123",
                "knowledgeBaseArn": "arn:aws:bedrock:us-east-1:123:knowledge-base/kb-123",
            }
        }
        mock_bedrock.create_data_source.return_value = {
            "dataSource": {"dataSourceId": "ds-456"}
        }

        def client_factory(svc, **kwargs):
            return {
                "bedrock-agent": mock_bedrock,
                "s3vectors": mock_s3vectors,
                "sts": mock_sts,
                "ssm": mock_ssm,
            }.get(svc, MagicMock())

        mock_boto3_client.side_effect = client_factory

        module = load_kb_custom_resource_module()
        with (
            patch.object(module, "bedrock_agent", mock_bedrock),
            patch.object(module, "ssm", mock_ssm),
            patch("time.sleep"),
        ):
            module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_create_failure_sends_failed(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_bedrock = MagicMock()
        mock_s3vectors = MagicMock()
        mock_s3vectors.create_vector_bucket.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Permission denied"}},
            "CreateVectorBucket",
        )

        def client_factory(svc, **kwargs):
            return {
                "bedrock-agent": mock_bedrock,
                "s3vectors": mock_s3vectors,
            }.get(svc, MagicMock())

        mock_boto3_client.side_effect = client_factory

        module = load_kb_custom_resource_module()
        with patch.object(module, "bedrock_agent", mock_bedrock):
            module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "FAILED"


class TestLambdaHandlerUpdate:
    """Tests for Update request type."""

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_update_returns_existing_attributes(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_bedrock = MagicMock()
        mock_bedrock.get_knowledge_base.return_value = {
            "knowledgeBase": {
                "knowledgeBaseArn": "arn:aws:bedrock:us-east-1:123:knowledge-base/kb-123",
                "storageConfiguration": {
                    "type": "S3_VECTORS",
                    "s3VectorsConfiguration": {"indexArn": "arn:aws:s3vectors:..."},
                },
            }
        }
        mock_bedrock.list_data_sources.return_value = {
            "dataSourceSummaries": [{"dataSourceId": "ds-456"}]
        }
        mock_boto3_client.return_value = mock_bedrock

        module = load_kb_custom_resource_module()
        base_event["RequestType"] = "Update"
        base_event["PhysicalResourceId"] = "kb-123"

        with patch.object(module, "bedrock_agent", mock_bedrock):
            module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"
        assert body["Data"]["KnowledgeBaseId"] == "kb-123"
        assert body["Data"]["DataSourceId"] == "ds-456"


class TestLambdaHandlerDelete:
    """Tests for Delete request type."""

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_delete_happy_path(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_bedrock = MagicMock()
        mock_bedrock.list_data_sources.return_value = {
            "dataSourceSummaries": [{"dataSourceId": "ds-456"}]
        }
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_bedrock

        module = load_kb_custom_resource_module()
        base_event["RequestType"] = "Delete"
        base_event["PhysicalResourceId"] = "kb-123"

        with (
            patch.object(module, "bedrock_agent", mock_bedrock),
            patch.object(module, "ssm", mock_ssm),
        ):
            module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"
        mock_bedrock.delete_knowledge_base.assert_called_once_with(knowledgeBaseId="kb-123")

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_delete_placeholder_id_skips(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_bedrock = MagicMock()
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_bedrock

        module = load_kb_custom_resource_module()
        base_event["RequestType"] = "Delete"
        base_event["PhysicalResourceId"] = "KnowledgeBase"

        with (
            patch.object(module, "bedrock_agent", mock_bedrock),
            patch.object(module, "ssm", mock_ssm),
        ):
            module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "SUCCESS"
        mock_bedrock.delete_knowledge_base.assert_not_called()

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_delete_failure_still_sends_response(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_bedrock = MagicMock()
        mock_bedrock.list_data_sources.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "KB not found"}},
            "ListDataSources",
        )
        mock_bedrock.delete_knowledge_base.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "KB not found"}},
            "DeleteKnowledgeBase",
        )
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_bedrock

        module = load_kb_custom_resource_module()
        base_event["RequestType"] = "Delete"
        base_event["PhysicalResourceId"] = "kb-missing"

        with (
            patch.object(module, "bedrock_agent", mock_bedrock),
            patch.object(module, "ssm", mock_ssm),
        ):
            module.lambda_handler(base_event, mock_context)

        # Should still send a response even on errors
        mock_urlopen.assert_called()


class TestLambdaHandlerMissing:
    """Tests for missing DataBucket and general error paths."""

    @patch("urllib.request.urlopen")
    @patch("boto3.client")
    def test_create_missing_data_bucket_sends_failed(
        self, mock_boto3_client, mock_urlopen, base_event, mock_context
    ):
        mock_bedrock = MagicMock()
        mock_s3vectors = MagicMock()

        def client_factory(svc, **kwargs):
            return {
                "bedrock-agent": mock_bedrock,
                "s3vectors": mock_s3vectors,
            }.get(svc, MagicMock())

        mock_boto3_client.side_effect = client_factory

        # Remove DataBucket from properties
        del base_event["ResourceProperties"]["DataBucket"]

        module = load_kb_custom_resource_module()
        with patch.object(module, "bedrock_agent", mock_bedrock):
            module.lambda_handler(base_event, mock_context)

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["Status"] == "FAILED"
