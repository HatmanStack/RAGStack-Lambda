"""Unit tests for ConfigurationResolver Lambda"""

import pytest
import json
import os
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

# Import the handler
import sys
sys.path.insert(0, os.path.dirname(__file__))
from index import (
    lambda_handler,
    handle_get_configuration,
    handle_update_configuration,
    handle_get_document_count,
    get_configuration_item,
    remove_partition_key
)


# Fixtures

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Set required environment variables."""
    os.environ['CONFIGURATION_TABLE_NAME'] = 'test-config-table'
    os.environ['TRACKING_TABLE'] = 'test-tracking-table'
    os.environ['LOG_LEVEL'] = 'INFO'


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
    with patch('boto3.resource') as mock_resource:
        mock_dynamodb_resource = MagicMock()

        # Table() returns different mocks based on table name
        def table_side_effect(table_name):
            if 'config' in table_name.lower():
                return mock_configuration_table
            else:
                return mock_tracking_table

        mock_dynamodb_resource.Table.side_effect = table_side_effect
        mock_resource.return_value = mock_dynamodb_resource

        # Reload the module to pick up mocked boto3
        import index
        import importlib
        importlib.reload(index)

        yield {
            'configuration_table': mock_configuration_table,
            'tracking_table': mock_tracking_table
        }


@pytest.fixture
def sample_schema():
    """Sample Schema configuration."""
    return {
        'Configuration': 'Schema',
        'Schema': {
            'properties': {
                'ocr_backend': {
                    'type': 'string',
                    'enum': ['textract', 'bedrock']
                }
            }
        }
    }


@pytest.fixture
def sample_default():
    """Sample Default configuration."""
    return {
        'Configuration': 'Default',
        'ocr_backend': 'textract',
        'text_embed_model_id': 'amazon.titan-embed-text-v2:0'
    }


@pytest.fixture
def sample_custom():
    """Sample Custom configuration."""
    return {
        'Configuration': 'Custom',
        'ocr_backend': 'bedrock'
    }


# Test: lambda_handler routing

def test_lambda_handler_get_configuration(mock_dynamodb, sample_schema, sample_default, sample_custom):
    """Test lambda_handler routes getConfiguration correctly."""
    mock_table = mock_dynamodb['configuration_table']

    def get_item_side_effect(Key):
        config_type = Key['Configuration']
        if config_type == 'Schema':
            return {'Item': sample_schema}
        elif config_type == 'Default':
            return {'Item': sample_default}
        elif config_type == 'Custom':
            return {'Item': sample_custom}
        return {}

    mock_table.get_item.side_effect = get_item_side_effect

    event = {
        'info': {'fieldName': 'getConfiguration'},
        'arguments': {}
    }

    result = lambda_handler(event, {})

    assert 'Schema' in result
    assert 'Default' in result
    assert 'Custom' in result


def test_lambda_handler_update_configuration(mock_dynamodb):
    """Test lambda_handler routes updateConfiguration correctly."""
    mock_table = mock_dynamodb['configuration_table']

    event = {
        'info': {'fieldName': 'updateConfiguration'},
        'arguments': {
            'customConfig': json.dumps({'ocr_backend': 'bedrock'})
        }
    }

    result = lambda_handler(event, {})

    assert result is True
    mock_table.put_item.assert_called_once()


def test_lambda_handler_unsupported_operation(mock_dynamodb):
    """Test lambda_handler raises error for unsupported operation."""
    event = {
        'info': {'fieldName': 'unknownOperation'},
        'arguments': {}
    }

    with pytest.raises(ValueError, match="Unsupported operation"):
        lambda_handler(event, {})


# Test: handle_get_configuration

@patch('index.get_configuration_item')
def test_handle_get_configuration_success(mock_get_item, sample_schema, sample_default, sample_custom):
    """Test handle_get_configuration returns all configs."""
    def get_item_side_effect(config_type):
        if config_type == 'Schema':
            return sample_schema
        elif config_type == 'Default':
            return sample_default
        elif config_type == 'Custom':
            return sample_custom

    mock_get_item.side_effect = get_item_side_effect

    result = handle_get_configuration()

    assert 'Schema' in result
    assert 'Default' in result
    assert 'Custom' in result

    # Results should be JSON strings
    assert isinstance(result['Schema'], str)
    assert isinstance(result['Default'], str)
    assert isinstance(result['Custom'], str)

    # Verify content
    schema = json.loads(result['Schema'])
    assert 'properties' in schema


@patch('index.get_configuration_item')
def test_handle_get_configuration_empty_custom(mock_get_item, sample_schema, sample_default):
    """Test handle_get_configuration when Custom config is empty."""
    def get_item_side_effect(config_type):
        if config_type == 'Schema':
            return sample_schema
        elif config_type == 'Default':
            return sample_default
        elif config_type == 'Custom':
            return None

    mock_get_item.side_effect = get_item_side_effect

    result = handle_get_configuration()

    custom_config = json.loads(result['Custom'])
    assert custom_config == {}


# Test: handle_update_configuration

@patch('index.configuration_table')
def test_handle_update_configuration_with_json_string(mock_table):
    """Test updating configuration with JSON string."""
    custom_config = json.dumps({'ocr_backend': 'bedrock', 'text_embed_model_id': 'cohere.embed-english-v3'})

    result = handle_update_configuration(custom_config)

    assert result is True
    mock_table.put_item.assert_called_once()
    call_args = mock_table.put_item.call_args[1]
    assert call_args['Item']['Configuration'] == 'Custom'
    assert call_args['Item']['ocr_backend'] == 'bedrock'


@patch('index.configuration_table')
def test_handle_update_configuration_with_dict(mock_table):
    """Test updating configuration with dictionary."""
    custom_config = {'ocr_backend': 'bedrock'}

    result = handle_update_configuration(custom_config)

    assert result is True
    mock_table.put_item.assert_called_once()


def test_handle_update_configuration_invalid_json():
    """Test updating configuration with invalid JSON."""
    with pytest.raises(ValueError, match="Invalid configuration format"):
        handle_update_configuration("invalid json {")


# Test: handle_get_document_count

@patch('index.tracking_table')
def test_handle_get_document_count_success(mock_table):
    """Test getting document count."""
    mock_table.scan.return_value = {'Count': 42}

    result = handle_get_document_count()

    assert result == 42
    mock_table.scan.assert_called_once()


@patch('index.tracking_table')
def test_handle_get_document_count_zero(mock_table):
    """Test getting document count when no documents exist."""
    mock_table.scan.return_value = {'Count': 0}

    result = handle_get_document_count()

    assert result == 0


@patch('index.tracking_table')
def test_handle_get_document_count_dynamodb_error(mock_table):
    """Test getting document count handles DynamoDB errors gracefully."""
    mock_table.scan.side_effect = ClientError(
        {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}},
        'Scan'
    )

    result = handle_get_document_count()

    # Should return 0 instead of raising
    assert result == 0


# Test: remove_partition_key

def test_remove_partition_key():
    """Test partition key removal."""
    item = {'Configuration': 'Default', 'key1': 'value1', 'key2': 'value2'}

    result = remove_partition_key(item)

    assert 'Configuration' not in result
    assert result['key1'] == 'value1'
    assert result['key2'] == 'value2'


def test_remove_partition_key_none():
    """Test partition key removal with None."""
    result = remove_partition_key(None)
    assert result == {}
