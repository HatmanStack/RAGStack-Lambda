"""
DetectFileType Lambda

Detects file type from content and returns routing decision for Step Functions.
For OCR files (PDF/images), also counts pages and determines batching strategy.

This Lambda combines file type detection with page info extraction for OCR files,
eliminating the need for a separate GetPageInfo Lambda invocation.

Input event:
{
    "document_id": "abc123",
    "input_s3_uri": "s3://input-bucket/uploads/doc.html",
    "output_s3_prefix": "s3://output-bucket/processed/abc123/"
}

Output (adds fileType, detectedType, and pageInfo for OCR files):
{
    "document_id": "abc123",
    "input_s3_uri": "s3://input-bucket/uploads/doc.html",
    "output_s3_prefix": "s3://output-bucket/processed/abc123/",
    "fileType": "text",
    "detectedType": "html",
    "pageInfo": {  // Only for OCR files
        "total_pages": 150,
        "needs_batching": true,
        "is_text_native": false,
        "batches": [{"page_start": 1, "page_end": 10}, ...]
    }
}
"""

import logging
import os
from datetime import UTC, datetime

import boto3
import fitz  # PyMuPDF - for PDF page counting

from ragstack_common.storage import extract_filename_from_s3_uri, parse_s3_uri, read_s3_binary
from ragstack_common.text_extractors import ContentSniffer

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level AWS clients (reused across warm invocations)
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# Content sniffer instance (reused across invocations)
_sniffer = None

# File type routing categories
TEXT_TYPES = {"html", "txt", "csv", "json", "xml", "eml", "epub", "docx", "xlsx"}
PASSTHROUGH_TYPES = {"markdown"}
MEDIA_TYPES = {"video", "audio"}

# Amount of content to read for sniffing (4KB)
SNIFF_BYTES = 4096

# Page batching configuration
BATCH_SIZE = 10  # Pages per batch
BATCH_THRESHOLD = 20  # Documents with more pages than this use batching
MIN_EXTRACTABLE_CHARS_PER_PAGE = 50  # Threshold for text-native detection


def _get_sniffer() -> ContentSniffer:
    """Get or initialize ContentSniffer (lazy initialization)."""
    global _sniffer
    if _sniffer is None:
        _sniffer = ContentSniffer()
    return _sniffer


def _get_routing_category(file_type: str) -> str:
    """Map detected file type to routing category.

    Args:
        file_type: Detected file type from content sniffer.

    Returns:
        Routing category: 'text', 'media', 'ocr', or 'passthrough'.
    """
    if file_type in TEXT_TYPES:
        return "text"
    if file_type in PASSTHROUGH_TYPES:
        return "passthrough"
    if file_type in MEDIA_TYPES:
        return "media"
    # Default to OCR for unknown types (PDFs, images, etc.)
    return "ocr"


def _is_markdown_file(filename: str) -> bool:
    """Check if file is a markdown file (passthrough)."""
    lower_name = filename.lower()
    return lower_name.endswith((".md", ".markdown"))


def _is_pdf_or_image(filename: str, content_first_bytes: bytes) -> bool:
    """Check if file is a PDF or image (OCR path)."""
    lower_name = filename.lower()

    # Check by extension
    pdf_image_extensions = {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".tif",
        ".gif",
        ".bmp",
        ".webp",
        ".avif",
    }
    for ext in pdf_image_extensions:
        if lower_name.endswith(ext):
            return True

    # Check by magic bytes
    # PDF: %PDF
    if content_first_bytes.startswith(b"%PDF"):
        return True

    # JPEG: FFD8FF
    if content_first_bytes.startswith(b"\xff\xd8\xff"):
        return True

    # PNG: 89 50 4E 47
    if content_first_bytes.startswith(b"\x89PNG"):
        return True

    # GIF: GIF87a or GIF89a
    if content_first_bytes.startswith((b"GIF87a", b"GIF89a")):
        return True

    # TIFF: 49 49 2A 00 or 4D 4D 00 2A
    if content_first_bytes.startswith((b"II*\x00", b"MM\x00*")):
        return True

    # BMP: BM
    if content_first_bytes.startswith(b"BM"):
        return True

    # WebP: RIFF....WEBP
    if content_first_bytes.startswith(b"RIFF") and b"WEBP" in content_first_bytes[:12]:
        return True

    # AVIF: ....ftypavif (ftyp box at offset 4)
    return (
        len(content_first_bytes) >= 12
        and b"ftyp" in content_first_bytes[:12]
        and (b"avif" in content_first_bytes[:16] or b"avis" in content_first_bytes[:16])
    )


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


