"""
Source extraction and URI resolution for Knowledge Base citations.

This module handles parsing Bedrock KB citations into structured source objects,
including:
- URI classification (PDF, scraped, image)
- Document metadata lookup from DynamoDB
- Presigned URL generation
- Source URL extraction from frontmatter
"""

import logging
import re
from urllib.parse import unquote

logger = logging.getLogger(__name__)


# ============================================================================
# Frontmatter extraction functions
# ============================================================================


def extract_source_url_from_content(content_text: str) -> str | None:
    """
    Extract source_url from scraped markdown frontmatter.

    Args:
        content_text: Content text that may contain YAML frontmatter

    Returns:
        Source URL if found, None otherwise

    Example frontmatter:
        ---
        source_url: "https://example.com/page"
        title: "Page Title"
        ---
    """
    if not content_text:
        return None

    if "source_url:" not in content_text:
        return None

    for line in content_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("source_url:"):
            url = stripped.split(":", 1)[1].strip()
            # Remove quotes if present
            if url.startswith(("'", '"')) and url.endswith(("'", '"')):
                url = url[1:-1]
            return url
    return None


def extract_image_caption_from_content(content_text: str) -> str | None:
    """
    Extract caption from image content frontmatter.

    Args:
        content_text: Content text that may contain frontmatter

    Returns:
        Caption if found, None otherwise

    Example format:
        ---
        image_id: abc123
        filename: photo.jpg
        user_caption: My photo caption
        ---
        # Image: photo.jpg
        <additional caption text>
    """
    if not content_text:
        return None

    lines = content_text.split("\n")
    in_frontmatter = False
    frontmatter_ended = False

    for line in lines:
        stripped = line.strip()

        # Track frontmatter boundaries
        if stripped == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            frontmatter_ended = True
            in_frontmatter = False
            continue

        # Look for captions in frontmatter
        if in_frontmatter:
            if stripped.startswith("user_caption:"):
                caption = stripped.split(":", 1)[1].strip()
                if caption:
                    return caption
            if stripped.startswith("ai_caption:"):
                caption = stripped.split(":", 1)[1].strip()
                if caption:
                    return caption

        # After frontmatter, look for actual content
        if frontmatter_ended and stripped and not stripped.startswith("#"):
            return stripped[:200] if len(stripped) > 200 else stripped

    return None


