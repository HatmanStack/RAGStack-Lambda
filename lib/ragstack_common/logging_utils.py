"""
Logging utilities for safe, secure logging in Lambda functions.

Provides functions to mask sensitive data before logging to prevent
accidental exposure of PII, credentials, or user content in CloudWatch Logs.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default keys that should be masked in logs.
# SECURITY: This list uses substring matching (e.g., "token" matches "access_token", "id_token").
# We intentionally cast a wide net to prevent accidental PII exposure. False positives
# (masking non-sensitive data) are acceptable; false negatives (exposing sensitive data) are not.
# The "key" substring is included because it matches API keys, but may also match benign
# fields like "primary_key" - this is an acceptable tradeoff for security.
DEFAULT_SENSITIVE_KEYS = frozenset(
    {
        "query",  # User queries may contain PII or sensitive search terms
        "message",  # Chat messages, user content
        "content",  # Document content, response bodies
        "body",  # Request/response bodies
        "token",  # Auth tokens (access, refresh, id, JWT)
        "password",  # Credentials
        "secret",  # API secrets, signing keys
        "key",  # API keys, encryption keys (broad match intentional)
        "authorization",  # Auth headers
        "credential",  # Any credential type
        "apikey",  # Alternate API key naming
        "api_key",  # Snake case variant
        "access_token",  # OAuth tokens
        "refresh_token",  # OAuth tokens
        "id_token",  # OIDC tokens
    }
)


def mask_value(key: str, value: Any, sensitive_keys: frozenset[str] | None = None) -> Any:
    """
    Mask a value if the key indicates it contains sensitive data.

    Args:
        key: The dictionary key or field name
        value: The value to potentially mask
        sensitive_keys: Set of key substrings to treat as sensitive

    Returns:
        Masked value if sensitive, original value otherwise
    """
    if sensitive_keys is None:
        sensitive_keys = DEFAULT_SENSITIVE_KEYS

    key_lower = key.lower()

    # Check if any sensitive key substring is in the key.
    # SECURITY: Using substring matching (not exact match) to catch variations like
    # "user_query", "auth_token", "api_key_id". This may produce false positives on
    # benign fields, which is acceptable - we prefer over-masking to under-masking.
    if any(s in key_lower for s in sensitive_keys):
        if isinstance(value, str):
            # Show partial content for debugging (first 10 chars + length) if long enough.
            # Short values are fully masked to prevent credential exposure.
            if len(value) > 20:
                return f"{value[:10]}...({len(value)} chars)"
            return "***"
        if isinstance(value, (list, dict)):
            # Don't serialize complex structures - just indicate type
            return f"[{type(value).__name__}: masked]"
        return "***"

    # Recursively process nested structures to catch sensitive keys at any depth.
    # SECURITY: This handles nested event structures like {"request": {"body": {"password": "..."}}}
    if isinstance(value, dict):
        return {k: mask_value(k, v, sensitive_keys) for k, v in value.items()}

    if isinstance(value, list):
        # Propagate parent key context for list items (e.g., "tokens" list items)
        return [mask_value(key, item, sensitive_keys) for item in value]

    return value


def safe_log_event(
    event: dict[str, Any],
    sensitive_keys: frozenset[str] | None = None,
    max_depth: int = 5,
) -> dict[str, Any]:
    """
    Return event with sensitive data masked for safe logging.

    Use this instead of logging raw events to prevent PII or secrets
    from appearing in CloudWatch Logs.

    Args:
        event: The Lambda event or dictionary to sanitize
        sensitive_keys: Optional set of key substrings to treat as sensitive
        max_depth: Maximum recursion depth for nested structures

    Returns:
        A copy of the event with sensitive values masked

    Example:
        ```python
        from ragstack_common.logging_utils import safe_log_event

        def lambda_handler(event, context):
            logger.info(f"Processing event: {safe_log_event(event)}")
            # Logs: {"query": "What is...(...50 chars)", "token": "***"}
        ```
    """
    if not isinstance(event, dict):
        return {"_raw": str(event)[:100]}

    if sensitive_keys is None:
        sensitive_keys = DEFAULT_SENSITIVE_KEYS

    try:
        return {k: mask_value(k, v, sensitive_keys) for k, v in event.items()}
    except Exception as e:
        # SECURITY: Fail-safe behavior - if masking fails for any reason (recursion depth,
        # circular references, custom objects), return minimal safe info rather than
        # risking exposure of the original event. We log the error type but not the
        # event contents.
        logger.warning(f"Failed to mask event: {e}")
        return {"_error": "Could not safely serialize event", "_keys": list(event.keys())[:10]}


def log_summary(
    operation: str,
    *,
    success: bool = True,
    duration_ms: float | None = None,
    item_count: int | None = None,
    error: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Create a structured log summary for an operation.

    Provides a consistent format for logging operation results
    without exposing sensitive data.

    Args:
        operation: Name of the operation (e.g., "query_kb", "process_document")
        success: Whether the operation succeeded
        duration_ms: Optional duration in milliseconds
        item_count: Optional count of items processed
        error: Optional error message (will be truncated)
        **kwargs: Additional safe fields to include

    Returns:
        Dictionary suitable for structured logging

    Example:
        ```python
        logger.info(log_summary(
            "query_kb",
            success=True,
            duration_ms=150.5,
            item_count=3,
            knowledge_base_id="kb-abc123"
        ))
        ```
    """
    summary: dict[str, Any] = {
        "operation": operation,
        "success": success,
    }

    if duration_ms is not None:
        summary["duration_ms"] = round(duration_ms, 2)

    if item_count is not None:
        summary["item_count"] = item_count

    if error:
        # Truncate error messages to prevent log bloat
        summary["error"] = error[:500] if len(error) > 500 else error

    # Add any additional safe fields
    for key, value in kwargs.items():
        # Only include primitive types directly
        if isinstance(value, (str, int, float, bool)):
            summary[key] = value
        elif isinstance(value, (list, tuple)):
            summary[key] = len(value)  # Just log the count

    return summary
