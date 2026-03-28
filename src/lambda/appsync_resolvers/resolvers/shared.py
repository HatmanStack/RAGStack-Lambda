"""Shared utilities, AWS clients, and configuration for resolver modules.

All boto3 clients, environment variables, and cross-domain helper functions
live here. Domain modules import what they need from this module.
"""

import json
import logging
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from ragstack_common.config import ConfigurationManager, get_knowledge_base_config
from ragstack_common.demo_mode import (
    DemoModeError,
    check_demo_mode_feature_allowed,
    demo_quota_check_and_increment,
    get_demo_upload_conditions,
    is_demo_mode_enabled,
)
from ragstack_common.filter_examples import (
    generate_filter_examples,
    store_filter_examples,
    update_config_with_examples,
)
from ragstack_common.image import ImageStatus, is_supported_image, validate_image_type
from ragstack_common.ingestion import ingest_documents_with_retry
from ragstack_common.key_library import KeyLibrary
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.scraper import ScrapeStatus
from ragstack_common.storage import (
    is_valid_uuid,
    parse_s3_uri,
    read_s3_text,
    write_metadata_to_s3,
)

logger = logging.getLogger()

# =========================================================================
# AWS Clients
# =========================================================================

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sfn = boto3.client("stepfunctions")
lambda_client = boto3.client("lambda")
bedrock_agent = boto3.client("bedrock-agent")
dynamodb_client = boto3.client("dynamodb")
bedrock_runtime = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION"))

# =========================================================================
# Environment Variables
# =========================================================================

TRACKING_TABLE = os.environ.get("TRACKING_TABLE")
DATA_BUCKET = os.environ.get("DATA_BUCKET")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID")
DATA_SOURCE_ID = os.environ.get("DATA_SOURCE_ID")

SCRAPE_JOBS_TABLE = os.environ.get("SCRAPE_JOBS_TABLE")
SCRAPE_URLS_TABLE = os.environ.get("SCRAPE_URLS_TABLE")
SCRAPE_START_FUNCTION_ARN = os.environ.get("SCRAPE_START_FUNCTION_ARN")

METADATA_ANALYZER_FUNCTION_ARN = os.environ.get("METADATA_ANALYZER_FUNCTION_ARN")
PROCESS_IMAGE_FUNCTION_ARN = os.environ.get("PROCESS_IMAGE_FUNCTION_ARN")
QUERY_KB_FUNCTION_ARN = os.environ.get("QUERY_KB_FUNCTION_ARN")
CONVERSATION_TABLE_NAME = os.environ.get("CONVERSATION_TABLE_NAME")
METADATA_KEY_LIBRARY_TABLE = os.environ.get("METADATA_KEY_LIBRARY_TABLE")
CONFIGURATION_TABLE_NAME = os.environ.get("CONFIGURATION_TABLE_NAME")
REINDEX_STATE_MACHINE_ARN = os.environ.get("REINDEX_STATE_MACHINE_ARN")
INGEST_TO_KB_FUNCTION_ARN = os.environ.get("INGEST_TO_KB_FUNCTION_ARN")

# =========================================================================
# Validation Constants
# =========================================================================

MAX_FILENAME_LENGTH = 255
MAX_DOCUMENTS_LIMIT = 100
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f]")

# Reindex lock key - must match reindex_kb/index.py
REINDEX_LOCK_KEY = "reindex_lock"

# =========================================================================
# Configuration Manager (lazy init)
# =========================================================================

_config_manager: ConfigurationManager | None = None


def get_config_manager() -> ConfigurationManager:
    """Lazy initialization of ConfigurationManager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


# =========================================================================
# Current Event (set by dispatcher, read by resolvers)
# =========================================================================

_current_event: dict[str, Any] | None = None


def set_current_event(event: dict[str, Any] | None) -> None:
    """Set the current event (called by dispatcher at handler entry)."""
    global _current_event
    _current_event = event


def get_current_event() -> dict[str, Any] | None:
    """Get the current event."""
    return _current_event


# =========================================================================
# Identity Helper
# =========================================================================


def get_current_user_id(event: dict[str, Any] | None = None) -> str | None:
    """Get user ID from the event's identity.

    Args:
        event: The AppSync event. Falls back to _current_event if None.

    Returns:
        User ID string or None if not available.
    """
    evt = event if event is not None else _current_event
    if not evt:
        return None
    identity = evt.get("identity") or {}
    return identity.get("sub") or identity.get("username")


# =========================================================================
# Shared Helper Functions
# =========================================================================


def convert_decimals(obj: Any) -> Any:
    """Convert DynamoDB Decimal types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def check_reindex_lock() -> None:
    """Check if a full KB reindex is in progress and raise error if so.

    Raises:
        ValueError: If reindex is in progress.
    """
    config_table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
    if not config_table_name:
        return

    try:
        table = dynamodb.Table(config_table_name)
        response = table.get_item(Key={"Configuration": REINDEX_LOCK_KEY})
        lock = response.get("Item")

        if lock and lock.get("is_locked"):
            started_at = str(lock.get("started_at", "unknown"))
            raise ValueError(
                f"Operation blocked: Knowledge Base reindex is in progress "
                f"(started: {started_at}). Please wait for the reindex to complete."
            )
    except ClientError as e:
        logger.warning(f"Error checking reindex lock: {e}")
    except ValueError:
        raise


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by stripping control characters.

    S3 keys accept any UTF-8 character, so only ASCII control characters
    are removed. Path traversal is handled separately in the upload resolvers.
    Returns "unnamed" if the result would be empty.
    """
    if not filename:
        return "unnamed"

    sanitized = CONTROL_CHARS_PATTERN.sub("", filename).strip()

    if not sanitized:
        return "unnamed"

    return sanitized


def generate_presigned_download_url(s3_uri: str, expiration: int = 3600) -> str | None:
    """Generate presigned URL for S3 object download."""
    if not s3_uri or not s3_uri.startswith("s3://"):
        return None
    try:
        bucket, key = parse_s3_uri(s3_uri)
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration,
        )
    except ClientError as e:
        logger.warning(f"Failed to generate presigned URL: {e}")
        return None