def _get_pdf_page_info(input_s3_uri: str, filename: str) -> dict:
    """
    Get page info for PDF files: count pages, check text-native, determine batching.

    Returns dict with total_pages, needs_batching, is_text_native, and batches array.
    """
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

    return {
        "total_pages": total_pages,
        "needs_batching": needs_batching,
        "is_text_native": is_text_native,
        "batches": batches,
    }


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


def lambda_handler(event, context):
    """
    Main Lambda handler for file type detection.

    Detects file type and returns routing decision for Step Functions.
    """
    logger.info(f"DetectFileType: Received event: {event}")

    # Extract event data
    document_id = event["document_id"]
    input_s3_uri = event["input_s3_uri"]
    output_s3_prefix = event["output_s3_prefix"]

    filename = extract_filename_from_s3_uri(input_s3_uri)
    logger.info(f"Detecting file type for: {filename}")

    # Check for markdown passthrough first (skip content download)
    if _is_markdown_file(filename):
        logger.info(f"Markdown file detected: {filename} -> passthrough")
        return {
            "document_id": document_id,
            "input_s3_uri": input_s3_uri,
            "output_s3_prefix": output_s3_prefix,
            "fileType": "passthrough",
            "detectedType": "markdown",
        }

    # Download first 4KB for content sniffing
    bucket, key = parse_s3_uri(input_s3_uri)

    try:
        response = s3_client.get_object(
            Bucket=bucket,
            Key=key,
            Range=f"bytes=0-{SNIFF_BYTES - 1}",
        )
        content = response["Body"].read()
    except s3_client.exceptions.NoSuchKey:
        logger.error(f"File not found: {input_s3_uri}")
        raise
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise

    logger.info(f"Downloaded {len(content)} bytes for sniffing")

    # Check for PDF/image files first (direct to OCR)
    if _is_pdf_or_image(filename, content):
        # Detect PDF by extension first (most reliable), then by magic bytes in content
        # Some PDFs may have whitespace/BOM before the %PDF header
        is_pdf = filename.lower().endswith(".pdf") or b"%PDF" in content[:1024]
        detected_type = "pdf" if is_pdf else "image"
        logger.info(f"PDF/image detected: {filename} -> ocr ({detected_type})")

        # For PDFs: get page count and determine batching strategy
        # For images: single page, no batching
        if detected_type == "pdf":
            page_info = _get_pdf_page_info(input_s3_uri, filename)
        else:
            # Images are single-page, no batching needed
            page_info = {
                "total_pages": 1,
                "needs_batching": False,
                "is_text_native": False,
                "batches": [],
            }

        # Update tracking table with document info
        _update_tracking_table(
            document_id=document_id,
            filename=filename,
            input_s3_uri=input_s3_uri,
            total_pages=page_info["total_pages"],
            is_text_native=page_info["is_text_native"],
            needs_batching=page_info["needs_batching"],
        )

        return {
            "document_id": document_id,
            "input_s3_uri": input_s3_uri,
            "output_s3_prefix": output_s3_prefix,
            "fileType": "ocr",
            "detectedType": detected_type,
            "pageInfo": page_info,
        }

    # Use ContentSniffer for text-based file detection
    sniffer = _get_sniffer()
    detected_type, confidence = sniffer.sniff(content, filename)

    logger.info(f"Content sniffer detected: {detected_type} (confidence: {confidence:.2f})")

    # Get routing category
    file_type = _get_routing_category(detected_type)

    logger.info(f"File type routing: {filename} -> {file_type} ({detected_type})")

    # Return event with added routing info
    return {
        "document_id": document_id,
        "input_s3_uri": input_s3_uri,
        "output_s3_prefix": output_s3_prefix,
        "fileType": file_type,
        "detectedType": detected_type,
    }
