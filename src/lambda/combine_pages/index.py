"""
Combine Pages Lambda

Merges partial text files from batch processing into final extracted_text.txt.
Updates DynamoDB tracking table with final status.

Input event (from Map state results):
{
    "document_id": "abc123",
    "output_s3_prefix": "s3://bucket/output/abc123/",
    "total_pages": 150,
    "batch_results": [
        {"page_start": 1, "page_end": 10, "partial_output_uri": "s3://..."},
        {"page_start": 11, "page_end": 20, "partial_output_uri": "s3://..."},
        ...
    ]
}

Output:
{
    "document_id": "abc123",
    "status": "ocr_complete",
    "total_pages": 150,
    "output_s3_uri": "s3://bucket/output/abc123/extracted_text.txt"
}
"""

import logging
import os
from datetime import UTC, datetime

import boto3

from ragstack_common.appsync import publish_document_update
from ragstack_common.models import Status
from ragstack_common.storage import delete_s3_object, read_s3_text, write_s3_text

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Parse S3 URI into bucket and key."""
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {s3_uri}")
    path = s3_uri[5:]
    bucket, key = path.split("/", 1)
    return bucket, key


def lambda_handler(event, context):
    """
    Main Lambda handler.

    Combines partial text files and updates tracking table.
    """
    logger.info(f"CombinePages event: {event}")

    # Get environment variables
    tracking_table = os.environ.get("TRACKING_TABLE")
    if not tracking_table:
        raise ValueError("TRACKING_TABLE environment variable is required")

    document_id = event["document_id"]
    output_s3_prefix = event["output_s3_prefix"]
    total_pages = event["total_pages"]
    batch_results = event["batch_results"]

    logger.info(f"Combining {len(batch_results)} batch results for document {document_id}")

    # Sort by page_start to ensure correct order
    sorted_results = sorted(batch_results, key=lambda x: x["page_start"])

    # Read and concatenate all partial files
    full_text_parts = []
    pages_processed = 0

    for result in sorted_results:
        partial_uri = result["partial_output_uri"]
        page_start = result["page_start"]
        page_end = result["page_end"]

        logger.info(f"Reading partial file: {partial_uri}")
        try:
            partial_text = read_s3_text(partial_uri)
            full_text_parts.append(partial_text)
            pages_processed += result.get("pages_processed", page_end - page_start + 1)
        except Exception as e:
            logger.error(f"Failed to read partial file {partial_uri}: {e}")
            raise

    # Write combined output
    bucket, base_key = _parse_s3_uri(output_s3_prefix)
    if not base_key.endswith("/"):
        base_key += "/"
    output_key = f"{base_key}extracted_text.txt"
    output_uri = f"s3://{bucket}/{output_key}"

    full_text = "\n\n".join(full_text_parts)
    write_s3_text(output_uri, full_text)
    logger.info(f"Wrote combined text ({len(full_text)} chars) to {output_uri}")

    # Clean up partial files
    for result in sorted_results:
        partial_uri = result["partial_output_uri"]
        try:
            delete_s3_object(partial_uri)
            logger.info(f"Deleted partial file: {partial_uri}")
        except Exception as e:
            # Non-fatal - log and continue
            logger.warning(f"Failed to delete partial file {partial_uri}: {e}")

    # Update DynamoDB tracking table
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(tracking_table)

    table.update_item(
        Key={"document_id": document_id},
        UpdateExpression=(
            "SET #status = :status, "
            "total_pages = :total_pages, "
            "output_s3_uri = :output_s3_uri, "
            "updated_at = :updated_at"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": Status.OCR_COMPLETE.value,
            ":total_pages": total_pages,
            ":output_s3_uri": output_uri,
            ":updated_at": datetime.now(UTC).isoformat(),
        },
    )
    logger.info(f"Updated tracking table for document {document_id}")

    # Publish real-time update
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")
    if graphql_endpoint:
        # Get filename from tracking table for the update
        response = table.get_item(Key={"document_id": document_id})
        filename = response.get("Item", {}).get("filename", "unknown")

        publish_document_update(
            graphql_endpoint,
            document_id,
            filename,
            "OCR_COMPLETE",
            total_pages=total_pages,
        )

    return {
        "document_id": document_id,
        "status": Status.OCR_COMPLETE.value,
        "total_pages": total_pages,
        "output_s3_uri": output_uri,
        "pages_processed": pages_processed,
    }
