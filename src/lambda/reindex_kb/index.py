"""
Reindex Knowledge Base Lambda Handler.

Handles the reindex workflow for regenerating Knowledge Base content:
1. Create new KB with S3 Vectors
2. Re-ingest all content (documents, images, scraped pages) with fresh metadata
3. Delete old KB on success

This Lambda is invoked by Step Functions at different stages of the workflow.

Content Types:
- Documents (type=None): Text extracted via OCR, stored at output_s3_uri
- Images (type="image"): Visual files with captions at caption_s3_uri
- Scraped (type="scraped"): Web content stored at output_s3_uri
"""

import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import boto3
from kb_migrator import KBMigrator

from ragstack_common.appsync import publish_reindex_update
from ragstack_common.config import ConfigurationManager
from ragstack_common.ingestion import ingest_documents_with_retry
from ragstack_common.key_library import KeyLibrary
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.storage import read_s3_text, write_metadata_to_s3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb = boto3.resource("dynamodb")
bedrock_agent = boto3.client("bedrock-agent")
s3_client = boto3.client("s3")
lambda_client = boto3.client("lambda")

# Lazy-initialized singletons
_key_library = None
_metadata_extractor = None
_config_manager = None

# Cache for job metadata (persists within a single Lambda invocation/batch)
# Key: job_id, Value: dict of extracted metadata from seed document
_job_metadata_cache: dict[str, dict] = {}

# Reindex lock key in configuration table
REINDEX_LOCK_KEY = "reindex_lock"


def acquire_reindex_lock(execution_arn: str) -> bool:
    """
    Acquire global reindex lock to prevent concurrent operations.

    Uses conditional write to ensure only one reindex can run at a time.
    The lock prevents individual document operations (reindex, reprocess, delete)
    from interfering with the full KB reindex.

    Args:
        execution_arn: Step Functions execution ARN for tracking.

    Returns:
        True if lock acquired, False if already locked.
    """
    config_table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
    if not config_table_name:
        logger.warning("CONFIGURATION_TABLE_NAME not set, skipping lock acquisition")
        return True  # Allow reindex to proceed without lock

    try:
        table = dynamodb.Table(config_table_name)
        table.put_item(
            Item={
                "config_key": REINDEX_LOCK_KEY,
                "is_locked": True,
                "execution_arn": execution_arn,
                "started_at": datetime.now(UTC).isoformat(),
            },
            ConditionExpression="attribute_not_exists(config_key) OR is_locked = :false",
            ExpressionAttributeValues={":false": False},
        )
        logger.info(f"Acquired reindex lock for execution: {execution_arn}")
        return True
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        logger.error("Failed to acquire reindex lock - another reindex is in progress")
        return False
    except Exception as e:
        logger.warning(f"Error acquiring reindex lock: {e}")
        return True  # Allow reindex to proceed on error


def release_reindex_lock() -> None:
    """
    Release the global reindex lock.

    Called after reindex completes (success or failure) to allow
    individual document operations to resume.
    """
    config_table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
    if not config_table_name:
        logger.warning("CONFIGURATION_TABLE_NAME not set, skipping lock release")
        return

    try:
        table = dynamodb.Table(config_table_name)
        table.update_item(
            Key={"config_key": REINDEX_LOCK_KEY},
            UpdateExpression="SET is_locked = :false, released_at = :released_at",
            ExpressionAttributeValues={
                ":false": False,
                ":released_at": datetime.now(UTC).isoformat(),
            },
        )
        logger.info("Released reindex lock")
    except Exception as e:
        logger.warning(f"Error releasing reindex lock: {e}")


def get_key_library() -> KeyLibrary:
    """Get or create KeyLibrary singleton."""
    global _key_library
    if _key_library is None:
        table_name = os.environ.get("METADATA_KEY_LIBRARY_TABLE")
        if table_name:
            _key_library = KeyLibrary(table_name=table_name)
        else:
            logger.warning("METADATA_KEY_LIBRARY_TABLE not set")
            _key_library = KeyLibrary()
    return _key_library


def get_metadata_extractor() -> MetadataExtractor:
    """Get or create MetadataExtractor singleton."""
    global _metadata_extractor
    if _metadata_extractor is None:
        config = get_config_manager()
        model_id = None
        max_keys = None
        extraction_mode = "auto"
        manual_keys = None

        if config:
            model_id = config.get_parameter("metadata_extraction_model")
            max_keys = config.get_parameter("metadata_max_keys")
            extraction_mode = config.get_parameter("metadata_extraction_mode", default="auto")
            manual_keys = config.get_parameter("metadata_manual_keys")

        _metadata_extractor = MetadataExtractor(
            key_library=get_key_library(),
            model_id=model_id,
            max_keys=max_keys if max_keys else 8,
            extraction_mode=extraction_mode,
            manual_keys=manual_keys,
        )
    return _metadata_extractor


