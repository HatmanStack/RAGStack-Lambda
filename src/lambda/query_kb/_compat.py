"""Import compatibility layer for query_kb package.

Centralizes try/except ImportError for both package-relative and
flat-directory deployment modes. Each consumer module imports from
this single module instead of repeating the pattern.

This module re-exports all shared symbols from _clients and sibling
modules. The dual try/except is isolated here; consumers only need
one try/except to resolve _compat itself.

IMPORTANT: _clients imports MUST come first. Sibling modules
(conversation, filters, media, etc.) import _clients symbols from
this module, so those symbols must be bound before any sibling
module is loaded.
"""

# --- _clients symbols (must be first) ---
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

# --- Sibling module symbols ---
# These imports are safe because sibling modules only depend on
# _clients symbols from _compat, which are already bound above.
try:
    from .conversation import (
        MAX_MESSAGE_LENGTH,
        get_conversation_history,
        store_conversation_turn,
        update_conversation_turn,
    )
    from .filters import (
        _get_filter_components,
        _get_filter_examples,
        get_config_manager,
    )
    from .media import (
        IMAGE_FORMAT_MAP,
        MAX_IMAGE_SIZE_BYTES,
        MEDIA_CONTENT_TYPES,
        extract_image_caption_from_content,
        extract_source_url_from_content,
        fetch_image_for_converse,
        format_timestamp,
        generate_media_url,
    )
    from .retrieval import (
        _augment_with_id_lookup,
        build_conversation_messages,
        build_retrieval_query,
    )
    from .sources import extract_sources
except ImportError:
    from conversation import (  # type: ignore[import-not-found,no-redef]
        MAX_MESSAGE_LENGTH,
        get_conversation_history,
        store_conversation_turn,
        update_conversation_turn,
    )
    from filters import (  # type: ignore[import-not-found,no-redef]
        _get_filter_components,
        _get_filter_examples,
        get_config_manager,
    )
    from media import (  # type: ignore[import-not-found,no-redef]
        IMAGE_FORMAT_MAP,
        MAX_IMAGE_SIZE_BYTES,
        MEDIA_CONTENT_TYPES,
        extract_image_caption_from_content,
        extract_source_url_from_content,
        fetch_image_for_converse,
        format_timestamp,
        generate_media_url,
    )
    from retrieval import (  # type: ignore[import-not-found,no-redef]
        _augment_with_id_lookup,
        build_conversation_messages,
        build_retrieval_query,
    )
    from sources import extract_sources  # type: ignore[import-not-found,no-redef]

__all__ = [
    # _clients
    "bedrock_agent",
    "bedrock_runtime",
    "dynamodb",
    "dynamodb_client",
    "s3_client",
    # conversation
    "MAX_MESSAGE_LENGTH",
    "get_conversation_history",
    "store_conversation_turn",
    "update_conversation_turn",
    # filters
    "_get_filter_components",
    "_get_filter_examples",
    "get_config_manager",
    # media
    "IMAGE_FORMAT_MAP",
    "MAX_IMAGE_SIZE_BYTES",
    "MEDIA_CONTENT_TYPES",
    "extract_image_caption_from_content",
    "extract_source_url_from_content",
    "fetch_image_for_converse",
    "format_timestamp",
    "generate_media_url",
    # retrieval
    "_augment_with_id_lookup",
    "build_conversation_messages",
    "build_retrieval_query",
    # sources
    "extract_sources",
]
