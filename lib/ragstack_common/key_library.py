"""Metadata Key Library for document pipeline

This module provides access to the metadata key library stored in DynamoDB.
The key library tracks discovered metadata fields, their data types, occurrence
counts, and sample values across all ingested documents.

Key library schema:
{
    "key_name": "location",           # Primary key (partition key)
    "data_type": "string",            # string | number | boolean | list
    "sample_values": ["NY", "Boston"], # Up to 10 sample values
    "occurrence_count": 47,            # How many vectors have this key
    "first_seen": "2024-01-15T...",   # ISO timestamp
    "last_seen": "2024-01-20T...",    # ISO timestamp
    "status": "active"                 # active | deprecated
}
"""

import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

MAX_SAMPLE_VALUES = 10
DEFAULT_CACHE_TTL_SECONDS = 300  # 5 minutes


class KeyLibrary:
    """
    Manages the metadata key library in DynamoDB.

    The key library stores discovered metadata field names, their data types,
    occurrence counts, and sample values. This enables consistent metadata
    extraction across documents and provides visibility into the metadata
    schema.

    Usage:
        key_library = KeyLibrary()
        active_keys = key_library.get_active_keys()
        key_library.upsert_key("location", "string", "New York")
    """

    def __init__(
        self,
        table_name: str | None = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ):
        """
        Initialize the key library.

        Args:
            table_name: DynamoDB table name. If not provided, reads from
                       METADATA_KEY_LIBRARY_TABLE environment variable.
            cache_ttl_seconds: TTL for cached active keys (default 5 minutes).
        """
        self.table_name = table_name or os.environ.get("METADATA_KEY_LIBRARY_TABLE")
        self._table = None
        self._table_exists = None
        self._cache_ttl = cache_ttl_seconds
        self._active_keys_cache = None
        self._active_keys_cache_time = None

        if self.table_name:
            logger.info(f"Initialized KeyLibrary with table: {self.table_name}")
        else:
            logger.warning(
                "KeyLibrary initialized without table name. "
                "Set METADATA_KEY_LIBRARY_TABLE environment variable or provide table_name."
            )

    @property
    def table(self):
        """Lazy-load DynamoDB table resource."""
        if self._table is None and self.table_name:
            dynamodb = boto3.resource("dynamodb")
            self._table = dynamodb.Table(self.table_name)
        return self._table

    def _check_table_exists(self) -> bool:
        """Check if the DynamoDB table exists and is accessible."""
        if self._table_exists is not None:
            return self._table_exists

        if not self.table:
            self._table_exists = False
            return False

        try:
            _ = self.table.table_status
            self._table_exists = True
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ResourceNotFoundException":
                logger.warning(f"Key library table '{self.table_name}' does not exist")
                self._table_exists = False
                return False
            raise

    def get_active_keys(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """
        Return all metadata keys with status=active.

        Args:
            use_cache: If True, returns cached results if available and fresh.
                      Set to False to force a fresh query.

        Returns:
            List of key dictionaries, each containing key_name, data_type,
            sample_values, occurrence_count, first_seen, last_seen, status.
            Returns empty list if table doesn't exist or is empty.
        """
        # Check cache first
        if use_cache and self._active_keys_cache is not None:
            now = time.time()
            if (
                self._active_keys_cache_time is not None
                and (now - self._active_keys_cache_time) < self._cache_ttl
            ):
                logger.debug(f"Returning {len(self._active_keys_cache)} cached active keys")
                return self._active_keys_cache

        if not self._check_table_exists():
            return []

        start_time = time.time()
        try:
            response = self.table.scan(
                FilterExpression="#status = :active",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":active": "active"},
            )
            items = response.get("Items", [])

            # Handle pagination for large tables
            while "LastEvaluatedKey" in response:
                response = self.table.scan(
                    FilterExpression="#status = :active",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={":active": "active"},
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                items.extend(response.get("Items", []))

            # Update cache
            self._active_keys_cache = items
            self._active_keys_cache_time = time.time()

            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"Retrieved {len(items)} active keys from library in {duration_ms:.1f}ms")
            return items

        except ClientError:
            logger.exception("Error scanning key library table")
            raise

    def get_key(self, key_name: str) -> dict[str, Any] | None:
        """
        Get details for a specific metadata key.

        Args:
            key_name: The metadata key name to retrieve.

        Returns:
            Key dictionary if found, None otherwise.
        """
        if not self._check_table_exists():
            return None

        try:
            response = self.table.get_item(Key={"key_name": key_name})
            item = response.get("Item")

            if item:
                logger.debug(f"Retrieved key '{key_name}' from library")
            else:
                logger.debug(f"Key '{key_name}' not found in library")

            return item

        except ClientError:
            logger.exception(f"Error retrieving key '{key_name}'")
            raise

    def get_key_names(self) -> list[str]:
        """
        Return sorted list of active key names.

        This is useful for including in LLM prompts to encourage
        reuse of existing keys.

        Returns:
            Sorted list of key name strings.
        """
        active_keys = self.get_active_keys()
        key_names = sorted([k["key_name"] for k in active_keys])
        logger.debug(f"Retrieved {len(key_names)} key names")
        return key_names

    def upsert_key(
        self,
        key_name: str,
        data_type: str,
        sample_value: Any,
    ) -> None:
        """
        Add or update a key in the library.

        If the key doesn't exist, creates it with occurrence_count=1.
        If it exists, increments occurrence_count and adds sample_value
        if not already present (up to MAX_SAMPLE_VALUES).

        Args:
            key_name: The metadata key name.
            data_type: Data type (string, number, boolean, list).
            sample_value: A sample value for this key.
        """
        if not self._check_table_exists():
            logger.warning(f"Cannot upsert key '{key_name}': table does not exist")
            return

        now = datetime.now(UTC).isoformat()
        sample_str = str(sample_value)[:100]  # Truncate long values

        try:
            # Use UpdateItem with conditional expressions for atomic operations
            self.table.update_item(
                Key={"key_name": key_name},
                UpdateExpression="""
                    SET data_type = :data_type,
                        last_seen = :now,
                        #status = if_not_exists(#status, :active),
                        first_seen = if_not_exists(first_seen, :now),
                        sample_values = if_not_exists(sample_values, :empty_list)
                    ADD occurrence_count :inc
                """,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":data_type": data_type,
                    ":now": now,
                    ":active": "active",
                    ":empty_list": [],
                    ":inc": 1,
                },
            )

            # Add sample value if not already present (separate operation)
            self._add_sample_value(key_name, sample_str)

            logger.debug(f"Upserted key '{key_name}' with type '{data_type}'")

        except ClientError:
            logger.exception(f"Error upserting key '{key_name}'")
            raise

    def _add_sample_value(self, key_name: str, sample_value: str) -> None:
        """
        Add a sample value to a key if not already present.

        Args:
            key_name: The metadata key name.
            sample_value: The sample value to add.
        """
        try:
            # Get current item to check sample_values
            item = self.get_key(key_name)
            if not item:
                return

            current_samples = item.get("sample_values", [])

            # Don't add if already present or at max capacity
            if sample_value in current_samples or len(current_samples) >= MAX_SAMPLE_VALUES:
                return

            # Add the new sample value
            self.table.update_item(
                Key={"key_name": key_name},
                UpdateExpression="SET sample_values = list_append(sample_values, :new_sample)",
                ExpressionAttributeValues={":new_sample": [sample_value]},
            )

        except ClientError:
            # Non-critical operation, just log the error
            logger.warning(f"Failed to add sample value for key '{key_name}'")

    def deprecate_key(self, key_name: str) -> None:
        """
        Mark a key as deprecated.

        Deprecated keys won't be returned by get_active_keys() but
        remain in the table for reference.

        Args:
            key_name: The metadata key name to deprecate.
        """
        if not self._check_table_exists():
            return

        try:
            self.table.update_item(
                Key={"key_name": key_name},
                UpdateExpression="SET #status = :deprecated",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":deprecated": "deprecated"},
            )
            logger.info(f"Deprecated key '{key_name}'")

        except ClientError:
            logger.exception(f"Error deprecating key '{key_name}'")
            raise

    def get_library_stats(self) -> dict[str, Any]:
        """
        Get summary statistics about the key library.

        Returns:
            Dictionary with total_keys, active_keys, deprecated_keys,
            total_occurrences.
        """
        if not self._check_table_exists():
            return {
                "total_keys": 0,
                "active_keys": 0,
                "deprecated_keys": 0,
                "total_occurrences": 0,
            }

        try:
            response = self.table.scan()
            items = response.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
                items.extend(response.get("Items", []))

            active = [i for i in items if i.get("status") == "active"]
            deprecated = [i for i in items if i.get("status") == "deprecated"]
            total_occurrences = sum(int(i.get("occurrence_count", 0)) for i in items)

            return {
                "total_keys": len(items),
                "active_keys": len(active),
                "deprecated_keys": len(deprecated),
                "total_occurrences": total_occurrences,
            }

        except ClientError:
            logger.exception("Error getting library stats")
            raise

    def check_key_similarity(
        self,
        proposed_key: str,
        threshold: float = 0.8,
    ) -> list[dict[str, Any]]:
        """
        Check if a proposed key is similar to existing keys.

        Uses string similarity to suggest existing keys that the user
        might want to use instead of creating a new one.

        Args:
            proposed_key: The key name being proposed.
            threshold: Minimum similarity score (0-1) to include in results.
                      Default 0.8 means 80% similar or higher.

        Returns:
            List of similar keys with format:
            [
                {
                    "keyName": "existing_key",
                    "similarity": 0.92,
                    "occurrenceCount": 47
                }
            ]
        """
        active_keys = self.get_active_keys()
        if not active_keys:
            return []

        similar_keys = []
        proposed_lower = proposed_key.lower().replace("-", "_").replace(" ", "_")

        for key in active_keys:
            existing_name = key.get("key_name", "")
            existing_lower = existing_name.lower()

            # Calculate similarity using sequence matching
            similarity = _calculate_similarity(proposed_lower, existing_lower)

            if similarity >= threshold:
                similar_keys.append(
                    {
                        "keyName": existing_name,
                        "similarity": round(similarity, 2),
                        "occurrenceCount": int(key.get("occurrence_count", 0)),
                    }
                )

        # Sort by similarity descending
        similar_keys.sort(key=lambda x: x["similarity"], reverse=True)

        logger.debug(
            f"Found {len(similar_keys)} keys similar to '{proposed_key}' (threshold: {threshold})"
        )
        return similar_keys[:5]  # Return top 5 matches


def _calculate_similarity(s1: str, s2: str) -> float:
    """
    Calculate string similarity using Levenshtein-like ratio.

    Uses difflib's SequenceMatcher which computes a ratio of matching
    characters to total characters.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Similarity ratio between 0 and 1.
    """
    from difflib import SequenceMatcher

    if not s1 or not s2:
        return 0.0

    # Exact match check first
    if s1 == s2:
        return 1.0

    return SequenceMatcher(None, s1, s2).ratio()
