"""
Unit tests for query_kb Lambda function.
"""

# Mock imports
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Set required environment variables BEFORE importing the module
os.environ["KNOWLEDGE_BASE_ID"] = "test-kb-id-12345"
os.environ["CONFIGURATION_TABLE_NAME"] = "test-config-table"
os.environ["REGION"] = "us-east-1"

mock_config = MagicMock()
sys.modules["ragstack_common"] = MagicMock()
sys.modules["ragstack_common.config"] = mock_config

# Ensure botocore is not mocked when loading the handler
# This prevents issues with exception handling
if "botocore" in sys.modules and isinstance(sys.modules["botocore"], MagicMock):
    del sys.modules["botocore"]
if "botocore.exceptions" in sys.modules and isinstance(
    sys.modules["botocore.exceptions"], MagicMock
):
    del sys.modules["botocore.exceptions"]

# Use importlib to load the Lambda function with a unique module name
# This avoids sys.modules['index'] caching issues when multiple tests load different index.py files
lambda_dir = Path(__file__).parent.parent.parent / "src" / "lambda" / "query_kb"
spec = importlib.util.spec_from_file_location("index_query_kb", lambda_dir / "index.py")
index = importlib.util.module_from_spec(spec)
sys.modules["index_query_kb"] = index
spec.loader.exec_module(index)


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
        "sessionId": "test-session-abc123",  # Bedrock always returns sessionId
        "citations": [
            {
                "retrievedReferences": [
                    {
                        "content": {"text": "This document discusses cloud architecture."},
                        "location": {
                            "s3Location": {"uri": "s3://bucket/doc1.pdf/pages/page-1.json"}
                        },
                        "score": 0.95,
                    },
                    {
                        "content": {"text": "AWS services are covered in detail."},
                        "location": {
                            "s3Location": {"uri": "s3://bucket/doc2.pdf/pages/page-2.json"}
                        },
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
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
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

    # Verify ChatResponse format
    assert result["answer"] == (
        "Based on the documents, the main topics are cloud architecture and AWS services."
    )
    assert result["sessionId"] is not None
    assert len(result["sources"]) == 2
    assert result["sources"][0]["documentId"] == "doc1.pdf"
    assert result["sources"][0]["s3Uri"] == "s3://bucket/doc1.pdf/pages/page-1.json"
    assert "cloud architecture" in result["sources"][0]["snippet"]

    # Verify config_manager was called
    mock_config_manager.get_parameter.assert_called_once()

    # Verify Bedrock agent was called with retrieve_and_generate
    mock_bedrock_agent.retrieve_and_generate.assert_called_once()


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123", "CONFIGURATION_TABLE_NAME": "test-config-table"},
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
def test_lambda_handler_empty_query(mock_boto3_client, mock_config_manager, lambda_context):
    """Test handling of empty query."""

    event = {"query": "", "max_results": 5}

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify ChatResponse format for empty query
    assert result["answer"] == ""
    assert result["sessionId"] is None
    assert result["sources"] == []
    assert result["error"] == "No query provided"

    # Verify boto3.client was still called to create bedrock_agent
    # (but retrieve_and_generate not called)
    mock_boto3_client.assert_called_once_with("bedrock-agent-runtime")


@patch.dict("os.environ", {"KNOWLEDGE_BASE_ID": "test-kb-123"})
@patch("index_query_kb.boto3.client")
def test_lambda_handler_no_query_field(mock_boto3_client, lambda_context):
    """Test handling of missing query field."""

    event = {"max_results": 5}  # No query field

    mock_bedrock_agent = mock_boto3_client.return_value

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify ChatResponse format for missing query
    assert result["answer"] == ""
    assert result["sessionId"] is None
    assert result["sources"] == []
    assert result["error"] == "No query provided"
    mock_bedrock_agent.retrieve.assert_not_called()


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123", "CONFIGURATION_TABLE_NAME": "test-config-table"},
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
def test_lambda_handler_ignores_extra_parameters(
    mock_boto3_client, mock_config_manager, lambda_context, mock_bedrock_response
):
    """Test that handler ignores unknown parameters gracefully."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    # Event with extra parameter (legacy max_results)
    event = {"query": "test query", "max_results": 10}

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve_and_generate.return_value = mock_bedrock_response

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify handler succeeds despite extra parameter
    assert result["answer"] is not None
    assert result["sessionId"] is not None


@patch.dict(
    "os.environ",
    {
        "KNOWLEDGE_BASE_ID": "test-kb-123",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
        "AWS_REGION": "us-east-1",
    },
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
def test_lambda_handler_minimal_request(
    mock_boto3_client, mock_config_manager, lambda_context, mock_bedrock_response
):
    """Test minimal request with just query parameter."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    event = {"query": "test query"}  # Only required field

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve_and_generate.return_value = mock_bedrock_response

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify successful ChatResponse
    assert result["answer"] is not None
    assert result["sessionId"] is not None
    assert isinstance(result["sources"], list)


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123", "CONFIGURATION_TABLE_NAME": "test-config-table"},
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
def test_lambda_handler_no_results(
    mock_boto3_client, mock_config_manager, valid_event, lambda_context
):
    """Test handling when Knowledge Base returns no results."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    # Mock empty response
    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve_and_generate.return_value = {
        "output": {"text": ""},
        "sessionId": "session-empty-123",
        "citations": [],
    }

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify ChatResponse format for no results
    assert result["answer"] == ""
    assert result["sources"] == []
    assert result["sessionId"] is not None


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123", "CONFIGURATION_TABLE_NAME": "test-config-table"},
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
def test_lambda_handler_bedrock_error(
    mock_boto3_client, mock_config_manager, valid_event, lambda_context
):
    """Test handling of Bedrock API error."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    # Mock Bedrock error
    # Use index.ClientError to ensure we're using the same one the handler uses
    def raise_bedrock_error(**kw):
        raise index.ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "retrieve_and_generate",
        )

    mock_bedrock_agent = Mock()
    mock_boto3_client.return_value = mock_bedrock_agent
    mock_bedrock_agent.retrieve_and_generate.side_effect = raise_bedrock_error

    # Execute - handler catches exceptions and returns error dict
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify ChatResponse format with error
    assert result["answer"] == ""
    assert result["sessionId"] is None
    assert result["sources"] == []
    assert "error" in result


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123", "CONFIGURATION_TABLE_NAME": "test-config-table"},
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
def test_lambda_handler_missing_content_fields(
    mock_boto3_client, mock_config_manager, valid_event, lambda_context
):
    """Test handling of incomplete retrieval results."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    # Mock response with missing fields
    incomplete_response = {
        "output": {"text": "Generated response"},
        "sessionId": "session-incomplete-456",
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
        ],
    }

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve_and_generate.return_value = incomplete_response

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify graceful handling - sources without complete info are skipped
    # since we can't parse invalid S3 URIs properly
    assert result["answer"] == "Generated response"
    assert result["sessionId"] is not None
    assert result["sources"] == []  # Invalid locations filtered out


@patch.dict(
    "os.environ",
    {"KNOWLEDGE_BASE_ID": "test-kb-123", "CONFIGURATION_TABLE_NAME": "test-config-table"},
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
def test_lambda_handler_result_count_logged(
    mock_boto3_client,
    mock_config_manager,
    valid_event,
    lambda_context,
    mock_bedrock_response,
    caplog,
):
    """Test that result count is logged."""

    # Setup config mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-haiku-20241022-v1:0"

    mock_bedrock_agent = mock_boto3_client.return_value
    mock_bedrock_agent.retrieve_and_generate.return_value = mock_bedrock_response

    # Execute
    with caplog.at_level("INFO"):
        index.lambda_handler(valid_event, lambda_context)

    # Verify logging includes source count
    assert "KB query successful" in caplog.text
    assert "Citations: 1" in caplog.text


@patch.dict(
    "os.environ",
    {
        "KNOWLEDGE_BASE_ID": "test-kb-123",
        "AWS_REGION": "us-east-1",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    },
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
def test_lambda_handler_uses_runtime_config(
    mock_boto3_client, mock_config_manager, valid_event, lambda_context
):
    """Test that handler reads chat_model_id from ConfigurationManager."""

    # Setup config manager mock
    mock_config_manager.get_parameter.return_value = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    # Setup Bedrock mock
    mock_bedrock_agent = Mock()
    mock_boto3_client.return_value = mock_bedrock_agent
    mock_bedrock_agent.retrieve_and_generate.return_value = {
        "output": {"text": "Test response"},
        "sessionId": "session-runtime-config-789",
        "citations": [],
    }

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify config_manager was called with correct parameter
    mock_config_manager.get_parameter.assert_called_once_with(
        "chat_model_id", default="amazon.nova-pro-v1:0"
    )

    # Verify retrieve_and_generate was called with the configured model
    call_args = mock_bedrock_agent.retrieve_and_generate.call_args
    model_arn = call_args[1]["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"][
        "modelArn"
    ]
    assert "anthropic.claude-3-5-sonnet-20241022-v2:0" in model_arn

    # Verify successful ChatResponse result
    assert result["answer"] == "Test response"
    assert result["sessionId"] is not None


@patch.dict(
    "os.environ",
    {
        "KNOWLEDGE_BASE_ID": "test-kb-123",
        "AWS_REGION": "us-west-2",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    },
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
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
        "sessionId": "session-region-test-999",
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


@patch.dict(
    "os.environ",
    {
        "KNOWLEDGE_BASE_ID": "test-kb-123",
        "AWS_REGION": "us-east-1",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    },
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
def test_lambda_handler_with_session_id(mock_boto3_client, mock_config_manager, lambda_context):
    """Test that sessionId is passed to Bedrock for conversation continuity."""
    # Setup config mock
    mock_config_manager.get_parameter.return_value = "amazon.nova-pro-v1:0"

    # Mock Bedrock response with sessionId
    mock_bedrock_agent = Mock()
    mock_boto3_client.return_value = mock_bedrock_agent
    mock_bedrock_agent.retrieve_and_generate.return_value = {
        "output": {"text": "Test answer"},
        "sessionId": "session-123",
        "citations": [],
    }

    # Event with sessionId
    event = {"query": "Follow-up question", "sessionId": "session-123"}

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify sessionId was passed to Bedrock
    call_args = mock_bedrock_agent.retrieve_and_generate.call_args
    assert "sessionId" in call_args[1]
    assert call_args[1]["sessionId"] == "session-123"

    # Verify response contains sessionId
    assert result["sessionId"] == "session-123"
    assert result["answer"] == "Test answer"


@patch.dict(
    "os.environ",
    {
        "KNOWLEDGE_BASE_ID": "test-kb-123",
        "AWS_REGION": "us-east-1",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    },
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
def test_lambda_handler_without_session_id_creates_new(
    mock_boto3_client, mock_config_manager, lambda_context
):
    """Test new conversation (no sessionId) - Bedrock creates new session."""
    # Setup config mock
    mock_config_manager.get_parameter.return_value = "amazon.nova-pro-v1:0"

    # Mock Bedrock response with new sessionId
    mock_bedrock_agent = Mock()
    mock_boto3_client.return_value = mock_bedrock_agent
    mock_bedrock_agent.retrieve_and_generate.return_value = {
        "output": {"text": "Test answer"},
        "sessionId": "new-session-456",  # Bedrock returns new sessionId
        "citations": [],
    }

    # Event without sessionId
    event = {"query": "First question"}

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify sessionId NOT in request (new conversation)
    call_args = mock_bedrock_agent.retrieve_and_generate.call_args
    assert "sessionId" not in call_args[1]

    # Verify response contains new sessionId from Bedrock
    assert result["sessionId"] == "new-session-456"
    assert result["answer"] == "Test answer"


@patch.dict(
    "os.environ",
    {
        "KNOWLEDGE_BASE_ID": "test-kb-123",
        "AWS_REGION": "us-east-1",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    },
)
@patch("index_query_kb.config_manager")
@patch("index_query_kb.boto3.client")
def test_lambda_handler_session_expiration_error(
    mock_boto3_client, mock_config_manager, lambda_context
):
    """Test graceful handling of expired session."""
    # Setup config mock
    mock_config_manager.get_parameter.return_value = "amazon.nova-pro-v1:0"

    # Bedrock returns validation error for expired session
    # Use index.ClientError to ensure we're using the same one the handler uses
    def raise_session_error(**kw):
        raise index.ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid session ID"}},
            "retrieve_and_generate",
        )

    mock_bedrock_agent = Mock()
    mock_boto3_client.return_value = mock_bedrock_agent
    mock_bedrock_agent.retrieve_and_generate.side_effect = raise_session_error

    # Event with expired sessionId
    event = {"query": "Test", "sessionId": "expired-session"}

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify user-friendly error
    assert result["error"] is not None
    assert "session" in result["error"].lower()
    assert result["sessionId"] is None
    assert result["answer"] == ""
    assert result["sources"] == []


def test_extract_sources_parses_s3_uris():
    """Test source extraction from Bedrock citations."""
    citations = [
        {
            "retrievedReferences": [
                {
                    "content": {"text": "Sample text from document about invoices"},
                    "location": {
                        "s3Location": {"uri": "s3://mybucket/my-document.pdf/pages/page-3.json"}
                    },
                }
            ]
        }
    ]

    sources = index.extract_sources(citations)

    assert len(sources) == 1
    assert sources[0]["documentId"] == "my-document.pdf"
    assert sources[0]["pageNumber"] == 3
    assert sources[0]["s3Uri"] == "s3://mybucket/my-document.pdf/pages/page-3.json"
    assert "Sample text" in sources[0]["snippet"]
    assert len(sources[0]["snippet"]) <= 200


def test_extract_sources_handles_url_encoding():
    """Test that URL-encoded document names are decoded."""
    citations = [
        {
            "retrievedReferences": [
                {
                    "content": {"text": "Text"},
                    "location": {
                        "s3Location": {
                            "uri": "s3://bucket/My%20Document%20With%20Spaces.pdf/pages/page-1.json"
                        }
                    },
                }
            ]
        }
    ]

    sources = index.extract_sources(citations)

    assert sources[0]["documentId"] == "My Document With Spaces.pdf"


def test_extract_sources_deduplicates():
    """Test that duplicate sources (same doc + page) are filtered."""
    citations = [
        {
            "retrievedReferences": [
                {
                    "content": {"text": "Text 1"},
                    "location": {"s3Location": {"uri": "s3://bucket/doc.pdf/pages/page-1.json"}},
                },
                {
                    "content": {"text": "Text 2"},
                    "location": {"s3Location": {"uri": "s3://bucket/doc.pdf/pages/page-1.json"}},
                },
                {
                    "content": {"text": "Text 3"},
                    "location": {"s3Location": {"uri": "s3://bucket/doc.pdf/pages/page-2.json"}},
                },
            ]
        }
    ]

    sources = index.extract_sources(citations)

    # Should have 2 unique sources (page 1 deduplicated)
    assert len(sources) == 2


def test_extract_sources_handles_missing_page_number():
    """Test sources without page numbers (non-paginated docs)."""
    citations = [
        {
            "retrievedReferences": [
                {
                    "content": {"text": "Text"},
                    "location": {
                        "s3Location": {"uri": "s3://bucket/document.txt/vectors/chunk-1.json"}
                    },
                }
            ]
        }
    ]

    sources = index.extract_sources(citations)

    assert len(sources) == 1
    assert sources[0]["documentId"] == "document.txt"
    assert sources[0]["pageNumber"] is None


def test_extract_sources_handles_empty_citations():
    """Test that empty citations return empty sources."""
    assert index.extract_sources([]) == []
    assert index.extract_sources([{"retrievedReferences": []}]) == []


def test_extract_sources_truncates_snippet():
    """Test that snippets are truncated to 200 chars."""
    long_text = "A" * 500
    citations = [
        {
            "retrievedReferences": [
                {
                    "content": {"text": long_text},
                    "location": {"s3Location": {"uri": "s3://bucket/doc.pdf/pages/page-1.json"}},
                }
            ]
        }
    ]

    sources = index.extract_sources(citations)

    assert len(sources[0]["snippet"]) == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
