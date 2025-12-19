"""Sync budget configuration changes to AWS Budgets.

This Lambda is triggered by DynamoDB Streams when the ConfigurationTable
'Custom' item is modified. It updates the AWS Budget threshold based on
the budget_alert_threshold and budget_alert_enabled config values.
"""

import logging
import os
from decimal import Decimal

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# AWS clients
budgets = boto3.client("budgets")
sts = boto3.client("sts")

# Environment variables
BUDGET_NAME = os.environ.get("BUDGET_NAME", "")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "")

# Cache account ID
_account_id = None


def get_account_id() -> str:
    """Get AWS account ID (cached)."""
    global _account_id
    if _account_id is None:
        _account_id = sts.get_caller_identity()["Account"]
    return _account_id


def get_dynamodb_value(image: dict, key: str, default=None):
    """Extract a value from DynamoDB stream image format."""
    if key not in image:
        return default

    item = image[key]
    if "N" in item:
        return Decimal(item["N"])
    if "S" in item:
        return item["S"]
    if "BOOL" in item:
        return item["BOOL"]
    if "NULL" in item:
        return None

    return default


def lambda_handler(event: dict, context) -> dict:
    """Process DynamoDB stream events and sync budget configuration.

    Args:
        event: DynamoDB stream event with Records
        context: Lambda context

    Returns:
        dict with statusCode
    """
    logger.info(f"Processing {len(event.get('Records', []))} records")

    for record in event.get("Records", []):
        try:
            process_record(record)
        except Exception as e:
            # Log but don't fail - we don't want to block config saves
            logger.error(f"Error processing record: {e}", exc_info=True)

    return {"statusCode": 200}


def process_record(record: dict) -> None:
    """Process a single DynamoDB stream record."""
    event_name = record.get("eventName")
    if event_name not in ("INSERT", "MODIFY"):
        logger.debug(f"Skipping event type: {event_name}")
        return

    # Get the key to verify this is the Custom config
    keys = record.get("dynamodb", {}).get("Keys", {})
    config_type = get_dynamodb_value(keys, "Configuration")

    if config_type != "Custom":
        logger.debug(f"Skipping non-Custom config: {config_type}")
        return

    # Get old and new images
    new_image = record.get("dynamodb", {}).get("NewImage", {})
    old_image = record.get("dynamodb", {}).get("OldImage", {})

    # Extract budget values
    new_threshold = get_dynamodb_value(new_image, "budget_alert_threshold")
    old_threshold = get_dynamodb_value(old_image, "budget_alert_threshold")
    new_enabled = get_dynamodb_value(new_image, "budget_alert_enabled")
    old_enabled = get_dynamodb_value(old_image, "budget_alert_enabled")

    # Check if budget config changed
    threshold_changed = new_threshold != old_threshold
    enabled_changed = new_enabled != old_enabled

    if not threshold_changed and not enabled_changed:
        logger.debug("No budget config changes detected")
        return

    logger.info(
        f"Budget config changed: threshold={old_threshold}->{new_threshold}, "
        f"enabled={old_enabled}->{new_enabled}"
    )

    # Update the budget if enabled with a valid threshold
    if new_enabled and new_threshold and new_threshold > 0:
        update_budget(float(new_threshold))
    elif not new_enabled:
        logger.info("Budget alerts disabled - setting threshold to very high value")
        # Set a very high threshold effectively disabling alerts
        update_budget(999999)


def update_budget(threshold: float) -> None:
    """Update the AWS Budget with new threshold.

    Args:
        threshold: New budget limit in USD
    """
    account_id = get_account_id()

    logger.info(f"Updating budget '{BUDGET_NAME}' to ${threshold}")

    try:
        # First, get the current budget to preserve cost filters
        response = budgets.describe_budget(AccountId=account_id, BudgetName=BUDGET_NAME)
        current_budget = response["Budget"]

        # Update the budget limit while preserving other settings
        budgets.update_budget(
            AccountId=account_id,
            NewBudget={
                "BudgetName": BUDGET_NAME,
                "BudgetLimit": {"Amount": str(threshold), "Unit": "USD"},
                "TimeUnit": current_budget.get("TimeUnit", "MONTHLY"),
                "BudgetType": current_budget.get("BudgetType", "COST"),
                "CostFilters": current_budget.get(
                    "CostFilters", {"TagKeyValue": [f"user:Project${PROJECT_NAME}"]}
                ),
            },
        )

        logger.info(f"Successfully updated budget to ${threshold}")

    except budgets.exceptions.NotFoundException:
        logger.warning(f"Budget '{BUDGET_NAME}' not found - skipping update")
    except Exception as e:
        logger.error(f"Failed to update budget: {e}", exc_info=True)
        raise
