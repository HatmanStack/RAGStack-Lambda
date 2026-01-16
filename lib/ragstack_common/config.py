"""Configuration Management for document pipeline

This module provides runtime configuration management using DynamoDB as the
storage backend. Configuration is structured as three entries:
- Schema: Defines available parameters and validation rules (read-only)
- Default: System default values (read-only)
- Custom: User-overridden values (read-write)

The ConfigurationManager merges Custom → Default to provide effective configuration.
No caching is used; configuration is read from DynamoDB on every call for
immediate consistency.
"""

import logging
import os
from copy import deepcopy
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_knowledge_base_config(
    config_manager: "ConfigurationManager | None" = None,
) -> tuple[str, str]:
    """
    Get Knowledge Base ID and Data Source ID from config with env var fallback.

    This function provides a migration path: reads from config table first,
    falls back to environment variables if not found in config.

    Args:
        config_manager: Optional ConfigurationManager instance. If not provided,
                       will attempt to create one from CONFIGURATION_TABLE_NAME env var.

    Returns:
        Tuple of (knowledge_base_id, data_source_id)

    Raises:
        ValueError: If neither config nor env vars provide the IDs
    """
    kb_id = None
    ds_id = None

    # Try config table first
    if config_manager:
        try:
            kb_id = config_manager.get_parameter("knowledge_base_id")
            ds_id = config_manager.get_parameter("data_source_id")
            if kb_id and ds_id:
                logger.info(f"Using KB config from table: kb_id={kb_id}, ds_id={ds_id}")
                return kb_id, ds_id
        except Exception as e:
            logger.warning(f"Failed to get KB config from table: {e}")

    # Fall back to environment variables
    kb_id = kb_id or os.environ.get("KNOWLEDGE_BASE_ID")
    ds_id = ds_id or os.environ.get("DATA_SOURCE_ID")

    if kb_id and ds_id:
        logger.info(f"Using KB config from env vars: kb_id={kb_id}, ds_id={ds_id}")
        return kb_id, ds_id

    raise ValueError(
        "Knowledge Base configuration not found. "
        "Set knowledge_base_id/data_source_id in config table or "
        "KNOWLEDGE_BASE_ID/DATA_SOURCE_ID environment variables."
    )


