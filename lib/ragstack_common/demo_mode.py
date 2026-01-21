"""Demo Mode utilities for feature restrictions and rate limiting.

This module provides functions to check if demo mode is enabled and enforce
restrictions on features (disabled operations) and rate limits (upload/chat quotas).

Demo mode is designed for public demonstrations where billing needs to be controlled.
"""

import logging
import os
from datetime import UTC, datetime

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Quota TTL in days (counters auto-expire)
DEMO_QUOTA_TTL_DAYS = 2

# Features that are completely disabled in demo mode
DISABLED_FEATURES = frozenset({"reindex_all", "reprocess", "delete_documents"})

# Maximum file size in demo mode (10 MB) - prevents abuse via large documents
DEMO_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class DemoModeError(Exception):
    """Raised when demo mode blocks an operation."""

    def __init__(self, message: str, feature: str):
        super().__init__(message)
        self.feature = feature
        self.message = message


def is_demo_mode_enabled(config_manager=None) -> bool:
    """
    Check if demo mode is enabled via environment variable or config.

    Environment variable takes precedence for deployment-time control.

    Args:
        config_manager: Optional ConfigurationManager instance

    Returns:
        True if demo mode is enabled, False otherwise
    """
    # Check environment variable first (deployment-time control)
    if os.environ.get("DEMO_MODE", "").lower() == "true":
        return True

    # Check config table for runtime override
    if config_manager:
        try:
            return config_manager.get_parameter("demo_mode_enabled", False) is True
        except Exception as e:
            logger.warning(f"Failed to check demo_mode_enabled config: {e}")

    return False


def check_demo_mode_feature_allowed(feature: str, config_manager=None) -> None:
    """
    Check if a feature is allowed in demo mode. Raise DemoModeError if blocked.

    Args:
        feature: Feature identifier (e.g., "reindex_all", "reprocess", "delete_documents")
        config_manager: Optional ConfigurationManager instance

    Raises:
        DemoModeError: If the feature is disabled in demo mode
    """
    if not is_demo_mode_enabled(config_manager):
        return

    if feature in DISABLED_FEATURES:
        feature_names = {
            "reindex_all": "Reindex All Documents",
            "reprocess": "Reprocess Document",
            "delete_documents": "Delete Documents",
        }
        friendly_name = feature_names.get(feature, feature)
        raise DemoModeError(
            f"{friendly_name} is disabled in Demo Mode. "
            "This feature is restricted to prevent excessive resource usage.",
            feature,
        )


def demo_quota_check_and_increment(
    user_id: str,
    quota_type: str,
    config_table_name: str,
    dynamodb_client,
    config_manager=None,
) -> tuple[bool, str]:
    """
    Atomically check and increment demo mode quotas using DynamoDB transactions.

    Uses TransactWriteItems to ensure atomic updates, preventing race conditions.
    Counters auto-expire after DEMO_QUOTA_TTL_DAYS via DynamoDB TTL.

    Args:
        user_id: User identifier (Cognito sub or username)
        quota_type: Type of quota ("upload" or "chat")
        config_table_name: DynamoDB configuration table name
        dynamodb_client: boto3 DynamoDB client
        config_manager: Optional ConfigurationManager instance

    Returns:
        Tuple of (allowed, message):
        - allowed: True if within quota, False if quota exceeded
        - message: Descriptive message about quota status
    """
    if not is_demo_mode_enabled(config_manager):
        return True, ""

    if not user_id:
        return False, "Demo Mode: Authentication required for this feature"

    # Get demo quota limits from config
    if quota_type == "upload":
        default_limit = 5
        config_key = "demo_upload_quota_daily"
        friendly_name = "uploads"
    else:  # chat
        default_limit = 30
        config_key = "demo_chat_quota_daily"
        friendly_name = "chat messages"

    quota_limit = default_limit
    if config_manager:
        try:
            raw_limit = config_manager.get_parameter(config_key, default_limit)
            # Handle Decimal from DynamoDB
            quota_limit = int(raw_limit) if raw_limit is not None else default_limit
        except Exception as e:
            logger.warning(f"Failed to get {config_key} config: {e}")

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    ttl = int(datetime.now(UTC).timestamp()) + (DEMO_QUOTA_TTL_DAYS * 86400)
    quota_key = f"quota#demo_{quota_type}#{user_id}#{today}"

    try:
        dynamodb_client.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": config_table_name,
                        "Key": {"Configuration": {"S": quota_key}},
                        "UpdateExpression": "ADD #count :inc SET #ttl = :ttl",
                        "ConditionExpression": "#count < :limit OR attribute_not_exists(#count)",
                        "ExpressionAttributeNames": {"#count": "count", "#ttl": "ttl"},
                        "ExpressionAttributeValues": {
                            ":inc": {"N": "1"},
                            ":limit": {"N": str(quota_limit)},
                            ":ttl": {"N": str(ttl)},
                        },
                    }
                }
            ],
            ReturnConsumedCapacity="NONE",
        )

        user_prefix = user_id[:8] if user_id else "unknown"
        logger.info(f"Demo quota incremented for {user_prefix}..., type={quota_type}")
        return True, ""

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "TransactionCanceledException":
            # Check CancellationReasons to distinguish quota exceeded from other failures
            cancellation_reasons = e.response.get("CancellationReasons", [])
            is_quota_exceeded = any(
                reason.get("Code") == "ConditionalCheckFailed"
                for reason in cancellation_reasons
                if reason
            )

            if is_quota_exceeded:
                logger.info(f"Demo {quota_type} quota exceeded for user")
                return False, (
                    f"Demo Mode: Daily {friendly_name} limit reached ({quota_limit}/day). "
                    "Please try again tomorrow."
                )

            # Other transaction cancellation reasons (TransactionConflict, etc.)
            logger.error(f"Transaction cancelled for non-quota reason: {cancellation_reasons}")
            raise

        logger.error(f"Error in demo quota transaction: {e}")
        raise

    except Exception as e:
        logger.error(f"Error in demo quota check: {e}")
        raise


