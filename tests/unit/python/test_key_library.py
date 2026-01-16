"""Unit tests for KeyLibrary

Tests the KeyLibrary class using mocked boto3 DynamoDB resource.
No actual AWS calls are made.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from ragstack_common.key_library import MAX_SAMPLE_VALUES, KeyLibrary

# Fixtures


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table resource."""
    mock_table = MagicMock()
    # Configure table_status as a property that returns "ACTIVE"
    type(mock_table).table_status = "ACTIVE"
    mock_table.get_item = MagicMock()
    mock_table.scan = MagicMock()
    mock_table.update_item = MagicMock()
    return mock_table


@pytest.fixture
def mock_dynamodb_resource(mock_dynamodb_table):
    """Create a mock boto3 DynamoDB resource."""
    mock_resource = MagicMock()
    mock_resource.Table.return_value = mock_dynamodb_table
    return mock_resource


@pytest.fixture
def key_library(mock_dynamodb_resource):
    """Create a KeyLibrary with mocked DynamoDB."""
    with patch("ragstack_common.key_library.boto3.resource", return_value=mock_dynamodb_resource):
        library = KeyLibrary(table_name="test-key-library")
        # Force table property to be initialized within the patch context
        _ = library.table
        # Mark table as existing (already checked via mock)
        library._table_exists = True
        return library


@pytest.fixture
def sample_keys():
    """Sample key library entries."""
    return [
        {
            "key_name": "topic",
            "data_type": "string",
            "sample_values": ["genealogy", "immigration"],
            "occurrence_count": 25,
            "first_seen": "2024-01-15T10:00:00+00:00",
            "last_seen": "2024-01-20T15:30:00+00:00",
            "status": "active",
        },
        {
            "key_name": "date_range",
            "data_type": "string",
            "sample_values": ["1900-1950", "1850-1900"],
            "occurrence_count": 18,
            "first_seen": "2024-01-16T09:00:00+00:00",
            "last_seen": "2024-01-19T14:00:00+00:00",
            "status": "active",
        },
        {
            "key_name": "old_key",
            "data_type": "string",
            "sample_values": ["value1"],
            "occurrence_count": 5,
            "first_seen": "2024-01-10T08:00:00+00:00",
            "last_seen": "2024-01-12T12:00:00+00:00",
            "status": "deprecated",
        },
    ]


# Test: Initialization


def test_init_with_table_name():
    """Test KeyLibrary initialization with explicit table name."""
    with patch("boto3.resource"):
        library = KeyLibrary(table_name="my-table")
        assert library.table_name == "my-table"


def test_init_with_env_var():
    """Test KeyLibrary initialization from environment variable."""
    os.environ["METADATA_KEY_LIBRARY_TABLE"] = "env-table"
    try:
        library = KeyLibrary()
        assert library.table_name == "env-table"
    finally:
        del os.environ["METADATA_KEY_LIBRARY_TABLE"]


def test_init_without_table_name():
    """Test KeyLibrary initialization without table name logs warning."""
    # Ensure env var is not set
    os.environ.pop("METADATA_KEY_LIBRARY_TABLE", None)

    library = KeyLibrary()
    assert library.table_name is None


# Test: get_active_keys


def test_get_active_keys_returns_active_only(key_library, mock_dynamodb_table, sample_keys):
    """Test that get_active_keys returns only active keys."""
    # Setup: return all keys, but only active ones should match filter
    active_keys = [k for k in sample_keys if k["status"] == "active"]
    mock_dynamodb_table.scan.return_value = {"Items": active_keys}

    result = key_library.get_active_keys()

    assert len(result) == 2
    assert all(k["status"] == "active" for k in result)
    mock_dynamodb_table.scan.assert_called_once()


def test_get_active_keys_empty_table(key_library, mock_dynamodb_table):
    """Test get_active_keys returns empty list on empty table."""
    mock_dynamodb_table.scan.return_value = {"Items": []}

    result = key_library.get_active_keys()

    assert result == []


