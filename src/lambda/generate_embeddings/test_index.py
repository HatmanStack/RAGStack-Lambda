"""
Unit tests for generate_embeddings Lambda function.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

# Mock the ragstack_common imports before importing index
import sys
from unittest.mock import MagicMock

mock_bedrock = MagicMock()
mock_storage = MagicMock()
mock_models = MagicMock()

sys.modules['ragstack_common'] = MagicMock()
sys.modules['ragstack_common.bedrock'] = mock_bedrock
sys.modules['ragstack_common.storage'] = mock_storage
sys.modules['ragstack_common.models'] = mock_models

mock_models.Status = MagicMock()
mock_models.Status.EMBEDDING_COMPLETE = MagicMock(value='embedding_complete')
mock_models.Status.FAILED = MagicMock(value='failed')

# Now import the Lambda function
import index


@pytest.fixture
def valid_event():
    """Valid input event for generate_embeddings Lambda."""
    return {
        'document_id': 'test-doc-123',
        'output_s3_uri': 's3://output-bucket/test-doc-123/text.txt',
        'pages': [
            {
                'page_number': 1,
                'image_s3_uri': 's3://output-bucket/test-doc-123/page_1.jpg'
            },
            {
                'page_number': 2,
                'image_s3_uri': 's3://output-bucket/test-doc-123/page_2.jpg'
            }
        ],
        'vector_bucket': 'test-vector-bucket'
    }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = 'generate_embeddings'
    context.memory_limit_in_mb = 2048
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:generate_embeddings'
    context.aws_request_id = 'test-request-id'
    return context


@patch.dict('os.environ', {
    'TRACKING_TABLE': 'test-tracking-table',
    'TEXT_EMBED_MODEL': 'amazon.titan-embed-text-v2:0',
    'IMAGE_EMBED_MODEL': 'amazon.titan-embed-image-v1'
})
@patch('index.write_s3_json')
@patch('index.read_s3_binary')
@patch('index.read_s3_text')
@patch('index.update_item')
@patch('index.BedrockClient')
def test_lambda_handler_success(mock_bedrock_class, mock_update_item, mock_read_text,
                                  mock_read_binary, mock_write_json,
                                  valid_event, lambda_context):
    """Test successful embedding generation."""

    # Setup mocks
    mock_bedrock_instance = Mock()
    mock_bedrock_class.return_value = mock_bedrock_instance

    # Mock text content
    mock_read_text.return_value = "This is test document content."

    # Mock text embedding
    text_embedding = [0.1, 0.2, 0.3] * 100  # 300-dim vector
    mock_bedrock_instance.generate_embedding.return_value = text_embedding

    # Mock image content
    mock_read_binary.return_value = b'fake_image_data'

    # Mock image embeddings
    image_embedding = [0.4, 0.5, 0.6] * 100
    mock_bedrock_instance.generate_image_embedding.return_value = image_embedding

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify
    assert result['document_id'] == 'test-doc-123'
    assert result['status'] == 'embedding_complete'
    assert 'text_embedding_uri' in result
    assert len(result['image_embeddings']) == 2

    # Verify text embedding was generated
    mock_bedrock_instance.generate_embedding.assert_called_once()

    # Verify image embeddings were generated (2 pages)
    assert mock_bedrock_instance.generate_image_embedding.call_count == 2

    # Verify embeddings were saved to S3 (1 text + 2 images = 3)
    assert mock_write_json.call_count == 3

    # Verify DynamoDB was updated
    mock_update_item.assert_called_once()


@patch.dict('os.environ', {
    'TRACKING_TABLE': 'test-tracking-table',
    'TEXT_EMBED_MODEL': 'amazon.titan-embed-text-v2:0'
})
@patch('index.write_s3_json')
@patch('index.read_s3_text')
@patch('index.update_item')
@patch('index.BedrockClient')
def test_lambda_handler_text_only(mock_bedrock_class, mock_update_item, mock_read_text,
                                    mock_write_json, lambda_context):
    """Test embedding generation with text only (no images)."""

    event = {
        'document_id': 'test-doc-456',
        'output_s3_uri': 's3://output-bucket/test-doc-456/text.txt',
        'pages': [],  # No pages with images
        'vector_bucket': 'test-vector-bucket'
    }

    # Setup mocks
    mock_bedrock_instance = Mock()
    mock_bedrock_class.return_value = mock_bedrock_instance
    mock_read_text.return_value = "Text content."
    mock_bedrock_instance.generate_embedding.return_value = [0.1] * 100

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify
    assert result['document_id'] == 'test-doc-456'
    assert result['status'] == 'embedding_complete'
    assert len(result['image_embeddings']) == 0

    # Only text embedding generated
    mock_bedrock_instance.generate_embedding.assert_called_once()
    mock_bedrock_instance.generate_image_embedding.assert_not_called()

    # Only 1 S3 write (text embedding only)
    assert mock_write_json.call_count == 1


@patch.dict('os.environ', {
    'TRACKING_TABLE': 'test-tracking-table',
    'TEXT_EMBED_MODEL': 'amazon.titan-embed-text-v2:0'
})
@patch('index.read_s3_text')
@patch('index.update_item')
@patch('index.BedrockClient')
def test_lambda_handler_text_truncation(mock_bedrock_class, mock_update_item,
                                         mock_read_text, lambda_context):
    """Test that very long text is truncated."""

    event = {
        'document_id': 'test-doc-789',
        'output_s3_uri': 's3://output-bucket/test.txt',
        'pages': [],
        'vector_bucket': 'test-vector-bucket'
    }

    # Setup mocks with very long text (>30k chars)
    mock_bedrock_instance = Mock()
    mock_bedrock_class.return_value = mock_bedrock_instance
    long_text = 'x' * 50000  # 50k characters
    mock_read_text.return_value = long_text
    mock_bedrock_instance.generate_embedding.return_value = [0.1] * 100

    # Execute
    index.lambda_handler(event, lambda_context)

    # Verify text was truncated to 30000 chars
    call_args = mock_bedrock_instance.generate_embedding.call_args
    truncated_text = call_args[1]['text']
    assert len(truncated_text) == 30000


@patch.dict('os.environ', {
    'TRACKING_TABLE': 'test-tracking-table',
    'TEXT_EMBED_MODEL': 'amazon.titan-embed-text-v2:0'
})
@patch('index.read_s3_text')
@patch('index.update_item')
@patch('index.BedrockClient')
def test_lambda_handler_bedrock_failure(mock_bedrock_class, mock_update_item,
                                         mock_read_text, valid_event, lambda_context):
    """Test handling of Bedrock API failure."""

    # Setup mocks - Bedrock fails
    mock_bedrock_instance = Mock()
    mock_bedrock_class.return_value = mock_bedrock_instance
    mock_read_text.return_value = "Test content"
    mock_bedrock_instance.generate_embedding.side_effect = Exception("Bedrock API error")

    # Execute and expect exception
    with pytest.raises(Exception) as exc_info:
        index.lambda_handler(valid_event, lambda_context)

    assert 'Bedrock API error' in str(exc_info.value)

    # Verify failed status was recorded
    mock_update_item.assert_called()
    update_args = mock_update_item.call_args[0][2]
    assert update_args['status'] == 'failed'
    assert 'error_message' in update_args


@patch.dict('os.environ', {
    'TRACKING_TABLE': 'test-tracking-table',
    'TEXT_EMBED_MODEL': 'amazon.titan-embed-text-v2:0',
    'IMAGE_EMBED_MODEL': 'amazon.titan-embed-image-v1'
})
@patch('index.write_s3_json')
@patch('index.read_s3_binary')
@patch('index.read_s3_text')
@patch('index.update_item')
@patch('index.BedrockClient')
def test_lambda_handler_skip_pages_without_images(mock_bedrock_class, mock_update_item,
                                                    mock_read_text, mock_read_binary,
                                                    mock_write_json, lambda_context):
    """Test that pages without image_s3_uri are skipped."""

    event = {
        'document_id': 'test-doc-999',
        'output_s3_uri': 's3://output-bucket/text.txt',
        'pages': [
            {'page_number': 1, 'image_s3_uri': 's3://bucket/page1.jpg'},
            {'page_number': 2},  # No image_s3_uri - should be skipped
            {'page_number': 3, 'image_s3_uri': None},  # Explicit None - should be skipped
        ],
        'vector_bucket': 'test-vector-bucket'
    }

    # Setup mocks
    mock_bedrock_instance = Mock()
    mock_bedrock_class.return_value = mock_bedrock_instance
    mock_read_text.return_value = "Text content"
    mock_bedrock_instance.generate_embedding.return_value = [0.1] * 100
    mock_read_binary.return_value = b'image_data'
    mock_bedrock_instance.generate_image_embedding.return_value = [0.2] * 100

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify only 1 image embedding was generated (page 1 only)
    assert mock_bedrock_instance.generate_image_embedding.call_count == 1
    assert len(result['image_embeddings']) == 1
    assert result['image_embeddings'][0]['page_number'] == 1


@patch.dict('os.environ', {
    'TRACKING_TABLE': 'test-tracking-table',
    'TEXT_EMBED_MODEL': 'amazon.titan-embed-text-v2:0'
})
def test_lambda_handler_missing_required_fields(lambda_context):
    """Test handling of missing required event fields."""

    invalid_event = {
        'document_id': 'test-doc-123'
        # Missing output_s3_uri and vector_bucket
    }

    # Execute and expect exception
    with pytest.raises(KeyError):
        index.lambda_handler(invalid_event, lambda_context)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
