"""Configuration Management for RAGStack-Lambda

This module provides runtime configuration management using DynamoDB as the
storage backend. Configuration is structured as three entries:
- Schema: Defines available parameters and validation rules (read-only)
- Default: System default values (read-only)
- Custom: User-overridden values (read-write)

The ConfigurationManager merges Custom → Default to provide effective configuration.
No caching is used; configuration is read from DynamoDB on every call for
immediate consistency.
"""

import boto3
import os
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
from copy import deepcopy

logger = logging.getLogger(__name__)


class ConfigurationManager:
    """
    Manages configuration retrieval and updates for RAGStack-Lambda.

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

    def __init__(self, table_name: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            table_name: Configuration table name. If not provided, reads from
                       CONFIGURATION_TABLE_NAME environment variable.

        Raises:
            ValueError: If table_name not provided and env var not set
        """
        table_name = table_name or os.environ.get('CONFIGURATION_TABLE_NAME')
        if not table_name:
            raise ValueError(
                "Configuration table name not provided. "
                "Set CONFIGURATION_TABLE_NAME environment variable or provide table_name parameter."
            )

        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

        logger.info(f"Initialized ConfigurationManager with table: {table_name}")

    def get_configuration_item(self, config_type: str) -> Optional[Dict[str, Any]]:
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
            response = self.table.get_item(Key={'Configuration': config_type})
            item = response.get('Item')

            if item:
                logger.debug(f"Retrieved {config_type} configuration from DynamoDB")
            else:
                logger.warning(f"{config_type} configuration not found in DynamoDB")

            return item

        except ClientError as e:
            logger.exception(f"Error retrieving {config_type} configuration")
            raise

    def get_effective_config(self) -> Dict[str, Any]:
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
        default_item = self.get_configuration_item('Default')
        default_config = self._remove_partition_key(default_item) if default_item else {}

        # Get Custom configuration
        custom_item = self.get_configuration_item('Custom')
        custom_config = self._remove_partition_key(custom_item) if custom_item else {}

        # Merge: Custom overrides Default
        effective_config = deepcopy(default_config)
        effective_config.update(custom_config)

        logger.info(f"Effective configuration: {list(effective_config.keys())}")
        logger.debug(f"Effective config values: {effective_config}")

        return effective_config

    def get_parameter(
        self,
        param_name: str,
        default: Any = None
    ) -> Any:
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

    def update_custom_config(self, custom_config: Dict[str, Any]) -> None:
        """
        Update Custom configuration in DynamoDB.

        This method is typically called by the ConfigurationResolver Lambda,
        not by processing Lambdas.

        Args:
            custom_config: Dictionary of custom configuration values

        Raises:
            ClientError: If DynamoDB write fails
        """
        try:
            # Remove 'Configuration' key if present to prevent partition key override
            safe_config = {k: v for k, v in custom_config.items() if k != 'Configuration'}

            # Put item to DynamoDB with protected partition key
            self.table.put_item(
                Item={
                    'Configuration': 'Custom',
                    **safe_config
                }
            )

            logger.info("Updated Custom configuration in DynamoDB")

        except ClientError as e:
            logger.exception("Error updating Custom configuration")
            raise

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the Schema configuration.

        Returns:
            Schema dictionary defining available parameters and validation rules

        Raises:
            ClientError: If DynamoDB access fails
        """
        schema_item = self.get_configuration_item('Schema')

        if not schema_item:
            logger.warning("Schema not found in ConfigurationTable")
            return {}

        # Schema is stored under 'Schema' key in the item
        return schema_item.get('Schema', {})

    @staticmethod
    def _remove_partition_key(item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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
        item_copy.pop('Configuration', None)

        return item_copy
