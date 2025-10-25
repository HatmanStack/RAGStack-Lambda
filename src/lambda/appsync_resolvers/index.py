"""
AppSync Lambda resolvers for document operations.

Handles:
- getDocument
- listDocuments
- createUploadUrl
- processDocument
"""

import json
import logging
import os
import re
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sfn = boto3.client('stepfunctions')

TRACKING_TABLE = os.environ['TRACKING_TABLE']
INPUT_BUCKET = os.environ['INPUT_BUCKET']
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

# Validation constants
MAX_FILENAME_LENGTH = 255
MAX_DOCUMENTS_LIMIT = 100
FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9._\-\s]+$')


def lambda_handler(event, context):
    """
    Route to appropriate resolver based on field name.
    """
    logger.info(f'AppSync resolver invoked for field: {event["info"]["fieldName"]}')
    logger.info(f'Arguments: {json.dumps(event.get("arguments", {}))}')

    field_name = event['info']['fieldName']

    resolvers = {
        'getDocument': get_document,
        'listDocuments': list_documents,
        'createUploadUrl': create_upload_url,
        'processDocument': process_document
    }

    resolver = resolvers.get(field_name)
    if not resolver:
        logger.error(f'Unknown field: {field_name}')
        raise ValueError(f'Unknown field: {field_name}')

    try:
        result = resolver(event['arguments'])
        logger.info(f'Resolver {field_name} completed successfully')
        return result
    except ValueError as e:
        logger.error(f'Validation error in {field_name}: {e}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error in {field_name}: {e}', exc_info=True)
        raise


def get_document(args):
    """Get document by ID."""
    try:
        document_id = args['documentId']
        logger.info(f'Fetching document: {document_id}')

        # Validate document ID format (UUID)
        if not is_valid_uuid(document_id):
            logger.warning(f'Invalid document ID format: {document_id}')
            raise ValueError('Invalid document ID format')

        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={'document_id': document_id})

        item = response.get('Item')
        if not item:
            logger.info(f'Document not found: {document_id}')
            return None

        logger.info(f'Document found: {document_id}, status: {item.get("status")}')
        return format_document(item)

    except ClientError as e:
        logger.error(f'DynamoDB error in get_document: {e}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error in get_document: {e}')
        raise


def list_documents(args):
    """List all documents with pagination."""
    try:
        limit = args.get('limit', 50)
        next_token = args.get('nextToken')

        # Validate limit
        if limit < 1 or limit > MAX_DOCUMENTS_LIMIT:
            logger.warning(f'Invalid limit requested: {limit}')
            raise ValueError(f'Limit must be between 1 and {MAX_DOCUMENTS_LIMIT}')

        logger.info(f'Listing documents with limit: {limit}')

        table = dynamodb.Table(TRACKING_TABLE)

        scan_kwargs = {
            'Limit': limit
        }

        if next_token:
            try:
                scan_kwargs['ExclusiveStartKey'] = json.loads(next_token)
                logger.info('Continuing pagination with next token')
            except json.JSONDecodeError:
                logger.warning('Invalid next token provided')
                raise ValueError('Invalid pagination token')

        response = table.scan(**scan_kwargs)

        items = [format_document(item) for item in response.get('Items', [])]
        logger.info(f'Retrieved {len(items)} documents')

        result = {
            'items': items
        }

        if 'LastEvaluatedKey' in response:
            result['nextToken'] = json.dumps(response['LastEvaluatedKey'])
            logger.info('More results available')

        return result

    except ClientError as e:
        logger.error(f'DynamoDB error in list_documents: {e}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error in list_documents: {e}')
        raise


