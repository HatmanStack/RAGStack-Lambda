"""
Sync Coordinator Lambda

Processes KB sync requests from SQS FIFO queue. Ensures only one sync runs at a time
by waiting for any in-progress sync to complete before starting a new one.

This Lambda has ReservedConcurrentExecutions=1 to prevent race conditions.
The FIFO queue with content-based deduplication coalesces rapid sync requests.

Input (SQS message body):
{
    "kb_id": "...",
    "ds_id": "...",
    "document_ids": ["abc123", "def456"],  # Documents waiting for this sync
    "source": "process_image" | "ingest_media"
}

The Lambda:
1. Waits for any running sync to complete (polling with backoff)
2. Starts a new ingestion job
3. Updates document statuses based on sync result
"""

import json
import logging
import os
import time
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

from ragstack_common.config import get_config_manager_or_none, get_knowledge_base_config
from ragstack_common.ingestion import start_ingestion_with_retry

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Initialize AWS clients
bedrock_agent = boto3.client("bedrock-agent")
dynamodb = boto3.resource("dynamodb")

# Configuration
MAX_WAIT_SECONDS = 300  # 5 minutes max wait for running sync
POLL_INTERVAL_SECONDS = 10  # Check every 10 seconds


def wait_for_sync_completion(kb_id: str, ds_id: str, max_wait: int = MAX_WAIT_SECONDS) -> bool:
    """
    Wait for any running ingestion job to complete.

    Args:
        kb_id: Knowledge Base ID.
        ds_id: Data Source ID.
        max_wait: Maximum seconds to wait.

    Returns:
        True if no sync is running (safe to start), False if timed out.
    """
    start_time = time.time()
    poll_count = 0

    while time.time() - start_time < max_wait:
        try:
            response = bedrock_agent.list_ingestion_jobs(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                maxResults=1,
                sortBy={"attribute": "STARTED_AT", "order": "DESCENDING"},
            )

            jobs = response.get("ingestionJobSummaries", [])
            if not jobs:
                logger.info("No ingestion jobs found, safe to start")
                return True

            latest_job = jobs[0]
            status = latest_job.get("status", "UNKNOWN")

            if status in ("COMPLETE", "FAILED", "STOPPED"):
                logger.info(f"Latest job status: {status}, safe to start new sync")
                return True

            if status in ("STARTING", "IN_PROGRESS"):
                job_id = latest_job.get("ingestionJobId", "unknown")
                poll_count += 1
                logger.info(
                    f"Sync in progress (job={job_id}, status={status}), "
                    f"waiting... (poll {poll_count})"
                )
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            # Unknown status - treat as safe
            logger.warning(f"Unknown job status: {status}, proceeding with caution")
            return True

        except ClientError as e:
            logger.error(f"Error checking ingestion jobs: {e}")
            # On error, wait and retry
            time.sleep(POLL_INTERVAL_SECONDS)

    logger.warning(f"Timed out waiting for sync completion after {max_wait}s")
    return False


def start_sync_job(kb_id: str, ds_id: str) -> dict | None:
    """
    Start a new ingestion job with retry for concurrent API conflicts.

    Args:
        kb_id: Knowledge Base ID.
        ds_id: Data Source ID.

    Returns:
        Ingestion job info dict, or None on failure.
    """
    try:
        response = start_ingestion_with_retry(kb_id, ds_id)
        job_info = response.get("ingestionJob", {})
        job_id = job_info.get("ingestionJobId")
        logger.info(f"Started ingestion job: {job_id}")
        return job_info

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", "")
        logger.error(f"Failed to start ingestion job: {error_code} - {error_msg}")
        return None


def update_document_statuses(
    document_ids: list[str],
    status: str | None = None,
    error_message: str | None = None,
    job_id: str | None = None,
) -> None:
    """
    Update tracking table status for documents.

    Args:
        document_ids: List of document IDs to update.
        status: New status (e.g., "SYNC_QUEUED", "INGESTION_FAILED").
        error_message: Optional error message for failures.
        job_id: Optional ingestion job ID to track.
    """
    tracking_table_name = os.environ.get("TRACKING_TABLE")
    if not tracking_table_name or not document_ids:
        return

    table = dynamodb.Table(tracking_table_name)
    now = datetime.now(UTC).isoformat()

    for doc_id in document_ids:
        try:
            update_expr = "SET updated_at = :updated_at"
            expr_names = {}
            expr_values = {":updated_at": now}

            if status:
                update_expr += ", #status = :status"
                expr_names["#status"] = "status"
                expr_values[":status"] = status

            if error_message:
                update_expr += ", error_message = :error"
                expr_values[":error"] = error_message

            if job_id:
                update_expr += ", ingestion_job_id = :job_id"
                expr_values[":job_id"] = job_id

            update_kwargs = {
                "Key": {"document_id": doc_id},
                "UpdateExpression": update_expr,
                "ExpressionAttributeValues": expr_values,
            }
            if expr_names:
                update_kwargs["ExpressionAttributeNames"] = expr_names
            table.update_item(**update_kwargs)
            logger.debug(f"Updated {doc_id} status to {status}")

        except ClientError as e:
            logger.warning(f"Failed to update status for {doc_id}: {e}")


def lambda_handler(event, context):
    """
    Process sync request from SQS FIFO queue.

    Waits for any running sync to complete, then starts a new sync job.
    Updates document statuses based on result.
    """
    # Get KB config from DynamoDB (with env var fallback)
    config_manager = get_config_manager_or_none()
    kb_id, ds_id = get_knowledge_base_config(config_manager)
    logger.info(f"Using KB config: kb_id={kb_id}, ds_id={ds_id}")

    # Process SQS records (should be just 1 due to BatchSize=1)
    all_document_ids = []

    for record in event.get("Records", []):
        try:
            body = json.loads(record.get("body", "{}"))
            document_ids = body.get("document_ids", [])
            source = body.get("source", "unknown")

            logger.info(f"Processing sync request from {source} for {len(document_ids)} documents")

            all_document_ids.extend(document_ids)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse SQS message body: {e}")
            continue

    # Wait for any running sync to complete
    if not wait_for_sync_completion(kb_id, ds_id):
        # Timed out - mark documents as failed
        logger.error("Timed out waiting for sync, marking documents as INGESTION_FAILED")
        update_document_statuses(
            all_document_ids,
            "INGESTION_FAILED",
            "Sync coordinator timed out waiting for previous sync",
        )
        # Don't raise - let the message be deleted (it will be retried via DLQ if needed)
        return {
            "status": "TIMEOUT",
            "documents_affected": len(all_document_ids),
        }

    # Start new sync
    job_info = start_sync_job(kb_id, ds_id)

    if job_info:
        job_id = job_info.get("ingestionJobId")
        logger.info(f"Sync started successfully: job_id={job_id}")

        # Store the job_id in tracking table for status checker to verify later
        # Status remains SYNC_QUEUED - will be updated to INDEXED by sync_status_checker
        update_document_statuses(all_document_ids, job_id=job_id)
        logger.info(f"Updated {len(all_document_ids)} documents with job_id={job_id}")

        return {
            "status": "SYNC_STARTED",
            "job_id": job_id,
            "documents_affected": len(all_document_ids),
        }
    # Failed to start sync - mark documents as failed
    logger.error("Failed to start sync, marking documents as INGESTION_FAILED")
    update_document_statuses(
        all_document_ids,
        "INGESTION_FAILED",
        "Sync coordinator failed to start ingestion job",
    )

    return {
        "status": "FAILED",
        "documents_affected": len(all_document_ids),
    }
