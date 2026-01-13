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


def expand_to_searchable_array(value: str, min_word_length: int = 3) -> list[str]:
    """
    Expand a string value into a searchable array with component parts.

    Includes the original value plus word components for flexible matching.
    For example: "chicago, illinois" -> ["chicago, illinois", "chicago", "illinois"]

    Args:
        value: The string value to expand.
        min_word_length: Minimum length for word components (default 3 to skip initials).

    Returns:
        List of searchable terms, limited to 10 items.
    """
    if not value or not value.strip():
        return []

    value = value.strip().lower()
    items = {value}  # Always include original

    # Split on commas first (highest priority after original)
    if "," in value:
        for part in value.split(","):
            part = part.strip()
            if part and len(part) >= min_word_length:
                items.add(part)

    # Split on spaces for word components
    for word in value.replace(",", " ").split():
        word = word.strip()
        if len(word) >= min_word_length:
            items.add(word)

    # Extract 4-digit years from date-like strings (e.g., "2016-01-15" -> "2016")
    year_match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", value)
    if year_match:
        items.add(year_match.group(1))

    # Prioritize: original value first, then sorted remaining items
    result = [value]
    remaining = sorted(items - {value})
    result.extend(remaining)

    return result[:MAX_ARRAY_ITEMS]


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
    normalized = {}

    for key, value in metadata.items():
        if value is None:
            continue

        if isinstance(value, list):
            # Already a list - expand each item and flatten
            expanded = set()
            for item in value:
                if isinstance(item, str):
                    expanded.update(expand_to_searchable_array(item))
                elif item is not None:
                    expanded.add(str(item).lower())
            if expanded:
                # Keep original items first, then additional expansions
                original_items = [str(v).lower().strip() for v in value if v]
                additional = sorted(expanded - set(original_items))
                result = original_items + additional
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
