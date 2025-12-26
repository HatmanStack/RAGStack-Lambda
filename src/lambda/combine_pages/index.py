"""
Combine Pages Lambda

Merges partial text files from batch processing into final extracted_text.txt.
Updates DynamoDB tracking table with final status and invokes IngestToKB.

Can be invoked two ways:
1. From Step Functions Map state (with batch_results array) - legacy mode
2. From BatchProcessor Lambda (without batch_results) - lists S3 for partial files

Input event:
{
    "document_id": "abc123",
    "output_s3_prefix": "s3://bucket/output/abc123/",
    "total_pages": 150,
    "batch_results": [...]  # Optional - if not provided, lists S3 for partial files
}

Output:
{
    "document_id": "abc123",
    "status": "ocr_complete",
    "total_pages": 150,
    "output_s3_uri": "s3://bucket/output/abc123/extracted_text.txt"
}
"""

import json
import logging
import os
import re
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


def _list_partial_files(output_s3_prefix: str) -> list[dict]:
    """
    List partial files from S3 matching pages_XXX-YYY.txt pattern.

    Returns list of dicts with page_start, page_end, and partial_output_uri.
    """
    bucket, prefix = _parse_s3_uri(output_s3_prefix)
    if not prefix.endswith("/"):
        prefix += "/"

    s3 = boto3.client("s3")

    # List objects with the prefix
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    partial_files = []
    pattern = re.compile(r"pages_(\d+)-(\d+)\.txt$")

    for obj in response.get("Contents", []):
        key = obj["Key"]
        match = pattern.search(key)
        if match:
            page_start = int(match.group(1))
            page_end = int(match.group(2))
            partial_files.append(
                {
                    "page_start": page_start,
                    "page_end": page_end,
                    "partial_output_uri": f"s3://{bucket}/{key}",
                }
            )

    # Sort by page_start
    partial_files.sort(key=lambda x: x["page_start"])

    logger.info(f"Found {len(partial_files)} partial files in {output_s3_prefix}")
    return partial_files


def _invoke_ingest_to_kb(document_id: str, output_s3_uri: str) -> None:
    """Invoke IngestToKB Lambda asynchronously."""
    ingest_function_arn = os.environ.get("INGEST_TO_KB_FUNCTION_ARN")
    if not ingest_function_arn:
        logger.warning("INGEST_TO_KB_FUNCTION_ARN not set, skipping ingestion")
        return

    lambda_client = boto3.client("lambda")

    payload = {
        "document_id": document_id,
        "output_s3_uri": output_s3_uri,
    }

    logger.info(f"Invoking IngestToKB for document {document_id}")

    lambda_client.invoke(
        FunctionName=ingest_function_arn,
        InvocationType="Event",  # Async invocation
        Payload=json.dumps(payload),
    )

    logger.info("IngestToKB invoked successfully")


def lambda_handler(event, context):
    """
    Main Lambda handler.

    Combines partial text files, updates tracking table, and triggers ingestion.
    """
    logger.info(f"CombinePages event: {event}")

    # Get environment variables
    tracking_table = os.environ.get("TRACKING_TABLE")
    if not tracking_table:
        raise ValueError("TRACKING_TABLE environment variable is required")

    document_id = event["document_id"]
    output_s3_prefix = event["output_s3_prefix"]
    total_pages = event["total_pages"]

    # Get batch results - either from event or by listing S3
    batch_results = event.get("batch_results")
    if batch_results:
        logger.info(f"Using {len(batch_results)} batch results from event")
        sorted_results = sorted(batch_results, key=lambda x: x["page_start"])
    else:
        logger.info("No batch_results in event, listing S3 for partial files")
        sorted_results = _list_partial_files(output_s3_prefix)

    if not sorted_results:
        raise ValueError(f"No partial files found for document {document_id}")

    # Calculate pages found for logging (threshold already checked by BatchProcessor)
    pages_found = 0
    for result in sorted_results:
        page_start = result["page_start"]
        page_end = result["page_end"]
        pages_found += page_end - page_start + 1

    logger.info(
        f"Combining {len(sorted_results)} batches ({pages_found}/{total_pages} pages) "
        f"for document {document_id}"
    )

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

    # Trigger IngestToKB asynchronously (for async mode from BatchProcessor)
    # In Step Functions mode, IngestToKB is called as next state, but we call anyway
    # IngestToKB is idempotent so duplicate calls are safe
    _invoke_ingest_to_kb(document_id, output_uri)

    return {
        "document_id": document_id,
        "status": Status.OCR_COMPLETE.value,
        "total_pages": total_pages,
        "output_s3_uri": output_uri,
        "pages_processed": pages_processed,
    }
