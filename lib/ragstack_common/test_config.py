"""Unit tests for ConfigurationManager

Tests the ConfigurationManager class using mocked boto3 DynamoDB resource.
No actual AWS calls are made.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Import the class we're testing
from ragstack_common.config import ConfigurationManager

# Fixtures


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table resource."""
    mock_table = MagicMock()
    mock_table.get_item = MagicMock()
    mock_table.put_item = MagicMock()
    return mock_table


@pytest.fixture
def mock_dynamodb_resource(mock_dynamodb_table):
    """Create a mock boto3 DynamoDB resource."""
    mock_resource = MagicMock()
    mock_resource.Table.return_value = mock_dynamodb_table
    return mock_resource


@pytest.fixture
def config_manager(mock_dynamodb_resource):
    """Create a ConfigurationManager with mocked DynamoDB."""
    with patch("boto3.resource", return_value=mock_dynamodb_resource):
        return ConfigurationManager(table_name="test-configuration-table")


@pytest.fixture
def sample_schema():
    """Sample Schema configuration."""
    return {
        "Configuration": "Schema",
        "Schema": {
            "properties": {
                "ocr_backend": {
                    "type": "string",
                    "enum": ["textract", "bedrock"],
                    "description": "OCR backend",
                },
                "text_embed_model_id": {
                    "type": "string",
                    "enum": ["amazon.titan-embed-text-v2:0"],
                    "description": "Text embedding model",
                },
            }
        },
    }


@pytest.fixture
def sample_default_config():
    """Sample Default configuration."""
    return {
        "Configuration": "Default",
        "ocr_backend": "textract",
        "bedrock_ocr_model_id": "anthropic.claude-3-5-haiku-20241022-v1:0",
        "text_embed_model_id": "amazon.titan-embed-text-v2:0",
        "image_embed_model_id": "amazon.titan-embed-image-v1",
        "chat_model_id": "amazon.nova-pro-v1:0",
    }


@pytest.fixture
def sample_custom_config():
    """Sample Custom configuration (overrides some defaults)."""
    return {
        "Configuration": "Custom",
        "ocr_backend": "bedrock",
        "text_embed_model_id": "cohere.embed-english-v3",
    }


# Test: Initialization


def test_init_with_table_name():
    """Test ConfigurationManager initialization with explicit table name."""
    with patch("boto3.resource") as mock_boto3:
        manager = ConfigurationManager(table_name="my-table")
        assert manager.table_name == "my-table"
        mock_boto3.assert_called_once_with("dynamodb")


def test_init_with_env_var():
    """Test ConfigurationManager initialization from environment variable."""
    os.environ["CONFIGURATION_TABLE_NAME"] = "env-table"
    try:
        with patch("boto3.resource"):
            manager = ConfigurationManager()
            assert manager.table_name == "env-table"
    finally:
        del os.environ["CONFIGURATION_TABLE_NAME"]


def test_init_without_table_name():
    """Test ConfigurationManager raises ValueError if no table name provided."""
    # Ensure env var is not set
    os.environ.pop("CONFIGURATION_TABLE_NAME", None)

    with pytest.raises(ValueError, match="Configuration table name not provided"):
        ConfigurationManager()


# Test: get_configuration_item


def test_get_configuration_item_success(config_manager, sample_default_config):
    """Test retrieving an existing configuration item."""
    config_manager.table.get_item.return_value = {"Item": sample_default_config}

    result = config_manager.get_configuration_item("Default")

    assert result == sample_default_config
    config_manager.table.get_item.assert_called_once_with(Key={"Configuration": "Default"})


def test_get_configuration_item_not_found(config_manager):
    """Test retrieving a non-existent configuration item."""
    config_manager.table.get_item.return_value = {}

    result = config_manager.get_configuration_item("NonExistent")

    assert result is None


def test_get_configuration_item_dynamodb_error(config_manager):
    """Test DynamoDB ClientError is propagated."""
    config_manager.table.get_item.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}}, "GetItem"
    )

    with pytest.raises(ClientError):
        config_manager.get_configuration_item("Default")


# Test: get_effective_config


def test_get_effective_config_with_custom_override(
    config_manager, sample_default_config, sample_custom_config
):
    """Test effective config merges Custom → Default correctly."""

    def mock_get_item(Key):
        if Key["Configuration"] == "Default":
            return {"Item": sample_default_config}
        if Key["Configuration"] == "Custom":
            return {"Item": sample_custom_config}
        return {}

    config_manager.table.get_item.side_effect = mock_get_item

    result = config_manager.get_effective_config()

    # Custom should override Default
    assert result["ocr_backend"] == "bedrock"  # From Custom
    assert result["text_embed_model_id"] == "cohere.embed-english-v3"  # From Custom
    assert result["image_embed_model_id"] == "amazon.titan-embed-image-v1"  # From Default
    assert result["chat_model_id"] == "amazon.nova-pro-v1:0"  # From Default

    # Configuration key should be removed
    assert "Configuration" not in result


def test_get_effective_config_no_custom(config_manager, sample_default_config):
    """Test effective config when no Custom config exists."""

    def mock_get_item(Key):
        if Key["Configuration"] == "Default":
            return {"Item": sample_default_config}
        return {}

    config_manager.table.get_item.side_effect = mock_get_item

    result = config_manager.get_effective_config()

    # Should return Default values only
    assert result["ocr_backend"] == "textract"
    assert "Configuration" not in result


def test_get_effective_config_empty_table(config_manager):
    """Test effective config when table is empty."""
    config_manager.table.get_item.return_value = {}

    result = config_manager.get_effective_config()

    # Should return empty dict
    assert result == {}


