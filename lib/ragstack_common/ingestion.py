"""
Knowledge Base ingestion utilities.

Provides functions for starting ingestion jobs and checking document status
in AWS Bedrock Knowledge Bases. Includes retry logic for handling concurrent
API conflicts.

Usage:
    from ragstack_common.ingestion import (
        start_ingestion_with_retry,
        check_document_status,
        batch_check_document_statuses,
    )

    # Start an ingestion job with automatic retry
    response = start_ingestion_with_retry(kb_id, ds_id)

    # Check single document status
    status = check_document_status(kb_id, ds_id, s3_uri)

    # Check multiple documents efficiently
    statuses = batch_check_document_statuses(kb_id, ds_id, s3_uris)
"""

import logging
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Default batch size for status checks (Bedrock API limit)
DEFAULT_STATUS_CHECK_BATCH_SIZE = 25

# Lazy-initialized client
_bedrock_agent = None


def _get_bedrock_agent():
    """Get or create bedrock-agent client."""
    global _bedrock_agent
    if _bedrock_agent is None:
        _bedrock_agent = boto3.client("bedrock-agent")
    return _bedrock_agent


def start_ingestion_with_retry(
    kb_id: str,
    ds_id: str,
    max_retries: int = 5,
    base_delay: float = 5.0,
    client=None,
) -> dict:
    """
    Start ingestion job with retry for concurrent API conflicts.

    IngestDocuments and StartIngestionJob cannot run simultaneously on the same
    data source. This function retries with exponential backoff when a conflict
    is detected.

    Args:
        kb_id: Knowledge base ID.
        ds_id: Data source ID.
        max_retries: Maximum retry attempts (default 5).
        base_delay: Base delay in seconds (default 5.0).
        client: Optional bedrock-agent client (for testing).

    Returns:
        StartIngestionJob response dict.

    Raises:
        ClientError: If all retries exhausted or non-retryable error.
    """
    bedrock_agent = client or _get_bedrock_agent()
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return bedrock_agent.start_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_msg = e.response.get("Error", {}).get("Message", "")

            # Check if this is a retryable concurrent API conflict
            is_ongoing = "ongoing" in error_msg.lower() or "running" in error_msg.lower()
            if error_code == "ValidationException" and is_ongoing:
                last_error = e
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)  # Exponential backoff
                    logger.warning(
                        f"Concurrent API conflict, retry {attempt + 1}/{max_retries} "
                        f"after {delay}s: {error_msg}"
                    )
                    time.sleep(delay)
                    continue

            # Non-retryable error, raise immediately
            raise

    # All retries exhausted
    logger.error(f"All {max_retries} retries exhausted for ingestion job")
    if last_error:
        raise last_error
    raise RuntimeError("Ingestion job failed with no error captured")


def ingest_documents_with_retry(
    kb_id: str,
    ds_id: str,
    documents: list[dict],
    max_retries: int = 5,
    base_delay: float = 2.0,
    client=None,
) -> dict:
    """
    Ingest documents with retry for concurrent API conflicts.

    IngestDocuments and StartIngestionJob cannot run simultaneously on the same
    data source. This function retries with exponential backoff when a conflict
    is detected (e.g., when a sync job is running).

    Args:
        kb_id: Knowledge base ID.
        ds_id: Data source ID.
        documents: List of document objects for the IngestKnowledgeBaseDocuments API.
        max_retries: Maximum retry attempts (default 5).
        base_delay: Base delay in seconds (default 2.0).
        client: Optional bedrock-agent client (for testing).

    Returns:
        IngestKnowledgeBaseDocuments response dict.

    Raises:
        ClientError: If all retries exhausted or non-retryable error.
    """
    bedrock_agent = client or _get_bedrock_agent()
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return bedrock_agent.ingest_knowledge_base_documents(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                documents=documents,
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_msg = e.response.get("Error", {}).get("Message", "")

            # Check for retryable concurrent API conflict or service unavailable
            is_conflict = error_code == "ConflictException"
            is_validation_ongoing = error_code == "ValidationException" and (
                "ongoing" in error_msg.lower() or "running" in error_msg.lower()
            )
            is_throttle = (
                error_code == "ValidationException" and "can't exceed" in error_msg.lower()
            ) or error_code == "ThrottlingException"
            is_service_unavailable = error_code == "ServiceUnavailableException"

            if is_conflict or is_validation_ongoing or is_throttle or is_service_unavailable:
                last_error = e
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)  # Exponential backoff
                    logger.warning(
                        f"API conflict/unavailable ({error_code}), "
                        f"retry {attempt + 1}/{max_retries} after {delay}s: {error_msg}"
                    )
                    time.sleep(delay)
                    continue

            # Non-retryable error, raise immediately
            raise

    # All retries exhausted
    logger.error(f"All {max_retries} retries exhausted for document ingestion")
    if last_error:
        raise last_error
    raise RuntimeError("Document ingestion failed with no error captured")


def check_document_status(
    kb_id: str,
    ds_id: str,
    s3_uri: str,
    sleep_first: bool = True,
    client=None,
) -> str:
    """
    Quick check for document ingestion status (single call, no polling).

    Args:
        kb_id: Knowledge Base ID.
        ds_id: Data Source ID.
        s3_uri: S3 URI of the document.
        sleep_first: Whether to pause briefly before checking (default True).
        client: Optional bedrock-agent client (for testing).

    Returns:
        Status string (INDEXED, FAILED, STARTING, DELETING, etc.) or "UNKNOWN".
    """
    bedrock_agent = client or _get_bedrock_agent()

    try:
        if sleep_first:
            time.sleep(2)  # Brief pause to let Bedrock process

        response = bedrock_agent.get_knowledge_base_documents(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            documentIdentifiers=[{"dataSourceType": "S3", "s3": {"uri": s3_uri}}],
        )
        doc_details = response.get("documentDetails", [])
        if doc_details:
            return doc_details[0].get("status", "UNKNOWN")
    except ClientError as e:
        logger.warning(f"Error checking document status: {e}")

    return "UNKNOWN"


def batch_check_document_statuses(
    kb_id: str,
    ds_id: str,
    s3_uris: list[str],
    batch_size: int = DEFAULT_STATUS_CHECK_BATCH_SIZE,
    client=None,
) -> dict[str, str]:
    """
    Check ingestion status for multiple documents in batches.

    More efficient than individual calls when checking many documents.

    Args:
        kb_id: Knowledge Base ID.
        ds_id: Data Source ID.
        s3_uris: List of S3 URIs to check.
        batch_size: Documents per API call (default 25, max allowed by Bedrock).
        client: Optional bedrock-agent client (for testing).

    Returns:
        Dict mapping S3 URI to status string.
    """
    bedrock_agent = client or _get_bedrock_agent()
    results = {}

    for i in range(0, len(s3_uris), batch_size):
        batch = s3_uris[i : i + batch_size]
        doc_identifiers = [{"dataSourceType": "S3", "s3": {"uri": uri}} for uri in batch]

        try:
            response = bedrock_agent.get_knowledge_base_documents(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                documentIdentifiers=doc_identifiers,
            )
            doc_details = response.get("documentDetails", [])
            for detail in doc_details:
                uri = detail.get("identifier", {}).get("s3", {}).get("uri")
                status = detail.get("status", "UNKNOWN")
                if uri:
                    results[uri] = status
        except ClientError as e:
            logger.warning(f"Error batch checking document statuses: {e}")
            # Mark batch as unknown on error
            for uri in batch:
                results[uri] = "UNKNOWN"

    return results