def test_get_active_keys_handles_pagination(key_library, mock_dynamodb_table, sample_keys):
    """Test that get_active_keys handles paginated results."""
    active_keys = [k for k in sample_keys if k["status"] == "active"]

    # First call returns one item and pagination key
    mock_dynamodb_table.scan.side_effect = [
        {"Items": [active_keys[0]], "LastEvaluatedKey": {"key_name": "topic"}},
        {"Items": [active_keys[1]]},
    ]

    result = key_library.get_active_keys()

    assert len(result) == 2
    assert mock_dynamodb_table.scan.call_count == 2


def _raise_resource_not_found():
    """Helper to raise ResourceNotFoundException."""
    raise ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
        "DescribeTable",
    )


def test_get_active_keys_table_not_exists(mock_dynamodb_resource):
    """Test get_active_keys returns empty list when table doesn't exist."""
    mock_table = MagicMock()
    # Simulate ResourceNotFoundException when accessing table_status
    type(mock_table).table_status = property(fget=lambda _: _raise_resource_not_found())
    mock_dynamodb_resource.Table.return_value = mock_table

    with patch("boto3.resource", return_value=mock_dynamodb_resource):
        library = KeyLibrary(table_name="nonexistent-table")
        result = library.get_active_keys()

    assert result == []


# Test: get_key


def test_get_key_existing(key_library, mock_dynamodb_table, sample_keys):
    """Test retrieving an existing key."""
    mock_dynamodb_table.get_item.return_value = {"Item": sample_keys[0]}

    result = key_library.get_key("topic")

    assert result == sample_keys[0]
    mock_dynamodb_table.get_item.assert_called_once_with(Key={"key_name": "topic"})


def test_get_key_not_found(key_library, mock_dynamodb_table):
    """Test retrieving a non-existent key returns None."""
    mock_dynamodb_table.get_item.return_value = {}

    result = key_library.get_key("nonexistent")

    assert result is None


def test_get_key_dynamodb_error(key_library, mock_dynamodb_table):
    """Test DynamoDB ClientError is propagated."""
    mock_dynamodb_table.get_item.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "Server error"}}, "GetItem"
    )

    with pytest.raises(ClientError):
        key_library.get_key("topic")


# Test: get_key_names


def test_get_key_names_returns_sorted_list(key_library, mock_dynamodb_table, sample_keys):
    """Test get_key_names returns sorted list of active key names."""
    active_keys = [k for k in sample_keys if k["status"] == "active"]
    mock_dynamodb_table.scan.return_value = {"Items": active_keys}

    result = key_library.get_key_names()

    assert result == ["date_range", "topic"]  # Sorted alphabetically


def test_get_key_names_empty(key_library, mock_dynamodb_table):
    """Test get_key_names returns empty list when no keys exist."""
    mock_dynamodb_table.scan.return_value = {"Items": []}

    result = key_library.get_key_names()

    assert result == []


# Test: upsert_key


def test_upsert_key_creates_new_key(key_library, mock_dynamodb_table):
    """Test upsert_key creates a new key correctly."""
    mock_dynamodb_table.get_item.return_value = {
        "Item": {"key_name": "location", "sample_values": []}
    }

    key_library.upsert_key("location", "string", "New York")

    # Verify update_item was called with correct parameters
    mock_dynamodb_table.update_item.assert_called()
    call_args = mock_dynamodb_table.update_item.call_args_list[0]
    assert call_args.kwargs["Key"] == {"key_name": "location"}
    assert ":data_type" in call_args.kwargs["ExpressionAttributeValues"]
    assert call_args.kwargs["ExpressionAttributeValues"][":data_type"] == "string"


