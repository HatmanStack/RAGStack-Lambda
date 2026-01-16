"""
Storage utilities for S3 and DynamoDB operations.

Provides simple, consistent interface for reading/writing data.
"""

import json
import logging
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError

from ragstack_common.metadata_normalizer import normalize_metadata_for_s3

logger = logging.getLogger(__name__)

# Lazy-loaded AWS clients (initialized on first use)
_s3_client = None
_dynamodb = None


def get_s3_client():
    """Get or create S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def get_dynamodb():
    """Get or create DynamoDB resource."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


# ============================================================================
# S3 Operations
# ============================================================================


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """
    Parse S3 URI or HTTPS S3 URL into bucket and key.

    Args:
        s3_uri: S3 URI like "s3://bucket-name/path/to/file.txt" or
                HTTPS URL like "https://s3.region.amazonaws.com/bucket/key"

    Returns:
        Tuple of (bucket, key)

    Raises:
        ValueError: If s3_uri is empty, None, or not a valid S3 URI/URL

    Example:
        bucket, key = parse_s3_uri("s3://my-bucket/docs/file.pdf")
        # bucket = "my-bucket"
        # key = "docs/file.pdf"
    """
    # CORRECTNESS: Check for None/empty before calling string methods to prevent
    # AttributeError on None or misleading "Invalid S3 URI: " error on empty string.
    # Type hint says str but callers may pass None from optional fields.
    if not s3_uri:
        raise ValueError("S3 URI cannot be empty or None")

    # Handle s3:// URI format
    if s3_uri.startswith("s3://"):
        parts = s3_uri[5:].split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""
        return bucket, key

    # Handle HTTPS S3 URL format (returned by AWS Transcribe, etc.)
    # Format: https://s3.region.amazonaws.com/bucket/key
    if s3_uri.startswith("https://s3.") and ".amazonaws.com/" in s3_uri:
        # Extract path after amazonaws.com/
        path_start = s3_uri.find(".amazonaws.com/") + len(".amazonaws.com/")
        path = s3_uri[path_start:]
        parts = path.split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""
        return bucket, key

    raise ValueError(f"Invalid S3 URI: {s3_uri}")


def read_s3_text(s3_uri: str, encoding: str = "utf-8") -> str:
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
        return response["Body"].read().decode(encoding)
    except ClientError:
        logger.exception(f"Failed to read S3 text from {s3_uri}")
        raise


def read_s3_binary(s3_uri: str) -> bytes:
    """Read binary content from S3."""
    bucket, key = parse_s3_uri(s3_uri)
    try:
        response = get_s3_client().get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except ClientError:
        logger.exception(f"Failed to read S3 binary from {s3_uri}")
        raise


def write_s3_text(s3_uri: str, content: str, encoding: str = "utf-8") -> str:
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
            Bucket=bucket, Key=key, Body=content.encode(encoding), ContentType="text/plain"
        )
        logger.info(f"Wrote text to {s3_uri}")
        return s3_uri
    except ClientError:
        logger.exception(f"Failed to write S3 text to {s3_uri}")
        raise


def delete_s3_object(s3_uri: str) -> None:
    """
    Delete an object from S3.

    Args:
        s3_uri: S3 URI (s3://bucket/key)

    Raises:
        ClientError: If deletion fails
    """
    bucket, key = parse_s3_uri(s3_uri)
    get_s3_client().delete_object(Bucket=bucket, Key=key)
    logger.debug(f"Deleted S3 object: {s3_uri}")


def generate_presigned_url(
    bucket: str,
    key: str,
    expiration: int = 3600,
    allowed_bucket: str | None = None,
) -> str | None:
    """
    Generate presigned URL for S3 object download.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        expiration: URL expiration time in seconds (default 1 hour)
        allowed_bucket: If provided, only generates URLs for this bucket (security)

    Returns:
        Presigned URL or None if generation fails or bucket not allowed
    """
    # Security: Only allow presigned URLs for specific bucket if configured
    if allowed_bucket and bucket != allowed_bucket:
        logger.warning(f"Attempted presigned URL for unauthorized bucket: {bucket}")
        return None
    try:
        return get_s3_client().generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expiration
        )
    except Exception as e:
        logger.error(f"Failed to generate presigned URL for {bucket}/{key}: {e}")
        return None


