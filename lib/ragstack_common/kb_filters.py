"""Shared Knowledge Base filter utilities.

Functions for extracting and normalizing metadata values from
Bedrock Knowledge Base retrieval results.
"""

from typing import Any


def extract_kb_scalar(value: Any) -> str | None:
    """Extract scalar value from KB metadata which returns lists with quoted strings.

    KB returns metadata like: ['"0"'] or ['value1', 'value2']
    This extracts the first value and strips extra quotes.

    Args:
        value: Raw metadata value from KB retrieval (may be None, list, or scalar).

    Returns:
        Extracted string value, or None if input is None or empty list.
    """
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        value = value[0]
    if isinstance(value, str):
        return value.strip('"')
    return str(value)