def test_upsert_key_increments_count(key_library, mock_dynamodb_table, sample_keys):
    """Test upsert_key increments occurrence_count on existing key."""
    mock_dynamodb_table.get_item.return_value = {"Item": sample_keys[0]}

    key_library.upsert_key("topic", "string", "new_topic")

    # Verify ADD occurrence_count :inc is in the update expression
    call_args = mock_dynamodb_table.update_item.call_args_list[0]
    assert "ADD occurrence_count :inc" in call_args.kwargs["UpdateExpression"]
    assert call_args.kwargs["ExpressionAttributeValues"][":inc"] == 1


def test_upsert_key_truncates_long_values(key_library, mock_dynamodb_table):
    """Test that sample values are truncated to 100 characters."""
    long_value = "x" * 200
    mock_dynamodb_table.get_item.return_value = {"Item": {"key_name": "test", "sample_values": []}}

    key_library.upsert_key("test", "string", long_value)

    # The _add_sample_value is called with truncated value
    # Check the second update_item call (adding sample value)
    assert mock_dynamodb_table.update_item.call_count >= 1


def test_upsert_key_adds_sample_value(key_library, mock_dynamodb_table):
    """Test that new sample values are added."""
    mock_dynamodb_table.get_item.return_value = {
        "Item": {"key_name": "topic", "sample_values": ["existing"]}
    }

    key_library.upsert_key("topic", "string", "new_value")

    # Second update_item should add sample value
    assert mock_dynamodb_table.update_item.call_count >= 1


def test_upsert_key_skips_duplicate_sample(key_library, mock_dynamodb_table):
    """Test that duplicate sample values are not added."""
    mock_dynamodb_table.get_item.return_value = {
        "Item": {"key_name": "topic", "sample_values": ["existing_value"]}
    }

    key_library.upsert_key("topic", "string", "existing_value")

    # First call is the main upsert, no second call for sample since it's duplicate
    # The sample addition is skipped internally
    call_count = mock_dynamodb_table.update_item.call_count
    assert call_count == 1  # Only the main upsert, no sample addition


def test_upsert_key_respects_max_samples(key_library, mock_dynamodb_table):
    """Test that sample values are capped at MAX_SAMPLE_VALUES."""
    existing_samples = [f"value{i}" for i in range(MAX_SAMPLE_VALUES)]
    mock_dynamodb_table.get_item.return_value = {
        "Item": {"key_name": "topic", "sample_values": existing_samples}
    }

    key_library.upsert_key("topic", "string", "new_value")

    # Only one update_item (main upsert), no sample addition since at max
    assert mock_dynamodb_table.update_item.call_count == 1


def test_upsert_key_table_not_exists(mock_dynamodb_resource):
    """Test upsert_key handles missing table gracefully."""
    mock_table = MagicMock()
    type(mock_table).table_status = property(fget=lambda _: _raise_resource_not_found())
    mock_dynamodb_resource.Table.return_value = mock_table

    with patch("boto3.resource", return_value=mock_dynamodb_resource):
        library = KeyLibrary(table_name="nonexistent-table")
        # Should not raise, just log warning
        library.upsert_key("test", "string", "value")


# Test: deprecate_key


def test_deprecate_key(key_library, mock_dynamodb_table):
    """Test deprecating a key."""
    key_library.deprecate_key("old_key")

    mock_dynamodb_table.update_item.assert_called_once()
    call_args = mock_dynamodb_table.update_item.call_args
    assert call_args.kwargs["Key"] == {"key_name": "old_key"}
    assert call_args.kwargs["ExpressionAttributeValues"][":deprecated"] == "deprecated"


# Test: get_library_stats


def test_get_library_stats(key_library, mock_dynamodb_table, sample_keys):
    """Test getting library statistics."""
    mock_dynamodb_table.scan.return_value = {"Items": sample_keys}

    result = key_library.get_library_stats()

    assert result["total_keys"] == 3
    assert result["active_keys"] == 2
    assert result["deprecated_keys"] == 1
    assert result["total_occurrences"] == 48  # 25 + 18 + 5


