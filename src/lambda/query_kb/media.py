"""Media URL generation and image/caption extraction for query_kb.

Functions for fetching images for the Converse API, generating presigned
media URLs with timestamp fragments, and extracting metadata from content.
"""

import logging
from decimal import Decimal
from typing import Any

try:
    from ._compat import s3_client
except ImportError:
    from _compat import s3_client  # type: ignore[import-not-found]

from ragstack_common.storage import parse_s3_uri

logger = logging.getLogger()

# Content types recognized as media for source attribution
MEDIA_CONTENT_TYPES = ("video", "audio", "transcript", "visual")

# Maximum image size for Converse API (5MB)
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024

# Supported image formats for Bedrock Converse API
IMAGE_FORMAT_MAP = {
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


def fetch_image_for_converse(s3_uri: str, content_type: str | None = None) -> dict[str, Any] | None:
    """
    Fetch image from S3 and prepare for Bedrock Converse API.

    Args:
        s3_uri: S3 URI of the image (s3://bucket/key)
        content_type: Optional content type, will be inferred from extension if not provided

    Returns:
        ImageBlock dict for Converse API, or None if image cannot be fetched/processed
    """
    try:
        bucket, key = parse_s3_uri(s3_uri)
        if not bucket or not key:
            logger.warning(f"Invalid S3 URI for image: {s3_uri}")
            return None

        # Fetch image from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        image_bytes = response["Body"].read()

        # Check size limit
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            logger.warning(f"Image too large ({len(image_bytes)} bytes): {s3_uri}")
            return None

        # Determine format from content type or extension
        if not content_type:
            content_type = response.get("ContentType", "")

        image_format = IMAGE_FORMAT_MAP.get(content_type.lower())
        if not image_format:
            # Try to infer from extension
            ext = key.lower().split(".")[-1]
            ext_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
            image_format = ext_map.get(ext)

        if not image_format:
            logger.warning(f"Unsupported image format: {content_type}, {s3_uri}")
            return None

        # Return ImageBlock for Converse API
        return {"image": {"format": image_format, "source": {"bytes": image_bytes}}}

    except Exception as e:
        logger.warning(f"Failed to fetch image {s3_uri}: {e}")
        return None


def generate_media_url(
    bucket: str,
    key: str,
    timestamp_start: int | None,
    timestamp_end: int | None,
    expiration: int = 3600,
) -> str | None:
    """
    Generate presigned URL for media with optional timestamp fragment.

    For media sources, appends HTML5 media fragment (#t=start,end) to enable
    direct seeking in video/audio players.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        timestamp_start: Start time in seconds
        timestamp_end: End time in seconds
        expiration: URL expiration time in seconds (default 1 hour)

    Returns:
        Presigned URL with optional timestamp fragment, or None on error
    """
    try:
        base_url: str = s3_client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expiration
        )
        if not base_url:
            return None

        # Append HTML5 media fragment for timestamp seeking
        if timestamp_start is not None:
            if timestamp_end is not None:
                return f"{base_url}#t={timestamp_start},{timestamp_end}"
            return f"{base_url}#t={timestamp_start}"
        return base_url
    except Exception as e:
        logger.error(f"Failed to generate media URL for {bucket}/{key}: {e}")
        return None


def extract_source_url_from_content(content_text: str) -> str | None:
    """
    Extract source_url from scraped markdown frontmatter.

    Args:
        content_text (str): Content text that may contain frontmatter

    Returns:
        str or None: Source URL if found, None otherwise
    """
    if not content_text:
        return None

    # Look for source_url in YAML frontmatter
    if "source_url:" in content_text:
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
        content_text (str): Content text that may contain frontmatter

    Returns:
        str or None: Caption if found, None otherwise
    """
    if not content_text:
        return None

    # Look for caption in content (usually after frontmatter)
    # Image content format:
    # ---
    # image_id: ...
    # filename: ...
    # ---
    # # Image: filename
    # <caption text>

    # First try to extract from frontmatter-style format
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

        # Look for user_caption or ai_caption in frontmatter
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
            # Return first non-header line as caption snippet
            return stripped[:200] if len(stripped) > 200 else stripped

    return None


def format_timestamp(seconds: int | float | Decimal | None) -> str | None:
    """
    Format seconds into M:SS or MM:SS display format.

    Args:
        seconds (int | float | Decimal): Time in seconds

    Returns:
        str: Formatted timestamp like "1:30" or "10:00"
    """
    if seconds is None:
        return None
    seconds = int(seconds)
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"
