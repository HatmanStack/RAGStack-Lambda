"""Metadata normalizer for S3 Vectors STRING_LIST expansion

This module provides functions to normalize metadata values for S3 Vectors storage.
All string values are converted to STRING_LIST arrays with smart expansion for
flexible element-level matching.

The normalizer:
- Expands strings into searchable arrays with component parts
- Supports comma-separated values, word splitting, year extraction
- Limits arrays to 10 items (AWS STRING_LIST limit)
- Ensures consistent lowercase values for filtering
"""

import re
from typing import Any

# AWS STRING_LIST maximum items
MAX_ARRAY_ITEMS = 10

# Maximum length for individual string values (S3 Vectors limit protection)
MAX_VALUE_LENGTH = 100


def expand_to_searchable_array(value: str, min_word_length: int = 3) -> list[str]:
    """
    Expand a string value into a searchable array with component parts.

    Includes word tokens first (best for $eq filtering), then the original
    phrase. For example: "chicago, illinois" -> ["chicago", "illinois", "chicago, illinois"]

    Args:
        value: The string value to expand.
        min_word_length: Minimum length for word components (default 3 to skip initials).

    Returns:
        List of searchable terms, limited to 10 items, each truncated to MAX_VALUE_LENGTH.
    """
    if not value or not value.strip():
        return []

    # Truncate input value to prevent excessively long strings
    value = value.strip().lower()[:MAX_VALUE_LENGTH]
    seen: set[str] = set()
    words: list[str] = []
    phrases: list[str] = []

    # Normalize delimiters: treat semicolons, pipes, slashes as commas
    normalized = re.sub(r"[;|/]", ",", value)

    # Collect delimiter-separated parts
    if "," in normalized:
        for part in normalized.split(","):
            part = part.strip()
            if part and len(part) >= min_word_length and part not in seen:
                seen.add(part)
                if " " in part:
                    phrases.append(part)
                else:
                    words.append(part)

    # Collect individual word tokens, stripping leading/trailing punctuation
    for raw_word in normalized.replace(",", " ").split():
        word = raw_word.strip().strip("().'\"")
        if len(word) >= min_word_length and word not in seen:
            seen.add(word)
            words.append(word)

    # Extract 4-digit years from date-like strings (e.g., "2016-01-15" -> "2016")
    year_match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", value)
    if year_match and year_match.group(1) not in seen:
        words.append(year_match.group(1))

    # Original phrase last (tokens are more useful for $eq filtering)
    if value not in seen:
        phrases.append(value)

    # Words first, then phrases (including original)
    return (words + phrases)[:MAX_ARRAY_ITEMS]


def normalize_metadata_for_s3(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize metadata values for S3 Vectors storage.

    All string values are converted to STRING_LIST arrays with smart expansion
    for flexible element-level matching. This allows searching for individual
    components (e.g., "chicago" matches "chicago, illinois").

    Expansion rules:
    - Original value always included
    - Comma-separated parts added as separate elements
    - Word components added (if >= 3 chars to skip initials)
    - Years extracted from date strings
    - Limited to 10 items per array (AWS limit)

    Args:
        metadata: Raw metadata dictionary.

    Returns:
        Normalized metadata with STRING_LIST arrays for all string fields.
    """
    normalized: dict[str, Any] = {}

    for key, value in metadata.items():
        if value is None:
            continue

        if isinstance(value, list):
            # Tokens-first: prioritize individual word tokens over full phrases.
            # For $eq filtering, single words ("dwight", "tillotson") are more
            # useful than multi-word phrases ("dwight sheldon tillotson") which
            # require exact match. This maximizes filterability when the list
            # has many items that would otherwise exhaust the MAX_ARRAY_ITEMS
            # budget with only full phrases and no searchable word tokens.
            seen: set[str] = set()
            words: list[str] = []
            phrases: list[str] = []
            for item in value:
                if item is None:
                    continue
                if isinstance(item, str):
                    tokens = expand_to_searchable_array(item)
                else:
                    # Preserve falsy values like 0 or False
                    tokens = [str(item).lower().strip()]
                for token in tokens:
                    if not token or token in seen:
                        continue
                    seen.add(token)
                    if " " in token:
                        phrases.append(token)
                    else:
                        words.append(token)
            # Words first (best for $eq filtering), then phrases
            result = words + phrases
            if result:
                normalized[key] = result[:MAX_ARRAY_ITEMS]

        elif isinstance(value, str):
            expanded = expand_to_searchable_array(value)
            if expanded:
                normalized[key] = expanded

        elif isinstance(value, bool):
            # Booleans stay as-is (not arrays)
            normalized[key] = value

        elif isinstance(value, (int, float)):
            # Numbers become single-item arrays for consistency
            normalized[key] = [str(value)]

        else:
            expanded = expand_to_searchable_array(str(value))
            if expanded:
                normalized[key] = expanded

    return normalized


# Default core metadata keys to preserve when reducing metadata
# This is a superset covering documents, media, and images
DEFAULT_CORE_METADATA_KEYS = frozenset(
    {
        "content_type",
        "document_id",
        "document_type",
        "duration_seconds",
        "filename",
        "main_topic",
        "segment_index",
        "timestamp_end",
        "timestamp_start",
    }
)


def reduce_metadata(
    metadata: dict[str, Any],
    reduction_level: int = 1,
    core_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    """
    Reduce metadata size by removing non-core keys or truncating values.

    Used when metadata is too large for ingestion APIs. Progressively strips
    non-essential fields while preserving core identifiers and search keys.

    Args:
        metadata: Original metadata dict.
        reduction_level: Aggressiveness of reduction:
            1 = keep all keys (no reduction)
            2 = truncate arrays to 3 items
            3 = core keys only
        core_keys: Set of keys to always preserve. Defaults to DEFAULT_CORE_METADATA_KEYS.

    Returns:
        Reduced metadata dict.
    """
    if core_keys is None:
        core_keys = DEFAULT_CORE_METADATA_KEYS

    reduced = {}

    for key, value in metadata.items():
        # Level 3: Only keep core keys
        if reduction_level >= 3 and key not in core_keys:
            continue

        # Core keys always kept as-is
        if key in core_keys:
            reduced[key] = value
            continue

        # Level 2+: Truncate arrays to 3 items, keep scalars
        if reduction_level >= 2:
            if isinstance(value, list):
                reduced[key] = value[:3]
            else:
                reduced[key] = value  # Preserve scalar values
        else:
            reduced[key] = value

    return reduced
