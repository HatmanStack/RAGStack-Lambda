"""GraphQL Resolver for Configuration Operations

This Lambda function handles GraphQL queries and mutations for configuration management:
- getConfiguration: Returns Schema, Default, and Custom configurations
- updateConfiguration: Updates Custom configuration
- getDocumentCount: Returns count of COMPLETED documents
- (reEmbedAllDocuments implemented in Phase 5)
"""

import os
import json
import boto3
import logging
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize boto3 clients (lazy initialization for testing)
dynamodb = None
configuration_table = None
tracking_table = None


def _initialize_tables():
    """Initialize DynamoDB tables (called on first use)."""
    global dynamodb, configuration_table, tracking_table
    if dynamodb is None:
        dynamodb = boto3.resource('dynamodb')
        configuration_table = dynamodb.Table(os.environ['CONFIGURATION_TABLE_NAME'])
        tracking_table = dynamodb.Table(os.environ['TRACKING_TABLE'])


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
                'fieldName': 'getConfiguration' | 'updateConfiguration' | 'getDocumentCount'
            },
            'arguments': {
                'customConfig': {...}  # For updateConfiguration
            }
        }
    """
    # Initialize tables on first invocation
    _initialize_tables()

    logger.info(f"Event received: {json.dumps(event)}")

    # Extract GraphQL operation
    operation = event['info']['fieldName']
    logger.info(f"Processing operation: {operation}")

    try:
        if operation == 'getConfiguration':
            return handle_get_configuration()

        elif operation == 'updateConfiguration':
            custom_config = event['arguments'].get('customConfig')
            return handle_update_configuration(custom_config)

        elif operation == 'getDocumentCount':
            return handle_get_document_count()

        else:
            raise ValueError(f"Unsupported operation: {operation}")

    except Exception as e:
        logger.error(f"Error processing {operation}: {str(e)}", exc_info=True)
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
        schema_item = get_configuration_item('Schema')
        schema_config = schema_item.get('Schema', {}) if schema_item else {}

        # Get Default configuration
        default_item = get_configuration_item('Default')
        default_config = remove_partition_key(default_item) if default_item else {}

        # Get Custom configuration
        custom_item = get_configuration_item('Custom')
        custom_config = remove_partition_key(custom_item) if custom_item else {}

        result = {
            'Schema': json.dumps(schema_config),  # AppSync expects JSON string
            'Default': json.dumps(default_config),
            'Custom': json.dumps(custom_config)
        }

        logger.info("Returning configuration to client")
        return result

    except Exception as e:
        logger.error(f"Error in getConfiguration: {str(e)}")
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

        logger.info(f"Updating Custom configuration with keys: {list(custom_config_obj.keys())}")

        # Validate that config is a dictionary
        if not isinstance(custom_config_obj, dict):
            raise ValueError("customConfig must be a JSON object")

        # Write to DynamoDB
        configuration_table.put_item(
            Item={
                'Configuration': 'Custom',
                **custom_config_obj
            }
        )

        logger.info("Custom configuration updated successfully")
        return True

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in customConfig: {str(e)}")
        raise ValueError(f"Invalid configuration format: {str(e)}")

    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Error in updateConfiguration: {str(e)}")
        raise


def handle_get_document_count():
    """
    Handle getDocumentCount query.

    Returns count of documents with status='COMPLETED' for embedding change detection.

    Returns:
        Integer count of COMPLETED documents
    """
    try:
        # Scan tracking table for COMPLETED status
        # Note: In production with large datasets, consider using a GSI or cached count
        response = tracking_table.scan(
            FilterExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'COMPLETED'},
            Select='COUNT'
        )

        count = response.get('Count', 0)
        logger.info(f"Found {count} COMPLETED documents")

        return count

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        logger.error(f"DynamoDB error counting documents ({error_code}): {str(e)}")

        # Only return 0 for non-critical errors (ResourceNotFoundException, etc.)
        # Raise for critical errors (AccessDeniedException, etc.)
        if error_code in ['ResourceNotFoundException', 'ValidationException']:
            logger.warning(f"Non-critical error, returning 0: {error_code}")
            return 0
        else:
            # Re-raise for critical errors so UI knows something is wrong
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
        response = configuration_table.get_item(Key={'Configuration': config_type})
        return response.get('Item')

    except ClientError as e:
        logger.error(f"Error retrieving {config_type}: {str(e)}")
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
    item_copy.pop('Configuration', None)
    return item_copy
