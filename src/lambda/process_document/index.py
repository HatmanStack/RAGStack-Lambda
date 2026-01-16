"""
Document Processor Lambda

Handles document validation, OCR, text extraction, and image extraction.
OCR backend and model are read from DynamoDB configuration (ConfigurationManager).

Input event:
{
    "document_id": "abc123",
    "input_s3_uri": "s3://input-bucket/uploads/doc.pdf",
    "output_s3_prefix": "s3://output-bucket/processed/abc123/"
}

Output:
{
    "document_id": "abc123",
    "status": "ocr_complete",
    "total_pages": 5,
    "is_text_native": true,
    "output_s3_uri": "s3://output-bucket/processed/abc123/full_text.txt",
    "pages": [...]
}
"""

import json
import logging
import os
from datetime import UTC, datetime

import boto3

from ragstack_common.appsync import publish_document_update
from ragstack_common.config import ConfigurationManager
from ragstack_common.models import Document, Status

# Import from shared package (installed via pip)
from ragstack_common.ocr import OcrService
from ragstack_common.storage import parse_s3_uri, update_item

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level AWS clients (reused across warm invocations)
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# Module-level initialization (lazy-initialized to avoid import-time failures)
_config_manager = None


def _get_config_manager():
    """Get or initialize ConfigurationManager (lazy initialization)."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


def _process_scraped_markdown(document_id, input_s3_uri, output_s3_prefix, tracking_table):
    """
    Process scraped markdown files by copying directly to output bucket.

    Scraped markdown (.scraped.md) files are already text and don't need OCR.
    They are copied directly from input to output bucket.
    """
    logger.info(f"Processing scraped markdown: {input_s3_uri}")

    # Parse input S3 URI
    input_bucket, input_key = parse_s3_uri(input_s3_uri)

    # Read content from input bucket
    response = s3_client.get_object(Bucket=input_bucket, Key=input_key)
    content = response["Body"].read().decode("utf-8")

    # Extract metadata from S3 object (set by scrape_process Lambda)
    metadata = response.get("Metadata", {})
    title = metadata.get("title", "")
    source_url = metadata.get("source_url", "")
    # Use title as filename, fall back to source URL or document ID
    filename = title or source_url or f"{document_id}.scraped.md"
    logger.info(f"Extracted metadata - title: {title}, source_url: {source_url}")

    # Parse output prefix to get bucket and key prefix
    output_bucket, output_prefix = parse_s3_uri(output_s3_prefix)

    # Write to output bucket as full_text.txt
    output_key = f"{output_prefix}full_text.txt".replace("//", "/")
    s3_client.put_object(
        Bucket=output_bucket,
        Key=output_key,
        Body=content.encode("utf-8"),
        ContentType="text/plain",
    )

    output_s3_uri = f"s3://{output_bucket}/{output_key}"
    logger.info(f"Copied scraped markdown to: {output_s3_uri}")

    # Update tracking table with full document info
    # For scraped documents, the tracking record may not exist yet
    # so we include all required fields (created_at, filename, input_s3_uri)
    now = datetime.now(UTC).isoformat()
    table = dynamodb.Table(tracking_table)

    # Determine document type: only .scraped.md files are "scraped", regular .md are "document"
    is_scraped = input_s3_uri.endswith(".scraped.md")
    doc_type = "scraped" if is_scraped else "document"

    # Use DynamoDB update with if_not_exists for fields that should only be set once
    # Include source_url for scraped content so query_kb can return the original web URL
    logger.info(
        f"[TRACKING] Updating {doc_type} doc={document_id}: "
        f"source_url={source_url}, filename={filename}"
    )
    table.update_item(
        Key={"document_id": document_id},
        UpdateExpression=(
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
            "source_url = if_not_exists(source_url, :source_url)"
        ),
        ExpressionAttributeNames={"#status": "status", "#type": "type"},
        ExpressionAttributeValues={
            ":status": Status.OCR_COMPLETE.value,
            ":type": doc_type,
            ":total_pages": 1,
            ":is_text_native": True,
            ":output_s3_uri": output_s3_uri,
            ":ocr_backend": "passthrough",
            ":updated_at": now,
            ":created_at": now,
            ":filename": filename,
            ":input_s3_uri": input_s3_uri,
            ":source_url": source_url,
        },
    )

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
                "text": content[:500] if content else "",
                "image_s3_uri": None,
                "ocr_backend": "passthrough",
            }
        ],
    }


def lambda_handler(event, context):
    """
    Main Lambda handler.
    """
    # Get environment variables (moved here for testability)
    tracking_table = os.environ.get("TRACKING_TABLE")
    if not tracking_table:
        raise ValueError("TRACKING_TABLE environment variable is required")

    logger.info(f"Processing document: {json.dumps(event)}")

    try:
        # Extract event data
        raw_document_id = event["document_id"]
        input_s3_uri = event["input_s3_uri"]
        output_s3_prefix = event["output_s3_prefix"]

        # Extract actual document_id from S3 key path
        # S3 key format: input/{document_id}/{filename}
        # State machine may have already extracted the document_id, or EventBridge may pass full key
        key_parts = raw_document_id.split("/")
        if len(key_parts) >= 2 and key_parts[0] == "input":
            document_id = key_parts[1]  # Extract UUID from path
            filename = key_parts[2] if len(key_parts) > 2 else "document.pdf"
        else:
            # State machine already extracted document_id, or it's in a different format
            document_id = raw_document_id
            # Try to extract filename from input_s3_uri
            input_parts = input_s3_uri.split("/")
            filename = input_parts[-1] if input_parts else "document.pdf"

        # Fix output_s3_prefix - EventBridge template produces wrong format
        # Received: s3://bucket/content/input/{doc_id}/{filename}/
        # Expected: s3://bucket/content/{doc_id}/
        if "/content/input/" in output_s3_prefix:
            bucket_and_prefix = output_s3_prefix.split("/content/input/")[0]
            output_s3_prefix = f"{bucket_and_prefix}/content/{document_id}/"

        logger.info(f"Parsed document_id: {document_id}, filename: {filename}")
        logger.info(f"Output S3 prefix: {output_s3_prefix}")

        # Skip processing for generated output files (prevent reprocessing loops)
        skip_suffixes = ("extracted_text.txt", "full_text.txt", "metadata.json")
        if input_s3_uri.endswith(skip_suffixes):
            logger.info(f"Skipping generated output file: {filename}")
            return {
                "document_id": document_id,
                "status": "skipped",
                "message": "Generated output file - not reprocessing",
            }

        # Check for markdown passthrough (.md and .scraped.md files skip OCR)
        if input_s3_uri.endswith(".md"):
            return _process_scraped_markdown(
                document_id, input_s3_uri, output_s3_prefix, tracking_table
            )

        # Read configuration from ConfigurationManager (runtime configuration)
        config_mgr = _get_config_manager()
        ocr_backend = config_mgr.get_parameter("ocr_backend", default="textract")
        bedrock_model_id = config_mgr.get_parameter(
            "bedrock_ocr_model_id", default="anthropic.claude-3-5-haiku-20241022-v1:0"
        )

        # Force Bedrock for formats not supported by Textract (WebP, AVIF)
        lower_uri = input_s3_uri.lower()
        if lower_uri.endswith((".webp", ".avif")) and ocr_backend == "textract":
            ocr_backend = "bedrock"
            logger.info(f"Forcing Bedrock OCR for unsupported Textract format: {filename}")

        logger.info(f"Using OCR backend: {ocr_backend}")
        if ocr_backend == "bedrock":
            logger.info(f"Using Bedrock OCR model: {bedrock_model_id}")

        # Update status to processing
        update_item(
            tracking_table,
            {"document_id": document_id},
            {"status": Status.PROCESSING.value, "updated_at": datetime.now(UTC).isoformat()},
        )

        # Publish real-time update (skip in batch mode to avoid spam)
        graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

        # Extract optional page range for batch processing
        page_start = event.get("page_start")
        page_end = event.get("page_end")
        is_batch_mode = page_start is not None and page_end is not None

        if not is_batch_mode:
            publish_document_update(graphql_endpoint, document_id, filename, "PROCESSING")

        # Create Document object (Phase 1 API)
        document = Document(
            document_id=document_id,
            filename=filename,
            input_s3_uri=input_s3_uri,
            output_s3_uri=output_s3_prefix,  # Will be updated by OcrService
            status=Status.PROCESSING,
            page_start=page_start,
            page_end=page_end,
        )

        # Create OCR service and process document (Phase 1 API)
        ocr_service = OcrService(
            region=os.environ.get("AWS_REGION"),
            backend=ocr_backend,
            bedrock_model_id=bedrock_model_id,
        )

        # Process document - returns updated Document object
        processed_document = ocr_service.process_document(document)

        # Check for processing errors
        if processed_document.status == Status.FAILED:
            raise Exception(processed_document.error_message or "OCR processing failed")

        # Update DynamoDB with results (skip in batch mode - CombinePages handles final status)
        if not is_batch_mode:
            logger.info(
                f"[TRACKING] Updating tracking table for doc={document_id}: "
                f"input_s3_uri={input_s3_uri}, filename={filename}, "
                f"output_s3_uri={processed_document.output_s3_uri}"
            )
            table = dynamodb.Table(tracking_table)
            table.update_item(
                Key={"document_id": document_id},
                UpdateExpression=(
                    "SET #status = :status, "
                    "total_pages = :total_pages, "
                    "is_text_native = :is_text_native, "
                    "output_s3_uri = :output_s3_uri, "
                    "updated_at = :updated_at, "
                    "input_s3_uri = if_not_exists(input_s3_uri, :input_s3_uri), "
                    "filename = if_not_exists(filename, :filename)"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": Status.OCR_COMPLETE.value,
                    ":total_pages": processed_document.total_pages,
                    ":is_text_native": processed_document.is_text_native or False,
                    ":output_s3_uri": processed_document.output_s3_uri,
                    ":updated_at": datetime.now(UTC).isoformat(),
                    ":input_s3_uri": input_s3_uri,
                    ":filename": filename,
                },
            )
            logger.info(f"[TRACKING] Successfully updated tracking table for doc={document_id}")

        # In batch mode, return partial result for Map state aggregation
        if is_batch_mode:
            logger.info(
                f"Batch mode complete: pages {page_start}-{page_end}, "
                f"output={processed_document.output_s3_uri}"
            )
            return {
                "document_id": document_id,
                "page_start": page_start,
                "page_end": page_end,
                "partial_output_uri": processed_document.output_s3_uri,
                "pages_processed": len(processed_document.pages),
            }

        # Publish real-time update (full document mode only)
        publish_document_update(
            graphql_endpoint,
            document_id,
            filename,
            "OCR_COMPLETE",
            total_pages=processed_document.total_pages,
        )

        # Return results for Step Functions (full document mode)
        return {
            "document_id": document_id,
            "status": Status.OCR_COMPLETE.value,
            "total_pages": processed_document.total_pages,
            "is_text_native": processed_document.is_text_native or False,
            "output_s3_uri": processed_document.output_s3_uri,
            "pages": [
                {
                    "page_number": p.page_number,
                    "text": p.text[:500] if p.text else "",  # Truncate for Step Functions
                    "image_s3_uri": getattr(p, "image_s3_uri", None),
                    "ocr_backend": p.ocr_backend,
                }
                for p in processed_document.pages
            ],
        }

    except Exception as e:
        logger.error(f"Document processing failed: {e}", exc_info=True)

        # Update status to failed
        try:
            tracking_table = os.environ.get("TRACKING_TABLE")
            raw_doc_id = event.get("document_id", "")
            key_parts = raw_doc_id.split("/")
            doc_id = key_parts[1] if len(key_parts) >= 2 and key_parts[0] == "input" else raw_doc_id
            if tracking_table:
                update_item(
                    tracking_table,
                    {"document_id": doc_id},
                    {
                        "status": Status.FAILED.value,
                        "error_message": str(e),
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                )
                # Publish failure update
                graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")
                publish_document_update(
                    graphql_endpoint,
                    doc_id,
                    event.get("filename", "unknown"),
                    "FAILED",
                    error_message=str(e),
                )
        except Exception as update_error:
            logger.error(f"Failed to update DynamoDB: {update_error}")

        raise
