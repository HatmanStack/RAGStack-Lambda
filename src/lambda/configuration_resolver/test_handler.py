"""Unit tests for configuration_resolver Lambda function."""

import json
import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# Mock boto3 before importing the module
sys.modules["boto3"] = MagicMock()


# Create a proper ClientError exception class for botocore mock
class MockClientError(Exception):
    """Mock ClientError for testing."""

    def __init__(self, error_response=None, operation_name=None):
        self.response = error_response or {}
        self.operation_name = operation_name
        super().__init__(str(error_response))


mock_botocore = MagicMock()
mock_botocore_exceptions = MagicMock()
mock_botocore_exceptions.ClientError = MockClientError
sys.modules["botocore"] = mock_botocore
sys.modules["botocore.exceptions"] = mock_botocore_exceptions

# Import after mocking
from index import (  # noqa: E402
    get_configuration_item,
    handle_get_configuration,
    handle_update_configuration,
    lambda_handler,
    remove_partition_key,
)


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"CONFIGURATION_TABLE_NAME": "test-table"}):
        yield


@pytest.fixture
def mock_table():
    """Mock DynamoDB table."""
    mock = MagicMock()
    with patch("index.configuration_table", mock):
        yield mock


def test_lambda_handler_get_configuration(mock_env, mock_table):
    """Test lambda_handler routing to getConfiguration."""
    # Mock table responses for Schema, Default, Custom
    mock_table.get_item.side_effect = [
        {"Item": {"Schema": {"type": "object", "properties": {}}}},
        {"Item": {"field1": "value1", "Configuration": "Default"}},
        {"Item": {"field2": "value2", "Configuration": "Custom"}},
    ]

    event = {"info": {"fieldName": "getConfiguration"}, "arguments": {}}

    result = lambda_handler(event, None)

    assert "Schema" in result
    assert "Default" in result
    assert "Custom" in result


def test_lambda_handler_update_configuration(mock_env, mock_table):
    """Test lambda_handler routing to updateConfiguration."""
    # Schema mock - implementation looks for Schema.properties
    mock_table.get_item.return_value = {"Item": {"Schema": {"properties": {"test_field": {}}}}}

    event = {
        "info": {"fieldName": "updateConfiguration"},
        "arguments": {"customConfig": json.dumps({"test_field": "test_value"})},
    }

    result = lambda_handler(event, None)

    assert result is True
    # Implementation uses update_item, not put_item
    assert mock_table.update_item.called


def test_lambda_handler_unsupported_operation(mock_env):
    """Test lambda_handler with unsupported operation."""
    event = {"info": {"fieldName": "unsupportedOperation"}, "arguments": {}}

    with pytest.raises(ValueError, match="Unsupported operation"):
        lambda_handler(event, None)


def test_handle_get_configuration(mock_env, mock_table):
    """Test handle_get_configuration returns all configs."""
    mock_table.get_item.side_effect = [
        {"Item": {"Schema": {"type": "object", "properties": {}}}},
        {"Item": {"field1": Decimal("100"), "field2": "value2", "Configuration": "Default"}},
        {"Item": {"field3": "value3", "Configuration": "Custom"}},
    ]

    result = handle_get_configuration()

    assert "Schema" in result
    assert "Default" in result
    assert "Custom" in result
    # Check Decimal conversion
    assert result["Default"]["field1"] == 100  # Decimal converted to int
    assert result["Default"]["field2"] == "value2"
    assert "Configuration" not in result["Default"]  # Partition key removed


def test_handle_get_configuration_with_decimals(mock_env, mock_table):
    """Test Decimal conversion in nested structures."""
    mock_table.get_item.side_effect = [
        {"Item": {"Schema": {}}},
        {
            "Item": {
                "Configuration": "Default",
                "nested": {
                    "decimal_value": Decimal("3.14"),
                    "list": [Decimal("1"), Decimal("2.5")],
                },
            }
        },
        {"Item": {}},
    ]

    result = handle_get_configuration()

    assert result["Default"]["nested"]["decimal_value"] == 3.14
    assert result["Default"]["nested"]["list"][0] == 1
    assert result["Default"]["nested"]["list"][1] == 2.5


