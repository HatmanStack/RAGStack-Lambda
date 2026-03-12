"""Unit tests for configuration_resolver Lambda."""

import importlib.util
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


def load_configuration_resolver_module():
    """Load the configuration_resolver index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src" / "lambda" / "configuration_resolver" / "index.py"
    ).resolve()

    if "configuration_resolver_index" in sys.modules:
        del sys.modules["configuration_resolver_index"]

    spec = importlib.util.spec_from_file_location(
        "configuration_resolver_index", str(module_path)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["configuration_resolver_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    with patch.dict(os.environ, {"CONFIGURATION_TABLE_NAME": "test-config-table"}):
        yield


@pytest.fixture
def mock_table():
    return MagicMock()


def _load_with_mocked_table(mock_table):
    """Load module and patch its global table reference."""
    with (
        patch("boto3.resource") as mock_resource,
    ):
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        module = load_configuration_resolver_module()
        # Reset lazy-init globals so _initialize_tables runs fresh
        module.dynamodb = None
        module.configuration_table = None
        # Now initialize to use our mock
        module.dynamodb = mock_dynamodb
        module.configuration_table = mock_table
    return module


class TestGetConfiguration:
    """Tests for getConfiguration query."""

    def test_returns_schema_default_custom(self, mock_table):
        mock_table.get_item.side_effect = [
            {"Item": {"Configuration": "Schema", "Schema": {"properties": {"key1": {}}}}},
            {"Item": {"Configuration": "Default", "key1": "value1"}},
            {"Item": {"Configuration": "Custom", "key1": "custom_value"}},
        ]

        module = _load_with_mocked_table(mock_table)
        result = module.lambda_handler(
            {"info": {"fieldName": "getConfiguration"}, "arguments": {}}, None
        )

        assert "Schema" in result
        assert result["Default"]["key1"] == "value1"
        assert result["Custom"]["key1"] == "custom_value"
        # Configuration partition key should be removed
        assert "Configuration" not in result["Default"]
        assert "Configuration" not in result["Custom"]

    def test_empty_tables_return_empty_dicts(self, mock_table):
        mock_table.get_item.return_value = {}

        module = _load_with_mocked_table(mock_table)
        result = module.lambda_handler(
            {"info": {"fieldName": "getConfiguration"}, "arguments": {}}, None
        )

        assert result["Schema"] == {}
        # Default always has demo_mode_enabled injected from env
        assert result["Default"]["demo_mode_enabled"] is False
        assert result["Custom"] == {}

    def test_decimal_conversion(self, mock_table):
        mock_table.get_item.side_effect = [
            {"Item": {"Configuration": "Schema", "Schema": {}}},
            {"Item": {"Configuration": "Default", "int_val": Decimal("42"), "float_val": Decimal("3.14")}},
            {},
        ]

        module = _load_with_mocked_table(mock_table)
        result = module.lambda_handler(
            {"info": {"fieldName": "getConfiguration"}, "arguments": {}}, None
        )

        assert result["Default"]["int_val"] == 42
        assert isinstance(result["Default"]["int_val"], int)
        assert result["Default"]["float_val"] == 3.14
        assert isinstance(result["Default"]["float_val"], float)

    def test_demo_mode_env_injected(self, mock_table):
        mock_table.get_item.side_effect = [
            {"Item": {"Configuration": "Schema", "Schema": {}}},
            {"Item": {"Configuration": "Default"}},
            {},
        ]

        module = _load_with_mocked_table(mock_table)
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            result = module.lambda_handler(
                {"info": {"fieldName": "getConfiguration"}, "arguments": {}}, None
            )

        assert result["Default"]["demo_mode_enabled"] is True


class TestUpdateConfiguration:
    """Tests for updateConfiguration mutation."""

    def test_update_valid_keys(self, mock_table):
        mock_table.get_item.side_effect = [
            # Schema lookup for validation
            {
                "Item": {
                    "Configuration": "Schema",
                    "Schema": {"properties": {"key1": {}, "key2": {}}},
                }
            },
        ]

        module = _load_with_mocked_table(mock_table)
        result = module.lambda_handler(
            {
                "info": {"fieldName": "updateConfiguration"},
                "arguments": {"customConfig": json.dumps({"key1": "new_value"})},
            },
            None,
        )

        assert result is True
        mock_table.update_item.assert_called_once()

    def test_update_with_dict_input(self, mock_table):
        mock_table.get_item.side_effect = [
            {
                "Item": {
                    "Configuration": "Schema",
                    "Schema": {"properties": {"key1": {}}},
                }
            },
        ]

        module = _load_with_mocked_table(mock_table)
        result = module.lambda_handler(
            {
                "info": {"fieldName": "updateConfiguration"},
                "arguments": {"customConfig": {"key1": "value"}},
            },
            None,
        )

        assert result is True

    def test_update_invalid_keys_raises(self, mock_table):
        mock_table.get_item.side_effect = [
            {
                "Item": {
                    "Configuration": "Schema",
                    "Schema": {"properties": {"key1": {}}},
                }
            },
        ]

        module = _load_with_mocked_table(mock_table)
        with pytest.raises(ValueError, match="Invalid configuration keys"):
            module.lambda_handler(
                {
                    "info": {"fieldName": "updateConfiguration"},
                    "arguments": {"customConfig": json.dumps({"bad_key": "value"})},
                },
                None,
            )

    def test_update_non_dict_raises(self, mock_table):
        module = _load_with_mocked_table(mock_table)
        with pytest.raises(ValueError, match="must be a JSON object"):
            module.lambda_handler(
                {
                    "info": {"fieldName": "updateConfiguration"},
                    "arguments": {"customConfig": json.dumps([1, 2, 3])},
                },
                None,
            )

    def test_update_invalid_json_raises(self, mock_table):
        module = _load_with_mocked_table(mock_table)
        with pytest.raises(ValueError, match="Invalid configuration format"):
            module.lambda_handler(
                {
                    "info": {"fieldName": "updateConfiguration"},
                    "arguments": {"customConfig": "not json{"},
                },
                None,
            )

    def test_update_empty_config_returns_true(self, mock_table):
        mock_table.get_item.side_effect = [
            {
                "Item": {
                    "Configuration": "Schema",
                    "Schema": {"properties": {"key1": {}}},
                }
            },
        ]

        module = _load_with_mocked_table(mock_table)
        result = module.lambda_handler(
            {
                "info": {"fieldName": "updateConfiguration"},
                "arguments": {"customConfig": json.dumps({})},
            },
            None,
        )

        assert result is True
        mock_table.update_item.assert_not_called()

    def test_update_float_converted_to_decimal(self, mock_table):
        mock_table.get_item.side_effect = [
            {
                "Item": {
                    "Configuration": "Schema",
                    "Schema": {"properties": {"threshold": {}}},
                }
            },
        ]

        module = _load_with_mocked_table(mock_table)
        module.lambda_handler(
            {
                "info": {"fieldName": "updateConfiguration"},
                "arguments": {"customConfig": {"threshold": 0.95}},
            },
            None,
        )

        call_kwargs = mock_table.update_item.call_args[1]
        assert isinstance(call_kwargs["ExpressionAttributeValues"][":threshold"], Decimal)


class TestGeneralHandler:
    """Tests for general handler behavior."""

    def test_unsupported_operation_raises(self, mock_table):
        module = _load_with_mocked_table(mock_table)
        with pytest.raises(ValueError, match="Unsupported operation"):
            module.lambda_handler(
                {"info": {"fieldName": "unknownOp"}, "arguments": {}}, None
            )

    def test_missing_config_table_raises(self):
        with patch.dict(os.environ, {"CONFIGURATION_TABLE_NAME": ""}):
            module = load_configuration_resolver_module()
            module.dynamodb = None
            module.configuration_table = None
            with pytest.raises(ValueError, match="CONFIGURATION_TABLE_NAME"):
                module.lambda_handler(
                    {"info": {"fieldName": "getConfiguration"}, "arguments": {}}, None
                )

    def test_dynamodb_client_error_propagates(self, mock_table):
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "DynamoDB down"}},
            "GetItem",
        )

        module = _load_with_mocked_table(mock_table)
        with pytest.raises(ClientError):
            module.lambda_handler(
                {"info": {"fieldName": "getConfiguration"}, "arguments": {}}, None
            )
