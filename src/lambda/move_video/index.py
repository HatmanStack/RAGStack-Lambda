"""
Move Video Lambda

Moves video files from input/ to content/{docId}/ for visual embedding ingestion.
Triggered by EventBridge when Step Functions media pipeline completes successfully.

This Lambda:
1. Parses Step Functions success event to extract document_id
2. Looks up tracking table to get video location and filename
3. Creates metadata.json file for KB visual embeddings
4. Copies video to content/{docId}/video.mp4
5. Deletes original from input/
6. Updates tracking table with new location
"""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

from ragstack_common.storage import parse_s3_uri

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")


def parse_event(event: dict) -> dict:
    """
    Parse EventBridge Step Functions event to extract document info.

    Args:
        event: EventBridge event with Step Functions execution details

    Returns:
        Dict with document_id and input details
    """
    detail = event.get("detail", {})

    # Parse execution output to get document_id
    output_str = detail.get("output", "{}")
    output = json.loads(output_str) if isinstance(output_str, str) else output_str
    document_id = output.get("document_id")

    # Parse execution input to get original S3 URI
    input_str = detail.get("input", "{}")
    input_data = json.loads(input_str) if isinstance(input_str, str) else input_str
    input_s3_uri = input_data.get("input_s3_uri")

    return {
        "document_id": document_id,
        "input_s3_uri": input_s3_uri,
        "execution_arn": detail.get("executionArn"),
        "status": detail.get("status"),
    }


def create_metadata(document_id: str, filename: str) -> dict:
    """Create metadata structure for KB visual embeddings."""
    return {
        "metadataAttributes": {
            "content_type": "visual",
            "document_id": document_id,
            "media_type": "video",
            "filename": filename,
        }
    }


def lambda_handler(event: dict, context) -> dict:
    """
    Move video from input/ to content/{docId}/ for visual embedding ingestion.

    Args:
        event: EventBridge Step Functions execution status change event
        context: Lambda context

    Returns:
        Result dict with status and new S3 URI
    """
    logger.info(f"Processing event: {json.dumps(event)}")

    tracking_table_name = os.environ.get("TRACKING_TABLE")
    data_bucket = os.environ.get("DATA_BUCKET")

    if not tracking_table_name:
        raise ValueError("TRACKING_TABLE environment variable is required")

    # Parse event
    event_data = parse_event(event)
    document_id = event_data.get("document_id")

    if not document_id:
        logger.warning("No document_id in event output, skipping")
        return {"status": "skipped", "message": "No document_id in event"}

    logger.info(f"Processing video for document: {document_id}")

    # Get tracking table
    tracking_table = dynamodb.Table(tracking_table_name)

    # Look up document in tracking table
    try:
        response = tracking_table.get_item(Key={"document_id": document_id})
        doc_item = response.get("Item")
    except ClientError as e:
        logger.error(f"Failed to get document from tracking table: {e}")
        raise

    if not doc_item:
        logger.warning(f"Document {document_id} not found in tracking table")
        return {"status": "skipped", "message": f"Document {document_id} not found"}

    # Check if this is a media file
    doc_type = doc_item.get("type", "")
    if doc_type != "media":
        logger.info(f"Document {document_id} is not media type (type={doc_type}), skipping")
        return {"status": "skipped", "message": f"Not a video file (type={doc_type})"}

    filename = doc_item.get("filename", "video.mp4")
    current_s3_uri = doc_item.get("input_s3_uri", "")

    # Parse current location
    source_bucket, source_key = parse_s3_uri(current_s3_uri)

    # Use data bucket from env or extract from current URI
    if not data_bucket and source_bucket:
        data_bucket = source_bucket

    if not data_bucket:
        raise ValueError("DATA_BUCKET environment variable is required or bucket not in URI")

    # Check if already moved (idempotency)
    if current_s3_uri and f"content/{document_id}/video.mp4" in current_s3_uri:
        logger.info(f"Video already moved to content folder: {current_s3_uri}")
        return {"status": "skipped", "message": "Video already moved", "s3_uri": current_s3_uri}

    # Define destination
    dest_key = f"content/{document_id}/video.mp4"
    dest_uri = f"s3://{data_bucket}/{dest_key}"
    metadata_key = f"{dest_key}.metadata.json"

    # Check if source exists
    if source_key:
        try:
            s3_client.head_object(Bucket=data_bucket, Key=source_key)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                logger.info(f"Source video not found at {source_key}, may already be moved")
                return {"status": "skipped", "message": "Source video not found"}
            raise
    else:
        logger.warning("No source key found in tracking table")
        return {"status": "skipped", "message": "No source key in tracking table"}

    try:
        # Step 1: Create and upload metadata file FIRST
        metadata = create_metadata(document_id, filename)
        logger.info(f"Uploading metadata to {metadata_key}")
        s3_client.put_object(
            Bucket=data_bucket,
            Key=metadata_key,
            Body=json.dumps(metadata),
            ContentType="application/json",
        )

        # Step 2: Copy video to destination
        logger.info(f"Copying video from {source_key} to {dest_key}")
        copy_source = {"Bucket": data_bucket, "Key": source_key}
        s3_client.copy_object(
            Bucket=data_bucket,
            Key=dest_key,
            CopySource=copy_source,
        )

        # Step 3: Delete original (only after successful copy)
        logger.info(f"Deleting original video at {source_key}")
        s3_client.delete_object(Bucket=data_bucket, Key=source_key)

        # Step 4: Update tracking table with new location
        tracking_table.update_item(
            Key={"document_id": document_id},
            UpdateExpression="SET input_s3_uri = :uri",
            ExpressionAttributeValues={":uri": dest_uri},
        )
        logger.info(f"Updated tracking table with new location: {dest_uri}")

        return {
            "status": "success",
            "document_id": document_id,
            "new_s3_uri": dest_uri,
            "metadata_uri": f"s3://{data_bucket}/{metadata_key}",
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to move video: {error_code} - {error_msg}")
        raise
