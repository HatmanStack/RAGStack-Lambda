"""
ProcessText Lambda

Handles text-based document extraction (HTML, TXT, CSV, JSON, XML, EML, EPUB, DOCX, XLSX).
Routes to appropriate extractor based on content sniffing.

Input event:
{
    "document_id": "abc123",
    "input_s3_uri": "s3://input-bucket/uploads/doc.html",
    "output_s3_prefix": "s3://output-bucket/processed/abc123/",
    "fileType": "text",
    "detectedType": "html"
}

Output:
{
    "document_id": "abc123",
    "status": "ocr_complete",
    "total_pages": 1,
    "is_text_native": true,
    "output_s3_uri": "s3://output-bucket/processed/abc123/full_text.txt",
    "pages": [{"page_number": 1, "text": "..."}]
}
"""

import logging
import os
from datetime import UTC, datetime

import boto3

from ragstack_common.appsync import publish_document_update
from ragstack_common.models import Status
from ragstack_common.storage import update_item
from ragstack_common.text_extractors import extract_text

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level AWS clients (reused across warm invocations)
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")


def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Parse S3 URI into bucket and key."""
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {s3_uri}")
    path = s3_uri[5:]  # Remove 's3://'
    parts = path.split("/", 1)
    if len(parts) < 2 or not parts[1]:
        raise ValueError(f"S3 URI must include a key/path: {s3_uri}")
    return parts[0], parts[1]


def _extract_filename(input_s3_uri: str) -> str:
    """Extract filename from S3 URI."""
    parts = input_s3_uri.split("/")
    return parts[-1] if parts else "document"


def lambda_handler(event, context):
    """
    Main Lambda handler for text-based file processing.
    """
    tracking_table = os.environ.get("TRACKING_TABLE")
    if not tracking_table:
        raise ValueError("TRACKING_TABLE environment variable is required")

    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    logger.info(f"ProcessText: Received event: {event}")

    document_id = None
    filename = None

    try:
        # Extract event data
        document_id = event["document_id"]
        input_s3_uri = event["input_s3_uri"]
        output_s3_prefix = event["output_s3_prefix"]
        detected_type = event.get("detectedType", "txt")

        filename = _extract_filename(input_s3_uri)
        logger.info(f"Processing text file: {filename} (type: {detected_type})")

        # Update status to processing
        update_item(
            tracking_table,
            {"document_id": document_id},
            {"status": Status.PROCESSING.value, "updated_at": datetime.now(UTC).isoformat()},
        )

        # Publish real-time update
        publish_document_update(graphql_endpoint, document_id, filename, "PROCESSING")

        # Download file from S3
        input_bucket, input_key = _parse_s3_uri(input_s3_uri)
        response = s3_client.get_object(Bucket=input_bucket, Key=input_key)
        content = response["Body"].read()

        logger.info(f"Downloaded {len(content)} bytes from {input_s3_uri}")

        # Extract text using text_extractors library
        result = extract_text(content, filename)

        logger.info(
            f"Extraction complete: type={result.file_type}, "
            f"words={result.word_count}, title={result.title}"
        )

        if result.parse_warning:
            logger.warning(f"Parse warning: {result.parse_warning}")

        # Write markdown output to S3
        output_bucket, output_prefix = _parse_s3_uri(output_s3_prefix)
        output_key = f"{output_prefix}full_text.txt".replace("//", "/")

        s3_client.put_object(
            Bucket=output_bucket,
            Key=output_key,
            Body=result.markdown.encode("utf-8"),
            ContentType="text/plain",
        )

        output_s3_uri = f"s3://{output_bucket}/{output_key}"
        logger.info(f"Wrote extracted text to: {output_s3_uri}")

        # Update DynamoDB tracking table
        now = datetime.now(UTC).isoformat()
        table = dynamodb.Table(tracking_table)

        update_expression = (
            "SET #status = :status, "
            "#type = if_not_exists(#type, :type), "
            "total_pages = :total_pages, "
            "is_text_native = :is_text_native, "
            "output_s3_uri = :output_s3_uri, "
            "ocr_backend = :ocr_backend, "
            "updated_at = :updated_at, "
            "created_at = if_not_exists(created_at, :created_at), "
            "filename = if_not_exists(filename, :filename), "
            "input_s3_uri = if_not_exists(input_s3_uri, :input_s3_uri), "
            "detected_file_type = :detected_file_type"
        )

        expression_values = {
            ":status": Status.OCR_COMPLETE.value,
            ":type": "document",
            ":total_pages": 1,
            ":is_text_native": True,
            ":output_s3_uri": output_s3_uri,
            ":ocr_backend": "text_extraction",
            ":updated_at": now,
            ":created_at": now,
            ":filename": filename,
            ":input_s3_uri": input_s3_uri,
            ":detected_file_type": result.file_type,
        }

        # Add parse warning if present
        if result.parse_warning:
            update_expression += ", parse_warning = :parse_warning"
            expression_values[":parse_warning"] = result.parse_warning

        table.update_item(
            Key={"document_id": document_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={"#status": "status", "#type": "type"},
            ExpressionAttributeValues=expression_values,
        )

        logger.info(f"Updated tracking table for document: {document_id}")

        # Publish completion update
        publish_document_update(
            graphql_endpoint,
            document_id,
            filename,
            "OCR_COMPLETE",
            total_pages=1,
        )

        # Truncate text for Step Functions output (16KB limit)
        preview_text = result.markdown[:500] if result.markdown else ""

        # Return result for Step Functions
        return {
            "document_id": document_id,
            "status": Status.OCR_COMPLETE.value,
            "total_pages": 1,
            "is_text_native": True,
            "output_s3_uri": output_s3_uri,
            "pages": [
                {
                    "page_number": 1,
                    "text": preview_text,
                    "image_s3_uri": None,
                    "ocr_backend": "text_extraction",
                }
            ],
        }

    except Exception as e:
        logger.error(f"Text processing failed: {e}", exc_info=True)

        # Update status to failed
        try:
            if tracking_table and document_id:
                update_item(
                    tracking_table,
                    {"document_id": document_id},
                    {
                        "status": Status.FAILED.value,
                        "error_message": str(e),
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                )
                # Publish failure update
                publish_document_update(
                    graphql_endpoint,
                    document_id,
                    filename or "unknown",
                    "FAILED",
                    error_message=str(e),
                )
        except Exception as update_error:
            logger.error(f"Failed to update DynamoDB: {update_error}")

        raise