def extract_filename_from_frontmatter(content_text: str) -> str | None:
    """
    Extract filename from frontmatter.

    Args:
        content_text: Content text with YAML frontmatter

    Returns:
        Filename if found, None otherwise
    """
    if not content_text:
        return None

    match = re.search(r"^filename:\s*(.+)$", content_text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def construct_image_uri_from_content_uri(
    content_s3_uri: str, content_text: str | None = None
) -> str | None:
    """
    Convert caption/content.txt S3 URI to the actual image file URI.

    The caption file is stored at: images/{imageId}/caption.txt (or content.txt)
    The actual image is at: images/{imageId}/{filename}.ext

    Args:
        content_s3_uri: S3 URI of the caption.txt or content.txt file
        content_text: Optional content text to extract filename from frontmatter

    Returns:
        S3 URI of the image file, or None if not determinable
    """
    if not content_s3_uri:
        return None

    is_caption_file = "caption.txt" in content_s3_uri or "content.txt" in content_s3_uri
    if not is_caption_file:
        return None

    try:
        if content_text:
            filename = extract_filename_from_frontmatter(content_text)
            if filename:
                base_uri = content_s3_uri.replace("/caption.txt", "").replace("/content.txt", "")
                return f"{base_uri}/{filename}"

        # Fallback: return base path (folder)
        return content_s3_uri.replace("/caption.txt", "").replace("/content.txt", "")
    except Exception:
        return None


# ============================================================================
# URI parsing and classification
# ============================================================================


class ParsedURI:
    """Result of parsing an S3 URI from a KB citation."""

    def __init__(
        self,
        bucket: str,
        document_id: str,
        original_filename: str | None = None,
        input_prefix: str | None = None,
        is_scraped: bool = False,
        is_image: bool = False,
    ):
        self.bucket = bucket
        self.document_id = document_id
        self.original_filename = original_filename
        self.input_prefix = input_prefix
        self.is_scraped = is_scraped
        self.is_image = is_image


def parse_citation_uri(uri: str) -> ParsedURI | None:
    """
    Parse an S3 URI from a KB citation into its components.

    Handles the following structures:
    1. Image: s3://bucket/images/{imageId}/caption.txt
    2. Input: s3://bucket/input/{docId}/{filename}
    3. Output: s3://bucket/output/{docId}/extracted_text.txt or full_text.txt

    Args:
        uri: S3 URI from a KB citation

    Returns:
        ParsedURI with extracted components, or None if invalid
    """
    if not uri:
        return None

    uri_path = uri.replace("s3://", "")
    parts = uri_path.split("/")

    if len(parts) < 3:
        logger.warning(f"Invalid S3 URI format (too few parts): {parts}")
        return None

    bucket = parts[0]
    document_id = None
    original_filename = None
    input_prefix = None
    is_scraped = False
    is_image = False

    # Detect structure based on path prefix
    if len(parts) > 2 and parts[1] == "images":
        # Image structure: bucket/images/{imageId}/caption.txt
        document_id = unquote(parts[2])
        input_prefix = "images"
        is_image = True
        logger.debug(f"Image structure detected: imageId={document_id}")

    elif len(parts) > 3 and parts[1] == "input":
        # Input structure: bucket/input/{docId}/{filename}
        document_id = unquote(parts[2])
        original_filename = unquote(parts[3]) if len(parts) > 3 else None
        input_prefix = "input"
        if original_filename and original_filename.endswith(".md"):
            is_scraped = True
        logger.debug(f"Input structure: docId={document_id}, file={original_filename}")

    elif len(parts) > 2 and parts[1] == "output":
        # Output structure: bucket/output/{docId}/...
        document_id = unquote(parts[2])
        input_prefix = "input"
        last_part = parts[-1] if parts else ""
        if last_part == "full_text.txt":
            original_filename = f"{document_id}.scraped.md"
            is_scraped = True
            logger.debug(f"Scraped content detected: docId={document_id}")
        else:
            logger.debug(f"Document output detected: docId={document_id}")

    else:
        # Fallback: try to parse as generic structure
        document_id = unquote(parts[1]) if len(parts) > 1 else None
        original_filename = unquote(parts[2]) if len(parts) > 2 else None
        logger.debug(f"Generic structure detected: docId={document_id}")

    # Validate
    if not document_id or len(document_id) < 5:
        logger.warning(f"Invalid document_id: {document_id}")
        return None

    return ParsedURI(
        bucket=bucket,
        document_id=document_id,
        original_filename=original_filename,
        input_prefix=input_prefix,
        is_scraped=is_scraped,
        is_image=is_image,
    )


def extract_page_number(uri_parts: list[str]) -> int | None:
    """
    Extract page number from URI parts if available.

    Args:
        uri_parts: Split parts of the S3 URI

    Returns:
        Page number if found, None otherwise
    """
    if "pages" not in uri_parts or len(uri_parts) <= 3:
        return None

    page_file = uri_parts[-1]  # e.g., "page-3.json"
    try:
        return int(page_file.split("-")[1].split(".")[0])
    except (IndexError, ValueError):
        logger.debug(f"Could not extract page number from: {page_file}")
        return None


# ============================================================================
# Document metadata lookup
# ============================================================================


def lookup_document_metadata(dynamodb, tracking_table_name: str, document_id: str) -> dict | None:
    """
    Look up document metadata from the tracking DynamoDB table.

    Args:
        dynamodb: boto3 DynamoDB resource
        tracking_table_name: Name of the tracking table
        document_id: Document ID to look up

    Returns:
        Dictionary with input_s3_uri, source_url, filename, etc., or None
    """
    if not tracking_table_name or not document_id:
        return None

    try:
        table = dynamodb.Table(tracking_table_name)
        response = table.get_item(Key={"document_id": document_id})
        return response.get("Item")
    except Exception as e:
        logger.error(f"Tracking lookup failed for {document_id}: {e}")
        return None


# ============================================================================
# Presigned URL generation
# ============================================================================


def generate_presigned_url(s3_client, bucket: str, key: str, expiration: int = 3600) -> str | None:
    """
    Generate presigned URL for S3 object download.

    Args:
        s3_client: boto3 S3 client
        bucket: S3 bucket name
        key: S3 object key
        expiration: URL expiration time in seconds (default 1 hour)

    Returns:
        Presigned URL or None if generation fails
    """
    try:
        return s3_client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expiration
        )
    except Exception as e:
        logger.error(f"Failed to generate presigned URL for {bucket}/{key}: {e}")
        return None


