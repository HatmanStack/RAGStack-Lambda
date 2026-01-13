"""
DetectFileType Lambda

Detects file type from content and returns routing decision for Step Functions.
Downloads first 4KB of file for efficient content sniffing.

Input event:
{
    "document_id": "abc123",
    "input_s3_uri": "s3://input-bucket/uploads/doc.html",
    "output_s3_prefix": "s3://output-bucket/processed/abc123/"
}

Output (adds fileType and detectedType):
{
    "document_id": "abc123",
    "input_s3_uri": "s3://input-bucket/uploads/doc.html",
    "output_s3_prefix": "s3://output-bucket/processed/abc123/",
    "fileType": "text",
    "detectedType": "html"
}
"""

import logging

import boto3

from ragstack_common.text_extractors import ContentSniffer

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level AWS client (reused across warm invocations)
s3_client = boto3.client("s3")

# Content sniffer instance (reused across invocations)
_sniffer = None

# File type routing categories
TEXT_TYPES = {"html", "txt", "csv", "json", "xml", "eml", "epub", "docx", "xlsx"}
PASSTHROUGH_TYPES = {"markdown"}
MEDIA_TYPES = {"video", "audio"}

# Amount of content to read for sniffing (4KB)
SNIFF_BYTES = 4096


def _get_sniffer() -> ContentSniffer:
    """Get or initialize ContentSniffer (lazy initialization)."""
    global _sniffer
    if _sniffer is None:
        _sniffer = ContentSniffer()
    return _sniffer


def _parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Parse S3 URI into bucket and key."""
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {s3_uri}")
    path = s3_uri[5:]  # Remove 's3://'
    parts = path.split("/", 1)
    if len(parts) < 2 or not parts[1]:
        raise ValueError(f"S3 URI must include a key/path: {s3_uri}")
    return parts[0], parts[1]


def _extract_filename(s3_uri: str) -> str:
    """Extract filename from S3 URI."""
    parts = s3_uri.split("/")
    return parts[-1] if parts else "document"


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

    filename = _extract_filename(input_s3_uri)
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
    bucket, key = _parse_s3_uri(input_s3_uri)

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
        logger.info(f"PDF/image detected: {filename} -> ocr")
        return {
            "document_id": document_id,
            "input_s3_uri": input_s3_uri,
            "output_s3_prefix": output_s3_prefix,
            "fileType": "ocr",
            "detectedType": "pdf" if content.startswith(b"%PDF") else "image",
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
