"""
Ingest Visual Lambda

Triggers Bedrock KB StartIngestionJob when video files are uploaded to content/{docId}/.
This enables visual embeddings to be created from video content.

Triggered by S3 EventBridge events when video.mp4 files are created in the content/ prefix.

Key behavior:
- Only processes content/*/video.mp4 files
- Skips metadata files (.metadata.json)
- Uses StartIngestionJob which handles incremental sync
- Logs ingestion statistics to monitor if text is being re-processed
"""

import json
import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent = boto3.client("bedrock-agent")


def parse_s3_event(event: dict) -> dict:
    """
    Parse S3 EventBridge event to extract bucket and key.

    Args:
        event: EventBridge S3 event

    Returns:
        Dict with bucket and key
    """
    detail = event.get("detail", {})
    bucket_info = detail.get("bucket", {})
    object_info = detail.get("object", {})

    return {
        "bucket": bucket_info.get("name"),
        "key": object_info.get("key"),
        "size": object_info.get("size"),
        "event_type": event.get("detail-type"),
    }


def is_valid_video_path(key: str) -> bool:
    """
    Check if the S3 key is a valid video file path for visual embeddings.

    Valid pattern: content/{docId}/video.mp4
    Skip: metadata files, non-video files, files not in content/
    """
    if not key:
        return False

    # Must be in content/ folder
    if not key.startswith("content/"):
        return False

    # Must be video.mp4 (not metadata or other files)
    if not key.endswith("/video.mp4"):
        return False

    # Skip metadata files
    return ".metadata.json" not in key


def lambda_handler(event: dict, context) -> dict:
    """
    Trigger StartIngestionJob for visual embedding ingestion.

    Args:
        event: S3 EventBridge event for object creation
        context: Lambda context

    Returns:
        Result dict with status and job info
    """
    logger.info(f"Processing event: {json.dumps(event)}")

    kb_id = os.environ.get("KNOWLEDGE_BASE_ID")
    ds_id = os.environ.get("DATA_SOURCE_ID")
    wait_for_completion = os.environ.get("WAIT_FOR_COMPLETION", "false").lower() == "true"

    if not kb_id or not ds_id:
        raise ValueError("KNOWLEDGE_BASE_ID and DATA_SOURCE_ID environment variables required")

    # Parse S3 event
    s3_info = parse_s3_event(event)
    bucket = s3_info.get("bucket")
    key = s3_info.get("key")

    logger.info(f"S3 event: bucket={bucket}, key={key}")

    # Skip metadata files
    if key and ".metadata.json" in key:
        logger.info(f"Skipping metadata file: {key}")
        return {"status": "skipped", "message": "Metadata file, skipping"}

    # Validate path pattern
    if not is_valid_video_path(key):
        logger.info(f"Skipping non-video file or invalid path: {key}")
        return {"status": "skipped", "message": f"Not a valid video path: {key}"}

    # Extract document ID for logging
    parts = key.split("/")
    doc_id = parts[1] if len(parts) > 1 else "unknown"
    logger.info(f"Starting ingestion for document: {doc_id}")

    try:
        # Start ingestion job
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
        )

        job_info = response.get("ingestionJob", {})
        job_id = job_info.get("ingestionJobId")
        job_status = job_info.get("status")

        logger.info(f"Started ingestion job: id={job_id}, status={job_status}")

        # Log initial statistics if available (for monitoring incremental sync)
        stats = job_info.get("statistics", {})
        if stats:
            logger.info(
                f"Ingestion stats: scanned={stats.get('numberOfDocumentsScanned')}, "
                f"indexed={stats.get('numberOfNewDocumentsIndexed')}, "
                f"modified={stats.get('numberOfModifiedDocumentsIndexed')}, "
                f"deleted={stats.get('numberOfDocumentsDeleted')}"
            )

        result = {
            "status": "success",
            "job_id": job_id,
            "job_status": job_status,
            "document_id": doc_id,
        }

        if stats:
            result["statistics"] = stats

        # Optional: Poll for completion
        if wait_for_completion and job_id:
            result = poll_for_completion(kb_id, ds_id, job_id, result)

        return result

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to start ingestion job: {error_code} - {error_msg}")
        raise


def poll_for_completion(
    kb_id: str,
    ds_id: str,
    job_id: str,
    result: dict,
    max_wait: int = 300,
    poll_interval: int = 10,
) -> dict:
    """
    Poll for ingestion job completion.

    Args:
        kb_id: Knowledge base ID
        ds_id: Data source ID
        job_id: Ingestion job ID
        result: Current result dict to update
        max_wait: Maximum wait time in seconds (default 5 minutes)
        poll_interval: Polling interval in seconds

    Returns:
        Updated result dict
    """
    logger.info(f"Polling for job completion: {job_id}")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            response = bedrock_agent.get_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                ingestionJobId=job_id,
            )

            job_info = response.get("ingestionJob", {})
            status = job_info.get("status")
            stats = job_info.get("statistics", {})

            logger.info(f"Job {job_id} status: {status}")

            if status in ("COMPLETE", "FAILED"):
                result["job_status"] = status
                if stats:
                    result["statistics"] = stats
                    # Log final statistics for monitoring
                    logger.info(
                        f"Final ingestion stats: scanned={stats.get('numberOfDocumentsScanned')}, "
                        f"indexed={stats.get('numberOfNewDocumentsIndexed')}, "
                        f"modified={stats.get('numberOfModifiedDocumentsIndexed')}, "
                        f"deleted={stats.get('numberOfDocumentsDeleted')}"
                    )
                    # Warning if text files are being re-indexed
                    new_indexed = stats.get("numberOfNewDocumentsIndexed", 0)
                    if new_indexed > 1:
                        logger.warning(
                            f"More than 1 new document indexed ({new_indexed}). "
                            "Incremental sync may not be working as expected. "
                            "Check if text files are being re-processed."
                        )
                break

            time.sleep(poll_interval)

        except ClientError as e:
            logger.warning(f"Error polling job status: {e}")
            break

    return result
