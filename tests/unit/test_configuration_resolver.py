"""Unit tests for ConfigurationResolver Lambda"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Set required environment variables BEFORE importing the module
os.environ["CONFIGURATION_TABLE_NAME"] = "test-config-table"
os.environ["TRACKING_TABLE"] = "test-tracking-table"
os.environ["INPUT_BUCKET"] = "test-input-bucket"
os.environ["STATE_MACHINE_ARN"] = (
    "arn:aws:states:us-east-1:123456789012:stateMachine:test-state-machine"
)
os.environ["LOG_LEVEL"] = "INFO"

# Mock boto3 BEFORE importing the handler module to prevent AWS client initialization
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "src" / "lambda" / "appsync_resolvers")
)

with patch("boto3.client"), patch("boto3.resource"):
    import index

# Fixtures


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Set required environment variables."""
    os.environ["CONFIGURATION_TABLE_NAME"] = "test-config-table"
    os.environ["TRACKING_TABLE"] = "test-tracking-table"
    os.environ["STATE_MACHINE_ARN"] = (
        "arn:aws:states:us-east-1:123456789012:stateMachine:test-state-machine"
    )
    os.environ["LOG_LEVEL"] = "INFO"


@pytest.fixture
def mock_configuration_table():
    """Mock DynamoDB configuration table."""
    return MagicMock()


@pytest.fixture
def mock_tracking_table():
    """Mock DynamoDB tracking table."""
    return MagicMock()


@pytest.fixture
def mock_dynamodb(mock_configuration_table, mock_tracking_table):
    """Mock boto3 DynamoDB resource."""
    with patch("boto3.resource") as mock_resource:
        mock_dynamodb_resource = MagicMock()

        # Table() returns different mocks based on table name
        def table_side_effect(table_name):
            if "config" in table_name.lower():
                return mock_configuration_table
            return mock_tracking_table

        mock_dynamodb_resource.Table.side_effect = table_side_effect
        mock_resource.return_value = mock_dynamodb_resource

        # Reload the module to pick up mocked boto3
        import importlib

        import index

        importlib.reload(index)

        yield {
            "configuration_table": mock_configuration_table,
            "tracking_table": mock_tracking_table,
        }


@pytest.fixture
def sample_schema():
    """Sample Schema configuration."""
    return {
        "Configuration": "Schema",
        "Schema": {
            "properties": {"ocr_backend": {"type": "string", "enum": ["textract", "bedrock"]}}
        },
    }


@pytest.fixture
def sample_default():
    """Sample Default configuration."""
    return {
        "Configuration": "Default",
        "ocr_backend": "textract",
        "text_embed_model_id": "amazon.titan-embed-text-v2:0",
    }


@pytest.fixture
def sample_custom():
    """Sample Custom configuration."""
    return {"Configuration": "Custom", "ocr_backend": "bedrock"}


# Test: lambda_handler routing


def test_lambda_handler_get_configuration(
    mock_dynamodb, sample_schema, sample_default, sample_custom
):
    """Test lambda_handler routes getConfiguration correctly."""
    mock_table = mock_dynamodb["configuration_table"]

    def get_item_side_effect(Key):
        config_type = Key["Configuration"]
        if config_type == "Schema":
            return {"Item": sample_schema}
        if config_type == "Default":
            return {"Item": sample_default}
        if config_type == "Custom":
            return {"Item": sample_custom}
        return {}

    mock_table.get_item.side_effect = get_item_side_effect

    event = {"info": {"fieldName": "getConfiguration"}, "arguments": {}}

    result = index.lambda_handler(event, {})

    assert "Schema" in result
    assert "Default" in result
    assert "Custom" in result


def test_lambda_handler_update_configuration(mock_dynamodb):
    """Test lambda_handler routes updateConfiguration correctly."""
    mock_table = mock_dynamodb["configuration_table"]

    event = {
        "info": {"fieldName": "updateConfiguration"},
        "arguments": {"customConfig": json.dumps({"ocr_backend": "bedrock"})},
    }

    result = index.lambda_handler(event, {})

    assert result is True
    mock_table.put_item.assert_called_once()


def test_lambda_handler_unsupported_operation(_mock_dynamodb):
    """Test lambda_handler raises error for unsupported operation."""
    event = {"info": {"fieldName": "unknownOperation"}, "arguments": {}}

    with pytest.raises(ValueError, match="Unsupported operation"):
        index.lambda_handler(event, {})


# Test: handle_get_configuration


@patch("index.get_configuration_item")
def test_handle_get_configuration_success(
    mock_get_item, sample_schema, sample_default, sample_custom
):
    """Test handle_get_configuration returns all configs."""

    def get_item_side_effect(config_type):
        if config_type == "Schema":
            return sample_schema
        if config_type == "Default":
            return sample_default
        if config_type == "Custom":
            return sample_custom
        return None

    mock_get_item.side_effect = get_item_side_effect

    result = index.handle_get_configuration()

    assert "Schema" in result
    assert "Default" in result
    assert "Custom" in result

    # Results should be JSON strings
    assert isinstance(result["Schema"], str)
    assert isinstance(result["Default"], str)
    assert isinstance(result["Custom"], str)

    # Verify content
    schema = json.loads(result["Schema"])
    assert "properties" in schema


