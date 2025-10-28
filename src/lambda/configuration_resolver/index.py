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
import uuid
import re
from decimal import Decimal
from datetime import datetime
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
        # Defensive env var checks with clear error messages
        config_table_name = os.environ.get('CONFIGURATION_TABLE_NAME')
        if not config_table_name:
            raise ValueError("Missing required environment variable: CONFIGURATION_TABLE_NAME")

        tracking_table_name = os.environ.get('TRACKING_TABLE')
        if not tracking_table_name:
            raise ValueError("Missing required environment variable: TRACKING_TABLE")

        dynamodb = boto3.resource('dynamodb')
        configuration_table = dynamodb.Table(config_table_name)
        tracking_table = dynamodb.Table(tracking_table_name)


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

    # Log event structure (not values) to avoid PII leakage
    event_summary = {
        "fields": list(event.keys()),
        "argumentKeys": list(event.get("arguments", {}).keys()) if event.get("arguments") else []
    }
    logger.info(f"Event received with structure: {json.dumps(event_summary)}")

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

        elif operation == 'reEmbedAllDocuments':
            return handle_re_embed_all_documents()

        elif operation == 'getReEmbedJobStatus':
            return handle_get_re_embed_job_status()

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

        # Decimal-safe JSON serialization for DynamoDB items
        def decimal_default(obj):
            if isinstance(obj, Decimal):
                return int(obj) if obj % 1 == 0 else float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        result = {
            'Schema': json.dumps(schema_config, default=decimal_default),  # AppSync expects JSON string
            'Default': json.dumps(default_config, default=decimal_default),
            'Custom': json.dumps(custom_config, default=decimal_default)
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

        # Validate that config is a dictionary BEFORE logging
        if not isinstance(custom_config_obj, dict) or custom_config_obj is None:
            raise ValueError("customConfig must be a JSON object (dict), got: " + type(custom_config_obj).__name__)

        logger.info(f"Updating Custom configuration with keys: {list(custom_config_obj.keys())}")

        # Remove 'Configuration' key to prevent partition key override
        safe_config = {k: v for k, v in custom_config_obj.items() if k != 'Configuration'}

        # Write to DynamoDB with protected partition key
        configuration_table.put_item(
            Item={
                'Configuration': 'Custom',
                **safe_config
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
        # Scan tracking table for COMPLETED status with pagination
        # Note: In production with large datasets, consider using a GSI or cached count
        count = 0
        scan_kwargs = {
            'FilterExpression': '#status = :status',
            'ExpressionAttributeNames': {'#status': 'status'},
            'ExpressionAttributeValues': {':status': 'COMPLETED'},
            'Select': 'COUNT'
        }

        # Paginate through all results
        while True:
            response = tracking_table.scan(**scan_kwargs)
            count += response.get('Count', 0)

            # Check if there are more pages
            last_key = response.get('LastEvaluatedKey')
            if not last_key:
                break

            # Set up for next page
            scan_kwargs['ExclusiveStartKey'] = last_key

        logger.info(f"Found {count} COMPLETED documents (paginated scan)")

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


def handle_re_embed_all_documents():
    """
    Handle reEmbedAllDocuments mutation.

    Creates a re-embedding job and triggers Step Functions for all COMPLETED documents.

    Returns:
        ReEmbedJobStatus object
    """
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        start_time = datetime.utcnow().isoformat() + 'Z'

        # Query all COMPLETED documents
        logger.info("Querying COMPLETED documents for re-embedding")
        documents = query_completed_documents()
        total_documents = len(documents)

        logger.info(f"Found {total_documents} documents to re-embed")

        if total_documents == 0:
            return {
                'jobId': job_id,
                'status': 'COMPLETED',
                'totalDocuments': 0,
                'processedDocuments': 0,
                'startTime': start_time,
                'completionTime': start_time
            }

        # Create job tracking item with unique partition key
        job_key = f'ReEmbedJob#{job_id}'
        configuration_table.put_item(
            Item={
                'Configuration': job_key,  # Unique key per job
                'jobId': job_id,
                'status': 'IN_PROGRESS',
                'totalDocuments': total_documents,
                'processedDocuments': 0,
                'startTime': start_time,
                'completionTime': None
            }
        )

        # Also update a "latest job pointer" for easy UI access
        configuration_table.put_item(
            Item={
                'Configuration': 'ReEmbedJob_Latest',
                'jobId': job_id,
                'jobKey': job_key
            }
        )

        # Trigger Step Functions for each document
        # SCALABILITY NOTE: For large document sets (>1000), this synchronous loop
        # may timeout. Consider using SQS + Lambda consumer pattern for production.
        sfn_client = boto3.client('stepfunctions')
        state_machine_arn = os.environ['STATE_MACHINE_ARN']

        # Limit to 500 documents per job to prevent Lambda timeout
        MAX_DOCUMENTS_PER_JOB = 500
        if total_documents > MAX_DOCUMENTS_PER_JOB:
            logger.warning(f"Document count ({total_documents}) exceeds limit ({MAX_DOCUMENTS_PER_JOB}). Processing first {MAX_DOCUMENTS_PER_JOB} only.")
            documents = documents[:MAX_DOCUMENTS_PER_JOB]
            total_documents = MAX_DOCUMENTS_PER_JOB

        for doc in documents:
            # Sanitize execution name: only alphanumeric, hyphen, underscore; max 80 chars
            raw_name = f"reembed-{doc['document_id']}-{job_id[:8]}"
            execution_name = re.sub(r'[^a-zA-Z0-9_-]', '-', raw_name)[:80]

            sfn_client.start_execution(
                stateMachineArn=state_machine_arn,
                name=execution_name,
                input=json.dumps({
                    'documentId': doc['document_id'],
                    'bucket': doc['input_bucket'],
                    'key': doc['input_key'],
                    'reEmbedJobId': job_id  # Pass job ID for tracking
                })
            )

        logger.info(f"Started re-embedding job {job_id} for {total_documents} documents")

        return {
            'jobId': job_id,
            'status': 'IN_PROGRESS',
            'totalDocuments': total_documents,
            'processedDocuments': 0,
            'startTime': start_time,
            'completionTime': None
        }

    except Exception as e:
        logger.error(f"Error in reEmbedAllDocuments: {str(e)}")
        raise


def query_completed_documents():
    """
    Query all documents with status='COMPLETED' using GSI.

    IMPORTANT: This requires a GSI on TrackingTable called 'StatusIndex'
    with status as the partition key. See Phase 1 for GSI setup.

    Returns:
        List of document items
    """
    documents = []

    try:
        # Query using GSI (much faster than scan for large tables)
        response = tracking_table.query(
            IndexName='StatusIndex',
            KeyConditionExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'COMPLETED'}
        )

        documents.extend(response.get('Items', []))

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = tracking_table.query(
                IndexName='StatusIndex',
                KeyConditionExpression='#status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': 'COMPLETED'},
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            documents.extend(response.get('Items', []))

        return documents

    except ClientError as e:
        # If GSI doesn't exist, fall back to scan (less efficient)
        logger.warning(f"GSI query failed, falling back to scan: {e}")

        response = tracking_table.scan(
            FilterExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'COMPLETED'}
        )

        documents.extend(response.get('Items', []))

        while 'LastEvaluatedKey' in response:
            response = tracking_table.scan(
                FilterExpression='#status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': 'COMPLETED'},
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            documents.extend(response.get('Items', []))

        return documents


def handle_get_re_embed_job_status():
    """
    Handle getReEmbedJobStatus query.

    Returns latest re-embedding job status.
    """
    try:
        # Get latest job pointer
        response = configuration_table.get_item(Key={'Configuration': 'ReEmbedJob_Latest'})
        pointer = response.get('Item')

        if not pointer:
            return None

        # Get actual job item using the job key
        job_key = pointer.get('jobKey')
        if not job_key:
            return None

        response = configuration_table.get_item(Key={'Configuration': job_key})
        item = response.get('Item')

        if not item:
            return None

        return {
            'jobId': item.get('jobId'),
            'status': item.get('status'),
            'totalDocuments': item.get('totalDocuments'),
            'processedDocuments': item.get('processedDocuments'),
            'startTime': item.get('startTime'),
            'completionTime': item.get('completionTime')
        }

    except ClientError as e:
        logger.error(f"Error getting re-embed job status: {str(e)}")
        return None
