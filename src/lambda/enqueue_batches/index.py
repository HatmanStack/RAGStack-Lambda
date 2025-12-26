"""
Enqueue Batches Lambda

Sends individual batch processing jobs to SQS queue and initializes DynamoDB tracking.
Called by Step Functions when a document needs batched processing.

Input event (from GetPageInfo):
{
    "document_id": "abc123",
    "input_s3_uri": "s3://bucket/input/abc123/document.pdf",
    "output_s3_prefix": "s3://bucket/output/abc123/",
    "total_pages": 150,
    "needs_batching": true,
    "batches": [
        {"page_start": 1, "page_end": 10},
        {"page_start": 11, "page_end": 20},
        ...
    ]
}

Output:
{
    "document_id": "abc123",
    "status": "batches_enqueued",
    "total_batches": 15,
    "total_pages": 150
}
"""

import json
import logging
import os
from datetime import UTC, datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Send all batches to SQS and initialize batch tracking in DynamoDB.

    The Lambda returns immediately after enqueueing. Batch completion is
    tracked via atomic counter in DynamoDB; last batch triggers CombinePages.
    """
    logger.info(f"EnqueueBatches event: {event}")

    # Get environment variables
    tracking_table = os.environ.get("TRACKING_TABLE")
    batch_queue_url = os.environ.get("BATCH_QUEUE_URL")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    if not tracking_table:
        raise ValueError("TRACKING_TABLE environment variable is required")
    if not batch_queue_url:
        raise ValueError("BATCH_QUEUE_URL environment variable is required")

    # Extract event data
    document_id = event["document_id"]
    input_s3_uri = event["input_s3_uri"]
    output_s3_prefix = event["output_s3_prefix"]
    total_pages = event["total_pages"]
    batches = event["batches"]
    total_batches = len(batches)

    logger.info(f"Enqueueing {total_batches} batches for document {document_id}")

    # Initialize clients
    dynamodb = boto3.resource("dynamodb")
    sqs = boto3.client("sqs")
    table = dynamodb.Table(tracking_table)

    # Update DynamoDB with batch tracking info
    now = datetime.now(UTC).isoformat()
    table.update_item(
        Key={"document_id": document_id},
        UpdateExpression=(
            "SET batches_total = :total, "
            "batches_remaining = :remaining, "
            "pages_succeeded = :zero, "
            "pages_failed = :zero, "
            "updated_at = :now"
        ),
        ExpressionAttributeValues={
            ":total": total_batches,
            ":remaining": total_batches,
            ":zero": 0,
            ":now": now,
        },
    )
    logger.info(f"Initialized batch tracking: {total_batches} batches")

    # Send batch messages to SQS (in batches of 10, the SQS limit)
    entries = []
    for i, batch in enumerate(batches):
        message_body = {
            "document_id": document_id,
            "batch_index": i,
            "input_s3_uri": input_s3_uri,
            "output_s3_prefix": output_s3_prefix,
            "page_start": batch["page_start"],
            "page_end": batch["page_end"],
            "total_batches": total_batches,
            "total_pages": total_pages,
        }
        entries.append(
            {
                "Id": str(i),
                "MessageBody": json.dumps(message_body),
            }
        )

        if len(entries) == 10:
            sqs.send_message_batch(QueueUrl=batch_queue_url, Entries=entries)
            entries = []

    if entries:  # Send remaining
        sqs.send_message_batch(QueueUrl=batch_queue_url, Entries=entries)

    logger.info(f"Enqueued {total_batches} batch messages to SQS")

    # Publish real-time update if GraphQL endpoint available
    if graphql_endpoint:
        try:
            from ragstack_common.appsync import publish_document_update

            # Get filename from tracking table
            response = table.get_item(Key={"document_id": document_id})
            filename = response.get("Item", {}).get("filename", "unknown")

            publish_document_update(
                graphql_endpoint,
                document_id,
                filename,
                "PROCESSING",
                total_pages=total_pages,
            )
        except Exception as e:
            logger.warning(f"Failed to publish real-time update: {e}")

    return {
        "document_id": document_id,
        "status": "batches_enqueued",
        "total_batches": total_batches,
        "total_pages": total_pages,
    }
