"""
Ingest Media Lambda

Handles ingestion of media (video/audio) content to Bedrock Knowledge Base.
Creates text embeddings from transcript and triggers visual ingestion via
StartIngestionJob (Bedrock KB handles video chunking natively).

Input event:
{
    "document_id": "abc123",
    "output_s3_uri": "s3://bucket/content/abc123/transcript_full.txt",
    "media_type": "video",
    "duration_seconds": 120,
    "total_segments": 4,
    "transcript_segments": [
        {
            "segment_index": 0,
            "timestamp_start": 0,
            "timestamp_end": 30,
            "text": "transcript text",
            "word_count": 10
        }
    ]
}

Output:
{
    "document_id": "abc123",
    "status": "indexed",
    "text_indexed": true,
    "segments_indexed": 4,
    "metadata_keys": ["main_topic", "speakers", ...]
}
"""

import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from ragstack_common.appsync import publish_document_update
from ragstack_common.config import (
    get_config_manager_or_none,
    get_knowledge_base_config,
)
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.metadata_normalizer import normalize_metadata_for_s3
from ragstack_common.storage import parse_s3_uri, read_s3_text

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent = boto3.client("bedrock-agent")
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")


def start_ingestion_with_retry(
    kb_id: str,
    ds_id: str,
    max_retries: int = 5,
    base_delay: float = 5.0,
) -> dict:
    """
    Start ingestion job with retry for concurrent API conflicts.

    IngestDocuments and StartIngestionJob cannot run simultaneously on the same
    data source. This function retries with exponential backoff when a conflict
    is detected.

    Args:
        kb_id: Knowledge base ID
        ds_id: Data source ID
        max_retries: Maximum retry attempts (default 5)
        base_delay: Base delay in seconds (default 5.0)

    Returns:
        StartIngestionJob response

    Raises:
        ClientError: If all retries exhausted or non-retryable error
    """
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
            if error_code == "ValidationException" and "ongoing" in error_msg.lower():
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


# Lazy-initialized singletons
_metadata_extractor = None


def get_metadata_extractor() -> MetadataExtractor:
    """Get or create MetadataExtractor singleton."""
    global _metadata_extractor
    if _metadata_extractor is None:
        _metadata_extractor = MetadataExtractor()
    return _metadata_extractor


# Core metadata keys (~8) to preserve when reducing metadata
# content_type covers media_type/file_type (they were redundant)
CORE_METADATA_KEYS = {
    "content_type",  # "video" or "audio"
    "document_id",
    "filename",
    "timestamp_start",  # For segment deep linking
    "timestamp_end",
    "segment_index",
    "duration_seconds",
    "main_topic",  # Primary topic for search
}


def check_document_status(kb_id: str, ds_id: str, s3_uri: str, sleep_first: bool = True) -> str:
    """
    Quick check for document ingestion status (single call, no polling).

    Args:
        kb_id: Knowledge Base ID.
        ds_id: Data Source ID.
        s3_uri: S3 URI of the document.
        sleep_first: Whether to sleep before checking (default True for single doc checks).

    Returns:
        Status string (INDEXED, FAILED, STARTING, etc.)
    """
    try:
        if sleep_first:
            time.sleep(2)

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


# Batch limits for Bedrock KB APIs
INGEST_BATCH_SIZE = 25
STATUS_CHECK_BATCH_SIZE = 25


def batch_check_document_statuses(kb_id: str, ds_id: str, s3_uris: list[str]) -> dict[str, str]:
    """
    Check ingestion status for multiple documents in batches.

    Args:
        kb_id: Knowledge Base ID.
        ds_id: Data Source ID.
        s3_uris: List of S3 URIs to check.

    Returns:
        Dict mapping S3 URI to status string.
    """
    results = {}

    for i in range(0, len(s3_uris), STATUS_CHECK_BATCH_SIZE):
        batch = s3_uris[i : i + STATUS_CHECK_BATCH_SIZE]
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


def reduce_metadata(metadata: dict[str, Any], reduction_level: int = 1) -> dict[str, Any]:
    """
    Reduce metadata size by removing non-core keys or truncating values.

    Args:
        metadata: Original metadata dict.
        reduction_level: 1 = remove non-core keys, 2 = also truncate arrays, 3 = minimal

    Returns:
        Reduced metadata dict.
    """
    reduced = {}

    for key, value in metadata.items():
        # Level 3: Only keep core keys
        if reduction_level >= 3 and key not in CORE_METADATA_KEYS:
            continue

        # Level 1+: Always keep core keys
        if key in CORE_METADATA_KEYS:
            reduced[key] = value
            continue

        # Level 2+: Truncate arrays to 3 items max, preserve scalars
        if reduction_level >= 2 and isinstance(value, list):
            reduced[key] = value[:3]
        else:
            reduced[key] = value

    return reduced