def generate_document_url(
    s3_client, document_s3_uri: str, allow_document_access: bool
) -> str | None:
    """
    Generate a presigned URL for document download if access is allowed.

    Args:
        s3_client: boto3 S3 client
        document_s3_uri: S3 URI of the document
        allow_document_access: Whether document access is enabled

    Returns:
        Presigned URL or None
    """
    if not allow_document_access or not document_s3_uri:
        return None

    if not document_s3_uri.startswith("s3://"):
        return None

    s3_path = document_s3_uri.replace("s3://", "")
    s3_parts = s3_path.split("/", 1)

    if len(s3_parts) != 2 or not s3_parts[1]:
        logger.warning(f"Could not parse S3 URI: {document_s3_uri}")
        return None

    bucket, key = s3_parts

    # Validate key looks reasonable
    if "/" not in key or len(key) <= 10:
        logger.warning(f"Skipping malformed key: {key}")
        return None

    return generate_presigned_url(s3_client, bucket, key)


# ============================================================================
# Source resolution
# ============================================================================


def resolve_document_s3_uri(
    parsed: ParsedURI,
    tracking_metadata: dict | None,
    citation_uri: str,
) -> str:
    """
    Determine the best S3 URI for a source document.

    Priority:
    1. For scraped content, use the KB citation URI (output)
    2. Use input_s3_uri from tracking table if available
    3. Construct from filename and input_prefix
    4. Fallback to KB citation URI

    Args:
        parsed: Parsed URI components
        tracking_metadata: Document metadata from tracking table
        citation_uri: Original KB citation URI

    Returns:
        Best S3 URI for the source document
    """
    # Scraped content: use output URI (input may be deleted)
    if parsed.is_scraped:
        return citation_uri

    # Prefer input_s3_uri from tracking table
    if tracking_metadata:
        input_uri = tracking_metadata.get("input_s3_uri")
        if input_uri:
            return input_uri

    # Construct from filename
    original_filename = (
        tracking_metadata.get("filename") if tracking_metadata else parsed.original_filename
    )
    if original_filename:
        if parsed.input_prefix:
            return f"s3://{parsed.bucket}/{parsed.input_prefix}/{parsed.document_id}/{original_filename}"
        return f"s3://{parsed.bucket}/{parsed.document_id}/{original_filename}"

    # Fallback to citation URI
    return citation_uri


def build_source_object(
    document_id: str,
    document_s3_uri: str,
    page_number: int | None,
    snippet: str,
    document_url: str | None,
    allow_document_access: bool,
    is_scraped: bool,
    source_url: str | None,
    is_image: bool,
    thumbnail_url: str | None,
    image_caption: str | None,
) -> dict:
    """
    Build a structured source object for the API response.

    Args:
        document_id: Document identifier
        document_s3_uri: S3 URI of the source document
        page_number: Page number if applicable
        snippet: Text snippet from the source
        document_url: Presigned download URL if allowed
        allow_document_access: Whether document access is enabled
        is_scraped: Whether this is scraped web content
        source_url: Original web URL for scraped content
        is_image: Whether this is an image source
        thumbnail_url: Presigned thumbnail URL for images
        image_caption: Caption for image sources

    Returns:
        Structured source dictionary
    """
    return {
        "documentId": document_id,
        "pageNumber": page_number,
        "s3Uri": document_s3_uri,
        "snippet": snippet,
        "documentUrl": document_url,
        "documentAccessAllowed": allow_document_access,
        "isScraped": is_scraped,
        "sourceUrl": source_url,
        "isImage": is_image,
        "thumbnailUrl": thumbnail_url,
        "caption": image_caption,
    }
