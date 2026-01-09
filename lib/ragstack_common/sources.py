"""
Source extraction utilities for Knowledge Base content.

This module provides utilities for extracting metadata from document content,
particularly for scraped web content and images with YAML frontmatter.
"""

import logging
import re

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
            # Remove matching quotes if present
            if len(url) >= 2 and url[0] in ("'", '"') and url[0] == url[-1]:
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
