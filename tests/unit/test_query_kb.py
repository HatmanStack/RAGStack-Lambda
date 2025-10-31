"""
Unit tests for query_kb Lambda function.
"""

# Mock imports
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

# Set required environment variables BEFORE importing the module
os.environ["KNOWLEDGE_BASE_ID"] = "test-kb-id-12345"
os.environ["CONFIGURATION_TABLE_NAME"] = "test-config-table"
os.environ["REGION"] = "us-east-1"

# Add Lambda function to path
lambda_dir = Path(__file__).parent.parent.parent / "src" / "lambda" / "query_kb"
sys.path.insert(0, str(lambda_dir))

mock_config = MagicMock()
sys.modules["ragstack_common"] = MagicMock()
sys.modules["ragstack_common.config"] = mock_config

# Now import the Lambda function
import index


@pytest.fixture
def valid_event():
    """Valid input event for query_kb Lambda."""
    return {"query": "What is the main topic of this document?", "max_results": 5}


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = "query_kb"
    context.memory_limit_in_mb = 1024
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:query_kb"
    context.aws_request_id = "test-request-id"
    return context


@pytest.fixture
def mock_bedrock_response():
    """Mock Bedrock Agent Runtime retrieve_and_generate response."""
    return {
        "output": {
            "text": (
                "Based on the documents, the main topics are cloud architecture and AWS services."
            )
        },
        "citations": [
            {
                "retrievedReferences": [
                    {
                        "content": {"text": "This document discusses cloud architecture."},
                        "location": {"s3Location": {"uri": "s3://bucket/doc1.pdf"}},
                        "score": 0.95,
                    },
                    {
                        "content": {"text": "AWS services are covered in detail."},
                        "location": {"s3Location": {"uri": "s3://bucket/doc2.pdf"}},
                        "score": 0.87,
                    },
                ]
            }
        ],
    }


@patch.dict(
    "os.environ",
    {
        "KNOWLEDGE_BASE_ID": "test-kb-123",
        "AWS_REGION": "us-east-1",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    },
)
@patch("index.config_manager")
@patch("index.boto3.client")
def test_lambda_handler_success(
    mock_boto3_client, mock_config_manager, valid_event, lambda_context, mock_bedrock_response
):
    """Test successful Knowledge Base query."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    # Setup mock
    mock_bedrock_agent = Mock()
    mock_boto3_client.return_value = mock_bedrock_agent
    mock_bedrock_agent.retrieve_and_generate.return_value = mock_bedrock_response

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify
    assert result["query"] == "What is the main topic of this document?"
    assert len(result["results"]) == 2
    assert result["results"][0]["content"] == "This document discusses cloud architecture."
    assert result["results"][0]["source"] == "s3://bucket/doc1.pdf"
    assert result["results"][0]["score"] == 0.95
    assert "response" in result
    assert "cloud architecture" in result["response"]

    # Verify config_manager was called
    mock_config_manager.get_parameter.assert_called_once()

    # Verify Bedrock agent was called with retrieve_and_generate
    mock_bedrock_agent.retrieve_and_generate.assert_called_once()


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123", "CONFIGURATION_TABLE_NAME": "test-config-table"},
)
@patch("index.config_manager")
@patch("index.boto3.client")
def test_lambda_handler_empty_query(mock_boto3_client, mock_config_manager, lambda_context):
    """Test handling of empty query."""

    event = {"query": "", "max_results": 5}

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify
    assert result["results"] == []
    assert result["message"] == "No query provided"

    # Verify boto3.client was still called to create bedrock_agent
    # (but retrieve_and_generate not called)
    mock_boto3_client.assert_called_once_with("bedrock-agent-runtime")


@patch.dict("os.environ", {"KNOWLEDGE_BASE_ID": "test-kb-123"})
@patch("index.boto3.client")
def test_lambda_handler_no_query_field(mock_boto3_client, lambda_context):
    """Test handling of missing query field."""

    event = {"max_results": 5}  # No query field

    mock_bedrock_agent = mock_boto3_client.return_value

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify
    assert result["results"] == []
    assert result["message"] == "No query provided"
    mock_bedrock_agent.retrieve.assert_not_called()


@patch.dict("os.environ", {
    "KNOWLEDGE_BASE_ID": "test-kb-123",
    "CONFIGURATION_TABLE_NAME": "test-config-table"
})
@patch("index.config_manager")
@patch("index.boto3.client")
def test_lambda_handler_custom_max_results(
    mock_boto3_client, mock_config_manager, lambda_context, mock_bedrock_response
):
    """Test custom max_results parameter."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    event = {"query": "test query", "max_results": 10}

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve_and_generate.return_value = mock_bedrock_response

    # Execute
    index.lambda_handler(event, lambda_context)

    # Verify numberOfResults was set to 10
    call_args = mock_bedrock_agent.retrieve_and_generate.call_args
    assert (
        call_args[1]["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"][
            "retrievalConfiguration"]["vectorSearchConfiguration"]["numberOfResults"]
        == 10
    )


