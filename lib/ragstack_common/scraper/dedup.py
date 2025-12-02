"""
Content deduplication for web scraping.

Uses content hashing to detect unchanged pages on re-scrape,
avoiding duplicate knowledge base entries.
"""

import hashlib
import logging
import re
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


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
    parsed = urlparse(url)

    # Lowercase scheme and hostname
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Normalize path - remove trailing slash
    path = parsed.path
    if path and path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Reconstruct without query params or fragments
    return f"{scheme}://{netloc}{path}"


def normalize_content_for_hash(markdown: str) -> str:
    """
    Normalize content before hashing (remove volatile parts).

    Removes frontmatter (scraped_at changes each time) and normalizes whitespace.

    Args:
        markdown: Markdown content with potential frontmatter

    Returns:
        Normalized content string
    """
    lines = markdown.split("\n")
    in_frontmatter = False
    content_lines = []

    for line in lines:
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter:
            content_lines.append(line)

    # Join and normalize whitespace
    normalized = "\n".join(content_lines)

    # Collapse multiple whitespace to single space
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


class DeduplicationService:
    """Service for checking and storing content hashes in DynamoDB."""

    def __init__(self, table_name: str, region_name: str | None = None):
        """
        Initialize deduplication service.

        Args:
            table_name: Name of the ScrapeUrls DynamoDB table
            region_name: Optional AWS region name
        """
        self.dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

    def get_existing_hash(self, url: str) -> str | None:
        """
        Get stored content hash for URL if exists.

        Uses the url_hash field to look up across jobs.

        Args:
            url: URL to look up

        Returns:
            Content hash string or None if not found
        """
        url_hash = compute_content_hash(normalize_url_for_hash(url))

        try:
            response = self.table.query(
                IndexName="UrlHashIndex",
                KeyConditionExpression="url_hash = :hash",
                ExpressionAttributeValues={":hash": url_hash},
                Limit=1,
                ScanIndexForward=False,  # Get most recent first
            )

            items = response.get("Items", [])
            if items:
                return items[0].get("content_hash")
            return None

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ResourceNotFoundException":
                # Index doesn't exist yet
                logger.warning("UrlHashIndex not found, skipping dedup lookup")
                return None
            logger.error(f"DynamoDB error in get_existing_hash: {error_code}")
            return None

    def is_content_changed(self, url: str, new_content: str) -> bool:
        """
        Check if content has changed since last scrape.

        Args:
            url: URL of the page
            new_content: New markdown content (with frontmatter)

        Returns:
            True if content is new or changed, False if unchanged
        """
        normalized = normalize_content_for_hash(new_content)
        new_hash = compute_content_hash(normalized)
        existing_hash = self.get_existing_hash(url)

        if existing_hash is None:
            return True  # New URL, definitely changed

        return new_hash != existing_hash

    def store_hash(self, job_id: str, url: str, content: str) -> None:
        """
        Store content hash for URL.

        Args:
            job_id: Scrape job ID
            url: URL of the page
            content: Markdown content (with frontmatter)
        """
        normalized = normalize_content_for_hash(content)
        content_hash = compute_content_hash(normalized)
        url_hash = compute_content_hash(normalize_url_for_hash(url))

        try:
            self.table.update_item(
                Key={"job_id": job_id, "url": url},
                UpdateExpression="SET content_hash = :ch, url_hash = :uh",
                ExpressionAttributeValues={
                    ":ch": content_hash,
                    ":uh": url_hash,
                },
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.error(f"Failed to store hash: {error_code}")
            raise

    def get_content_hash(self, content: str) -> str:
        """
        Get the hash of normalized content.

        Utility method for external use.

        Args:
            content: Markdown content

        Returns:
            Content hash string
        """
        normalized = normalize_content_for_hash(content)
        return compute_content_hash(normalized)