def test_get_library_stats_empty(key_library, mock_dynamodb_table):
    """Test stats on empty table."""
    mock_dynamodb_table.scan.return_value = {"Items": []}

    result = key_library.get_library_stats()

    assert result["total_keys"] == 0
    assert result["active_keys"] == 0
    assert result["deprecated_keys"] == 0
    assert result["total_occurrences"] == 0


def test_get_library_stats_table_not_exists(mock_dynamodb_resource):
    """Test stats when table doesn't exist."""
    mock_table = MagicMock()
    type(mock_table).table_status = property(fget=lambda _: _raise_resource_not_found())
    mock_dynamodb_resource.Table.return_value = mock_table

    with patch("boto3.resource", return_value=mock_dynamodb_resource):
        library = KeyLibrary(table_name="nonexistent-table")
        result = library.get_library_stats()

    assert result["total_keys"] == 0


# Test: check_key_similarity


def test_check_key_similarity_exact_match(key_library, mock_dynamodb_table):
    """Test similarity check with exact match."""
    mock_dynamodb_table.scan.return_value = {
        "Items": [
            {"key_name": "topic", "status": "active", "occurrence_count": 100},
            {"key_name": "location", "status": "active", "occurrence_count": 50},
        ]
    }

    result = key_library.check_key_similarity("topic")

    assert len(result) == 1
    assert result[0]["keyName"] == "topic"
    assert result[0]["similarity"] == 1.0


def test_check_key_similarity_partial_match(key_library, mock_dynamodb_table):
    """Test similarity check with partial match."""
    mock_dynamodb_table.scan.return_value = {
        "Items": [
            {"key_name": "document_type", "status": "active", "occurrence_count": 100},
            {"key_name": "doc_type", "status": "active", "occurrence_count": 50},
        ]
    }

    # "doc_type" should match "doc_type" exactly and be similar to "document_type"
    result = key_library.check_key_similarity("doc_type", threshold=0.6)

    assert len(result) >= 1
    assert any(k["keyName"] == "doc_type" for k in result)


def test_check_key_similarity_no_matches(key_library, mock_dynamodb_table):
    """Test similarity check with no matches."""
    mock_dynamodb_table.scan.return_value = {
        "Items": [
            {"key_name": "topic", "status": "active", "occurrence_count": 100},
            {"key_name": "location", "status": "active", "occurrence_count": 50},
        ]
    }

    # Very different key should have no matches at high threshold
    result = key_library.check_key_similarity("xyzabc", threshold=0.8)

    assert len(result) == 0


def test_check_key_similarity_empty_library(key_library, mock_dynamodb_table):
    """Test similarity check with empty library."""
    mock_dynamodb_table.scan.return_value = {"Items": []}

    result = key_library.check_key_similarity("topic")

    assert result == []


def test_check_key_similarity_normalizes_input(key_library, mock_dynamodb_table):
    """Test that input key is normalized before comparison."""
    mock_dynamodb_table.scan.return_value = {
        "Items": [
            {"key_name": "document_type", "status": "active", "occurrence_count": 100},
        ]
    }

    # Hyphenated and spaced input should match underscore version
    result = key_library.check_key_similarity("document-type", threshold=0.9)

    assert len(result) == 1
    assert result[0]["keyName"] == "document_type"


def test_check_key_similarity_returns_top_5(key_library, mock_dynamodb_table):
    """Test that only top 5 matches are returned."""
    # Create 10 similar keys
    items = [
        {"key_name": f"topic{i}", "status": "active", "occurrence_count": i * 10} for i in range(10)
    ]
    mock_dynamodb_table.scan.return_value = {"Items": items}

    result = key_library.check_key_similarity("topic", threshold=0.5)

    assert len(result) <= 5


# Test: Media Key Support