@patch.dict("os.environ", {
    "KNOWLEDGE_BASE_ID": "test-kb-123",
    "CONFIGURATION_TABLE_NAME": "test-config-table"
})
@patch("index.config_manager")
@patch("index.boto3.client")
def test_lambda_handler_default_max_results(
    mock_boto3_client, mock_config_manager, lambda_context, mock_bedrock_response
):
    """Test default max_results when not specified."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    event = {"query": "test query"}  # No max_results

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve_and_generate.return_value = mock_bedrock_response

    # Execute
    index.lambda_handler(event, lambda_context)

    # Verify default numberOfResults is 5
    call_args = mock_bedrock_agent.retrieve_and_generate.call_args
    assert (
        call_args[1]["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"][
            "retrievalConfiguration"]["vectorSearchConfiguration"]["numberOfResults"]
        == 5
    )


@patch.dict("os.environ", {
    "KNOWLEDGE_BASE_ID": "test-kb-123",
    "CONFIGURATION_TABLE_NAME": "test-config-table"
})
@patch("index.config_manager")
@patch("index.boto3.client")
def test_lambda_handler_no_results(mock_boto3_client, mock_config_manager, valid_event, lambda_context):
    """Test handling when Knowledge Base returns no results."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    # Mock empty response
    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve_and_generate.return_value = {
        "output": {"text": ""},
        "citations": []
    }

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify
    assert result["results"] == []
    assert result["query"] == valid_event["query"]


@patch.dict("os.environ", {
    "KNOWLEDGE_BASE_ID": "test-kb-123",
    "CONFIGURATION_TABLE_NAME": "test-config-table"
})
@patch("index.config_manager")
@patch("index.boto3.client")
def test_lambda_handler_bedrock_error(mock_boto3_client, mock_config_manager, valid_event, lambda_context):
    """Test handling of Bedrock API error."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    # Mock Bedrock error
    error = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "retrieve_and_generate"
    )
    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve_and_generate.side_effect = error

    # Execute - handler catches exceptions and returns error dict
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify error is in response
    assert result["results"] == []
    assert "error" in result


@patch.dict("os.environ", {
    "KNOWLEDGE_BASE_ID": "test-kb-123",
    "CONFIGURATION_TABLE_NAME": "test-config-table"
})
@patch("index.config_manager")
@patch("index.boto3.client")
def test_lambda_handler_missing_content_fields(mock_boto3_client, mock_config_manager, valid_event, lambda_context):
    """Test handling of incomplete retrieval results."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    # Mock response with missing fields
    incomplete_response = {
        "output": {"text": "Generated response"},
        "citations": [
            {
                "retrievedReferences": [
                    {
                        "content": {},  # Missing 'text' - tests graceful handling
                        "location": {},  # Missing 's3Location' - tests graceful handling
                        "score": 0.5,
                    }
                ]
            }
        ]
    }

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve_and_generate.return_value = incomplete_response

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify graceful handling
    assert len(result["results"]) == 1
    assert result["results"][0]["content"] == ""  # Default empty string
    assert result["results"][0]["source"] == ""  # Default empty string
    assert result["results"][0]["score"] == 0.5


@patch.dict("os.environ", {
    "KNOWLEDGE_BASE_ID": "test-kb-123",
    "CONFIGURATION_TABLE_NAME": "test-config-table"
})
@patch("index.config_manager")
@patch("index.boto3.client")
def test_lambda_handler_result_count_logged(
    mock_boto3_client, mock_config_manager, valid_event, lambda_context, mock_bedrock_response, caplog
):
    """Test that result count is logged."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve_and_generate.return_value = mock_bedrock_response

    # Execute
    with caplog.at_level("INFO"):
        index.lambda_handler(valid_event, lambda_context)

    # Verify logging
    assert "Generated response with 2 source documents" in caplog.text


@patch.dict(
    "os.environ",
    {
        "KNOWLEDGE_BASE_ID": "test-kb-123",
        "AWS_REGION": "us-east-1",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    },
)
@patch("index.config_manager")
@patch("index.boto3.client")
def test_lambda_handler_uses_runtime_config(
    mock_boto3_client, mock_config_manager, valid_event, lambda_context
):
    """Test that handler reads response_model_id from ConfigurationManager."""

    # Setup config manager mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    # Setup Bedrock mock
    mock_bedrock_agent = Mock()
    mock_boto3_client.return_value = mock_bedrock_agent
    mock_bedrock_agent.retrieve_and_generate.return_value = {
        "output": {"text": "Test response"},
        "citations": [],
    }

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify config_manager was called with correct parameter
    mock_config_manager.get_parameter.assert_called_once_with(
        "response_model_id", default="anthropic.claude-3-5-haiku-20241022-v1:0"
    )

    # Verify retrieve_and_generate was called with the configured model
    call_args = mock_bedrock_agent.retrieve_and_generate.call_args
    model_arn = call_args[1]["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"][
        "modelArn"
    ]
    assert "anthropic.claude-3-5-sonnet-20241022-v2:0" in model_arn

    # Verify successful result
    assert "response" in result


@patch.dict(
    "os.environ",
    {
        "KNOWLEDGE_BASE_ID": "test-kb-123",
        "AWS_REGION": "us-west-2",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    },
)
@patch("index.config_manager")
@patch("index.boto3.client")
def test_lambda_handler_uses_correct_region_in_model_arn(
    mock_boto3_client, mock_config_manager, valid_event, lambda_context
):
    """Test that handler uses correct AWS region in model ARN."""

    # Setup config manager mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    # Setup Bedrock mock
    mock_bedrock_agent = Mock()
    mock_boto3_client.return_value = mock_bedrock_agent
    mock_bedrock_agent.retrieve_and_generate.return_value = {
        "output": {"text": "Test response"},
        "citations": [],
    }

    # Execute
    index.lambda_handler(valid_event, lambda_context)

    # Verify model ARN contains correct region
    call_args = mock_bedrock_agent.retrieve_and_generate.call_args
    model_arn = call_args[1]["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"][
        "modelArn"
    ]
    assert "us-west-2" in model_arn
    assert "arn:aws:bedrock:us-west-2::foundation-model" in model_arn


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
