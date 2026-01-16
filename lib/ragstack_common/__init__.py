"""Common Library

Shared utilities and classes for document pipeline document processing pipeline.
"""

from ragstack_common import constants
from ragstack_common.appsync import (
    publish_document_update,
    publish_image_update,
    publish_scrape_update,
)
from ragstack_common.auth import check_public_access
from ragstack_common.config import (
    ConfigurationManager,
    get_config_manager_or_none,
    get_knowledge_base_config,
)
from ragstack_common.filter_generator import FilterGenerator
from ragstack_common.image import (
    ImageStatus,
    is_supported_image,
    validate_image_size,
    validate_image_type,
)
from ragstack_common.ingestion import (
    batch_check_document_statuses,
    check_document_status,
    start_ingestion_with_retry,
)
from ragstack_common.key_library import KeyLibrary
from ragstack_common.logging_utils import log_summary, safe_log_event
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.metadata_normalizer import (
    DEFAULT_CORE_METADATA_KEYS,
    expand_to_searchable_array,
    normalize_metadata_for_s3,
    reduce_metadata,
)
from ragstack_common.multislice_retriever import MultiSliceRetriever
from ragstack_common.storage import (
    extract_filename_from_s3_uri,
    generate_presigned_url,
    get_file_type_from_filename,
    is_valid_uuid,
    parse_s3_uri,
    write_metadata_to_s3,
)

__all__ = [
    "batch_check_document_statuses",
    "check_document_status",
    "ConfigurationManager",
    "FilterGenerator",
    "generate_presigned_url",
    "get_config_manager_or_none",
    "get_knowledge_base_config",
    "ImageStatus",
    "KeyLibrary",
    "MetadataExtractor",
    "MultiSliceRetriever",
    "check_public_access",
    "constants",
    "DEFAULT_CORE_METADATA_KEYS",
    "expand_to_searchable_array",
    "extract_filename_from_s3_uri",
    "get_file_type_from_filename",
    "is_supported_image",
    "is_valid_uuid",
    "log_summary",
    "normalize_metadata_for_s3",
    "parse_s3_uri",
    "publish_document_update",
    "publish_image_update",
    "publish_scrape_update",
    "reduce_metadata",
    "safe_log_event",
    "start_ingestion_with_retry",
    "validate_image_size",
    "validate_image_type",
    "write_metadata_to_s3",
]