def create_upload_url(args):
    """
    Create presigned URL for S3 upload.

    Returns upload URL and document ID for tracking.
    """
    try:
        filename = args['filename']
        logger.info(f'Creating upload URL for file: {filename}')

        # Validate filename
        if not filename or len(filename) > MAX_FILENAME_LENGTH:
            logger.warning(f'Invalid filename length: {len(filename) if filename else 0}')
            raise ValueError(f'Filename must be between 1 and {MAX_FILENAME_LENGTH} characters')

        # Check for path traversal and invalid characters
        if '/' in filename or '\\' in filename or '..' in filename:
            logger.warning(f'Filename contains invalid characters: {filename}')
            raise ValueError('Filename contains invalid path characters')

        # Ensure filename has valid characters
        if not FILENAME_PATTERN.match(filename):
            logger.warning(f'Filename contains invalid characters: {filename}')
            raise ValueError('Filename contains invalid characters (use alphanumeric, dots, dashes, underscores, spaces only)')

        document_id = str(uuid4())
        logger.info(f'Generated document ID: {document_id}')

        # Generate S3 key
        s3_key = f'{document_id}/{filename}'

        # Create presigned POST
        logger.info(f'Generating presigned POST for S3 key: {s3_key}')
        presigned = s3.generate_presigned_post(
            Bucket=INPUT_BUCKET,
            Key=s3_key,
            ExpiresIn=3600  # 1 hour
        )

        # Create tracking record
        logger.info(f'Creating tracking record for document: {document_id}')
        table = dynamodb.Table(TRACKING_TABLE)
        table.put_item(Item={
            'document_id': document_id,
            'filename': filename,
            'input_s3_uri': f's3://{INPUT_BUCKET}/{s3_key}',
            'status': 'uploaded',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })

        logger.info(f'Upload URL created successfully for document: {document_id}')
        return {
            'uploadUrl': presigned['url'],
            'documentId': document_id,
            'fields': json.dumps(presigned['fields'])
        }

    except ClientError as e:
        logger.error(f'AWS service error in create_upload_url: {e}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error in create_upload_url: {e}')
        raise


def process_document(args):
    """
    Manually trigger document processing via Step Functions.

    Returns updated document record.
    """
    try:
        document_id = args['documentId']
        logger.info(f'Manually triggering processing for document: {document_id}')

        # Validate document ID format
        if not is_valid_uuid(document_id):
            logger.warning(f'Invalid document ID format: {document_id}')
            raise ValueError('Invalid document ID format')

        # Check if state machine ARN is configured
        if not STATE_MACHINE_ARN:
            logger.error('STATE_MACHINE_ARN environment variable not set')
            raise ValueError('Processing not configured')

        # Get document from DynamoDB
        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={'document_id': document_id})

        item = response.get('Item')
        if not item:
            logger.warning(f'Document not found: {document_id}')
            raise ValueError('Document not found')

        # Check if document is in a state that can be reprocessed
        current_status = item.get('status', '').lower()
        if current_status == 'processing':
            logger.warning(f'Document already processing: {document_id}')
            raise ValueError('Document is already being processed')

        # Update status to processing
        logger.info(f'Updating document status to processing: {document_id}')
        table.update_item(
            Key={'document_id': document_id},
            UpdateExpression='SET #status = :status, updated_at = :updated_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'processing',
                ':updated_at': datetime.now().isoformat()
            }
        )

        # Start Step Functions execution
        execution_input = {
            'document_id': document_id,
            'input_s3_uri': item.get('input_s3_uri'),
            'filename': item.get('filename')
        }

        logger.info(f'Starting Step Functions execution for document: {document_id}')
        execution_response = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f'{document_id}-{int(datetime.now().timestamp())}',
            input=json.dumps(execution_input)
        )

        logger.info(f'Step Functions execution started: {execution_response["executionArn"]}')

        # Get updated document
        response = table.get_item(Key={'document_id': document_id})
        updated_item = response.get('Item')

        return format_document(updated_item)

    except ClientError as e:
        logger.error(f'AWS service error in process_document: {e}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error in process_document: {e}')
        raise


def format_document(item):
    """Format DynamoDB item as GraphQL Document type."""
    return {
        'documentId': item['document_id'],
        'filename': item.get('filename', ''),
        'inputS3Uri': item.get('input_s3_uri', ''),
        'outputS3Uri': item.get('output_s3_uri'),
        'status': item.get('status', 'uploaded').upper(),
        'fileType': item.get('file_type'),
        'isTextNative': item.get('is_text_native', False),
        'totalPages': item.get('total_pages', 0),
        'errorMessage': item.get('error_message'),
        'createdAt': item.get('created_at'),
        'updatedAt': item.get('updated_at'),
        'metadata': json.dumps(item.get('metadata', {}))
    }


def is_valid_uuid(uuid_string):
    """Validate UUID format."""
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(uuid_string))