@patch("index.get_configuration_item")
def test_handle_get_configuration_empty_custom(mock_get_item, sample_schema, sample_default):
    """Test handle_get_configuration when Custom config is empty."""

    def get_item_side_effect(config_type):
        if config_type == "Schema":
            return sample_schema
        if config_type == "Default":
            return sample_default
        if config_type == "Custom":
            return None
        return None

    mock_get_item.side_effect = get_item_side_effect

    result = index.handle_get_configuration()

    custom_config = json.loads(result["Custom"])
    assert custom_config == {}


# Test: handle_update_configuration


@patch("index.configuration_table")
def test_handle_update_configuration_with_json_string(mock_table):
    """Test updating configuration with JSON string."""
    custom_config = json.dumps(
        {"ocr_backend": "bedrock", "text_embed_model_id": "cohere.embed-english-v3"}
    )

    result = index.handle_update_configuration(custom_config)

    assert result is True
    mock_table.put_item.assert_called_once()
    call_args = mock_table.put_item.call_args[1]
    assert call_args["Item"]["Configuration"] == "Custom"
    assert call_args["Item"]["ocr_backend"] == "bedrock"


@patch("index.configuration_table")
def test_handle_update_configuration_with_dict(mock_table):
    """Test updating configuration with dictionary."""
    custom_config = {"ocr_backend": "bedrock"}

    result = index.handle_update_configuration(custom_config)

    assert result is True
    mock_table.put_item.assert_called_once()


def test_handle_update_configuration_invalid_json():
    """Test updating configuration with invalid JSON."""
    with pytest.raises(ValueError, match="Invalid configuration format"):
        index.handle_update_configuration("invalid json {")


# Test: handle_get_document_count


@patch("index.tracking_table")
def test_handle_get_document_count_success(mock_table):
    """Test getting document count."""
    mock_table.scan.return_value = {"Count": 42}

    result = index.handle_get_document_count()

    assert result == 42
    mock_table.scan.assert_called_once()


@patch("index.tracking_table")
def test_handle_get_document_count_zero(mock_table):
    """Test getting document count when no documents exist."""
    mock_table.scan.return_value = {"Count": 0}

    result = index.handle_get_document_count()

    assert result == 0


@patch("index.tracking_table")
def test_handle_get_document_count_dynamodb_error(mock_table):
    """Test getting document count handles DynamoDB errors gracefully."""
    mock_table.scan.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}}, "Scan"
    )

    result = index.handle_get_document_count()

    # Should return 0 instead of raising
    assert result == 0


# Test: remove_partition_key


def test_remove_partition_key():
    """Test partition key removal."""
    item = {"Configuration": "Default", "key1": "value1", "key2": "value2"}

    result = index.remove_partition_key(item)

    assert "Configuration" not in result
    assert result["key1"] == "value1"
    assert result["key2"] == "value2"


def test_remove_partition_key_none():
    """Test partition key removal with None."""
    result = index.remove_partition_key(None)
    assert result == {}


# Test: query_completed_documents


@patch("index.tracking_table")
def test_query_completed_documents_using_gsi(mock_table):
    """Test querying COMPLETED documents using StatusIndex GSI."""
    mock_table.query.return_value = {
        "Items": [
            {
                "document_id": "doc1",
                "input_bucket": "bucket1",
                "input_key": "key1",
                "status": "COMPLETED",
            },
            {
                "document_id": "doc2",
                "input_bucket": "bucket2",
                "input_key": "key2",
                "status": "COMPLETED",
            },
        ]
    }

    result = index.query_completed_documents()

    assert len(result) == 2
    assert result[0]["document_id"] == "doc1"
    assert result[1]["document_id"] == "doc2"
    mock_table.query.assert_called_once()


@patch("index.tracking_table")
def test_query_completed_documents_with_pagination(mock_table):
    """Test querying COMPLETED documents with pagination."""
    # First call returns data with pagination token
    mock_table.query.side_effect = [
        {
            "Items": [
                {
                    "document_id": "doc1",
                    "input_bucket": "b1",
                    "input_key": "k1",
                    "status": "COMPLETED",
                }
            ],
            "LastEvaluatedKey": {"document_id": "doc1"},
        },
        {
            "Items": [
                {
                    "document_id": "doc2",
                    "input_bucket": "b2",
                    "input_key": "k2",
                    "status": "COMPLETED",
                }
            ]
        },
    ]

    result = index.query_completed_documents()

    assert len(result) == 2
    assert mock_table.query.call_count == 2


@patch("index.tracking_table")
def test_query_completed_documents_fallback_to_scan(mock_table):
    """Test fallback to scan when GSI is not available."""
    # First call (query) fails, fallback to scan
    mock_table.query.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "GSI not found"}}, "Query"
    )
    mock_table.scan.return_value = {
        "Items": [
            {
                "document_id": "doc1",
                "input_bucket": "bucket1",
                "input_key": "key1",
                "status": "COMPLETED",
            }
        ]
    }

    result = index.query_completed_documents()

    assert len(result) == 1
    assert result[0]["document_id"] == "doc1"
    mock_table.scan.assert_called_once()


