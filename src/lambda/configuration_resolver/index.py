"""GraphQL Resolver for Configuration Operations

This Lambda function handles GraphQL queries and mutations for configuration management:
- getConfiguration: Returns Schema, Default, and Custom configurations
- updateConfiguration: Updates Custom configuration
"""

import json
import logging
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Initialize boto3 clients (lazy initialization for testing)
dynamodb = None
configuration_table = None


def _initialize_tables():
    """Initialize DynamoDB tables (called on first use)."""
    global dynamodb, configuration_table
    if dynamodb is None:
        # Defensive env var checks with clear error messages
        config_table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
        if not config_table_name:
            raise ValueError("Missing required environment variable: CONFIGURATION_TABLE_NAME")

        dynamodb = boto3.resource("dynamodb")
        configuration_table = dynamodb.Table(config_table_name)


def lambda_handler(event, context):
    """
    AWS Lambda handler for GraphQL configuration operations.

    Args:
        event: AppSync event with operation details
        context: Lambda context

    Returns:
        Response data matching GraphQL schema

    Event structure:
        {
            'info': {
                'fieldName': 'getConfiguration' | 'updateConfiguration'
            },
            'arguments': {
                'customConfig': {...}  # For updateConfiguration
            }
        }
    """
    # Initialize tables on first invocation
    _initialize_tables()

    # Log event structure (not values) to avoid PII leakage
    event_summary = {
        "fields": list(event.keys()),
        "argumentKeys": list(event.get("arguments", {}).keys()) if event.get("arguments") else [],
    }
    logger.info(f"Event received with structure: {json.dumps(event_summary)}")

    # Extract GraphQL operation
    operation = event["info"]["fieldName"]
    logger.info(f"Processing operation: {operation}")

    try:
        if operation == "getConfiguration":
            return handle_get_configuration()

        if operation == "updateConfiguration":
            custom_config = event["arguments"].get("customConfig")
            return handle_update_configuration(custom_config)

        raise ValueError(f"Unsupported operation: {operation}")

    except Exception:
        logger.exception(f"Error processing {operation}")
        raise


def handle_get_configuration():
    """
    Handle getConfiguration query.

    Returns:
        {
            'Schema': {...},   # Schema configuration
            'Default': {...},  # Default configuration
            'Custom': {...}    # Custom configuration (may be empty)
        }
    """
    try:
        # Get Schema configuration
        schema_item = get_configuration_item("Schema")
        schema_config = schema_item.get("Schema", {}) if schema_item else {}

        # Get Default configuration
        default_item = get_configuration_item("Default")
        default_config = remove_partition_key(default_item) if default_item else {}

        # Get Custom configuration
        custom_item = get_configuration_item("Custom")
        custom_config = remove_partition_key(custom_item) if custom_item else {}

        # Convert Decimals to native Python types for JSON serialization
        def convert_decimals(obj):
            if isinstance(obj, dict):
                return {k: convert_decimals(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_decimals(item) for item in obj]
            if isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            return obj

        # Return raw dicts - AppSync will handle AWSJSON serialization
        result = {
            "Schema": convert_decimals(schema_config),
            "Default": convert_decimals(default_config),
            "Custom": convert_decimals(custom_config),
        }

        logger.info("Returning configuration to client")
        return result

    except Exception:
        logger.exception("Error in getConfiguration")
        raise


def handle_update_configuration(custom_config):
    """
    Handle updateConfiguration mutation.

    Args:
        custom_config: AWSJSON string or dict of custom configuration

    Returns:
        Boolean indicating success
    """
    try:
        # Parse JSON if it's a string
        if isinstance(custom_config, str):
            custom_config_obj = json.loads(custom_config)
        else:
            custom_config_obj = custom_config

        # Validate that config is a dictionary BEFORE logging
        if not isinstance(custom_config_obj, dict) or custom_config_obj is None:
            raise ValueError(
                "customConfig must be a JSON object (dict), got: "
                + type(custom_config_obj).__name__
            )

        logger.info(f"Updating Custom configuration with keys: {list(custom_config_obj.keys())}")

        # Validate keys against Schema
        schema_item = get_configuration_item("Schema")
        if not schema_item:
            raise ValueError("Schema configuration not found in DynamoDB")

        schema_config = schema_item.get("Schema", {})
        valid_fields = set(schema_config.get("properties", {}).keys())

        # Check for invalid keys
        provided_keys = set(custom_config_obj.keys()) - {"Configuration"}  # Exclude partition key
        invalid_keys = provided_keys - valid_fields

        if invalid_keys:
            raise ValueError(
                f"Invalid configuration keys: {', '.join(sorted(invalid_keys))}. "
                f"Valid keys are: {', '.join(sorted(valid_fields))}"
            )

        # Remove 'Configuration' key to prevent partition key override
        safe_config = {k: v for k, v in custom_config_obj.items() if k != "Configuration"}

        # Write to DynamoDB with protected partition key
        configuration_table.put_item(Item={"Configuration": "Custom", **safe_config})

        logger.info("Custom configuration updated successfully")
        return True

    except json.JSONDecodeError as e:
        logger.exception("Invalid JSON in customConfig")
        raise ValueError(f"Invalid configuration format: {str(e)}") from e

    except ClientError:
        logger.exception("DynamoDB error")
        raise

    except Exception:
        logger.exception("Error in updateConfiguration")
        raise


def get_configuration_item(config_type):
    """
    Retrieve a configuration item from DynamoDB.

    Args:
        config_type: 'Schema', 'Default', or 'Custom'

    Returns:
        Configuration item dictionary or None
    """
    try:
        response = configuration_table.get_item(Key={"Configuration": config_type})
        return response.get("Item")

    except ClientError:
        logger.exception(f"Error retrieving {config_type}")
        raise


def remove_partition_key(item):
    """
    Remove 'Configuration' partition key from DynamoDB item.

    Args:
        item: DynamoDB item dictionary

    Returns:
        Item without 'Configuration' key
    """
    if not item:
        return {}

    item_copy = dict(item)
    item_copy.pop("Configuration", None)
    return item_copy
