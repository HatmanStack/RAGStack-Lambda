"""Sync budget configuration changes to AWS Budgets.

This Lambda is triggered by:
1. DynamoDB Streams when ConfigurationTable 'Custom' item is modified
2. CloudFormation custom resource on stack create/update (initial budget creation)

It updates/creates the AWS Budget based on configuration.
"""

import json
import logging
import os
import urllib.error
import urllib.request
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


def send_cfn_response(event: dict, context, status: str, reason: str = "") -> None:
    """Send response to CloudFormation."""
    logger.info(f"send_cfn_response called with status={status}")

    physical_id = event.get("PhysicalResourceId") or event.get("LogicalResourceId", "BudgetInit")
    logger.info(f"PhysicalResourceId: {physical_id}")

    response_body = {
        "Status": status,
        "Reason": reason or f"See CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": physical_id,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
    }

    body = json.dumps(response_body).encode("utf-8")
    logger.info(f"Response body: {response_body}")

    response_url = event["ResponseURL"]
    logger.info(f"ResponseURL: {response_url[:100]}...")  # Truncate for security

    req = urllib.request.Request(
        response_url,
        data=body,
        method="PUT",
        headers={"Content-Type": "", "Content-Length": len(body)},
    )
    logger.info("urllib.request.Request created, sending...")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            logger.info(f"CloudFormation response status: {response.status}")
            logger.info(f"Response headers: {dict(response.headers)}")
    except urllib.error.URLError as e:
        logger.error(f"URLError sending response: {e.reason}")
        raise
    except urllib.error.HTTPError as e:
        logger.error(f"HTTPError sending response: {e.code} {e.reason}")
        raise
    except Exception as e:
        logger.error(f"Failed to send response to CloudFormation: {type(e).__name__}: {e}")
        raise


def handle_cfn_event(event: dict, context) -> dict:
    """Handle CloudFormation custom resource event."""
    request_type = event.get("RequestType")
    logger.info(f"CloudFormation {request_type} request")

    try:
        if request_type in ("Create", "Update"):
            # Get records from ResourceProperties (simulated DynamoDB event)
            records = event.get("ResourceProperties", {}).get("Records", [])
            for record in records:
                process_record(record)
        # Delete: nothing to do (budget persists)

        send_cfn_response(event, context, "SUCCESS")
    except Exception as e:
        logger.error(f"CloudFormation handler error: {e}", exc_info=True)
        send_cfn_response(event, context, "FAILED", str(e))

    return {"statusCode": 200}


def lambda_handler(event: dict, context) -> dict:
    """Process DynamoDB stream events or CloudFormation custom resource events.

    Args:
        event: DynamoDB stream event with Records OR CloudFormation custom resource event
        context: Lambda context

    Returns:
        dict with statusCode
    """
    # CRITICAL: If this is a CloudFormation event, we MUST respond even if we crash
    # Wrap entire handler in try/except to guarantee response
    is_cfn_event = "RequestType" in event and "ResponseURL" in event

    try:
        return _handle_event(event, context)
    except Exception as e:
        logger.error(f"Unhandled exception in lambda_handler: {e}", exc_info=True)
        # If CloudFormation event, send FAILED response so stack doesn't hang
        if is_cfn_event:
            try:
                send_cfn_response(event, context, "FAILED", f"Unhandled error: {str(e)}")
            except Exception as resp_error:
                logger.error(f"Failed to send error response to CFN: {resp_error}")
        return {"statusCode": 500, "error": str(e)}


def _handle_event(event: dict, context) -> dict:
    """Internal handler - separated so we can wrap with global exception handling."""
    # Log raw event immediately
    logger.info(f"RAW EVENT: {json.dumps(event, default=str)}")
    logger.info(f"Event keys: {list(event.keys())}")
    logger.info(f"RequestType present: {'RequestType' in event}")
    logger.info(f"ResponseURL present: {'ResponseURL' in event}")

    # Handle CloudFormation DELETE immediately - before anything else can fail
    if event.get("RequestType") == "Delete":
        logger.info("DELETE request detected - sending SUCCESS immediately")
        try:
            send_cfn_response(event, context, "SUCCESS")
            logger.info("SUCCESS response sent for DELETE")
        except Exception as e:
            logger.error(f"Failed to send DELETE response: {e}", exc_info=True)
        return {"statusCode": 200}

    # Detect other CloudFormation custom resource events
    if "RequestType" in event and "ResponseURL" in event:
        logger.info("CloudFormation Create/Update event detected")
        return handle_cfn_event(event, context)

    # DynamoDB stream event
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


def create_budget(threshold: float) -> None:
    """Create AWS Budget with notifications.

    Args:
        threshold: Budget limit in USD
    """
    account_id = get_account_id()

    logger.info(f"Creating budget '{BUDGET_NAME}' with ${threshold} limit")

    budgets.create_budget(
        AccountId=account_id,
        Budget={
            "BudgetName": BUDGET_NAME,
            "BudgetLimit": {"Amount": str(threshold), "Unit": "USD"},
            "TimeUnit": "MONTHLY",
            "BudgetType": "COST",
            "CostFilters": {"TagKeyValue": [f"user:Project${PROJECT_NAME}"]},
        },
        NotificationsWithSubscribers=[
            {
                "Notification": {
                    "NotificationType": "ACTUAL",
                    "ComparisonOperator": "GREATER_THAN",
                    "Threshold": 80,
                    "ThresholdType": "PERCENTAGE",
                },
                "Subscribers": [{"SubscriptionType": "EMAIL", "Address": ADMIN_EMAIL}],
            },
            {
                "Notification": {
                    "NotificationType": "FORECASTED",
                    "ComparisonOperator": "GREATER_THAN",
                    "Threshold": 100,
                    "ThresholdType": "PERCENTAGE",
                },
                "Subscribers": [{"SubscriptionType": "EMAIL", "Address": ADMIN_EMAIL}],
            },
        ],
    )

    logger.info(f"Successfully created budget '{BUDGET_NAME}'")


def update_budget(threshold: float) -> None:
    """Update the AWS Budget with new threshold, creating if it doesn't exist.

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
        # Budget doesn't exist - create it
        logger.info(f"Budget '{BUDGET_NAME}' not found - creating it")
        create_budget(threshold)
    except Exception as e:
        logger.error(f"Failed to update budget: {e}", exc_info=True)
        raise
