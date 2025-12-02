"""
Content deduplication for web scraping.

Uses content hashing to detect unchanged pages on re-scrape,
avoiding duplicate knowledge base entries.
"""

import hashlib


def compute_content_hash(content: str) -> str:
    """
    Compute SHA-256 hash of content for deduplication.

    Args:
        content: Extracted Markdown content

    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def should_skip_page(content_hash: str, existing_hash: str | None) -> bool:
    """
    Determine if a page should be skipped based on content hash.

    Args:
        content_hash: Hash of current content
        existing_hash: Hash from previous scrape (None if new page)

    Returns:
        True if page is unchanged and should be skipped
    """
    if existing_hash is None:
        return False
    return content_hash == existing_hash


def normalize_url_for_hash(url: str) -> str:
    """
    Normalize URL for consistent hash lookup.

    Removes fragments, query params, normalizes case and trailing slashes.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL string
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("URL normalization for hash not yet implemented")