def get_config_manager() -> ConfigurationManager | None:
    """Get or create ConfigurationManager singleton."""
    global _config_manager
    if _config_manager is None:
        table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
        if table_name:
            try:
                _config_manager = ConfigurationManager(table_name=table_name)
            except Exception as e:
                logger.warning(f"Failed to initialize ConfigurationManager: {e}")
                return None
    return _config_manager


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Main Lambda handler for reindex operations.

    The Step Functions state machine invokes this with different 'action' values:
    - init: Initialize reindex, count documents, create new KB
    - process_batch: Process a batch of documents
    - finalize: Update configuration with new KB ID, delete old KB
    - cleanup_failed: Clean up on failure

    Args:
        event: Step Functions event with action and state
        context: Lambda context

    Returns:
        Updated state for Step Functions
    """
    action = event.get("action", "init")
    logger.info(f"Reindex action: {action}")

    # Clear caches at start of each invocation to prevent stale data
    # across warm Lambda containers
    global _job_metadata_cache
    _job_metadata_cache.clear()

    try:
        if action == "init":
            return handle_init(event)
        if action == "process_batch":
            return handle_process_batch(event)
        if action == "finalize":
            return handle_finalize(event)
        if action == "cleanup_failed":
            return handle_cleanup_failed(event)
        raise ValueError(f"Unknown action: {action}")

    except Exception as e:
        logger.exception(f"Reindex error: {e}")
        # Publish failure update - but NOT for finalize action since it has retries
        # and the state machine will handle final failure via cleanup_failed state
        graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")
        if graphql_endpoint and action != "finalize":
            publish_reindex_update(
                graphql_endpoint,
                status="FAILED",
                total_documents=event.get("total_documents", 0),
                processed_count=event.get("processed_count", 0),
                error_count=1,
                error_messages=[str(e)],
            )
        raise


def handle_init(event: dict) -> dict:
    """
    Initialize the reindex operation.

    1. Acquire global reindex lock
    2. Count documents to reindex
    3. Create new Knowledge Base
    4. Return initial state for processing loop
    """
    tracking_table_name = os.environ.get("TRACKING_TABLE")
    data_bucket = os.environ.get("DATA_BUCKET")
    vector_bucket = os.environ.get("VECTOR_BUCKET")
    stack_name = os.environ.get("STACK_NAME")
    kb_role_arn = os.environ.get("KB_ROLE_ARN")
    embedding_model_arn = os.environ.get("EMBEDDING_MODEL_ARN")
    old_kb_id = os.environ.get("KNOWLEDGE_BASE_ID")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    # Acquire global reindex lock to prevent concurrent document operations
    execution_id = f"reindex-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    if not acquire_reindex_lock(execution_id):
        raise RuntimeError(
            "Cannot start reindex: another reindex operation is already in progress. "
            "Wait for it to complete or check the configuration table for stale locks."
        )

    # Publish starting status
    publish_reindex_update(
        graphql_endpoint,
        status="PENDING",
        total_documents=0,
        processed_count=0,
    )

    # Reset key library occurrence counts so they accurately reflect post-reindex state
    key_library = get_key_library()
    reset_count = key_library.reset_occurrence_counts()
    logger.info(f"Reset occurrence counts for {reset_count} metadata keys")

    # Count all content to reindex (documents, images, scraped pages)
    tracking_table = dynamodb.Table(tracking_table_name)
    all_content = list_all_content(tracking_table)

    # Count by type for logging
    doc_count = sum(1 for item in all_content if not item.get("type"))
    image_count = sum(1 for item in all_content if item.get("type") == "image")
    scraped_count = sum(1 for item in all_content if item.get("type") == "scraped")
    media_count = sum(1 for item in all_content if item.get("type") == "media")

    total_documents = len(all_content)
    logger.info(
        f"Found {total_documents} items to reindex: "
        f"{doc_count} documents, {image_count} images, {scraped_count} scraped, {media_count} media"
    )

    # Publish creating KB status
    publish_reindex_update(
        graphql_endpoint,
        status="CREATING_KB",
        total_documents=total_documents,
        processed_count=0,
    )

    # Create new Knowledge Base with timestamp suffix
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    migrator = KBMigrator(
        data_bucket=data_bucket,
        vector_bucket=vector_bucket,
        stack_name=stack_name,
        kb_role_arn=kb_role_arn,
        embedding_model_arn=embedding_model_arn,
    )

    new_kb = migrator.create_knowledge_base(suffix=timestamp)
    logger.info(f"Created new KB: {new_kb['kb_id']}")

    # Run baseline sync on empty KB and wait for completion
    # This establishes sync tracking before any API ingestion
    logger.info(f"Starting baseline sync on new KB: {new_kb['kb_id']}")
    baseline_response = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=new_kb["kb_id"],
        dataSourceId=new_kb["data_source_id"],
    )
    baseline_job_id = baseline_response.get("ingestionJob", {}).get("ingestionJobId")
    logger.info(f"Baseline sync started: {baseline_job_id}")

    # Wait for baseline to complete before proceeding
    if baseline_job_id:
        max_wait = 120  # 2 minutes max
        poll_interval = 5
        elapsed = 0

        while elapsed < max_wait:
            job_response = bedrock_agent.get_ingestion_job(
                knowledgeBaseId=new_kb["kb_id"],
                dataSourceId=new_kb["data_source_id"],
                ingestionJobId=baseline_job_id,
            )
            status = job_response.get("ingestionJob", {}).get("status")
            logger.info(f"Baseline sync status: {status} ({elapsed}s)")

            if status in ("COMPLETE", "FAILED"):
                break

            time.sleep(poll_interval)
            elapsed += poll_interval

        if status == "FAILED":
            logger.warning("Baseline sync failed, continuing anyway")
        elif elapsed >= max_wait:
            logger.warning("Baseline sync timed out, continuing anyway")

    # Return state for processing loop
    return {
        "action": "process_batch",
        "old_kb_id": old_kb_id,
        "new_kb_id": new_kb["kb_id"],
        "new_data_source_id": new_kb["data_source_id"],
        "vector_index_arn": new_kb["vector_index_arn"],
        "total_documents": total_documents,
        "processed_count": 0,
        "error_count": 0,
        "error_messages": [],
        "batch_size": 10,
        "current_batch_index": 0,
    }


def handle_process_batch(event: dict) -> dict:
    """
    Process a batch of content items.

    Re-extracts metadata and ingests each item into the new KB.
    Handles documents, images, and scraped pages with type-specific logic.
    """
    tracking_table_name = os.environ.get("TRACKING_TABLE")
    data_bucket = os.environ.get("DATA_BUCKET")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    new_kb_id = event["new_kb_id"]
    new_ds_id = event["new_data_source_id"]
    total_documents = event["total_documents"]
    processed_count = event["processed_count"]
    error_count = event["error_count"]
    error_messages = event.get("error_messages", [])
    batch_size = event.get("batch_size", 10)
    current_batch_index = event.get("current_batch_index", 0)

    # Get all content for this batch
    tracking_table = dynamodb.Table(tracking_table_name)
    all_content = list_all_content(tracking_table)

    batch_start = current_batch_index * batch_size
    batch_end = min(batch_start + batch_size, len(all_content))
    batch_items = all_content[batch_start:batch_end]

    logger.info(f"Processing batch {current_batch_index}: items {batch_start}-{batch_end}")

    # Process each item in the batch
    for item in batch_items:
        doc_id = item.get("document_id")
        filename = item.get("filename", "unknown")
        item_type = item.get("type", "")  # "", "image", or "scraped"

        # Publish progress
        publish_reindex_update(
            graphql_endpoint,
            status="PROCESSING",
            total_documents=total_documents,
            processed_count=processed_count,
            current_document=filename,
            error_count=error_count,
            error_messages=error_messages[-5:] if error_messages else None,
        )

        try:
            if item_type == "media":
                # Media (video/audio): ingest video file + transcript
                processed_count, error_count, error_messages = process_media_item(
                    item,
                    new_kb_id,
                    new_ds_id,
                    data_bucket,
                    processed_count,
                    error_count,
                    error_messages,
                )
            elif item_type == "image":
                # Images: read text from caption_s3_uri, ingest both image and caption
                processed_count, error_count, error_messages = process_image_item(
                    item,
                    new_kb_id,
                    new_ds_id,
                    data_bucket,
                    processed_count,
                    error_count,
                    error_messages,
                )
            elif item_type == "scraped":
                # Scraped pages: use job-aware metadata extraction
                processed_count, error_count, error_messages = process_scraped_item(
                    item,
                    new_kb_id,
                    new_ds_id,
                    data_bucket,
                    all_content,
                    processed_count,
                    error_count,
                    error_messages,
                )
            else:
                # Regular documents: read text from output_s3_uri
                processed_count, error_count, error_messages = process_text_item(
                    item,
                    new_kb_id,
                    new_ds_id,
                    data_bucket,
                    "document",
                    processed_count,
                    error_count,
                    error_messages,
                )

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        except Exception as e:
            error_count += 1
            error_msg = f"{filename}: {str(e)[:100]}"
            error_messages.append(error_msg)
            logger.error(f"Failed to reindex {doc_id}: {e}")
            processed_count += 1  # Count as processed even if failed

    # Check if more batches to process
    if batch_end < len(all_content):
        # More items to process
        return {
            **event,
            "action": "process_batch",
            "processed_count": processed_count,
            "error_count": error_count,
            "error_messages": error_messages,
            "current_batch_index": current_batch_index + 1,
        }
    # All items processed, move to finalize
    return {
        **event,
        "action": "finalize",
        "processed_count": processed_count,
        "error_count": error_count,
        "error_messages": error_messages,
    }


def process_text_item(
    item: dict,
    kb_id: str,
    ds_id: str,
    data_bucket: str,
    content_type: str,
    processed_count: int,
    error_count: int,
    error_messages: list,
) -> tuple[int, int, list]:
    """
    Process a text-based item (document or scraped page).

    Args:
        item: DynamoDB tracking record
        kb_id: Knowledge Base ID
        ds_id: Data Source ID
        data_bucket: S3 bucket name
        content_type: "document" or "web_page"
        processed_count: Current processed count
        error_count: Current error count
        error_messages: List of error messages

    Returns:
        Tuple of (processed_count, error_count, error_messages)
    """
    doc_id = item.get("document_id")
    filename = item.get("filename", "unknown")
    output_s3_uri = item.get("output_s3_uri")

    if not output_s3_uri:
        logger.warning(f"Item {doc_id} has no output_s3_uri, skipping")
        return processed_count + 1, error_count, error_messages

    # Re-extract metadata from text content
    metadata = extract_document_metadata(output_s3_uri, doc_id)

    # Add base metadata
    metadata["content_type"] = content_type
    metadata["document_id"] = doc_id
    metadata["filename"] = filename

    # For scraped pages, preserve source_url if available
    if content_type == "web_page" and item.get("source_url"):
        metadata["source_url"] = item["source_url"]

    # Write metadata to S3
    metadata_uri = write_metadata_to_s3(output_s3_uri, metadata)

    # Ingest to new KB
    ingest_document(kb_id, ds_id, output_s3_uri, metadata_uri)

    logger.info(f"Reindexed {content_type} {doc_id}: {filename}")
    return processed_count + 1, error_count, error_messages


def process_scraped_item(
    item: dict,
    kb_id: str,
    ds_id: str,
    data_bucket: str,
    all_content: list[dict],
    processed_count: int,
    error_count: int,
    error_messages: list,
) -> tuple[int, int, list]:
    """
    Process a scraped job or page with job-aware metadata.

    New format (single tracking record per job):
    - output_s3_uri ends with "/" (folder: content/{job_id}/)
    - job_id IS the document_id
    - Gets job_metadata from scrape_jobs table
    - Lists all .md files in folder and processes each

    Old format (tracking record per page):
    - output_s3_uri is a single file
    - Extracts job metadata from seed document via LLM

    Args:
        item: DynamoDB tracking record
        kb_id: Knowledge Base ID
        ds_id: Data Source ID
        data_bucket: S3 bucket name
        all_content: All content items (to find seed document for old format)
        processed_count: Current processed count
        error_count: Current error count
        error_messages: List of error messages

    Returns:
        Tuple of (processed_count, error_count, error_messages)
    """
    import json
    from datetime import UTC, datetime
    from urllib.parse import urlparse

    doc_id = item.get("document_id")
    filename = item.get("filename", "unknown")
    output_s3_uri = item.get("output_s3_uri")
    input_s3_uri = item.get("input_s3_uri")
    source_url = item.get("source_url", "")

    if not output_s3_uri:
        logger.warning(f"Scraped item {doc_id} has no output_s3_uri, skipping")
        return processed_count + 1, error_count, error_messages

    # Detect new format: output_s3_uri ends with / (folder)
    is_new_format = output_s3_uri.endswith("/")

    if is_new_format:
        # NEW FORMAT: Single tracking record per job, files in content/{job_id}/
        job_id = doc_id  # document_id IS the job_id

        # Get job_metadata from scrape_jobs table (NOT LLM extraction)
        job_info = get_scrape_job_info(job_id)
        job_metadata = job_info.get("job_metadata", {}) if job_info else {}
        logger.info(
            f"Processing scraped job {job_id} (new format): "
            f"{len(job_metadata)} metadata fields from DB"
        )

        # Parse bucket and prefix from output_s3_uri
        path = output_s3_uri[5:]  # Remove 's3://'
        bucket, prefix = path.split("/", 1)

        # List all .md files in content/{job_id}/
        paginator = s3_client.get_paginator("list_objects_v2")
        files_processed = 0

        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Skip metadata files
                if key.endswith(".metadata.json"):
                    continue
                # Only process .md files
                if not key.endswith(".md"):
                    continue

                content_uri = f"s3://{bucket}/{key}"
                metadata_key = f"{key}.metadata.json"

                # Read existing metadata to get source_url
                page_source_url = ""
                try:
                    response = s3_client.get_object(Bucket=bucket, Key=metadata_key)
                    existing = json.loads(response["Body"].read().decode("utf-8"))
                    page_source_url = existing.get("metadataAttributes", {}).get("source_url", "")
                except Exception:
                    logger.debug(f"No existing metadata for {key}")

                # Combine job_metadata + page-specific fields
                parsed = urlparse(page_source_url) if page_source_url else None
                metadata = dict(job_metadata) if job_metadata else {}
                metadata.update(
                    {
                        "content_type": "web_page",
                        "source_url": page_source_url,
                        "job_id": job_id,
                        "scraped_date": datetime.now(UTC).strftime("%Y-%m-%d"),
                    }
                )
                if parsed and parsed.netloc:
                    metadata["source_domain"] = parsed.netloc

                # Write updated metadata
                metadata_uri = write_metadata_to_s3(content_uri, metadata)

                # Ingest to KB
                try:
                    ingest_document(kb_id, ds_id, content_uri, metadata_uri)
                    files_processed += 1
                except Exception as e:
                    error_count += 1
                    error_messages.append(f"{key}: {str(e)[:50]}")
                    logger.error(f"Failed to ingest {key}: {e}")

        logger.info(f"Reindexed scraped job {job_id}: {files_processed} files")
        return processed_count + 1, error_count, error_messages

    # OLD FORMAT: Per-page tracking record
    # Get job_id from S3 input file metadata
    job_id = None
    if input_s3_uri:
        job_id = get_job_id_from_s3(input_s3_uri)

    # Get job-level metadata (from seed document, using new extraction settings)
    job_metadata = {}
    if job_id:
        job_metadata = get_or_extract_job_metadata(job_id, all_content, data_bucket)
        logger.info(f"Using job metadata for {doc_id}: {len(job_metadata)} fields (job {job_id})")
    else:
        logger.warning(f"No job_id found for scraped item {doc_id}, using page-only metadata")

    # Start with job-level metadata (semantic fields from seed)
    metadata = dict(job_metadata) if job_metadata else {}

    # Add/override with page-specific deterministic fields
    parsed = urlparse(source_url) if source_url else None
    metadata.update(
        {
            "content_type": "web_page",
            "document_id": doc_id,
            "filename": filename,
            "source_url": source_url,
            "scraped_date": datetime.now(UTC).strftime("%Y-%m-%d"),
        }
    )

    if parsed and parsed.netloc:
        metadata["source_domain"] = parsed.netloc

    if job_id:
        metadata["job_id"] = job_id

    # Write metadata to S3
    metadata_uri = write_metadata_to_s3(output_s3_uri, metadata)

    # Ingest to new KB
    ingest_document(kb_id, ds_id, output_s3_uri, metadata_uri)

    logger.info(f"Reindexed scraped page {doc_id}: {filename} (job: {job_id or 'none'})")
    return processed_count + 1, error_count, error_messages


def process_media_item(
    item: dict,
    kb_id: str,
    ds_id: str,
    data_bucket: str,
    processed_count: int,
    error_count: int,
    error_messages: list,
) -> tuple[int, int, list]:
    """
    Process a media item (video/audio).

    Media is ingested as multiple documents:
    1. The source video file (for visual embeddings via Nova Multimodal)
    2. The transcript text (for semantic text search)
    3. Individual transcript segments with timestamps (for deep linking)

    Args:
        item: DynamoDB tracking record
        kb_id: Knowledge Base ID
        ds_id: Data Source ID
        data_bucket: S3 bucket name
        processed_count: Current processed count
        error_count: Current error count
        error_messages: List of error messages

    Returns:
        Tuple of (processed_count, error_count, error_messages)
    """
    import re

    doc_id = item.get("document_id")
    filename = item.get("filename", "unknown")
    input_s3_uri = item.get("input_s3_uri")  # Source video file
    output_s3_uri = item.get("output_s3_uri")  # Transcript text
    media_type = item.get("media_type", "video")

    # Extract metadata from transcript
    metadata = {}
    if output_s3_uri:
        try:
            transcript_text = read_s3_text(output_s3_uri)
            if transcript_text and transcript_text.strip():
                extractor = get_metadata_extractor()
                metadata = extractor.extract_metadata(transcript_text, doc_id)
        except Exception as e:
            logger.warning(f"Failed to extract metadata for media {doc_id}: {e}")

    # Add base metadata
    metadata["content_type"] = "media"
    metadata["media_type"] = media_type
    metadata["file_type"] = media_type  # For filtering: "video" or "audio"
    metadata["document_id"] = doc_id
    metadata["filename"] = filename

    # Ingest source video file for visual embeddings (if video)
    if input_s3_uri and media_type == "video":
        try:
            video_metadata_uri = write_metadata_to_s3(input_s3_uri, metadata)
            ingest_document(kb_id, ds_id, input_s3_uri, video_metadata_uri)
            logger.info(f"Reindexed video file {doc_id}: {filename}")
        except Exception as e:
            logger.warning(f"Failed to ingest video file for {doc_id}: {e}")

    # Ingest full transcript for text search
    if output_s3_uri:
        try:
            transcript_metadata_uri = write_metadata_to_s3(output_s3_uri, metadata)
            ingest_document(kb_id, ds_id, output_s3_uri, transcript_metadata_uri)
            logger.info(f"Reindexed transcript {doc_id}: {filename}")
        except Exception as e:
            logger.warning(f"Failed to ingest transcript for {doc_id}: {e}")

    # Ingest transcript segments with timestamps for deep linking
    # Segments are stored at content/<doc_id>/segment-000.txt, etc.
    if output_s3_uri:
        try:
            # Parse bucket and get content directory
            path = output_s3_uri[5:]  # Remove 's3://'
            bucket, key = path.split("/", 1)
            content_dir = "/".join(key.split("/")[:-1])

            # List segment files (flat structure in content dir)
            response = s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=f"{content_dir}/segment-",
            )

            segment_count = 0
            for obj in response.get("Contents", []):
                segment_key = obj["Key"]
                # Extract segment index from filename (segment-000.txt -> 0)
                match = re.search(r"segment-(\d+)\.txt$", segment_key)
                if not match:
                    continue

                segment_index = int(match.group(1))
                # Calculate timestamps (30-sec segments)
                timestamp_start = segment_index * 30
                timestamp_end = (segment_index + 1) * 30

                # Build segment metadata with timestamps
                segment_metadata = {
                    **metadata,
                    "segment_index": segment_index,
                    "timestamp_start": timestamp_start,
                    "timestamp_end": timestamp_end,
                }

                segment_uri = f"s3://{bucket}/{segment_key}"
                segment_metadata_uri = write_metadata_to_s3(segment_uri, segment_metadata)
                ingest_document(kb_id, ds_id, segment_uri, segment_metadata_uri)
                segment_count += 1

            if segment_count > 0:
                logger.info(f"Reindexed {segment_count} transcript segments for {doc_id}")

        except Exception as e:
            logger.warning(f"Failed to ingest transcript segments for {doc_id}: {e}")

    return processed_count + 1, error_count, error_messages


def process_image_item(
    item: dict,
    kb_id: str,
    ds_id: str,
    data_bucket: str,
    processed_count: int,
    error_count: int,
    error_messages: list,
) -> tuple[int, int, list]:
    """
    Process an image item.

    Images are ingested as TWO documents:
    1. The image file itself (for visual embeddings)
    2. The caption text (for semantic text search)

    Both share the same metadata for filtering.

    Args:
        item: DynamoDB tracking record
        kb_id: Knowledge Base ID
        ds_id: Data Source ID
        data_bucket: S3 bucket name
        processed_count: Current processed count
        error_count: Current error count
        error_messages: List of error messages

    Returns:
        Tuple of (processed_count, error_count, error_messages)
    """
    doc_id = item.get("document_id")
    filename = item.get("filename", "unknown")
    image_s3_uri = item.get("output_s3_uri") or item.get("input_s3_uri")
    caption_s3_uri = item.get("caption_s3_uri")

    if not caption_s3_uri:
        logger.warning(f"Image {doc_id} has no caption_s3_uri, skipping")
        return processed_count + 1, error_count, error_messages

    # Read caption text for metadata extraction
    try:
        caption_text = read_s3_text(caption_s3_uri)
    except Exception as e:
        logger.warning(f"Failed to read caption for {doc_id}: {e}")
        caption_text = ""

    # Extract metadata from caption using LLM
    metadata = {}
    if caption_text and caption_text.strip():
        try:
            extractor = get_metadata_extractor()
            metadata = extractor.extract_metadata(caption_text, doc_id)
        except Exception as e:
            logger.warning(f"Failed to extract metadata for image {doc_id}: {e}")

    # Add base metadata for images
    metadata["content_type"] = "image"
    metadata["document_id"] = doc_id
    metadata["filename"] = filename

    if item.get("user_caption"):
        metadata["has_user_caption"] = "true"
    if item.get("ai_caption"):
        metadata["has_ai_caption"] = "true"

    # Write metadata to S3 for BOTH files (Bedrock requires metadata filename to match content)
    # Caption metadata
    caption_metadata_uri = write_metadata_to_s3(caption_s3_uri, metadata)
    # Image metadata (same content, different filename)
    image_metadata_uri = write_metadata_to_s3(image_s3_uri, metadata)

    # Ingest both image and caption to KB
    # Both documents have same metadata content but separate files
    image_document = {
        "content": {
            "dataSourceType": "S3",
            "s3": {"s3Location": {"uri": image_s3_uri}},
        },
        "metadata": {
            "type": "S3_LOCATION",
            "s3Location": {"uri": image_metadata_uri},
        },
    }

    # Caption document (text embedding with metadata for filtering)
    caption_document = {
        "content": {
            "dataSourceType": "S3",
            "s3": {"s3Location": {"uri": caption_s3_uri}},
        },
        "metadata": {
            "type": "S3_LOCATION",
            "s3Location": {"uri": caption_metadata_uri},
        },
    }

    # Ingest both documents (with retry for conflicts)
    response = ingest_documents_with_retry(
        kb_id=kb_id,
        ds_id=ds_id,
        documents=[image_document, caption_document],
    )

    doc_details = response.get("documentDetails", [])
    statuses = [d.get("status", "UNKNOWN") for d in doc_details]
    logger.info(f"Reindexed image {doc_id}: {filename}, statuses: {statuses}")

    return processed_count + 1, error_count, error_messages


def update_lambda_kb_env_vars(
    stack_name: str, new_kb_id: str, new_data_source_id: str | None = None
) -> list[str]:
    """
    Update KNOWLEDGE_BASE_ID and DATA_SOURCE_ID environment variables in Lambdas.

    Args:
        stack_name: The CloudFormation stack name (used as Lambda name prefix)
        new_kb_id: The new Knowledge Base ID
        new_data_source_id: The new Data Source ID (optional)

    Returns:
        List of error messages (empty if all updates succeeded)
    """
    # Lambdas that need env var updates
    # All Lambdas with KNOWLEDGE_BASE_ID (some also have DATA_SOURCE_ID)
    lambda_suffixes = [
        "query",
        "search",
        "ingest",
        "ingest-media",
        "reindex-kb",
        "process-image",
        "metadata-analyzer",
        "process-zip",
    ]
    errors = []

    for suffix in lambda_suffixes:
        function_name = f"{stack_name}-{suffix}"
        try:
            # Get current configuration
            response = lambda_client.get_function_configuration(FunctionName=function_name)
            current_env = response.get("Environment", {}).get("Variables", {})

            updated = False

            # Update KNOWLEDGE_BASE_ID if present
            if "KNOWLEDGE_BASE_ID" in current_env:
                current_env["KNOWLEDGE_BASE_ID"] = new_kb_id
                updated = True

            # Update DATA_SOURCE_ID if present and we have a new one
            if new_data_source_id and "DATA_SOURCE_ID" in current_env:
                current_env["DATA_SOURCE_ID"] = new_data_source_id
                updated = True

            if not updated:
                logger.info(f"Lambda {function_name} has no KB env vars, skipping")
                continue

            lambda_client.update_function_configuration(
                FunctionName=function_name,
                Environment={"Variables": current_env},
            )
            logger.info(f"Updated {function_name} KB_ID={new_kb_id}, DS_ID={new_data_source_id}")

        except Exception as e:
            error_msg = f"Failed to update {function_name}: {str(e)[:100]}"
            logger.error(error_msg)
            errors.append(error_msg)

    return errors


def update_config_kb_ids(new_kb_id: str, new_data_source_id: str) -> list[str]:
    """
    Update Knowledge Base ID and Data Source ID in the configuration table.

    This is the primary way Lambdas get KB config - env vars are now just fallback.

    Args:
        new_kb_id: The new Knowledge Base ID
        new_data_source_id: The new Data Source ID

    Returns:
        List of error messages (empty if update succeeded)
    """
    errors = []
    config_table_name = os.environ.get("CONFIGURATION_TABLE_NAME")

    if not config_table_name:
        logger.warning("CONFIGURATION_TABLE_NAME not set, skipping config update")
        return ["CONFIGURATION_TABLE_NAME not set"]

    try:
        config_manager = ConfigurationManager(table_name=config_table_name)

        # Update Custom config with new KB IDs
        # This uses atomic UpdateItem so it merges with existing custom config
        config_manager.update_custom_config(
            {
                "knowledge_base_id": new_kb_id,
                "data_source_id": new_data_source_id,
            }
        )

        logger.info(f"Updated config table with KB_ID={new_kb_id}, DS_ID={new_data_source_id}")

    except Exception as e:
        error_msg = f"Failed to update config table: {str(e)[:100]}"
        logger.error(error_msg)
        errors.append(error_msg)

    return errors


def handle_finalize(event: dict) -> dict:
    """
    Finalize the reindex operation.

    1. Update config table with new KB ID and Data Source ID (primary source)
    2. Update Lambda environment variables (fallback, for backwards compatibility)
    3. Start initial sync to establish tracking baseline (prevents re-sync on first video upload)
    4. Delete old KB
    5. Publish completion status
    """
    old_kb_id = event.get("old_kb_id")
    new_kb_id = event["new_kb_id"]
    new_data_source_id = event.get("new_data_source_id")
    total_documents = event["total_documents"]
    processed_count = event["processed_count"]
    error_count = event["error_count"]
    error_messages = event.get("error_messages", [])
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")
    data_bucket = os.environ.get("DATA_BUCKET")
    vector_bucket = os.environ.get("VECTOR_BUCKET")
    stack_name = os.environ.get("STACK_NAME")
    kb_role_arn = os.environ.get("KB_ROLE_ARN")
    embedding_model_arn = os.environ.get("EMBEDDING_MODEL_ARN")

    # Update config table first (primary source for KB IDs)
    # Do this BEFORE deleting old KB so queries keep working if update fails
    publish_reindex_update(
        graphql_endpoint,
        status="UPDATING_CONFIG",
        total_documents=total_documents,
        processed_count=processed_count,
        error_count=error_count,
        new_knowledge_base_id=new_kb_id,
    )

    config_errors = update_config_kb_ids(new_kb_id, new_data_source_id)
    if config_errors:
        error_messages.extend(config_errors)
        logger.warning(f"Config table update issues: {config_errors}")

    # Also update Lambda env vars as fallback (for backwards compatibility)
    lambda_errors = update_lambda_kb_env_vars(stack_name, new_kb_id, new_data_source_id)
    if lambda_errors:
        error_messages.extend(lambda_errors)
        logger.warning(f"Some Lambda env var updates failed: {lambda_errors}")

    # Start ingestion job for visual embeddings (images/videos)
    # Wait for any ongoing API operations to complete first
    if new_data_source_id:
        logger.info(f"Starting ingestion job for visual embeddings on {new_kb_id}")

        # Poll until API operations complete (max 5 minutes)
        max_wait = 300  # 5 minutes
        poll_interval = 10  # 10 seconds
        elapsed = 0

        while elapsed < max_wait:
            try:
                bedrock_agent.start_ingestion_job(
                    knowledgeBaseId=new_kb_id,
                    dataSourceId=new_data_source_id,
                )
                logger.info("Ingestion job started successfully")
                break
            except bedrock_agent.exceptions.ValidationException as e:
                if "ongoing KnowledgeBaseDocuments API request" in str(e):
                    logger.info(f"API operations still in progress, waiting... ({elapsed}s)")
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                else:
                    raise
        else:
            # Timeout - raise to trigger state machine retry
            raise RuntimeError(
                f"Timed out waiting for API operations to complete after {max_wait}s"
            )

    # Publish deleting old KB status
    publish_reindex_update(
        graphql_endpoint,
        status="DELETING_OLD_KB",
        total_documents=total_documents,
        processed_count=processed_count,
        error_count=error_count,
        new_knowledge_base_id=new_kb_id,
    )

    # Delete old KB if it exists and is different from new
    if old_kb_id and old_kb_id != new_kb_id:
        try:
            migrator = KBMigrator(
                data_bucket=data_bucket,
                vector_bucket=vector_bucket,
                stack_name=stack_name,
                kb_role_arn=kb_role_arn,
                embedding_model_arn=embedding_model_arn,
            )
            migrator.delete_knowledge_base(old_kb_id, delete_vectors=True)
            logger.info(f"Deleted old KB: {old_kb_id}")
        except Exception as e:
            logger.warning(f"Failed to delete old KB {old_kb_id}: {e}")
            # Don't fail the operation if old KB deletion fails
            error_messages.append(f"Failed to delete old KB: {str(e)[:100]}")

    # Deactivate metadata keys with zero occurrences (no longer in any documents)
    try:
        key_library = get_key_library()
        deactivated = key_library.deactivate_zero_count_keys()
        if deactivated > 0:
            logger.info(f"Deactivated {deactivated} metadata keys with zero occurrences")
    except Exception as e:
        logger.warning(f"Failed to deactivate zero-count keys: {e}")

    # Release the global reindex lock to allow individual document operations
    release_reindex_lock()

    # Publish completion status
    publish_reindex_update(
        graphql_endpoint,
        status="COMPLETED",
        total_documents=total_documents,
        processed_count=processed_count,
        error_count=error_count,
        error_messages=error_messages[-5:] if error_messages else None,
        new_knowledge_base_id=new_kb_id,
    )

    return {
        "status": "COMPLETED",
        "new_kb_id": new_kb_id,
        "total_documents": total_documents,
        "processed_count": processed_count,
        "error_count": error_count,
    }


def handle_cleanup_failed(event: dict) -> dict:
    """
    Clean up after a failed reindex operation.

    Deletes the new KB if it was created.
    Event structure from PrepareCleanup: { action, state: { new_kb_id, error, ... } }
    """
    # Extract state from nested structure (PrepareCleanup wraps the original state)
    state = event.get("state", event)  # Fallback to event itself for backwards compatibility

    new_kb_id = state.get("new_kb_id")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")
    data_bucket = os.environ.get("DATA_BUCKET")
    vector_bucket = os.environ.get("VECTOR_BUCKET")
    stack_name = os.environ.get("STACK_NAME")
    kb_role_arn = os.environ.get("KB_ROLE_ARN")
    embedding_model_arn = os.environ.get("EMBEDDING_MODEL_ARN")

    # Extract error message from the error object
    error_obj = state.get("error", {})
    error_message = error_obj.get("Cause", error_obj.get("Error", "Unknown error"))

    # Publish failure status
    publish_reindex_update(
        graphql_endpoint,
        status="FAILED",
        total_documents=state.get("total_documents", 0),
        processed_count=state.get("processed_count", 0),
        error_count=1,
        error_messages=[error_message],
    )

    # Delete new KB if it was created
    if new_kb_id:
        try:
            migrator = KBMigrator(
                data_bucket=data_bucket,
                vector_bucket=vector_bucket,
                stack_name=stack_name,
                kb_role_arn=kb_role_arn,
                embedding_model_arn=embedding_model_arn,
            )
            migrator.delete_knowledge_base(new_kb_id, delete_vectors=True)
            logger.info(f"Cleaned up new KB: {new_kb_id}")
        except Exception as e:
            logger.error(f"Failed to clean up new KB {new_kb_id}: {e}")

    # Release the global reindex lock to allow individual document operations
    release_reindex_lock()

    return {
        "status": "FAILED",
        "error_message": error_message,
    }


def get_job_id_from_s3(input_s3_uri: str) -> str | None:
    """
    Get job_id from S3 object metadata.

    The scrape_process Lambda stores job_id in S3 object metadata when saving
    scraped markdown files.

    Args:
        input_s3_uri: S3 URI of the input file (e.g., s3://bucket/input/docId/docId.scraped.md)

    Returns:
        job_id if found, None otherwise
    """
    if not input_s3_uri or not input_s3_uri.startswith("s3://"):
        return None

    try:
        path = input_s3_uri[5:]  # Remove 's3://'
        bucket, key = path.split("/", 1)

        response = s3_client.head_object(Bucket=bucket, Key=key)
        metadata = response.get("Metadata", {})
        return metadata.get("job_id") or metadata.get("job-id")
    except Exception as e:
        logger.debug(f"Failed to get job_id from S3 metadata: {e}")
        return None


def get_scrape_job_info(job_id: str) -> dict | None:
    """
    Look up scrape job info from ScrapeJobs table.

    Args:
        job_id: The scrape job ID

    Returns:
        Dict with base_url and other job info, or None if not found
    """
    jobs_table_name = os.environ.get("SCRAPE_JOBS_TABLE")
    if not jobs_table_name:
        logger.warning("SCRAPE_JOBS_TABLE not configured, skipping job metadata lookup")
        return None

    try:
        jobs_table = dynamodb.Table(jobs_table_name)
        response = jobs_table.get_item(Key={"job_id": job_id})
        return response.get("Item")
    except Exception as e:
        logger.warning(f"Failed to get scrape job info for {job_id}: {e}")
        return None


def find_seed_document(
    all_content: list[dict],
    base_url: str,
) -> dict | None:
    """
    Find the seed document for a scrape job.

    The seed document is the one whose source_url matches the job's base_url.

    Args:
        all_content: List of all content items from tracking table
        base_url: The job's base URL (seed URL)

    Returns:
        The seed document item, or None if not found
    """
    for item in all_content:
        if item.get("type") == "scraped" and item.get("source_url") == base_url:
            return item
    return None


def extract_job_level_metadata(
    seed_doc: dict,
    data_bucket: str,
) -> dict:
    """
    Extract job-level metadata from the seed document.

    Uses the current metadata extraction settings to re-extract metadata
    from the seed document's text content.

    Args:
        seed_doc: The seed document tracking record
        data_bucket: S3 bucket name

    Returns:
        Dictionary of extracted metadata
    """
    output_s3_uri = seed_doc.get("output_s3_uri")
    doc_id = seed_doc.get("document_id", "seed")

    if not output_s3_uri:
        logger.warning(f"Seed document {doc_id} has no output_s3_uri")
        return {}

    try:
        text = read_s3_text(output_s3_uri)

        if not text or not text.strip():
            logger.warning(f"Empty seed document text for {doc_id}")
            return {}

        # Truncate for job-level extraction (same as scrape_start does)
        content_for_extraction = text[:8000]

        extractor = get_metadata_extractor()
        # Don't update key library for job-level metadata
        metadata = extractor.extract_metadata(
            content_for_extraction,
            doc_id,
            update_library=False,
        )

        logger.info(f"Extracted job-level metadata from seed {doc_id}: {list(metadata.keys())}")
        return metadata

    except Exception as e:
        logger.warning(f"Failed to extract job-level metadata from seed {doc_id}: {e}")
        return {}


def get_or_extract_job_metadata(
    job_id: str,
    all_content: list[dict],
    data_bucket: str,
) -> dict:
    """
    Get job-level metadata for a scrape job, extracting from seed if needed.

    Uses a cache to avoid re-extracting for each document in the same job.

    Args:
        job_id: The scrape job ID
        all_content: List of all content items (to find seed document)
        data_bucket: S3 bucket name

    Returns:
        Dictionary of job-level metadata
    """
    global _job_metadata_cache

    # Check cache first
    if job_id in _job_metadata_cache:
        logger.debug(f"Using cached job metadata for {job_id}")
        return _job_metadata_cache[job_id]

    # Look up job info to get base_url
    job_info = get_scrape_job_info(job_id)
    if not job_info:
        logger.warning(f"Could not find job info for {job_id}")
        _job_metadata_cache[job_id] = {}
        return {}

    base_url = job_info.get("base_url")
    if not base_url:
        logger.warning(f"Job {job_id} has no base_url")
        _job_metadata_cache[job_id] = {}
        return {}

    # Find seed document
    seed_doc = find_seed_document(all_content, base_url)
    if not seed_doc:
        logger.warning(f"Could not find seed document for job {job_id} (base_url: {base_url})")
        _job_metadata_cache[job_id] = {}
        return {}

    # Extract metadata from seed document
    job_metadata = extract_job_level_metadata(seed_doc, data_bucket)

    # Cache for future documents in the same job
    _job_metadata_cache[job_id] = job_metadata
    logger.info(f"Cached job metadata for {job_id}: {len(job_metadata)} fields")

    return job_metadata


def list_all_content(tracking_table) -> list[dict]:
    """
    List all content from tracking table (documents, images, and scraped pages).

    Returns:
        List of all content items sorted by type for consistent ordering
    """
    items = []
    scan_kwargs: dict = {}

    while True:
        response = tracking_table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    # Sort by type for consistent processing order: documents, images, scraped, media
    def sort_key(item):
        item_type = item.get("type", "")
        if not item_type:
            return (0, item.get("document_id", ""))  # Documents (no type) first
        if item_type == "image":
            return (1, item.get("document_id", ""))
        if item_type == "scraped":
            return (2, item.get("document_id", ""))
        if item_type == "media":
            return (3, item.get("document_id", ""))
        return (4, item.get("document_id", ""))

    return sorted(items, key=sort_key)


def extract_document_metadata(output_s3_uri: str, document_id: str) -> dict[str, Any]:
    """
    Extract metadata from document text using LLM.

    Args:
        output_s3_uri: S3 URI to the document text file
        document_id: Document identifier

    Returns:
        Dictionary of extracted metadata, or empty dict on failure
    """
    try:
        text = read_s3_text(output_s3_uri)

        if not text or not text.strip():
            logger.warning(f"Empty document text for {document_id}")
            return {}

        extractor = get_metadata_extractor()
        metadata = extractor.extract_metadata(text, document_id)

        logger.info(f"Extracted metadata for {document_id}: {list(metadata.keys())}")
        return metadata

    except Exception as e:
        logger.warning(f"Failed to extract metadata for {document_id}: {e}")
        return {}


def ingest_document(kb_id: str, ds_id: str, content_uri: str, metadata_uri: str) -> None:
    """
    Ingest a single document into the Knowledge Base.

    Args:
        kb_id: Knowledge Base ID
        ds_id: Data Source ID
        content_uri: S3 URI of the content file
        metadata_uri: S3 URI of the metadata file
    """
    document = {
        "content": {
            "dataSourceType": "S3",
            "s3": {"s3Location": {"uri": content_uri}},
        },
        "metadata": {
            "type": "S3_LOCATION",
            "s3Location": {"uri": metadata_uri},
        },
    }

    response = ingest_documents_with_retry(
        kb_id=kb_id,
        ds_id=ds_id,
        documents=[document],
    )

    doc_details = response.get("documentDetails", [])
    if doc_details:
        status = doc_details[0].get("status", "UNKNOWN")
        logger.info(f"Ingested document: {content_uri}, status: {status}")