def get_demo_upload_conditions(config_manager=None) -> list | None:
    """
    Get S3 presigned POST conditions for demo mode uploads.

    Returns content-length-range condition to limit file size.

    Args:
        config_manager: Optional ConfigurationManager instance

    Returns:
        List of S3 conditions if demo mode enabled, None otherwise
    """
    if not is_demo_mode_enabled(config_manager):
        return None

    # Limit file size in demo mode to prevent abuse
    return [["content-length-range", 0, DEMO_MAX_FILE_SIZE_BYTES]]


def get_demo_max_file_size_mb() -> int:
    """Get the max file size in MB for demo mode uploads."""
    return DEMO_MAX_FILE_SIZE_BYTES // (1024 * 1024)


def get_demo_quota_remaining(
    user_id: str,
    quota_type: str,
    config_table_name: str,
    dynamodb_client,
    config_manager=None,
) -> dict:
    """
    Get remaining quota for a user in demo mode.

    Args:
        user_id: User identifier
        quota_type: Type of quota ("upload" or "chat")
        config_table_name: DynamoDB configuration table name
        dynamodb_client: boto3 DynamoDB client
        config_manager: Optional ConfigurationManager instance

    Returns:
        Dictionary with quota info: {used, limit, remaining}
    """
    if not is_demo_mode_enabled(config_manager):
        return {"used": 0, "limit": -1, "remaining": -1}  # -1 means unlimited

    # Get demo quota limits
    if quota_type == "upload":
        default_limit = 5
        config_key = "demo_upload_quota_daily"
    else:
        default_limit = 30
        config_key = "demo_chat_quota_daily"

    quota_limit = default_limit
    if config_manager:
        try:
            raw_limit = config_manager.get_parameter(config_key, default_limit)
            quota_limit = int(raw_limit) if raw_limit is not None else default_limit
        except Exception:
            pass

    if not user_id:
        return {"used": 0, "limit": quota_limit, "remaining": quota_limit}

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    quota_key = f"quota#demo_{quota_type}#{user_id}#{today}"

    try:
        response = dynamodb_client.get_item(
            TableName=config_table_name,
            Key={"Configuration": {"S": quota_key}},
        )
        item = response.get("Item", {})
        used = int(item.get("count", {}).get("N", "0"))
        remaining = max(0, quota_limit - used)
        return {"used": used, "limit": quota_limit, "remaining": remaining}

    except Exception as e:
        logger.warning(f"Failed to get quota remaining: {e}")
        return {"used": 0, "limit": quota_limit, "remaining": quota_limit}