def write_metadata_to_s3(output_s3_uri: str, metadata: dict[str, Any]) -> str:
    """
    Write metadata to S3 as a .metadata.json file.

    Args:
        output_s3_uri: S3 URI of the content file.
        metadata: Dictionary of metadata key-value pairs.

    Returns:
        S3 URI of the metadata file.
    """
    if not output_s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {output_s3_uri}")

    path = output_s3_uri[5:]
    if "/" not in path:
        raise ValueError(f"Invalid S3 URI: missing object key in {output_s3_uri}")

    bucket, key = path.split("/", 1)

    metadata_key = f"{key}.metadata.json"
    metadata_uri = f"s3://{bucket}/{metadata_key}"

    # Normalize metadata for S3 Vectors
    normalized_metadata = normalize_metadata_for_s3(metadata)

    metadata_content = {"metadataAttributes": normalized_metadata}

    s3_client.put_object(
        Bucket=bucket,
        Key=metadata_key,
        Body=json.dumps(metadata_content),
        ContentType="application/json",
    )

    logger.info(f"Wrote metadata to {metadata_uri}")
    return metadata_uri


def ingest_text_to_kb(
    document_id: str,
    output_s3_uri: str,
    metadata: dict[str, Any],
    kb_id: str,
    ds_id: str,
    max_retries: int = 3,
) -> dict[str, Any]:
    """
    Ingest transcript to KB using direct API with retry on metadata failures.

    Args:
        document_id: Document identifier.
        output_s3_uri: S3 URI of the text content.
        metadata: Metadata dictionary.
        kb_id: Knowledge Base ID.
        ds_id: Data Source ID.
        max_retries: Max retries with progressively reduced metadata.

    Returns:
        Result dictionary with ingestion status.
    """
    current_metadata = metadata.copy()

    for attempt in range(max_retries):
        # Write metadata file
        metadata_uri = write_metadata_to_s3(output_s3_uri, current_metadata)
        logger.info(f"Wrote transcript metadata (attempt {attempt + 1}): {metadata_uri}")

        # Build document for direct API ingestion
        document = {
            "content": {
                "dataSourceType": "S3",
                "s3": {"s3Location": {"uri": output_s3_uri}},
            },
            "metadata": {
                "type": "S3_LOCATION",
                "s3Location": {"uri": metadata_uri},
            },
        }

        # Ingest via direct API (Bedrock handles embedding + indexing)
        response = bedrock_agent.ingest_knowledge_base_documents(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            documents=[document],
        )

        doc_details = response.get("documentDetails", [])
        initial_status = doc_details[0].get("status", "UNKNOWN") if doc_details else "UNKNOWN"
        logger.info(f"Transcript ingestion initial status: {initial_status}")

        # Quick check for final status
        final_status = check_document_status(kb_id, ds_id, output_s3_uri)
        logger.info(f"Transcript ingestion final status: {final_status}")

        # Success or in-progress - done
        if final_status in ("INDEXED", "STARTING", "IN_PROGRESS"):
            return {
                "status": final_status,
                "metadata_uri": metadata_uri,
                "ingested_metadata": current_metadata,
            }

        # Failed - try with reduced metadata
        if final_status == "FAILED" and attempt < max_retries - 1:
            reduction_level = attempt + 1
            logger.warning(
                f"Ingestion failed, retrying with reduced metadata (level {reduction_level})"
            )
            current_metadata = reduce_metadata(metadata, reduction_level)
            continue

        # Final attempt or non-retryable status
        return {
            "status": final_status,
            "metadata_uri": metadata_uri,
            "ingested_metadata": current_metadata,
        }

    return {"status": "FAILED", "metadata_uri": metadata_uri, "ingested_metadata": current_metadata}


