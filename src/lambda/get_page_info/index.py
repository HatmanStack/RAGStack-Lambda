"""
Get Page Info Lambda

Counts PDF pages and determines processing strategy (single-pass vs batched).
For large documents, generates an array of page batches for parallel processing.

Input event:
{
    "document_id": "abc123",
    "input_s3_uri": "s3://bucket/input/abc123/document.pdf",
    "output_s3_prefix": "s3://bucket/output/abc123/"
}

Output:
{
    "document_id": "abc123",
    "input_s3_uri": "s3://...",
    "output_s3_prefix": "s3://...",
    "total_pages": 150,
    "needs_batching": true,
    "is_text_native": false,
    "batches": [
        {"page_start": 1, "page_end": 10},
        {"page_start": 11, "page_end": 20},
        ...
    ]
}
"""

import logging
import os
from datetime import UTC, datetime

import boto3
import fitz  # PyMuPDF

from ragstack_common.storage import parse_s3_uri, read_s3_binary

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
BATCH_SIZE = 10  # Pages per batch
BATCH_THRESHOLD = 20  # Documents with more pages than this use batching
MIN_EXTRACTABLE_CHARS_PER_PAGE = 50  # Threshold for text-native detection


def _update_tracking_table(
    document_id: str,
    filename: str,
    input_s3_uri: str,
    total_pages: int,
    is_text_native: bool,
    needs_batching: bool,
) -> None:
    """Update DynamoDB tracking table with document info."""
    tracking_table = os.environ.get("TRACKING_TABLE")
    if not tracking_table:
        logger.warning("TRACKING_TABLE not set, skipping tracking update")
        return

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(tracking_table)

    now = datetime.now(UTC).isoformat()

    table.update_item(
        Key={"document_id": document_id},
        UpdateExpression=(
            "SET #status = :status, "
            "filename = if_not_exists(filename, :filename), "
            "input_s3_uri = if_not_exists(input_s3_uri, :input_s3_uri), "
            "total_pages = :total_pages, "
            "is_text_native = :is_text_native, "
            "needs_batching = :needs_batching, "
            "created_at = if_not_exists(created_at, :now), "
            "updated_at = :now"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "processing",
            ":filename": filename,
            ":input_s3_uri": input_s3_uri,
            ":total_pages": total_pages,
            ":is_text_native": is_text_native,
            ":needs_batching": needs_batching,
            ":now": now,
        },
    )
    logger.info(f"Updated tracking table for {document_id}: {filename}, {total_pages} pages")


def _is_text_native_pdf(pdf_bytes: bytes) -> bool:
    """
    Check if PDF has extractable text (text-native vs scanned).

    Samples first 3 pages and checks if average text per page exceeds threshold.
    Text-native PDFs don't need OCR batching since text extraction is fast.
    """
    try:
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_to_check = min(3, len(pdf_doc))

        total_chars = 0
        for i in range(pages_to_check):
            page = pdf_doc[i]
            text = page.get_text()
            total_chars += len(text.strip())

        pdf_doc.close()

        avg_chars = total_chars / pages_to_check if pages_to_check > 0 else 0
        is_text_native = avg_chars >= MIN_EXTRACTABLE_CHARS_PER_PAGE

        logger.info(
            f"PDF text check: {avg_chars:.0f} chars/page avg "
            f"(threshold: {MIN_EXTRACTABLE_CHARS_PER_PAGE}), "
            f"text_native={is_text_native}"
        )
        return is_text_native

    except Exception:
        logger.exception("Error checking PDF text content")
        return False


def lambda_handler(event, context):
    """
    Main Lambda handler.

    Counts PDF pages and determines if batching is needed.
    """
    logger.info(f"GetPageInfo event: {event}")

    document_id = event["document_id"]
    input_s3_uri = event["input_s3_uri"]
    output_s3_prefix = event["output_s3_prefix"]

    # Get filename from S3 URI
    _, key = parse_s3_uri(input_s3_uri)
    filename = key.split("/")[-1]

    # Check if this is a PDF
    is_pdf = filename.lower().endswith(".pdf")

    if not is_pdf:
        # Non-PDF files (images, etc.) don't need batching
        logger.info(f"Non-PDF file: {filename}, skipping batching")

        # Update tracking table for non-PDF
        _update_tracking_table(
            document_id=document_id,
            filename=filename,
            input_s3_uri=input_s3_uri,
            total_pages=1,
            is_text_native=False,
            needs_batching=False,
        )

        return {
            "document_id": document_id,
            "input_s3_uri": input_s3_uri,
            "output_s3_prefix": output_s3_prefix,
            "total_pages": 1,
            "needs_batching": False,
            "is_text_native": False,
            "batches": [],
        }

    # Download PDF to count pages
    logger.info(f"Downloading PDF to count pages: {input_s3_uri}")
    pdf_bytes = read_s3_binary(input_s3_uri)

    # Count pages
    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(pdf_doc)
    pdf_doc.close()
    logger.info(f"PDF has {total_pages} pages")

    # Check if text-native
    is_text_native = _is_text_native_pdf(pdf_bytes)

    # Determine if batching is needed
    # Text-native PDFs don't need batching (text extraction is fast)
    # Small PDFs don't need batching (single-pass is fine)
    needs_batching = total_pages > BATCH_THRESHOLD and not is_text_native

    # Generate batch array if needed
    batches = []
    if needs_batching:
        for start in range(1, total_pages + 1, BATCH_SIZE):
            end = min(start + BATCH_SIZE - 1, total_pages)
            batches.append({"page_start": start, "page_end": end})
        logger.info(f"Generated {len(batches)} batches for parallel processing")
    else:
        reason = "text-native" if is_text_native else f"<= {BATCH_THRESHOLD} pages"
        logger.info(f"No batching needed: {reason}")

    # Update tracking table with document info
    _update_tracking_table(
        document_id=document_id,
        filename=filename,
        input_s3_uri=input_s3_uri,
        total_pages=total_pages,
        is_text_native=is_text_native,
        needs_batching=needs_batching,
    )

    return {
        "document_id": document_id,
        "input_s3_uri": input_s3_uri,
        "output_s3_prefix": output_s3_prefix,
        "total_pages": total_pages,
        "needs_batching": needs_batching,
        "is_text_native": is_text_native,
        "batches": batches,
    }