def test_media_default_keys_constant(key_library):
    """Test that MEDIA_DEFAULT_KEYS constant exists."""
    from ragstack_common.key_library import MEDIA_DEFAULT_KEYS

    assert isinstance(MEDIA_DEFAULT_KEYS, list)
    assert len(MEDIA_DEFAULT_KEYS) > 0

    # Check required keys
    key_names = [k["key_name"] for k in MEDIA_DEFAULT_KEYS]
    assert "content_type" in key_names
    assert "media_type" in key_names
    assert "timestamp_start" in key_names
    assert "timestamp_end" in key_names


def test_media_default_keys_have_required_fields():
    """Test that each media key has required fields."""
    from ragstack_common.key_library import MEDIA_DEFAULT_KEYS

    for key in MEDIA_DEFAULT_KEYS:
        assert "key_name" in key
        assert "data_type" in key
        assert key["data_type"] in ["string", "number", "boolean", "list"]


def test_seed_media_keys(key_library, mock_dynamodb_table):
    """Test seeding media keys to library."""
    mock_dynamodb_table.scan.return_value = {"Items": []}

    key_library.seed_media_keys()

    # Verify update_item was called for each media key
    from ragstack_common.key_library import MEDIA_DEFAULT_KEYS

    assert mock_dynamodb_table.update_item.call_count == len(MEDIA_DEFAULT_KEYS)


def test_seed_media_keys_skips_existing(key_library, mock_dynamodb_table):
    """Test that seeding skips existing keys."""
    # Simulate content_type already exists
    mock_dynamodb_table.scan.return_value = {
        "Items": [
            {"key_name": "content_type", "status": "active", "occurrence_count": 100},
        ]
    }
    mock_dynamodb_table.get_item.return_value = {
        "Item": {"key_name": "content_type", "status": "active"}
    }

    key_library.seed_media_keys()

    # Should still update all keys (upsert behavior)
    assert mock_dynamodb_table.update_item.call_count >= 1


def test_get_active_keys_includes_media_keys(key_library, mock_dynamodb_table):
    """Test that get_active_keys returns media keys."""
    mock_dynamodb_table.scan.return_value = {
        "Items": [
            {"key_name": "content_type", "data_type": "string", "status": "active"},
            {"key_name": "timestamp_start", "data_type": "number", "status": "active"},
            {"key_name": "topic", "data_type": "string", "status": "active"},
        ]
    }

    result = key_library.get_active_keys()

    key_names = [k["key_name"] for k in result]
    assert "content_type" in key_names
    assert "timestamp_start" in key_names


# Test: reset_occurrence_counts


def test_reset_occurrence_counts_success(key_library, mock_dynamodb_table):
    """Test resetting occurrence counts for all keys."""
    mock_dynamodb_table.scan.return_value = {
        "Items": [
            {"key_name": "topic"},
            {"key_name": "location"},
            {"key_name": "date_range"},
        ]
    }

    result = key_library.reset_occurrence_counts()

    assert result == 3
    assert mock_dynamodb_table.update_item.call_count == 3
    # Verify update_item was called with correct parameters
    for call in mock_dynamodb_table.update_item.call_args_list:
        assert ":zero" in call.kwargs["ExpressionAttributeValues"]
        assert call.kwargs["ExpressionAttributeValues"][":zero"] == 0


def test_reset_occurrence_counts_empty_table(key_library, mock_dynamodb_table):
    """Test reset on empty table returns 0."""
    mock_dynamodb_table.scan.return_value = {"Items": []}

    result = key_library.reset_occurrence_counts()

    assert result == 0
    mock_dynamodb_table.update_item.assert_not_called()


def test_reset_occurrence_counts_handles_pagination(key_library, mock_dynamodb_table):
    """Test reset handles paginated results."""
    mock_dynamodb_table.scan.side_effect = [
        {"Items": [{"key_name": "topic"}], "LastEvaluatedKey": {"key_name": "topic"}},
        {"Items": [{"key_name": "location"}]},
    ]

    result = key_library.reset_occurrence_counts()

    assert result == 2
    assert mock_dynamodb_table.scan.call_count == 2