# Test: handle_re_embed_all_documents


@patch("boto3.client")
@patch("index.query_completed_documents")
@patch("index.configuration_table")
def test_handle_re_embed_all_documents_success(
    mock_config_table, mock_query_docs, mock_boto_client
):
    """Test re-embedding job creation with documents."""
    mock_query_docs.return_value = [
        {"document_id": "doc1", "input_bucket": "bucket1", "input_key": "key1"},
        {"document_id": "doc2", "input_bucket": "bucket2", "input_key": "key2"},
    ]

    mock_sfn_client = MagicMock()
    mock_boto_client.return_value = mock_sfn_client

    result = index.handle_re_embed_all_documents()

    assert result["status"] == "IN_PROGRESS"
    assert result["totalDocuments"] == 2
    assert result["processedDocuments"] == 0
    assert "jobId" in result
    assert "startTime" in result

    # Verify DynamoDB writes (job item + latest pointer)
    assert mock_config_table.put_item.call_count == 2

    # Verify Step Functions executions started
    assert mock_sfn_client.start_execution.call_count == 2


@patch("index.query_completed_documents")
@patch("index.configuration_table")
def test_handle_re_embed_all_documents_no_documents(mock_config_table, mock_query_docs):
    """Test re-embedding when no documents exist."""
    mock_query_docs.return_value = []

    result = index.handle_re_embed_all_documents()

    assert result["status"] == "COMPLETED"
    assert result["totalDocuments"] == 0
    assert result["processedDocuments"] == 0
    assert result["startTime"] == result["completionTime"]

    # Should not create tracking items or start Step Functions
    mock_config_table.put_item.assert_not_called()


@patch("boto3.client")
@patch("index.query_completed_documents")
@patch("index.configuration_table")
def test_handle_re_embed_all_documents_enforces_limit(
    _mock_config_table, mock_query_docs, mock_boto_client
):
    """Test re-embedding enforces 500 document limit."""
    # Create 600 mock documents
    mock_documents = [
        {"document_id": f"doc{i}", "input_bucket": f"bucket{i}", "input_key": f"key{i}"}
        for i in range(600)
    ]
    mock_query_docs.return_value = mock_documents

    mock_sfn_client = MagicMock()
    mock_boto_client.return_value = mock_sfn_client

    result = index.handle_re_embed_all_documents()

    # Should limit to 500
    assert result["totalDocuments"] == 500
    assert mock_sfn_client.start_execution.call_count == 500


# Test: handle_get_re_embed_job_status


@patch("index.configuration_table")
def test_handle_get_re_embed_job_status_success(mock_table):
    """Test getting re-embed job status."""
    job_id = "test-job-123"
    job_key = f"ReEmbedJob#{job_id}"

    # Mock latest pointer
    mock_table.get_item.side_effect = [
        {"Item": {"Configuration": "ReEmbedJob_Latest", "jobId": job_id, "jobKey": job_key}},
        {
            "Item": {
                "Configuration": job_key,
                "jobId": job_id,
                "status": "IN_PROGRESS",
                "totalDocuments": 100,
                "processedDocuments": 50,
                "startTime": "2025-10-28T10:00:00Z",
                "completionTime": None,
            }
        },
    ]

    result = index.handle_get_re_embed_job_status()

    assert result["jobId"] == job_id
    assert result["status"] == "IN_PROGRESS"
    assert result["totalDocuments"] == 100
    assert result["processedDocuments"] == 50
    assert result["startTime"] == "2025-10-28T10:00:00Z"
    assert result["completionTime"] is None


@patch("index.configuration_table")
def test_handle_get_re_embed_job_status_no_job(mock_table):
    """Test getting re-embed job status when no job exists."""
    mock_table.get_item.return_value = {}

    result = index.handle_get_re_embed_job_status()

    assert result is None


@patch("index.configuration_table")
def test_handle_get_re_embed_job_status_completed(mock_table):
    """Test getting completed re-embed job status."""
    job_id = "test-job-456"
    job_key = f"ReEmbedJob#{job_id}"

    mock_table.get_item.side_effect = [
        {"Item": {"Configuration": "ReEmbedJob_Latest", "jobId": job_id, "jobKey": job_key}},
        {
            "Item": {
                "Configuration": job_key,
                "jobId": job_id,
                "status": "COMPLETED",
                "totalDocuments": 50,
                "processedDocuments": 50,
                "startTime": "2025-10-28T10:00:00Z",
                "completionTime": "2025-10-28T11:00:00Z",
            }
        },
    ]

    result = index.handle_get_re_embed_job_status()

    assert result["status"] == "COMPLETED"
    assert result["totalDocuments"] == result["processedDocuments"]
    assert result["completionTime"] == "2025-10-28T11:00:00Z"
