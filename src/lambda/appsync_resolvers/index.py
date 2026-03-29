"""AppSync Lambda resolver dispatcher.

Routes GraphQL field names to domain-specific resolver modules.
Shared state (clients, env vars, helpers) is defined in resolvers/shared.py.
"""

import json
import logging
from typing import Any

from resolvers.chat import get_conversation, query_knowledge_base
from resolvers.documents import (
    create_upload_url,
    delete_documents,
    get_document,
    list_documents,
    process_document,
    reindex_document,
    reprocess_document,
)
from resolvers.images import (
    create_image_upload_url,
    create_zip_upload_url,
    delete_image,
    generate_caption,
    get_image,
    list_images,
    submit_image,
)
from resolvers.metadata import (
    analyze_metadata,
    check_key_similarity,
    delete_metadata_key,
    get_filter_examples,
    get_key_library,
    get_metadata_stats,
    regenerate_filter_examples,
    start_reindex,
)
from resolvers.scrape import (
    cancel_scrape,
    check_scrape_url,
    get_scrape_job,
    list_scrape_jobs,
    start_scrape,
)
from resolvers.shared import (
    DATA_BUCKET,
    TRACKING_TABLE,
    get_config_manager,
    set_current_event,
)

from ragstack_common.auth import check_public_access
from ragstack_common.demo_mode import DemoModeError, check_demo_mode_feature_allowed

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Resolver dispatch table mapping GraphQL field names to handler functions
RESOLVERS = {
    # Document management
    "getDocument": get_document,
    "listDocuments": list_documents,
    "createUploadUrl": create_upload_url,
    "processDocument": process_document,
    "deleteDocuments": delete_documents,
    "reprocessDocument": reprocess_document,
    "reindexDocument": reindex_document,
    # Scrape
    "getScrapeJob": get_scrape_job,
    "listScrapeJobs": list_scrape_jobs,
    "checkScrapeUrl": check_scrape_url,
    "startScrape": start_scrape,
    "cancelScrape": cancel_scrape,
    # Images
    "createImageUploadUrl": create_image_upload_url,
    "generateCaption": generate_caption,
    "submitImage": submit_image,
    "getImage": get_image,
    "listImages": list_images,
    "deleteImage": delete_image,
    "createZipUploadUrl": create_zip_upload_url,
    # Metadata analysis
    "analyzeMetadata": analyze_metadata,
    "getMetadataStats": get_metadata_stats,
    "getFilterExamples": get_filter_examples,
    "getKeyLibrary": get_key_library,
    "checkKeySimilarity": check_key_similarity,
    "regenerateFilterExamples": regenerate_filter_examples,
    "deleteMetadataKey": delete_metadata_key,
    # KB Reindex
    "startReindex": start_reindex,
    # Async chat
    "queryKnowledgeBase": query_knowledge_base,
    "getConversation": get_conversation,
}

# Demo mode feature restrictions - block certain mutations entirely
DEMO_RESTRICTED_FEATURES = {
    "startReindex": "reindex_all",
    "reprocessDocument": "reprocess",
    "deleteDocuments": "delete_documents",
}

# Public access requirements per field
ACCESS_REQUIREMENTS = {
    "createUploadUrl": "upload",
    "createImageUploadUrl": "image_upload",
    "generateCaption": "image_upload",
    "submitImage": "image_upload",
    "createZipUploadUrl": "image_upload",
    "startScrape": "scrape",
    "checkScrapeUrl": "scrape",
    "cancelScrape": "scrape",
    "queryKnowledgeBase": "chat",
    "getConversation": "chat",
}


def lambda_handler(event: dict[str, Any], context: Any) -> Any:
    """Route to appropriate resolver based on GraphQL field name."""
    # Store event for resolvers that need identity context
    set_current_event(event)

    # Validate required environment variables
    if not TRACKING_TABLE:
        raise ValueError("TRACKING_TABLE environment variable is required")
    if not DATA_BUCKET:
        raise ValueError("DATA_BUCKET environment variable is required")

    # Clear config cache at handler entry to ensure fresh reads per invocation
    from resolvers.shared import clear_config_cache

    clear_config_cache()

    field_name = event["info"]["fieldName"]
    logger.info(f"AppSync resolver invoked for field: {field_name}")

    # Redact user query content from logs
    log_args = event.get("arguments", {})
    if field_name == "queryKnowledgeBase" and "query" in log_args:
        log_args = {**log_args, "query": "<REDACTED>"}
    logger.info(f"Arguments: {json.dumps(log_args)}")

    # Demo mode feature restrictions
    if field_name in DEMO_RESTRICTED_FEATURES:
        try:
            check_demo_mode_feature_allowed(
                DEMO_RESTRICTED_FEATURES[field_name], get_config_manager()
            )
        except DemoModeError as e:
            logger.info(f"Demo mode blocked {field_name}: {e.message}")
            raise ValueError(e.message) from e

    # Public access checks
    if field_name in ACCESS_REQUIREMENTS:
        access_type = ACCESS_REQUIREMENTS[field_name]
        allowed, error_msg = check_public_access(event, access_type, get_config_manager())
        if not allowed:
            raise ValueError(error_msg)

    # Dispatch to resolver
    resolver = RESOLVERS.get(field_name)
    if not resolver:
        logger.error(f"Unknown field: {field_name}")
        raise ValueError(f"Unknown field: {field_name}")

    try:
        result = resolver(event["arguments"])
        logger.info(f"Resolver {field_name} completed successfully")
        return result
    except ValueError as e:
        logger.exception(f"Validation error in {field_name}: {e}")
        raise
    except Exception as e:
        # Safety net: catch unexpected errors for GraphQL error formatting
        logger.exception(f"Unexpected error in {field_name}: {e}")
        raise
    finally:
        set_current_event(None)
