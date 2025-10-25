"""
AppSync Lambda resolvers for document operations.

Handles:
- getDocument
- listDocuments
- createUploadUrl
"""

import json
import logging
import os
import boto3
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

TRACKING_TABLE = os.environ['TRACKING_TABLE']
INPUT_BUCKET = os.environ['INPUT_BUCKET']


def lambda_handler(event, context):
    """
    Route to appropriate resolver based on field name.
    """
    logger.info(f'Event: {json.dumps(event)}')

    field_name = event['info']['fieldName']

    resolvers = {
        'getDocument': get_document,
        'listDocuments': list_documents,
        'createUploadUrl': create_upload_url
    }

    resolver = resolvers.get(field_name)
    if not resolver:
        raise ValueError(f'Unknown field: {field_name}')

    return resolver(event['arguments'])


def get_document(args):
    """Get document by ID."""
    document_id = args['documentId']

    table = dynamodb.Table(TRACKING_TABLE)
    response = table.get_item(Key={'document_id': document_id})

    item = response.get('Item')
    if not item:
        return None

    return format_document(item)


def list_documents(args):
    """List all documents with pagination."""
    limit = args.get('limit', 50)
    next_token = args.get('nextToken')

    table = dynamodb.Table(TRACKING_TABLE)

    scan_kwargs = {
        'Limit': limit
    }

    if next_token:
        scan_kwargs['ExclusiveStartKey'] = json.loads(next_token)

    response = table.scan(**scan_kwargs)

    items = [format_document(item) for item in response.get('Items', [])]

    result = {
        'items': items
    }

    if 'LastEvaluatedKey' in response:
        result['nextToken'] = json.dumps(response['LastEvaluatedKey'])

    return result


def create_upload_url(args):
    """
    Create presigned URL for S3 upload.

    Returns upload URL and document ID for tracking.
    """
    filename = args['filename']
    document_id = str(uuid4())

    # Generate S3 key
    s3_key = f'{document_id}/{filename}'

    # Create presigned POST
    presigned = s3.generate_presigned_post(
        Bucket=INPUT_BUCKET,
        Key=s3_key,
        ExpiresIn=3600  # 1 hour
    )

    # Create tracking record
    table = dynamodb.Table(TRACKING_TABLE)
    table.put_item(Item={
        'document_id': document_id,
        'filename': filename,
        'input_s3_uri': f's3://{INPUT_BUCKET}/{s3_key}',
        'status': 'uploaded',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    })

    return {
        'uploadUrl': presigned['url'],
        'documentId': document_id,
        'fields': json.dumps(presigned['fields'])
    }


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