def test_handle_update_configuration_valid(mock_env, mock_table):
    """Test update with valid configuration."""
    # Schema structure matches what implementation expects
    mock_table.get_item.return_value = {
        "Item": {"Schema": {"properties": {"test_field": {}, "another_field": {}}}}
    }

    custom_config = json.dumps({"test_field": "new_value"})
    result = handle_update_configuration(custom_config)

    assert result is True
    assert mock_table.update_item.called

    # Verify update_item was called with correct key
    call_args = mock_table.update_item.call_args
    assert call_args.kwargs["Key"] == {"Configuration": "Custom"}
    # Verify the update expression contains our field
    assert "test_field" in call_args.kwargs["UpdateExpression"]


def test_handle_update_configuration_dict_input(mock_env, mock_table):
    """Test update with dict input instead of JSON string."""
    mock_table.get_item.return_value = {"Item": {"Schema": {"properties": {"test_field": {}}}}}

    custom_config = {"test_field": "new_value"}  # Dict, not string
    result = handle_update_configuration(custom_config)

    assert result is True


def test_handle_update_configuration_invalid_json(mock_env, mock_table):
    """Test update with invalid JSON string."""
    with pytest.raises(ValueError, match="Invalid configuration format"):
        handle_update_configuration("invalid json {")


def test_handle_update_configuration_invalid_keys(mock_env, mock_table):
    """Test update with invalid configuration keys."""
    mock_table.get_item.return_value = {"Item": {"Schema": {"properties": {"valid_field": {}}}}}

    custom_config = json.dumps({"invalid_field": "value"})

    with pytest.raises(ValueError, match="Invalid configuration keys"):
        handle_update_configuration(custom_config)


def test_handle_update_configuration_prevents_partition_key_override(mock_env, mock_table):
    """Test that Configuration key cannot be overridden."""
    mock_table.get_item.return_value = {"Item": {"Schema": {"properties": {"test_field": {}}}}}

    custom_config = json.dumps(
        {
            "Configuration": "Malicious",  # Attempt to override partition key
            "test_field": "value",
        }
    )

    handle_update_configuration(custom_config)

    # Verify update_item was called with Custom partition key
    call_args = mock_table.update_item.call_args
    assert call_args.kwargs["Key"] == {"Configuration": "Custom"}
    # Configuration should not be in the update expression (stripped)
    assert "Configuration" not in call_args.kwargs.get("ExpressionAttributeNames", {}).values()


def test_get_configuration_item_success(mock_env, mock_table):
    """Test successful retrieval of config item."""
    expected_item = {"Configuration": "Schema", "field": "value"}
    mock_table.get_item.return_value = {"Item": expected_item}

    result = get_configuration_item("Schema")

    assert result == expected_item
    mock_table.get_item.assert_called_once_with(Key={"Configuration": "Schema"})


def test_get_configuration_item_not_found(mock_env, mock_table):
    """Test retrieval when item doesn't exist."""
    mock_table.get_item.return_value = {}

    result = get_configuration_item("NonExistent")

    assert result is None


def test_remove_partition_key():
    """Test partition key removal."""
    item = {"Configuration": "Default", "field1": "value1", "field2": "value2"}

    result = remove_partition_key(item)

    assert "Configuration" not in result
    assert result["field1"] == "value1"
    assert result["field2"] == "value2"


def test_remove_partition_key_empty_item():
    """Test partition key removal with empty item."""
    result = remove_partition_key(None)
    assert result == {}

    result = remove_partition_key({})
    assert result == {}


def test_lambda_handler_missing_env_var():
    """Test lambda_handler fails gracefully without env vars."""
    import index

    # Store original values for cleanup
    original_dynamodb = index.dynamodb
    original_table = index.configuration_table

    index.dynamodb = None
    index.configuration_table = None

    try:
        with patch.dict(os.environ, {}, clear=True):
            event = {"info": {"fieldName": "getConfiguration"}, "arguments": {}}

            with pytest.raises(ValueError, match="Missing required environment variable"):
                lambda_handler(event, None)
    finally:
        # Restore original values
        index.dynamodb = original_dynamodb
        index.configuration_table = original_table