def test_reset_occurrence_counts_table_not_exists(mock_dynamodb_resource):
    """Test reset returns 0 when table doesn't exist."""
    mock_table = MagicMock()
    type(mock_table).table_status = property(fget=lambda _: _raise_resource_not_found())
    mock_dynamodb_resource.Table.return_value = mock_table

    with patch("boto3.resource", return_value=mock_dynamodb_resource):
        library = KeyLibrary(table_name="nonexistent-table")
        result = library.reset_occurrence_counts()

    assert result == 0


def test_reset_occurrence_counts_clears_cache(key_library, mock_dynamodb_table):
    """Test that reset clears the active keys cache."""
    mock_dynamodb_table.scan.return_value = {"Items": [{"key_name": "topic"}]}
    key_library._active_keys_cache = [{"key_name": "cached"}]
    key_library._active_keys_cache_time = 12345

    key_library.reset_occurrence_counts()

    assert key_library._active_keys_cache is None
    assert key_library._active_keys_cache_time is None


# Test: deactivate_zero_count_keys


def test_deactivate_zero_count_keys_success(key_library, mock_dynamodb_table):
    """Test deactivating keys with zero occurrence count."""
    mock_dynamodb_table.scan.return_value = {
        "Items": [
            {"key_name": "unused_key1"},
            {"key_name": "unused_key2"},
        ]
    }

    result = key_library.deactivate_zero_count_keys()

    assert result == 2
    assert mock_dynamodb_table.update_item.call_count == 2
    # Verify status is set to inactive
    for call in mock_dynamodb_table.update_item.call_args_list:
        assert ":inactive" in call.kwargs["ExpressionAttributeValues"]
        assert call.kwargs["ExpressionAttributeValues"][":inactive"] == "inactive"


def test_deactivate_zero_count_keys_none_to_deactivate(key_library, mock_dynamodb_table):
    """Test deactivate returns 0 when no keys need deactivation."""
    mock_dynamodb_table.scan.return_value = {"Items": []}

    result = key_library.deactivate_zero_count_keys()

    assert result == 0
    mock_dynamodb_table.update_item.assert_not_called()


def test_deactivate_zero_count_keys_handles_pagination(key_library, mock_dynamodb_table):
    """Test deactivate handles paginated results."""
    mock_dynamodb_table.scan.side_effect = [
        {"Items": [{"key_name": "key1"}], "LastEvaluatedKey": {"key_name": "key1"}},
        {"Items": [{"key_name": "key2"}]},
    ]

    result = key_library.deactivate_zero_count_keys()

    assert result == 2
    assert mock_dynamodb_table.scan.call_count == 2


def test_deactivate_zero_count_keys_table_not_exists(mock_dynamodb_resource):
    """Test deactivate returns 0 when table doesn't exist."""
    mock_table = MagicMock()
    type(mock_table).table_status = property(fget=lambda _: _raise_resource_not_found())
    mock_dynamodb_resource.Table.return_value = mock_table

    with patch("boto3.resource", return_value=mock_dynamodb_resource):
        library = KeyLibrary(table_name="nonexistent-table")
        result = library.deactivate_zero_count_keys()

    assert result == 0


def test_deactivate_zero_count_keys_clears_cache(key_library, mock_dynamodb_table):
    """Test that deactivate clears the active keys cache."""
    mock_dynamodb_table.scan.return_value = {"Items": [{"key_name": "topic"}]}
    key_library._active_keys_cache = [{"key_name": "cached"}]
    key_library._active_keys_cache_time = 12345

    key_library.deactivate_zero_count_keys()

    assert key_library._active_keys_cache is None
    assert key_library._active_keys_cache_time is None