class ConfigurationManager:
    """
    Manages configuration retrieval and updates for document pipeline.

    This class reads configuration from a DynamoDB table with a single partition key
    'Configuration' that has three reserved values: Schema, Default, and Custom.

    Usage:
        config_manager = ConfigurationManager()
        ocr_backend = config_manager.get_parameter('ocr_backend')

    Design Decisions:
        - No caching: reads from DynamoDB on every call for immediate consistency
        - Fails fast: raises exceptions if table access fails (no fallback)
        - Merges Custom → Default: Custom values override Default values
    """

    def __init__(self, table_name: str | None = None):
        """
        Initialize configuration manager.

        Args:
            table_name: Configuration table name. If not provided, reads from
                       CONFIGURATION_TABLE_NAME environment variable.

        Raises:
            ValueError: If table_name not provided and env var not set
        """
        table_name = table_name or os.environ.get("CONFIGURATION_TABLE_NAME")
        if not table_name:
            raise ValueError(
                "Configuration table name not provided. "
                "Set CONFIGURATION_TABLE_NAME environment variable or provide table_name parameter."
            )

        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

        logger.info(f"Initialized ConfigurationManager with table: {table_name}")

    def get_configuration_item(self, config_type: str) -> dict[str, Any] | None:
        """
        Retrieve a specific configuration item from DynamoDB.

        Args:
            config_type: Configuration type ('Schema', 'Default', or 'Custom')

        Returns:
            Configuration dictionary if found, None if item doesn't exist

        Raises:
            ClientError: If DynamoDB access fails
        """
        try:
            response = self.table.get_item(Key={"Configuration": config_type})
            item = response.get("Item")

            if item:
                logger.debug(f"Retrieved {config_type} configuration from DynamoDB")
            else:
                logger.warning(f"{config_type} configuration not found in DynamoDB")

            return item

        except ClientError:
            logger.exception(f"Error retrieving {config_type} configuration")
            raise

    def get_effective_config(self) -> dict[str, Any]:
        """
        Get effective configuration by merging Custom → Default.

        NO CACHING: This method reads from DynamoDB on every call to ensure
        immediate consistency when configuration changes.

        Returns:
            Merged configuration dictionary with Custom values overriding Defaults

        Raises:
            ClientError: If DynamoDB access fails
        """
        # Get Default configuration
        default_item = self.get_configuration_item("Default")
        default_config = self._remove_partition_key(default_item) if default_item else {}

        # Get Custom configuration
        custom_item = self.get_configuration_item("Custom")
        custom_config = self._remove_partition_key(custom_item) if custom_item else {}

        # Merge: Custom overrides Default (deep-merge for nested dicts)
        effective_config = deepcopy(default_config)
        for k, v in custom_config.items():
            if isinstance(v, dict) and isinstance(effective_config.get(k), dict):
                # Deep-merge nested dicts (one level)
                effective_config[k].update(v)
            else:
                effective_config[k] = v

        logger.info(f"Effective configuration: {list(effective_config.keys())}")

        # Mask sensitive-looking keys in debug logs to prevent secret leakage
        masked = {
            k: ("***" if any(s in k.lower() for s in ("secret", "token", "key", "password")) else v)
            for k, v in effective_config.items()
        }
        logger.debug(f"Effective config values: {masked}")

        return effective_config

    def get_parameter(self, param_name: str, default: Any = None) -> Any:
        """
        Get a single configuration parameter value.

        This is a convenience method that calls get_effective_config() and
        extracts a single parameter.

        Args:
            param_name: Parameter name to retrieve
            default: Default value if parameter not found

        Returns:
            Parameter value from effective config, or default if not found

        Raises:
            ClientError: If DynamoDB access fails
        """
        config = self.get_effective_config()
        value = config.get(param_name, default)

        logger.debug(f"Parameter '{param_name}' = {value}")

        return value

    def update_custom_config(self, custom_config: dict[str, Any]) -> None:
        """
        Update Custom configuration in DynamoDB.

        Merges the provided values with existing Custom config using UpdateItem.
        This preserves existing custom settings while updating specific values.

        Args:
            custom_config: Dictionary of custom configuration values to update

        Raises:
            ClientError: If DynamoDB write fails
        """
        try:
            # Remove 'Configuration' key if present to prevent partition key override
            safe_config = {k: v for k, v in custom_config.items() if k != "Configuration"}

            if not safe_config:
                logger.warning("No configuration values to update")
                return

            # Build UpdateExpression to merge values instead of replacing
            update_parts = []
            expression_names = {}
            expression_values = {}

            for i, (key, value) in enumerate(safe_config.items()):
                attr_name = f"#k{i}"
                attr_value = f":v{i}"
                update_parts.append(f"{attr_name} = {attr_value}")
                expression_names[attr_name] = key
                expression_values[attr_value] = value

            update_expression = "SET " + ", ".join(update_parts)

            self.table.update_item(
                Key={"Configuration": "Custom"},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_names,
                ExpressionAttributeValues=expression_values,
            )

            logger.info("Updated Custom configuration in DynamoDB")

        except ClientError:
            logger.exception("Error updating Custom configuration")
            raise

    def get_schema(self) -> dict[str, Any]:
        """
        Get the Schema configuration.

        Returns:
            Schema dictionary defining available parameters and validation rules

        Raises:
            ClientError: If DynamoDB access fails
        """
        schema_item = self.get_configuration_item("Schema")

        if not schema_item:
            logger.warning("Schema not found in ConfigurationTable")
            return {}

        # Schema is stored under 'Schema' key in the item
        return schema_item.get("Schema", {})

    @staticmethod
    def _remove_partition_key(item: dict[str, Any] | None) -> dict[str, Any]:
        """
        Remove 'Configuration' partition key from DynamoDB item.

        Args:
            item: DynamoDB item dictionary

        Returns:
            Item dictionary without the 'Configuration' key
        """
        if not item:
            return {}

        item_copy = dict(item)
        item_copy.pop("Configuration", None)

        return item_copy
