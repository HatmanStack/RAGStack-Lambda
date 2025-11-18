"""
Unit tests for search_kb Lambda function.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Set required environment variables BEFORE importing the module
os.environ["KNOWLEDGE_BASE_ID"] = "test-kb-id-12345"
os.environ["REGION"] = "us-east-1"

# Ensure botocore is not mocked when loading the handler
if "botocore" in sys.modules and hasattr(sys.modules["botocore"], "_mock_name"):
    del sys.modules["botocore"]
if "botocore.exceptions" in sys.modules and hasattr(
    sys.modules["botocore.exceptions"], "_mock_name"
):
    del sys.modules["botocore.exceptions"]

# Use importlib to load the Lambda function with a unique module name
lambda_dir = Path(__file__).parent.parent.parent / "src" / "lambda" / "search_kb"
spec = importlib.util.spec_from_file_location("index_search_kb", lambda_dir / "index.py")
index = importlib.util.module_from_spec(spec)
sys.modules["index_search_kb"] = index
spec.loader.exec_module(index)


@pytest.fixture
def valid_event():
    """Valid input event for search_kb Lambda."""
    return {"query": "What is the main topic of this document?", "maxResults": 5}


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = "search_kb"
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:search_kb"
    context.aws_request_id = "test-request-id"
    return context


@pytest.fixture
def mock_bedrock_retrieve_response():
    """Mock Bedrock Agent Runtime retrieve response (raw vector search)."""
    return {
        "retrievalResults": [
            {
                "content": {"text": "This document discusses cloud architecture and best practices."},
                "location": {"s3Location": {"uri": "s3://bucket/doc1.pdf/pages/page-1.json"}},
                "score": 0.95,
            },
            {
                "content": {"text": "AWS services are covered in detail with examples."},
                "location": {"s3Location": {"uri": "s3://bucket/doc2.pdf/pages/page-2.json"}},
                "score": 0.87,
            },
            {
                "content": {"text": "Security best practices for cloud deployments."},
                "location": {"s3Location": {"uri": "s3://bucket/doc3.pdf/pages/page-5.json"}},
                "score": 0.82,
            },
        ]
    }


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123"},
)
@patch("index_search_kb.boto3.client")
def test_lambda_handler_success(
    mock_boto3_client, valid_event, lambda_context, mock_bedrock_retrieve_response
):
    """Test successful Knowledge Base search."""
    # Setup mock
    mock_bedrock_agent = Mock()
    mock_boto3_client.return_value = mock_bedrock_agent
    mock_bedrock_agent.retrieve.return_value = mock_bedrock_retrieve_response

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify KBQueryResult format
    assert result["query"] == "What is the main topic of this document?"
    assert result["total"] == 3
    assert len(result["results"]) == 3
    assert result["results"][0]["content"] == "This document discusses cloud architecture and best practices."
    assert result["results"][0]["source"] == "s3://bucket/doc1.pdf/pages/page-1.json"
    assert result["results"][0]["score"] == 0.95

    # Verify Bedrock agent was called with retrieve
    mock_bedrock_agent.retrieve.assert_called_once()
    call_args = mock_bedrock_agent.retrieve.call_args
    assert call_args[1]["knowledgeBaseId"] == "test-kb-123"
    assert call_args[1]["retrievalQuery"]["text"] == "What is the main topic of this document?"
    assert call_args[1]["retrievalConfiguration"]["vectorSearchConfiguration"]["numberOfResults"] == 5


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123"},
)
@patch("index_search_kb.boto3.client")
def test_lambda_handler_empty_query(mock_boto3_client, lambda_context):
    """Test handling of empty query."""
    event = {"query": "", "maxResults": 5}

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify KBQueryResult format for empty query
    assert result["query"] == ""
    assert result["results"] == []
    assert result["total"] == 0
    assert result["error"] == "No query provided"

    # Verify boto3.client was still called but retrieve not called
    mock_boto3_client.assert_called_once_with("bedrock-agent-runtime")


@patch.dict("os.environ", {"KNOWLEDGE_BASE_ID": "test-kb-123"})
@patch("index_search_kb.boto3.client")
def test_lambda_handler_no_query_field(mock_boto3_client, lambda_context):
    """Test handling of missing query field."""
    event = {"maxResults": 5}  # No query field

    mock_bedrock_agent = mock_boto3_client.return_value

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify KBQueryResult format for missing query
    assert result["query"] == ""
    assert result["results"] == []
    assert result["total"] == 0
    assert result["error"] == "No query provided"
    mock_bedrock_agent.retrieve.assert_not_called()


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123"},
)
@patch("index_search_kb.boto3.client")
def test_lambda_handler_default_max_results(
    mock_boto3_client, lambda_context, mock_bedrock_retrieve_response
):
    """Test default maxResults when not provided."""
    event = {"query": "test query"}  # No maxResults

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve.return_value = mock_bedrock_retrieve_response

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify default maxResults of 5
    call_args = mock_bedrock_agent.retrieve.call_args
    assert call_args[1]["retrievalConfiguration"]["vectorSearchConfiguration"]["numberOfResults"] == 5
    assert result["query"] == "test query"
    assert result["total"] == 3


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123"},
)
@patch("index_search_kb.boto3.client")
def test_lambda_handler_custom_max_results(
    mock_boto3_client, lambda_context, mock_bedrock_retrieve_response
):
    """Test custom maxResults parameter."""
    event = {"query": "test query", "maxResults": 10}

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve.return_value = mock_bedrock_retrieve_response

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify custom maxResults
    call_args = mock_bedrock_agent.retrieve.call_args
    assert call_args[1]["retrievalConfiguration"]["vectorSearchConfiguration"]["numberOfResults"] == 10


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123"},
)
@patch("index_search_kb.boto3.client")
def test_lambda_handler_invalid_max_results(
    mock_boto3_client, lambda_context, mock_bedrock_retrieve_response
):
    """Test that invalid maxResults defaults to 5."""
    # Test with negative number
    event = {"query": "test", "maxResults": -1}

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve.return_value = mock_bedrock_retrieve_response

    result = index.lambda_handler(event, lambda_context)

    # Should use default of 5
    call_args = mock_bedrock_agent.retrieve.call_args
    assert call_args[1]["retrievalConfiguration"]["vectorSearchConfiguration"]["numberOfResults"] == 5

    # Test with too large number
    event = {"query": "test", "maxResults": 101}
    mock_bedrock_agent.retrieve.reset_mock()
    result = index.lambda_handler(event, lambda_context)

    # Should use default of 5
    call_args = mock_bedrock_agent.retrieve.call_args
    assert call_args[1]["retrievalConfiguration"]["vectorSearchConfiguration"]["numberOfResults"] == 5


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123"},
)
@patch("index_search_kb.boto3.client")
def test_lambda_handler_no_results(mock_boto3_client, valid_event, lambda_context):
    """Test handling when Knowledge Base returns no results."""
    # Mock empty response
    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": []}

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify KBQueryResult format for no results
    assert result["query"] == "What is the main topic of this document?"
    assert result["results"] == []
    assert result["total"] == 0


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123"},
)
@patch("index_search_kb.boto3.client")
def test_lambda_handler_bedrock_error(mock_boto3_client, valid_event, lambda_context):
    """Test handling of Bedrock API error."""

    # Mock Bedrock error
    def raise_bedrock_error(**kw):
        raise index.ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "retrieve",
        )

    mock_bedrock_agent = Mock()
    mock_boto3_client.return_value = mock_bedrock_agent
    mock_bedrock_agent.retrieve.side_effect = raise_bedrock_error

    # Execute - handler catches exceptions and returns error dict
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify KBQueryResult format with error
    assert result["query"] == "What is the main topic of this document?"
    assert result["results"] == []
    assert result["total"] == 0
    assert "error" in result
    assert "Rate exceeded" in result["error"]


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123"},
)
@patch("index_search_kb.boto3.client")
def test_lambda_handler_missing_content_fields(mock_boto3_client, valid_event, lambda_context):
    """Test handling of incomplete retrieval results."""
    # Mock response with missing fields
    incomplete_response = {
        "retrievalResults": [
            {
                "content": {},  # Missing 'text'
                "location": {},  # Missing 's3Location'
                "score": 0.5,
            }
        ]
    }

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve.return_value = incomplete_response

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify graceful handling - results with missing fields use empty strings
    assert len(result["results"]) == 1
    assert result["results"][0]["content"] == ""
    assert result["results"][0]["source"] == ""
    assert result["results"][0]["score"] == 0.5


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123"},
)
@patch("index_search_kb.boto3.client")
def test_lambda_handler_result_count_logged(
    mock_boto3_client, valid_event, lambda_context, mock_bedrock_retrieve_response, caplog
):
    """Test that result count is logged."""
    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve.return_value = mock_bedrock_retrieve_response

    # Execute
    with caplog.at_level("INFO"):
        index.lambda_handler(valid_event, lambda_context)

    # Verify logging includes result count
    assert "Found 3 results" in caplog.text


@patch.dict("os.environ", {"KNOWLEDGE_BASE_ID": "test-kb-123"})
@patch("index_search_kb.boto3.client")
def test_lambda_handler_query_too_long(mock_boto3_client, lambda_context):
    """Test handling of query exceeding max length."""
    event = {"query": "A" * 10001, "maxResults": 5}  # Query > 10000 chars

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify error response
    assert result["results"] == []
    assert result["total"] == 0
    assert "error" in result
    assert "exceeds maximum length" in result["error"]


@patch.dict("os.environ", {"KNOWLEDGE_BASE_ID": "test-kb-123"})
@patch("index_search_kb.boto3.client")
def test_lambda_handler_non_string_query(mock_boto3_client, lambda_context):
    """Test handling of non-string query."""
    event = {"query": 123, "maxResults": 5}  # Query is not a string

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify error response
    assert result["results"] == []
    assert result["total"] == 0
    assert "error" in result
    assert "must be a string" in result["error"]


@patch.dict("os.environ", {"KNOWLEDGE_BASE_ID": ""}, clear=True)
@patch("index_search_kb.boto3.client")
def test_lambda_handler_missing_knowledge_base_id(mock_boto3_client, valid_event, lambda_context):
    """Test handling when KNOWLEDGE_BASE_ID env var is missing."""
    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify error response
    assert result["query"] == ""
    assert result["results"] == []
    assert result["total"] == 0
    assert "error" in result
    assert "KNOWLEDGE_BASE_ID" in result["error"]


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123"},
)
@patch("index_search_kb.boto3.client")
def test_lambda_handler_appsync_event_format(
    mock_boto3_client, lambda_context, mock_bedrock_retrieve_response
):
    """Test handling of AppSync event format with arguments wrapper."""
    # AppSync wraps arguments
    event = {"arguments": {"query": "test query", "maxResults": 3}}

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve.return_value = mock_bedrock_retrieve_response

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify successful parsing
    assert result["query"] == "test query"
    assert result["total"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
