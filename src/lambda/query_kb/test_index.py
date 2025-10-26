"""
Unit tests for query_kb Lambda function.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

# Mock imports
import sys
sys.modules['ragstack_common'] = MagicMock()

# Now import the Lambda function
import index


@pytest.fixture
def valid_event():
    """Valid input event for query_kb Lambda."""
    return {
        'query': 'What is the main topic of this document?',
        'max_results': 5
    }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = 'query_kb'
    context.memory_limit_in_mb = 1024
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:query_kb'
    context.aws_request_id = 'test-request-id'
    return context


@pytest.fixture
def mock_bedrock_response():
    """Mock Bedrock Agent Runtime retrieve response."""
    return {
        'retrievalResults': [
            {
                'content': {
                    'text': 'This document discusses cloud architecture.'
                },
                'location': {
                    's3Location': {
                        'uri': 's3://bucket/doc1.pdf'
                    }
                },
                'score': 0.95
            },
            {
                'content': {
                    'text': 'AWS services are covered in detail.'
                },
                'location': {
                    's3Location': {
                        'uri': 's3://bucket/doc2.pdf'
                    }
                },
                'score': 0.87
            }
        ]
    }


@patch.dict('os.environ', {'KNOWLEDGE_BASE_ID': 'test-kb-123'})
@patch('index.boto3.client')
def test_lambda_handler_success(mock_boto3_client, valid_event, lambda_context,
                                  mock_bedrock_response):
    """Test successful Knowledge Base query."""

    # Setup mock
    mock_bedrock_agent = Mock()
    mock_boto3_client.return_value = mock_bedrock_agent
    mock_bedrock_agent.retrieve.return_value = mock_bedrock_response

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify
    assert result['query'] == 'What is the main topic of this document?'
    assert len(result['results']) == 2
    assert result['results'][0]['content'] == 'This document discusses cloud architecture.'
    assert result['results'][0]['source'] == 's3://bucket/doc1.pdf'
    assert result['results'][0]['score'] == 0.95

    # Verify Bedrock agent was called correctly
    mock_bedrock_agent.retrieve.assert_called_once_with(
        knowledgeBaseId='test-kb-123',
        retrievalQuery={'text': 'What is the main topic of this document?'},
        retrievalConfiguration={
            'vectorSearchConfiguration': {
                'numberOfResults': 5
            }
        }
    )


@patch.dict('os.environ', {'KNOWLEDGE_BASE_ID': 'test-kb-123'})
@patch('index.boto3.client')
def test_lambda_handler_empty_query(mock_boto3_client, lambda_context):
    """Test handling of empty query."""

    event = {
        'query': '',
        'max_results': 5
    }

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify
    assert result['results'] == []
    assert result['message'] == 'No query provided'

    # Verify boto3.client was still called to create bedrock_agent (but retrieve not called)
    mock_boto3_client.assert_called_once_with('bedrock-agent-runtime')


@patch.dict('os.environ', {'KNOWLEDGE_BASE_ID': 'test-kb-123'})
@patch('index.boto3.client')
def test_lambda_handler_no_query_field(mock_boto3_client, lambda_context):
    """Test handling of missing query field."""

    event = {'max_results': 5}  # No query field

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify
    assert result['results'] == []
    assert result['message'] == 'No query provided'
    mock_bedrock_agent.retrieve.assert_not_called()


@patch.dict('os.environ', {'KNOWLEDGE_BASE_ID': 'test-kb-123'})
@patch('index.boto3.client')
def test_lambda_handler_custom_max_results(mock_boto3_client, lambda_context,
                                             mock_bedrock_response):
    """Test custom max_results parameter."""

    event = {
        'query': 'test query',
        'max_results': 10
    }

    mock_bedrock_agent.retrieve.return_value = mock_bedrock_response

    # Execute
    index.lambda_handler(event, lambda_context)

    # Verify numberOfResults was set to 10
    call_args = mock_bedrock_agent.retrieve.call_args
    assert call_args[1]['retrievalConfiguration']['vectorSearchConfiguration']['numberOfResults'] == 10


@patch.dict('os.environ', {'KNOWLEDGE_BASE_ID': 'test-kb-123'})
@patch('index.boto3.client')
def test_lambda_handler_default_max_results(mock_boto3_client, lambda_context,
                                              mock_bedrock_response):
    """Test default max_results when not specified."""

    event = {'query': 'test query'}  # No max_results

    mock_bedrock_agent.retrieve.return_value = mock_bedrock_response

    # Execute
    index.lambda_handler(event, lambda_context)

    # Verify default numberOfResults is 5
    call_args = mock_bedrock_agent.retrieve.call_args
    assert call_args[1]['retrievalConfiguration']['vectorSearchConfiguration']['numberOfResults'] == 5


@patch.dict('os.environ', {'KNOWLEDGE_BASE_ID': 'test-kb-123'})
@patch('index.boto3.client')
def test_lambda_handler_no_results(mock_boto3_client, valid_event, lambda_context):
    """Test handling when Knowledge Base returns no results."""

    # Mock empty response
    mock_bedrock_agent.retrieve.return_value = {'retrievalResults': []}

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify
    assert result['results'] == []
    assert result['query'] == valid_event['query']


@patch.dict('os.environ', {'KNOWLEDGE_BASE_ID': 'test-kb-123'})
@patch('index.boto3.client')
def test_lambda_handler_bedrock_error(mock_boto3_client, valid_event, lambda_context):
    """Test handling of Bedrock API error."""

    # Mock Bedrock error
    error = ClientError(
        {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
        'retrieve'
    )
    mock_bedrock_agent.retrieve.side_effect = error

    # Execute and expect exception
    with pytest.raises(Exception) as exc_info:
        index.lambda_handler(valid_event, lambda_context)

    assert 'Error querying Knowledge Base' in str(exc_info.value)


@patch.dict('os.environ', {'KNOWLEDGE_BASE_ID': 'test-kb-123'})
@patch('index.boto3.client')
def test_lambda_handler_missing_content_fields(mock_boto3_client, valid_event,
                                                 lambda_context):
    """Test handling of incomplete retrieval results."""

    # Mock response with missing fields
    incomplete_response = {
        'retrievalResults': [
            {
                'content': {},  # Missing 'text'
                'location': {},  # Missing 's3Location'
                'score': 0.5
            }
        ]
    }

    mock_bedrock_agent.retrieve.return_value = incomplete_response

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify graceful handling
    assert len(result['results']) == 1
    assert result['results'][0]['content'] == ''  # Default empty string
    assert result['results'][0]['source'] == ''  # Default empty string
    assert result['results'][0]['score'] == 0.5


@patch.dict('os.environ', {'KNOWLEDGE_BASE_ID': 'test-kb-123'})
@patch('index.boto3.client')
def test_lambda_handler_result_count_logged(mock_boto3_client, valid_event,
                                              lambda_context, mock_bedrock_response,
                                              caplog):
    """Test that result count is logged."""

    mock_bedrock_agent.retrieve.return_value = mock_bedrock_response

    # Execute
    with caplog.at_level('INFO'):
        index.lambda_handler(valid_event, lambda_context)

    # Verify logging
    assert 'Found 2 results' in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
