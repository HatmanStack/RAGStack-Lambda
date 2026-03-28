"""Query KB Lambda - re-exports from package modules.

SAM Handler path: index.lambda_handler
This file exists for backwards compatibility with the SAM handler path
and test imports that access functions via `index.<function_name>`.
"""

try:
    from ._compat import (  # noqa: F401
        bedrock_agent,
        bedrock_runtime,
        dynamodb,
        dynamodb_client,
        s3_client,
    )
    from .conversation import get_conversation_history, store_conversation_turn  # noqa: F401
    from .filters import get_config_manager  # noqa: F401
    from .handler import atomic_quota_check_and_increment, lambda_handler  # noqa: F401
    from .media import (  # noqa: F401
        IMAGE_FORMAT_MAP,
        MAX_IMAGE_SIZE_BYTES,
        MEDIA_CONTENT_TYPES,
        extract_image_caption_from_content,
        extract_source_url_from_content,
        fetch_image_for_converse,
        format_timestamp,
        generate_media_url,
    )
    from .retrieval import (  # noqa: F401
        build_conversation_messages,
        build_retrieval_query,
    )
    from .sources import extract_sources  # noqa: F401
except ImportError:
    from _compat import (  # type: ignore[import-not-found]  # noqa: F401
        bedrock_agent,
        bedrock_runtime,
        dynamodb,
        dynamodb_client,
        s3_client,
    )
    from conversation import (  # type: ignore[import-not-found]  # noqa: F401
        get_conversation_history,
        store_conversation_turn,
    )
    from filters import get_config_manager  # type: ignore[import-not-found]  # noqa: F401
    from handler import (  # type: ignore[import-not-found]  # noqa: F401
        atomic_quota_check_and_increment,
        lambda_handler,
    )
    from media import (  # type: ignore[import-not-found]  # noqa: F401
        IMAGE_FORMAT_MAP,
        MAX_IMAGE_SIZE_BYTES,
        MEDIA_CONTENT_TYPES,
        extract_image_caption_from_content,
        extract_source_url_from_content,
        fetch_image_for_converse,
        format_timestamp,
        generate_media_url,
    )
    from retrieval import (  # type: ignore[import-not-found]  # noqa: F401
        build_conversation_messages,
        build_retrieval_query,
    )
    from sources import extract_sources  # type: ignore[import-not-found]  # noqa: F401

from ragstack_common.kb_filters import extract_kb_scalar  # noqa: F401
from ragstack_common.sources import (  # noqa: F401
    construct_image_uri_from_content_uri,
)
