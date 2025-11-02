"""Unit tests for ConfigurationResolver Lambda"""

import importlib.util
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

# Use importlib to load the Lambda function with a unique module name
# This avoids sys.modules['index'] caching issues when multiple tests load different index.py files
lambda_dir = Path(__file__).parent.parent.parent / "src" / "lambda" / "configuration_resolver"
with patch("boto3.client"), patch("boto3.resource"):
    spec = importlib.util.spec_from_file_location("index_config_resolver", lambda_dir / "index.py")
    index = importlib.util.module_from_spec(spec)
    sys.modules["index_config_resolver"] = index
    spec.loader.exec_module(index)

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
        import importlib.util

        # Re-execute the module spec to reload it with mocked boto3
        lambda_dir = (
            Path(__file__).parent.parent.parent / "src" / "lambda" / "configuration_resolver"
        )
        spec = importlib.util.spec_from_file_location(
            "index_config_resolver_reloaded", lambda_dir / "index.py"
        )
        index_config_resolver_reloaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(index_config_resolver_reloaded)

        yield {
            "configuration_table": mock_configuration_table,
            "tracking_table": mock_tracking_table,
            "index": index_config_resolver_reloaded,
        }


@pytest.fixture
def sample_schema():
    """Sample Schema configuration with all new fields."""
    return {
        "Configuration": "Schema",
        "Schema": {
            "properties": {
                "ocr_backend": {
                    "type": "string",
                    "enum": ["textract", "bedrock"],
                    "order": 1
                },
                "bedrock_ocr_model_id": {
                    "type": "string",
                    "enum": [
                        "anthropic.claude-3-5-haiku-20241022-v1:0",
                        "anthropic.claude-3-5-sonnet-20241022-v2:0"
                    ],
                    "order": 2,
                    "dependsOn": {"field": "ocr_backend", "value": "bedrock"}
                },
                "chat_model_id": {
                    "type": "string",
                    "enum": [
                        "amazon.nova-pro-v1:0",
                        "amazon.nova-lite-v1:0",
                        "anthropic.claude-3-5-sonnet-20241022-v2:0"
                    ],
                    "order": 3
                }
            }
        },
    }


@pytest.fixture
def sample_default():
    """Sample Default configuration with all fields."""
    return {
        "Configuration": "Default",
        "ocr_backend": "textract",
        "bedrock_ocr_model_id": "anthropic.claude-3-5-haiku-20241022-v1:0",
        "chat_model_id": "amazon.nova-pro-v1:0"
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
    index_module = mock_dynamodb["index"]

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

    result = index_module.lambda_handler(event, {})

    assert "Schema" in result
    assert "Default" in result
    assert "Custom" in result


def test_lambda_handler_update_configuration(mock_dynamodb):
    """Test lambda_handler routes updateConfiguration correctly."""
    mock_table = mock_dynamodb["configuration_table"]
    index_module = mock_dynamodb["index"]

    event = {
        "info": {"fieldName": "updateConfiguration"},
        "arguments": {"customConfig": json.dumps({"ocr_backend": "bedrock"})},
    }

    result = index_module.lambda_handler(event, {})

    assert result is True
    mock_table.put_item.assert_called_once()


def test_lambda_handler_unsupported_operation(mock_dynamodb):
    """Test lambda_handler raises error for unsupported operation."""
    index_module = mock_dynamodb["index"]
    event = {"info": {"fieldName": "unknownOperation"}, "arguments": {}}

    with pytest.raises(ValueError, match="Unsupported operation"):
        index_module.lambda_handler(event, {})


# Test: handle_get_configuration


@patch("index_config_resolver.get_configuration_item")
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


@patch("index_config_resolver.get_configuration_item")
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


# Test: handle_get_configuration with new configuration fields


@patch("index_config_resolver.get_configuration_item")
def test_get_configuration_includes_new_fields(mock_get_item, sample_schema, sample_default):
    """Test that getConfiguration returns schema with new OCR and chat fields."""

    def get_item_side_effect(config_type):
        if config_type == "Schema":
            return sample_schema
        if config_type == "Default":
            return sample_default
        if config_type == "Custom":
            return {"Configuration": "Custom"}
        return None

    mock_get_item.side_effect = get_item_side_effect

    result = index.handle_get_configuration()
    schema = json.loads(result["Schema"])

    # Assert new fields exist in schema
    assert "ocr_backend" in schema["properties"]
    assert "bedrock_ocr_model_id" in schema["properties"]
    assert "chat_model_id" in schema["properties"]

    # Assert ocr_backend structure
    ocr_field = schema["properties"]["ocr_backend"]
    assert ocr_field["type"] == "string"
    assert set(ocr_field["enum"]) == {"textract", "bedrock"}
    assert ocr_field["order"] == 1

    # Assert bedrock_ocr_model_id has dependsOn
    bedrock_model_field = schema["properties"]["bedrock_ocr_model_id"]
    assert "dependsOn" in bedrock_model_field
    assert bedrock_model_field["dependsOn"]["field"] == "ocr_backend"
    assert bedrock_model_field["dependsOn"]["value"] == "bedrock"
    assert bedrock_model_field["order"] == 2

    # Assert chat_model_id structure
    chat_field = schema["properties"]["chat_model_id"]
    assert chat_field["type"] == "string"
    assert len(chat_field["enum"]) >= 3  # Should have multiple model options
    assert chat_field["order"] == 3


@patch("index_config_resolver.get_configuration_item")
def test_get_configuration_includes_default_values(mock_get_item, sample_schema, sample_default):
    """Test that default configuration includes new fields."""

    def get_item_side_effect(config_type):
        if config_type == "Schema":
            return sample_schema
        if config_type == "Default":
            return sample_default
        if config_type == "Custom":
            return {"Configuration": "Custom"}
        return None

    mock_get_item.side_effect = get_item_side_effect

    result = index.handle_get_configuration()
    defaults = json.loads(result["Default"])

    # Assert defaults exist
    assert defaults["ocr_backend"] == "textract"
    assert defaults["bedrock_ocr_model_id"] == "anthropic.claude-3-5-haiku-20241022-v1:0"
    assert defaults["chat_model_id"] == "amazon.nova-pro-v1:0"

    # Assert existing defaults preserved
    assert "text_embed_model_id" in defaults
    assert "image_embed_model_id" in defaults


@patch("index_config_resolver.get_configuration_item")
def test_field_ordering(mock_get_item, sample_schema, sample_default):
    """Test that fields have correct order property for UI sorting."""

    def get_item_side_effect(config_type):
        if config_type == "Schema":
            return sample_schema
        return None

    mock_get_item.side_effect = get_item_side_effect

    result = index.handle_get_configuration()
    schema = json.loads(result["Schema"])

    # Get all orders
    ocr_order = schema["properties"]["ocr_backend"]["order"]
    bedrock_order = schema["properties"]["bedrock_ocr_model_id"]["order"]
    chat_order = schema["properties"]["chat_model_id"]["order"]

    # Assert logical ordering (OCR fields first, then chat)
    assert ocr_order == 1
    assert bedrock_order == 2
    assert chat_order == 3


# Test: handle_update_configuration


@patch("index_config_resolver.configuration_table")
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


@patch("index_config_resolver.configuration_table")
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