def group_segments_by_time_window(
    segments: list[dict[str, Any]],
    window_seconds: int = 300,
) -> list[list[dict[str, Any]]]:
    """
    Group segments into time windows for chunked metadata extraction.

    Args:
        segments: List of segment dicts with timestamp_start.
        window_seconds: Time window size in seconds (default 5 minutes).

    Returns:
        List of segment groups, each covering a time window.
    """
    if not segments:
        return []

    # Sort by timestamp
    sorted_segments = sorted(segments, key=lambda s: s.get("timestamp_start", 0))

    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = []
    window_start = 0

    for segment in sorted_segments:
        timestamp = segment.get("timestamp_start", 0)

        # Start new group if segment is beyond current window
        if timestamp >= window_start + window_seconds:
            if current_group:
                groups.append(current_group)
            current_group = [segment]
            window_start = (timestamp // window_seconds) * window_seconds
        else:
            current_group.append(segment)

    # Don't forget the last group
    if current_group:
        groups.append(current_group)

    return groups


def extract_metadata_for_segment_group(
    segments: list[dict[str, Any]],
    base_metadata: dict[str, Any],
    document_id: str,
) -> dict[str, Any]:
    """
    Extract metadata from a group of segments using LLM.

    Args:
        segments: List of segments in this time window.
        base_metadata: Technical metadata to include.
        document_id: Document identifier.

    Returns:
        Extracted metadata for this segment group.
    """
    # Combine text from all segments in this group
    combined_text = " ".join(s.get("text", "") for s in segments)

    if not combined_text.strip():
        return base_metadata.copy()

    try:
        extractor = get_metadata_extractor()
        return extractor.extract_media_metadata(
            transcript=combined_text,
            segments=segments,
            technical_metadata=base_metadata,
            document_id=document_id,
        )
    except Exception as e:
        logger.warning(f"Failed to extract metadata for segment group: {e}")
        return base_metadata.copy()


def _prepare_segment_data(
    transcript_segments: list[dict[str, Any]],
    base_metadata: dict[str, Any],
    base_bucket: str,
    content_dir: str,
    document_id: str,
) -> list[dict[str, Any]]:
    """
    Prepare segment data with metadata for batch ingestion.

    Groups segments by time window for metadata extraction, then builds
    segment-specific metadata with timestamps.

    Returns list of dicts with: segment_uri, segment_metadata, segment_index
    """
    segment_data = []

    # Group segments into 5-minute windows for metadata extraction
    segment_groups = group_segments_by_time_window(transcript_segments, window_seconds=300)
    logger.info(f"Grouped {len(transcript_segments)} segments into {len(segment_groups)} windows")

    for group in segment_groups:
        # Extract metadata for this time window
        group_metadata = extract_metadata_for_segment_group(group, base_metadata, document_id)

        for segment in group:
            segment_index = segment.get("segment_index", 0)
            timestamp_start = segment.get("timestamp_start", 0)
            timestamp_end = segment.get("timestamp_end", 0)

            # Flat segment path: content/<doc_id>/segment-000.txt
            segment_key = f"{content_dir}/segment-{segment_index:03d}.txt"
            segment_uri = f"s3://{base_bucket}/{segment_key}"

            # Build segment-specific metadata with timestamps
            segment_metadata = {
                **group_metadata,
                "segment_index": segment_index,
                "timestamp_start": timestamp_start,
                "timestamp_end": timestamp_end,
            }

            segment_data.append(
                {
                    "segment_uri": segment_uri,
                    "segment_metadata": segment_metadata,
                    "segment_index": segment_index,
                }
            )

    return segment_data


def _batch_ingest_segments(
    segment_data: list[dict[str, Any]],
    kb_id: str,
    ds_id: str,
) -> None:
    """
    Batch ingest segments (25 per API call).

    Writes metadata files and calls IngestKnowledgeBaseDocuments in batches.
    """
    for i in range(0, len(segment_data), INGEST_BATCH_SIZE):
        batch = segment_data[i : i + INGEST_BATCH_SIZE]
        documents = []

        for item in batch:
            # Write metadata file for this segment
            metadata_uri = write_metadata_to_s3(item["segment_uri"], item["segment_metadata"])

            documents.append(
                {
                    "content": {
                        "dataSourceType": "S3",
                        "s3": {"s3Location": {"uri": item["segment_uri"]}},
                    },
                    "metadata": {
                        "type": "S3_LOCATION",
                        "s3Location": {"uri": metadata_uri},
                    },
                }
            )

        # Ingest batch via direct API
        try:
            bedrock_agent.ingest_knowledge_base_documents(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                documents=documents,
            )
            logger.debug(f"Ingested batch of {len(documents)} segments")
        except ClientError as e:
            logger.error(f"Failed to ingest segment batch: {e}")


def ingest_transcript_segments(
    document_id: str,
    transcript_segments: list[dict[str, Any]],
    base_metadata: dict[str, Any],
    output_s3_uri: str,
    kb_id: str,
    ds_id: str,
    max_retries: int = 3,
) -> int:
    """
    Ingest transcript segments to KB using batched direct API.

    Uses batched ingestion and status checks to minimize latency:
    - Ingests all segments in batches of 25
    - Single sleep after all batches
    - Batch checks all statuses
    - Retries only failed segments with reduced metadata

    Args:
        document_id: Document identifier.
        transcript_segments: List of segment dicts with timestamp_start, timestamp_end, text.
        base_metadata: Technical metadata to include with each segment.
        output_s3_uri: Base S3 URI for the document content.
        kb_id: Knowledge Base ID.
        ds_id: Data Source ID.
        max_retries: Maximum retry attempts with progressively reduced metadata.

    Returns:
        Number of segments successfully ingested.
    """
    if not transcript_segments:
        logger.info(f"No transcript segments for {document_id}")
        return 0

    # Parse base URI to get bucket and prefix
    base_bucket, base_prefix = parse_s3_uri(output_s3_uri)
    if not base_bucket:
        logger.warning(f"Invalid output_s3_uri: {output_s3_uri}")
        return 0

    # Get the content directory (remove filename from prefix)
    content_dir = "/".join(base_prefix.split("/")[:-1])

    # Prepare all segment data with metadata
    try:
        all_segment_data = _prepare_segment_data(
            transcript_segments, base_metadata, base_bucket, content_dir, document_id
        )
    except Exception as e:
        logger.error(f"Failed to prepare segment data: {e}")
        return 0

    if not all_segment_data:
        return 0

    total_segments = len(all_segment_data)
    pending = all_segment_data.copy()

    for attempt in range(max_retries):
        if not pending:
            break

        # Reduce metadata for retries (level 2+ for segments)
        if attempt > 0:
            reduction_level = attempt + 1
            logger.warning(
                f"Retry {attempt}: reducing metadata (level {reduction_level}) for "
                f"{len(pending)} failed segments"
            )
            for item in pending:
                item["segment_metadata"] = reduce_metadata(
                    item["segment_metadata"], reduction_level
                )

        # Batch ingest all pending segments
        logger.info(f"Attempt {attempt + 1}: ingesting {len(pending)} segments in batches")
        _batch_ingest_segments(pending, kb_id, ds_id)

        # Single sleep after all batches
        time.sleep(2)

        # Batch check all statuses
        pending_uris = [item["segment_uri"] for item in pending]
        statuses = batch_check_document_statuses(kb_id, ds_id, pending_uris)

        # Filter to only failed segments for retry
        still_pending = []
        for item in pending:
            status = statuses.get(item["segment_uri"], "UNKNOWN")
            if status == "FAILED":
                still_pending.append(item)
            elif status not in ("INDEXED", "STARTING", "IN_PROGRESS"):
                # Unknown status - assume it might have failed
                still_pending.append(item)

        succeeded_this_round = len(pending) - len(still_pending)
        logger.info(
            f"Attempt {attempt + 1}: {succeeded_this_round} succeeded, "
            f"{len(still_pending)} failed/pending"
        )

        pending = still_pending

    # Calculate final success count
    ingested_count = total_segments - len(pending)
    if pending:
        failed_indices = [item["segment_index"] for item in pending]
        logger.warning(
            f"Failed to ingest {len(pending)} segments after {max_retries} attempts: "
            f"{failed_indices[:10]}{'...' if len(failed_indices) > 10 else ''}"
        )

    logger.info(f"Ingested {ingested_count}/{total_segments} segments for {document_id}")
    return ingested_count


def lambda_handler(event, context):
    """Ingest media content with dual embeddings."""
    # Get KB config from config table (with env var fallback)
    config = get_config_manager_or_none()
    kb_id, ds_id = get_knowledge_base_config(config)
    tracking_table_name = os.environ.get("TRACKING_TABLE")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    if not tracking_table_name:
        raise ValueError("TRACKING_TABLE is required")

    # Extract event data
    document_id = event.get("document_id")
    output_s3_uri = event.get("output_s3_uri")
    _video_s3_uri = event.get("video_s3_uri")  # For future visual embeddings

    if not document_id:
        raise ValueError("document_id is required")

    if not output_s3_uri:
        raise ValueError("output_s3_uri is required")

    media_type = event.get("media_type", "video")
    duration_seconds = event.get("duration_seconds", 0)
    total_segments = event.get("total_segments", 0)
    transcript_segments = event.get("transcript_segments", [])

    logger.info(
        f"Ingesting media {document_id}: type={media_type}, "
        f"duration={duration_seconds}s, segments={total_segments}"
    )

    # Get tracking table
    tracking_table = dynamodb.Table(tracking_table_name)

    # Fetch document details
    doc_response = tracking_table.get_item(Key={"document_id": document_id})
    doc_item = doc_response.get("Item", {})
    filename = doc_item.get("filename", "unknown")

    try:
        # Read transcript for metadata extraction
        transcript_text = read_s3_text(output_s3_uri) if output_s3_uri else ""

        # Build technical metadata (~5 keys)
        technical_metadata = {
            "content_type": media_type,  # "video" or "audio" for filtering
            "duration_seconds": duration_seconds,
            "total_segments": total_segments,
        }

        # Extract metadata from transcript
        extractor = get_metadata_extractor()
        extracted_metadata = extractor.extract_media_metadata(
            transcript=transcript_text,
            segments=transcript_segments,
            technical_metadata=technical_metadata,
            document_id=document_id,
        )

        # Ensure content_type is set correctly for filtering
        extracted_metadata["content_type"] = media_type  # "video" or "audio"

        meta_keys = list(extracted_metadata.keys())
        logger.info(f"Extracted metadata keys ({len(meta_keys)}): {meta_keys}")

        # Ingest text transcript to KB (full transcript for context)
        text_result = ingest_text_to_kb(
            document_id=document_id,
            output_s3_uri=output_s3_uri,
            metadata=extracted_metadata,
            kb_id=kb_id,
            ds_id=ds_id,
        )

        text_indexed = text_result.get("status") in ("STARTING", "IN_PROGRESS", "INDEXED")

        # Use the metadata that was actually ingested (may be reduced from original)
        ingested_metadata = text_result.get("ingested_metadata", extracted_metadata)

        # Ingest individual transcript segments with timestamps
        # This enables deep linking into videos via ?t=<timestamp>
        segments_indexed = ingest_transcript_segments(
            document_id=document_id,
            transcript_segments=transcript_segments,
            base_metadata=ingested_metadata,  # Use reduced metadata for segments too
            output_s3_uri=output_s3_uri,
            kb_id=kb_id,
            ds_id=ds_id,
        )

        # Update tracking table with actually ingested metadata
        tracking_table.update_item(
            Key={"document_id": document_id},
            UpdateExpression=(
                "SET #status = :status, updated_at = :updated_at, extracted_metadata = :metadata"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "indexed",
                ":updated_at": datetime.now(UTC).isoformat(),
                ":metadata": ingested_metadata,
            },
        )

        # Publish update
        publish_document_update(
            graphql_endpoint,
            document_id,
            filename,
            "INDEXED",
            total_pages=total_segments,
        )

        # Start KB ingestion job for visual embeddings (video file)
        # This syncs the video file to KB for multimodal visual search
        try:
            ingestion_response = start_ingestion_with_retry(kb_id, ds_id)
            job_info = ingestion_response.get("ingestionJob", {})
            ingestion_job_id = job_info.get("ingestionJobId")
            logger.info(f"Started ingestion job {ingestion_job_id} for media {document_id}")
        except ClientError as e:
            logger.warning(f"Failed to start visual ingestion for {document_id}: {e}")
            # Don't fail - text ingestion succeeded, visual can be retried
            ingestion_job_id = None

        return {
            "document_id": document_id,
            "status": "indexed",
            "text_indexed": text_indexed,
            "segments_indexed": segments_indexed,
            "metadata_keys": list(extracted_metadata.keys()),
            "visual_ingestion_job_id": ingestion_job_id,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to ingest media: {error_code} - {error_msg}")

        # Update status to failed
        try:
            tracking_table.update_item(
                Key={"document_id": document_id},
                UpdateExpression=(
                    "SET #status = :status, error_message = :error, updated_at = :updated_at"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": "failed",
                    ":error": error_msg,
                    ":updated_at": datetime.now(UTC).isoformat(),
                },
            )
            publish_document_update(
                graphql_endpoint,
                document_id,
                filename,
                "FAILED",
                error_message=error_msg,
            )
        except Exception as update_error:
            logger.error(f"Failed to update status: {update_error}")

        raise

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to ingest media: {error_msg}", exc_info=True)

        # Update status to failed
        try:
            tracking_table.update_item(
                Key={"document_id": document_id},
                UpdateExpression=(
                    "SET #status = :status, error_message = :error, updated_at = :updated_at"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": "failed",
                    ":error": error_msg,
                    ":updated_at": datetime.now(UTC).isoformat(),
                },
            )
            publish_document_update(
                graphql_endpoint,
                document_id,
                filename,
                "FAILED",
                error_message=error_msg,
            )
        except Exception as update_error:
            logger.error(f"Failed to update status: {update_error}")

        raise
