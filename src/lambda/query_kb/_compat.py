"""Import compatibility layer for query_kb package.

Centralizes try/except ImportError for both package-relative and
flat-directory deployment modes. Each consumer module imports from
this single module instead of repeating the pattern.

This module re-exports all shared symbols from _clients and sibling
modules. The dual try/except is isolated here; consumers only need
one try/except to resolve _compat itself.
"""

# Re-export _clients symbols
try:
    from ._clients import (
        bedrock_agent,
        bedrock_runtime,
        dynamodb,
        dynamodb_client,
        s3_client,
    )
except ImportError:
    from _clients import (  # type: ignore[import-not-found,no-redef]
        bedrock_agent,
        bedrock_runtime,
        dynamodb,
        dynamodb_client,
        s3_client,
    )

__all__ = [
    "bedrock_agent",
    "bedrock_runtime",
    "dynamodb",
    "dynamodb_client",
    "s3_client",
]