# Test: get_parameter


def test_get_parameter_exists(config_manager, sample_default_config):
    """Test getting a parameter that exists in config."""
    config_manager.table.get_item.return_value = {"Item": sample_default_config}

    result = config_manager.get_parameter("ocr_backend")

    assert result == "textract"


def test_get_parameter_with_default(config_manager):
    """Test getting a parameter with fallback default value."""
    config_manager.table.get_item.return_value = {}

    result = config_manager.get_parameter("non_existent_param", default="fallback_value")

    assert result == "fallback_value"


def test_get_parameter_none_default(config_manager):
    """Test getting a non-existent parameter returns None by default."""
    config_manager.table.get_item.return_value = {}

    result = config_manager.get_parameter("non_existent_param")

    assert result is None


# Test: update_custom_config


def test_update_custom_config_success(config_manager):
    """Test updating custom configuration."""
    new_config = {"ocr_backend": "bedrock", "text_embed_model_id": "cohere.embed-multilingual-v3"}

    config_manager.update_custom_config(new_config)

    config_manager.table.put_item.assert_called_once_with(
        Item={
            "Configuration": "Custom",
            "ocr_backend": "bedrock",
            "text_embed_model_id": "cohere.embed-multilingual-v3",
        }
    )


def test_update_custom_config_dynamodb_error(config_manager):
    """Test DynamoDB error during update is propagated."""
    config_manager.table.put_item.side_effect = ClientError(
        {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Throttled"}},
        "PutItem",
    )

    with pytest.raises(ClientError):
        config_manager.update_custom_config({"ocr_backend": "bedrock"})


# Test: get_schema


def test_get_schema_success(config_manager, sample_schema):
    """Test retrieving Schema configuration."""
    config_manager.table.get_item.return_value = {"Item": sample_schema}

    result = config_manager.get_schema()

    assert "properties" in result
    assert "ocr_backend" in result["properties"]


def test_get_schema_not_found(config_manager):
    """Test retrieving Schema when it doesn't exist."""
    config_manager.table.get_item.return_value = {}

    result = config_manager.get_schema()

    assert result == {}


# Test: _remove_partition_key


def test_remove_partition_key():
    """Test partition key removal helper method."""
    item = {"Configuration": "Default", "ocr_backend": "textract", "model_id": "some-model"}

    result = ConfigurationManager._remove_partition_key(item)

    assert "Configuration" not in result
    assert result["ocr_backend"] == "textract"
    assert result["model_id"] == "some-model"


def test_remove_partition_key_none():
    """Test partition key removal with None input."""
    result = ConfigurationManager._remove_partition_key(None)
    assert result == {}


def test_remove_partition_key_empty_dict():
    """Test partition key removal with empty dict."""
    result = ConfigurationManager._remove_partition_key({})
    assert result == {}


# Test: New configuration fields (Phase 1)


def test_get_effective_config_with_new_fields(config_manager):
    """Test that new OCR and chat fields are correctly merged."""
    default_config = {
        "Configuration": "Default",
        "ocr_backend": "textract",
        "bedrock_ocr_model_id": "anthropic.claude-3-5-haiku-20241022-v1:0",
        "chat_model_id": "amazon.nova-pro-v1:0",
        "text_embed_model_id": "amazon.titan-embed-text-v2:0",
        "image_embed_model_id": "amazon.titan-embed-image-v1"
    }

    custom_config = {
        "Configuration": "Custom",
        "ocr_backend": "bedrock",  # Override
        "chat_model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0"  # Override
    }

    def mock_get_item(Key):
        if Key["Configuration"] == "Default":
            return {"Item": default_config}
        if Key["Configuration"] == "Custom":
            return {"Item": custom_config}
        return {}

    config_manager.table.get_item.side_effect = mock_get_item

    result = config_manager.get_effective_config()

    # Assert Custom values override Default
    assert result["ocr_backend"] == "bedrock"  # Custom override
    assert result["chat_model_id"] == "anthropic.claude-3-5-sonnet-20241022-v2:0"  # Custom override
    assert result["bedrock_ocr_model_id"] == "anthropic.claude-3-5-haiku-20241022-v1:0"  # Default (no override)

    # Assert existing fields preserved
    assert result["text_embed_model_id"] == "amazon.titan-embed-text-v2:0"
    assert result["image_embed_model_id"] == "amazon.titan-embed-image-v1"


def test_get_effective_config_defaults_only_new_fields(config_manager):
    """Test that Default values are used when no Custom overrides exist for new fields."""
    default_config = {
        "Configuration": "Default",
        "ocr_backend": "textract",
        "bedrock_ocr_model_id": "anthropic.claude-3-5-haiku-20241022-v1:0",
        "chat_model_id": "amazon.nova-pro-v1:0",
        "text_embed_model_id": "amazon.titan-embed-text-v2:0",
        "image_embed_model_id": "amazon.titan-embed-image-v1"
    }

    def mock_get_item(Key):
        if Key["Configuration"] == "Default":
            return {"Item": default_config}
        return {}  # No Custom config

    config_manager.table.get_item.side_effect = mock_get_item

    result = config_manager.get_effective_config()

    # Assert all values are from Default
    assert result["ocr_backend"] == "textract"
    assert result["bedrock_ocr_model_id"] == "anthropic.claude-3-5-haiku-20241022-v1:0"
    assert result["chat_model_id"] == "amazon.nova-pro-v1:0"
    assert result["text_embed_model_id"] == "amazon.titan-embed-text-v2:0"
    assert result["image_embed_model_id"] == "amazon.titan-embed-image-v1"
