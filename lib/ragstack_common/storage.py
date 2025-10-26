"""
Storage utilities for S3 and DynamoDB operations.

Provides simple, consistent interface for reading/writing data.
"""

import json
import boto3
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

# Lazy-loaded AWS clients (initialized on first use)
_s3_client = None
_dynamodb = None


def get_s3_client():
    """Get or create S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3')
    return _s3_client


def get_dynamodb():
    """Get or create DynamoDB resource."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource('dynamodb')
    return _dynamodb


# ============================================================================
# S3 Operations
# ============================================================================

def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """
    Parse S3 URI into bucket and key.

    Args:
        s3_uri: S3 URI like "s3://bucket-name/path/to/file.txt"

    Returns:
        Tuple of (bucket, key)

    Example:
        bucket, key = parse_s3_uri("s3://my-bucket/docs/file.pdf")
        # bucket = "my-bucket"
        # key = "docs/file.pdf"
    """
    if not s3_uri.startswith('s3://'):
        raise ValueError(f"Invalid S3 URI: {s3_uri}")

    parts = s3_uri[5:].split('/', 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ''
    return bucket, key


def read_s3_text(s3_uri: str, encoding: str = 'utf-8') -> str:
    """
    Read text content from S3.

    Args:
        s3_uri: S3 URI to text file
        encoding: Text encoding (default utf-8)

    Returns:
        Text content as string
    """
    bucket, key = parse_s3_uri(s3_uri)
    try:
        response = get_s3_client().get_object(Bucket=bucket, Key=key)
        return response['Body'].read().decode(encoding)
    except ClientError as e:
        logger.error(f"Failed to read S3 text from {s3_uri}: {e}")
        raise


def read_s3_json(s3_uri: str) -> dict:
    """Read JSON content from S3."""
    text = read_s3_text(s3_uri)
    return json.loads(text)


def read_s3_binary(s3_uri: str) -> bytes:
    """Read binary content from S3."""
    bucket, key = parse_s3_uri(s3_uri)
    try:
        response = get_s3_client().get_object(Bucket=bucket, Key=key)
        return response['Body'].read()
    except ClientError as e:
        logger.error(f"Failed to read S3 binary from {s3_uri}: {e}")
        raise


def write_s3_text(s3_uri: str, content: str, encoding: str = 'utf-8') -> str:
    """
    Write text content to S3.

    Args:
        s3_uri: Destination S3 URI
        content: Text content to write
        encoding: Text encoding (default utf-8)

    Returns:
        The S3 URI that was written to
    """
    bucket, key = parse_s3_uri(s3_uri)
    try:
        get_s3_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode(encoding),
            ContentType='text/plain'
        )
        logger.info(f"Wrote text to {s3_uri}")
        return s3_uri
    except ClientError as e:
        logger.error(f"Failed to write S3 text to {s3_uri}: {e}")
        raise


def write_s3_json(s3_uri: str, data: dict) -> str:
    """
    Write JSON content to S3.

    Args:
        s3_uri: Destination S3 URI
        data: Data to write as JSON

    Returns:
        The S3 URI that was written to
    """
    content = json.dumps(data, indent=2)
    bucket, key = parse_s3_uri(s3_uri)
    try:
        get_s3_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode('utf-8'),
            ContentType='application/json'
        )
        logger.info(f"Wrote JSON to {s3_uri}")
        return s3_uri
    except ClientError as e:
        logger.error(f"Failed to write S3 JSON to {s3_uri}: {e}")
        raise


def write_s3_binary(s3_uri: str, content: bytes, content_type: str = 'application/octet-stream') -> str:
    """
    Write binary content to S3.

    Args:
        s3_uri: Destination S3 URI
        content: Binary content to write
        content_type: MIME type of the content

    Returns:
        The S3 URI that was written to
    """
    bucket, key = parse_s3_uri(s3_uri)
    try:
        get_s3_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type
        )
        logger.info(f"Wrote binary to {s3_uri}")
        return s3_uri
    except ClientError as e:
        logger.error(f"Failed to write S3 binary to {s3_uri}: {e}")
        raise


def s3_object_exists(s3_uri: str) -> bool:
    """Check if S3 object exists."""
    bucket, key = parse_s3_uri(s3_uri)
    try:
        get_s3_client().head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


# ============================================================================
# DynamoDB Operations
# ============================================================================

def get_table(table_name: str):
    """Get DynamoDB table resource."""
    return get_dynamodb().Table(table_name)


def put_item(table_name: str, item: Dict[str, Any]) -> None:
    """
    Put item into DynamoDB table.

    Args:
        table_name: DynamoDB table name
        item: Item data as dictionary
    """
    table = get_table(table_name)
    try:
        table.put_item(Item=item)
        logger.info(f"Put item to {table_name}: {item.get('document_id', 'unknown')}")
    except ClientError as e:
        logger.error(f"Failed to put item to {table_name}: {e}")
        raise


def get_item(table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get item from DynamoDB table.

    Args:
        table_name: DynamoDB table name
        key: Primary key (e.g., {'document_id': 'abc123'})

    Returns:
        Item dictionary or None if not found
    """
    table = get_table(table_name)
    try:
        response = table.get_item(Key=key)
        return response.get('Item')
    except ClientError as e:
        logger.error(f"Failed to get item from {table_name}: {e}")
        raise


def update_item(table_name: str, key: Dict[str, Any], updates: Dict[str, Any]) -> None:
    """
    Update item in DynamoDB table.

    Args:
        table_name: DynamoDB table name
        key: Primary key
        updates: Dictionary of attributes to update

    Example:
        update_item('Documents', {'document_id': '123'}, {'status': 'processing'})
    """
    table = get_table(table_name)

    # Build update expression
    update_expr = "SET " + ", ".join([f"#{k} = :{k}" for k in updates.keys()])
    expr_attr_names = {f"#{k}": k for k in updates.keys()}
    expr_attr_values = {f":{k}": v for k, v in updates.items()}

    try:
        table.update_item(
            Key=key,
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values
        )
        logger.info(f"Updated item in {table_name}: {key}")
    except ClientError as e:
        logger.error(f"Failed to update item in {table_name}: {e}")
        raise


def query_items(table_name: str, key_condition: str, expr_attr_values: Dict[str, Any]) -> list:
    """
    Query items from DynamoDB table.

    Args:
        table_name: DynamoDB table name
        key_condition: Key condition expression
        expr_attr_values: Expression attribute values

    Returns:
        List of items

    Example:
        items = query_items(
            'Metering',
            'document_id = :id',
            {':id': 'doc-123'}
        )
    """
    table = get_table(table_name)
    try:
        response = table.query(
            KeyConditionExpression=key_condition,
            ExpressionAttributeValues=expr_attr_values
        )
        return response.get('Items', [])
    except ClientError as e:
        logger.error(f"Failed to query {table_name}: {e}")
        raise
