"""
Sync Status Checker Lambda

Periodically checks the status of documents waiting for KB sync (SYNC_QUEUED)
and updates their status to INDEXED or INGESTION_FAILED based on actual
Bedrock KB document status.

This Lambda is triggered by EventBridge on a schedule (e.g., every 2 minutes).

Flow:
1. Query tracking table for documents with status=SYNC_QUEUED
2. For each document, check its status in Bedrock KB
3. Update tracking table:
   - INDEXED in KB → status = INDEXED
   - FAILED in KB → status = INGESTION_FAILED
   - Still processing → leave as SYNC_QUEUED
"""

import logging
import os
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

from ragstack_common.appsync import publish_image_update
from ragstack_common.config import get_config_manager, get_knowledge_base_config
from ragstack_common.ingestion import batch_check_document_statuses

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")

# Maximum documents to process per invocation (to stay within Lambda timeout)
MAX_DOCUMENTS_PER_RUN = 100


def get_sync_queued_documents(table_name: str) -> list[dict]:
    """
    Query tracking table for documents with SYNC_QUEUED status.

    Returns list of document dicts with document_id, output_s3_uri, etc.
    """
    table = dynamodb.Table(table_name)

    # Scan for SYNC_QUEUED status (could use GSI for efficiency at scale)
    # Note: For production with many documents, consider adding a GSI on status
    documents = []

    try:
        response = table.scan(
            FilterExpression="#status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "SYNC_QUEUED"},
            Limit=MAX_DOCUMENTS_PER_RUN,
        )
        documents.extend(response.get("Items", []))

        # Handle pagination if needed
        while "LastEvaluatedKey" in response and len(documents) < MAX_DOCUMENTS_PER_RUN:
            response = table.scan(
                FilterExpression="#status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "SYNC_QUEUED"},
                ExclusiveStartKey=response["LastEvaluatedKey"],
                Limit=MAX_DOCUMENTS_PER_RUN - len(documents),
            )
            documents.extend(response.get("Items", []))

    except ClientError as e:
        logger.error(f"Error scanning tracking table: {e}")

    return documents[:MAX_DOCUMENTS_PER_RUN]


def update_document_status(
    table_name: str,
    document_id: str,
    new_status: str,
    error_message: str | None = None,
) -> None:
    """Update a single document's status in tracking table."""
    table = dynamodb.Table(table_name)
    now = datetime.now(UTC).isoformat()

    try:
        update_expr = "SET #status = :status, updated_at = :updated_at"
        expr_names = {"#status": "status"}
        expr_values = {
            ":status": new_status,
            ":updated_at": now,
        }

        if error_message:
            update_expr += ", error_message = :error"
            expr_values[":error"] = error_message
            # Remove ingestion_job_id on completion (success or failure)
            update_expr += " REMOVE ingestion_job_id"
        else:
            # Remove both ingestion_job_id and any stale error_message on success
            update_expr += " REMOVE ingestion_job_id, error_message"

        table.update_item(
            Key={"document_id": document_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        logger.info(f"Updated {document_id} status to {new_status}")

    except ClientError as e:
        logger.error(f"Failed to update status for {document_id}: {e}")


def lambda_handler(event, context):
    """
    Check status of SYNC_QUEUED documents and update accordingly.

    Triggered by EventBridge schedule rule.
    """
    # Get KB config from DynamoDB (with env var fallback)
    config_manager = get_config_manager()
    kb_id, ds_id = get_knowledge_base_config(config_manager)
    logger.info(f"Using KB config: kb_id={kb_id}, ds_id={ds_id}")

    tracking_table = os.environ.get("TRACKING_TABLE")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    if not tracking_table:
        raise ValueError("TRACKING_TABLE is required")

    # Get documents waiting for sync
    documents = get_sync_queued_documents(tracking_table)

    if not documents:
        logger.info("No documents with SYNC_QUEUED status")
        return {"checked": 0, "updated": 0}

    logger.info(f"Checking status for {len(documents)} SYNC_QUEUED documents")

    # Build mapping of S3 URI to document info
    uri_to_doc = {}
    for doc in documents:
        # For images, check both the image file and caption file
        # The caption.txt is what gets indexed for text search
        caption_uri = doc.get("caption_s3_uri")
        output_uri = doc.get("output_s3_uri")

        # Use caption_uri if available (image), otherwise output_uri (document)
        check_uri = caption_uri or output_uri
        if check_uri:
            uri_to_doc[check_uri] = doc

    if not uri_to_doc:
        logger.warning("No valid S3 URIs found for SYNC_QUEUED documents")
        return {"checked": 0, "updated": 0}

    # Batch check document statuses in Bedrock KB
    s3_uris = list(uri_to_doc.keys())
    statuses = batch_check_document_statuses(kb_id, ds_id, s3_uris)

    # Process results and update tracking table
    updated_count = 0
    indexed_count = 0
    failed_count = 0

    for uri, kb_status in statuses.items():
        doc = uri_to_doc.get(uri)
        if not doc:
            continue

        document_id = doc.get("document_id")
        filename = doc.get("filename", "unknown")
        doc_type = doc.get("type", "document")

        if kb_status == "INDEXED":
            # Document successfully indexed
            update_document_status(tracking_table, document_id, "INDEXED")
            updated_count += 1
            indexed_count += 1

            # Publish real-time update for images
            if doc_type == "image" and graphql_endpoint:
                try:
                    publish_image_update(
                        graphql_endpoint,
                        document_id,
                        filename,
                        "INDEXED",
                    )
                except Exception as e:
                    logger.warning(f"Failed to publish update for {document_id}: {e}")

        elif kb_status == "FAILED":
            # Document ingestion failed
            update_document_status(
                tracking_table,
                document_id,
                "INGESTION_FAILED",
                "KB ingestion job reported FAILED status",
            )
            updated_count += 1
            failed_count += 1

            # Publish real-time update for images
            if doc_type == "image" and graphql_endpoint:
                try:
                    publish_image_update(
                        graphql_endpoint,
                        document_id,
                        filename,
                        "INGESTION_FAILED",
                        error_message="KB sync failed",
                    )
                except Exception as e:
                    logger.warning(f"Failed to publish update for {document_id}: {e}")

        else:
            # Still processing (STARTING, IN_PROGRESS) or UNKNOWN
            logger.debug(f"Document {document_id} status: {kb_status}, leaving as SYNC_QUEUED")

    logger.info(
        f"Status check complete: {len(documents)} checked, "
        f"{updated_count} updated ({indexed_count} indexed, {failed_count} failed)"
    )

    return {
        "checked": len(documents),
        "updated": updated_count,
        "indexed": indexed_count,
        "failed": failed_count,
    }
