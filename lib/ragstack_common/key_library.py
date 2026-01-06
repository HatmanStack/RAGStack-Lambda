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
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

MAX_SAMPLE_VALUES = 10


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

    def __init__(self, table_name: str | None = None):
        """
        Initialize the key library.

        Args:
            table_name: DynamoDB table name. If not provided, reads from
                       METADATA_KEY_LIBRARY_TABLE environment variable.
        """
        self.table_name = table_name or os.environ.get("METADATA_KEY_LIBRARY_TABLE")
        self._table = None
        self._table_exists = None

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

    def get_active_keys(self) -> list[dict[str, Any]]:
        """
        Return all metadata keys with status=active.

        Returns:
            List of key dictionaries, each containing key_name, data_type,
            sample_values, occurrence_count, first_seen, last_seen, status.
            Returns empty list if table doesn't exist or is empty.
        """
        if not self._check_table_exists():
            return []

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

            logger.debug(f"Retrieved {len(items)} active keys from library")
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
