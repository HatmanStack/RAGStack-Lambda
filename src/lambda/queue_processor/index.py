"""
Queue Processor Lambda

Receives SQS messages from DocumentProcessingQueue and starts Step Functions executions.
Reserved concurrency limits concurrent large document processing.

Input event (SQS):
{
    "Records": [
        {
            "body": "{\"document_id\": \"input/abc123/doc.pdf\", ...}"
        }
    ]
}
"""

import json
import logging
import os
import re

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Reindex lock key - must match reindex_kb/index.py
REINDEX_LOCK_KEY = "reindex_lock"


def check_reindex_lock() -> None:
    """
    Check if a full KB reindex is in progress and raise error if so.

    During reindex, new uploads are blocked to prevent them from being
    ingested to the old KB (which gets deleted when reindex completes).

    Raises:
        RuntimeError: If reindex is in progress.
    """
    config_table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
    if not config_table_name:
        return  # Can't check lock without config table

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(config_table_name)
        response = table.get_item(Key={"config_key": REINDEX_LOCK_KEY})
        lock = response.get("Item")

        if lock and lock.get("is_locked"):
            started_at = lock.get("started_at", "unknown")
            raise RuntimeError(
                f"Upload blocked: Knowledge Base reindex is in progress "
                f"(started: {started_at}). Message will be retried after reindex."
            )
    except ClientError as e:
        # Log but don't block uploads if we can't check the lock
        logger.warning(f"Error checking reindex lock: {e}")
    except RuntimeError:
        # Re-raise our lock error
        raise


def lambda_handler(event, context):
    """
    Process SQS messages and start Step Functions executions.

    Uses reserved concurrency to limit concurrent large document processing.
    Blocks processing during KB reindex to prevent uploads to old KB.
    """
    # Check if reindex is in progress - if so, raise error to retry later
    # This prevents uploads from going to the old KB during reindex
    check_reindex_lock()

    sfn_client = boto3.client("stepfunctions")
    state_machine_arn = os.environ["STATE_MACHINE_ARN"]

    for record in event["Records"]:
        message = json.loads(record["body"])
        document_id = message.get("document_id", "unknown")

        # Create execution name from document_id (sanitized) + message ID
        # Step Functions execution names: 1-80 chars, alphanumeric + hyphens + underscores
        # Use messageId (unique per SQS message) instead of aws_request_id (same for batch)
        message_id_suffix = record.get("messageId", context.aws_request_id)[:12]
        max_prefix_len = 80 - 1 - len(message_id_suffix)
        sanitized_id = re.sub(r"[^a-zA-Z0-9_-]", "_", document_id)[:max_prefix_len]
        execution_name = f"{sanitized_id}-{message_id_suffix}"

        logger.info(f"Starting execution for document: {document_id}")

        sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps(message),
        )

        logger.info(f"Started execution: {execution_name}")

    return {"statusCode": 200, "body": "OK"}
