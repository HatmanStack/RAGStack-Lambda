"""
DLQ Replay Lambda - moves messages from a DLQ back to its source queue.

Manually triggered via CLI/console. Supports all 5 queue pairs including FIFO.
"""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import uuid4

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Maximum iterations to prevent runaway execution (10 messages per iteration)
MAX_ITERATIONS = 100

# DLQ name to environment variable prefix mapping
QUEUE_MAP: dict[str, tuple[str, str, bool]] = {
    # dlq_name: (DLQ_URL_ENV_VAR, SOURCE_QUEUE_URL_ENV_VAR, is_fifo)
    "processing": ("PROCESSING_DLQ_URL", "PROCESSING_QUEUE_URL", False),
    "batch": ("BATCH_DLQ_URL", "BATCH_QUEUE_URL", False),
    "scrape-discovery": ("SCRAPE_DISCOVERY_DLQ_URL", "SCRAPE_DISCOVERY_QUEUE_URL", False),
    "scrape-processing": ("SCRAPE_PROCESSING_DLQ_URL", "SCRAPE_PROCESSING_QUEUE_URL", False),
    "sync": ("SYNC_DLQ_URL", "SYNC_QUEUE_URL", True),
}

sqs_client: Any = None


def get_sqs_client() -> Any:
    """Get or create SQS client."""
    global sqs_client
    if sqs_client is None:
        sqs_client = boto3.client("sqs")
    return sqs_client


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Replay messages from a DLQ back to its source queue.

    Args:
        event: Must contain {"dlq_name": "processing" | "batch" | "scrape-discovery"
               | "scrape-processing" | "sync"}
        context: Lambda context (unused)

    Returns:
        Summary dict with replayed and failed counts.
    """
    dlq_name = event.get("dlq_name", "")
    if dlq_name not in QUEUE_MAP:
        valid_names = ", ".join(sorted(QUEUE_MAP.keys()))
        raise ValueError(f"Invalid dlq_name '{dlq_name}'. Must be one of: {valid_names}")

    dlq_env, source_env, is_fifo = QUEUE_MAP[dlq_name]
    dlq_url = os.environ[dlq_env]
    source_url = os.environ[source_env]

    logger.info(f"Replaying DLQ '{dlq_name}' from {dlq_url} to {source_url}")

    client = get_sqs_client()
    replayed = 0
    failed = 0

    for iteration in range(MAX_ITERATIONS):
        response = client.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=1,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )

        messages = response.get("Messages", [])
        if not messages:
            logger.info(f"DLQ empty after {iteration + 1} iteration(s)")
            break

        for msg in messages:
            try:
                send_kwargs: dict[str, Any] = {
                    "QueueUrl": source_url,
                    "MessageBody": msg["Body"],
                }

                # Forward message attributes if present
                if msg.get("MessageAttributes"):
                    send_kwargs["MessageAttributes"] = msg["MessageAttributes"]

                # FIFO queues require MessageGroupId and MessageDeduplicationId
                if is_fifo:
                    attrs = msg.get("Attributes", {})
                    send_kwargs["MessageGroupId"] = attrs.get(
                        "MessageGroupId", "dlq-replay"
                    )
                    # Always use a fresh dedup ID so SQS does not treat the
                    # replay as a duplicate of the original message.
                    send_kwargs["MessageDeduplicationId"] = uuid4().hex

                client.send_message(**send_kwargs)

                # Delete from DLQ after successful send
                client.delete_message(
                    QueueUrl=dlq_url,
                    ReceiptHandle=msg["ReceiptHandle"],
                )
                replayed += 1
                logger.info(f"Replayed message {msg['MessageId']}")

            except Exception:
                failed += 1
                logger.exception(f"Failed to replay message {msg['MessageId']}")

    else:
        logger.warning(
            f"Reached max iterations ({MAX_ITERATIONS}). "
            f"Replayed {replayed}, failed {failed}."
        )

    result: dict[str, int] = {"replayed": replayed, "failed": failed}
    logger.info(f"Replay complete: {result}")
    return result