def write_metadata_to_s3(s3_uri: str, metadata: dict[str, Any]) -> str:
    """
    Write metadata to S3 as a .metadata.json file alongside the content file.

    For S3 Vectors knowledge bases, metadata must be stored in S3 rather than
    provided inline. The metadata file must be in the same location as the
    content file with .metadata.json suffix.

    Args:
        s3_uri: S3 URI of the content file (e.g., s3://bucket/path/file.txt)
        metadata: Dictionary of metadata key-value pairs

    Returns:
        S3 URI of the metadata file
    """
    bucket, key = parse_s3_uri(s3_uri)

    if not key:
        raise ValueError(f"Invalid S3 URI: missing object key in {s3_uri}")

    # Create metadata file key (same location with .metadata.json suffix)
    metadata_key = f"{key}.metadata.json"
    metadata_uri = f"s3://{bucket}/{metadata_key}"

    # Normalize metadata for S3 Vectors (convert multi-value fields to arrays)
    normalized_metadata = normalize_metadata_for_s3(metadata)

    # Build metadata JSON in Bedrock KB format
    metadata_content = {"metadataAttributes": normalized_metadata}

    # Write to S3
    get_s3_client().put_object(
        Bucket=bucket,
        Key=metadata_key,
        Body=json.dumps(metadata_content),
        ContentType="application/json",
    )

    logger.info(f"Wrote metadata to {metadata_uri}")
    return metadata_uri


# ============================================================================
# Validation Utilities
# ============================================================================


def is_valid_uuid(value: str) -> bool:
    """
    Check if string is a valid UUID format.

    Args:
        value: String to validate

    Returns:
        True if valid UUID format, False otherwise
    """
    if not value:
        return False
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def extract_filename_from_s3_uri(s3_uri: str, default: str = "document") -> str:
    """
    Extract filename from S3 URI.

    Args:
        s3_uri: S3 URI like "s3://bucket/path/to/file.txt"
        default: Default value if extraction fails

    Returns:
        Filename portion of the URI (e.g., "file.txt")
    """
    if not s3_uri:
        return default
    parts = s3_uri.split("/")
    return parts[-1] if parts and parts[-1] else default


def get_file_type_from_filename(filename: str) -> str:
    """
    Extract file type from filename.

    Args:
        filename: Original filename

    Returns:
        File extension without dot, lowercase (e.g., "pdf", "jpg")
    """
    if not filename or "." not in filename:
        return "unknown"
    return filename.rsplit(".", 1)[-1].lower()


# ============================================================================
# DynamoDB Operations
# ============================================================================


def get_table(table_name: str):
    """Get DynamoDB table resource."""
    return get_dynamodb().Table(table_name)


def put_item(table_name: str, item: dict[str, Any]) -> None:
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
    except ClientError:
        logger.exception(f"Failed to put item to {table_name}")
        raise


def get_item(table_name: str, key: dict[str, Any]) -> dict[str, Any] | None:
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
        return response.get("Item")
    except ClientError:
        logger.exception(f"Failed to get item from {table_name}")
        raise


def update_item(table_name: str, key: dict[str, Any], updates: dict[str, Any]) -> None:
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
    update_expr = "SET " + ", ".join([f"#{k} = :{k}" for k in updates])
    expr_attr_names = {f"#{k}": k for k in updates}
    expr_attr_values = {f":{k}": v for k, v in updates.items()}

    try:
        table.update_item(
            Key=key,
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )
        logger.info(f"Updated item in {table_name}: {key}")
    except ClientError:
        logger.exception(f"Failed to update item in {table_name}")
        raise
