"""Document resolver functions for AppSync Lambda handler.

Handles document CRUD, upload, reprocess, reindex operations.
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from botocore.exceptions import ClientError

from ragstack_common.config import get_knowledge_base_config
from ragstack_common.demo_mode import (
    demo_quota_check_and_increment,
    get_demo_upload_conditions,
    is_demo_mode_enabled,
)
from ragstack_common.ingestion import ingest_documents_with_retry
from ragstack_common.key_library import KeyLibrary
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.storage import is_valid_uuid, parse_s3_uri, read_s3_text, write_metadata_to_s3
from resolvers.shared import (
    DATA_BUCKET,
    INGEST_TO_KB_FUNCTION_ARN,
    MAX_FILENAME_LENGTH,
    METADATA_KEY_LIBRARY_TABLE,
    PROCESS_IMAGE_FUNCTION_ARN,
    SCRAPE_JOBS_TABLE,
    SCRAPE_URLS_TABLE,
    STATE_MACHINE_ARN,
    TRACKING_TABLE,
    bedrock_agent,
    check_reindex_lock,
    dynamodb,
    dynamodb_client,
    generate_presigned_download_url,
    get_config_manager,
    get_current_user_id,
    lambda_client,
    s3,
    sanitize_filename,
    sfn,
)

logger = logging.getLogger()


def get_document(args: dict[str, Any]) -> dict[str, Any] | None:
    """Get document by ID."""
    try:
        document_id = args["documentId"]
        logger.info(f"Fetching document: {document_id}")

        # Validate document ID format (UUID)
        if not is_valid_uuid(document_id):
            logger.warning(f"Invalid document ID format: {document_id}")
            raise ValueError("Invalid document ID format")

        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={"document_id": document_id})

        item = response.get("Item")
        if not item:
            logger.info(f"Document not found: {document_id}")
            return None

        logger.info(f"Document found: {document_id}, status: {str(item.get('status', ''))}")
        return format_document(item)

    except ClientError as e:
        logger.error(f"DynamoDB error in get_document: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_document: {e}")
        raise


def list_documents(args: dict[str, Any]) -> dict[str, Any]:
    """
    List all documents (excluding images and scraped pages).

    Returns all documents in a single response (no pagination).
    Images and scraped pages have their own list endpoints.
    """
    try:
        logger.info("Listing all documents")

        table = dynamodb.Table(TRACKING_TABLE)

        # Filter out images and scraped pages - they have their own list endpoints
        # Note: We scan all items without DynamoDB Limit because Limit applies
        # BEFORE FilterExpression, which would return inconsistent results.
        scan_kwargs: dict[str, Any] = {
            "FilterExpression": (
                "attribute_not_exists(#type) OR (#type <> :image_type AND #type <> :scraped_type)"
            ),
            "ExpressionAttributeNames": {"#type": "type"},
            "ExpressionAttributeValues": {
                ":image_type": "image",
                ":scraped_type": "scraped",
            },
        }

        # Scan all items
        all_items = []
        while True:
            response = table.scan(**scan_kwargs)
            all_items.extend(response.get("Items", []))

            if "LastEvaluatedKey" not in response:
                break
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        items = [format_document(item) for item in all_items]
        logger.info(f"Retrieved {len(items)} documents")

        return {"items": items}

    except ClientError as e:
        logger.error(f"DynamoDB error in list_documents: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in list_documents: {e}")
        raise


def delete_documents(args: dict[str, Any]) -> dict[str, Any]:
    """
    Delete documents from S3, Knowledge Base, and DynamoDB tracking table.

    Performs a complete delete:
    1. Lists all files in the content folder for KB deletion
    2. Deletes all files in the content folder from S3
    3. Removes all document vectors from Bedrock Knowledge Base
    4. Deletes tracking record from DynamoDB

    Handles multi-file documents like images (caption + visual) and media (transcript + segments).

    Args:
        args: Dictionary containing:
            - documentIds: List of document IDs to delete

    Returns:
        DeleteDocumentsResult with deletedCount, failedIds, and errors
    """
    document_ids = args.get("documentIds", [])
    logger.info(f"Deleting {len(document_ids)} documents (full delete: S3, KB, DynamoDB)")

    if not document_ids:
        return {"deletedCount": 0, "failedIds": [], "errors": []}

    # Check if full KB reindex is in progress - block deletes to prevent conflicts
    check_reindex_lock()

    # Limit batch size to prevent abuse
    max_batch_size = 100
    if len(document_ids) > max_batch_size:
        raise ValueError(f"Cannot delete more than {max_batch_size} documents at once")

    # Get KB config from DynamoDB config table (with env var fallback)
    config_manager = get_config_manager()
    try:
        kb_id, ds_id = get_knowledge_base_config(config_manager)
        logger.info(f"Using KB config: kb_id={kb_id}, ds_id={ds_id}")
    except ValueError as e:
        logger.warning(f"KB config not available, skipping KB deletion: {e}")
        kb_id, ds_id = None, None

    table = dynamodb.Table(TRACKING_TABLE)
    deleted_count = 0
    failed_ids = []
    errors = []

    # Collect KB document identifiers for batch delete
    kb_doc_identifiers: list[Any] = []

    for doc_id in document_ids:
        try:
            # Validate document ID format
            if not is_valid_uuid(doc_id):
                failed_ids.append(doc_id)
                errors.append(f"Invalid document ID format: {doc_id}")
                continue

            # Check if document exists and get its data
            response = table.get_item(Key={"document_id": doc_id})
            item = response.get("Item")

            if not item:
                failed_ids.append(doc_id)
                errors.append(f"Document not found: {doc_id}")
                continue

            # Get S3 URIs
            input_s3_uri = str(item.get("input_s3_uri", ""))
            output_s3_uri = str(item.get("output_s3_uri", ""))
            base_uri = input_s3_uri or output_s3_uri

            # List all KB URIs BEFORE deleting from S3
            # This handles multi-file docs (images, media segments, etc.)
            if kb_id and ds_id and base_uri:
                kb_uris = _list_kb_uris_for_document(base_uri)
                for uri in kb_uris:
                    kb_doc_identifiers.append({"dataSourceType": "S3", "s3": {"uri": uri}})
                if kb_uris:
                    logger.info(f"Queued {len(kb_uris)} KB deletions for doc {doc_id}")

            # Delete files from S3 - delete entire content folder
            if input_s3_uri and input_s3_uri.startswith("s3://"):
                _delete_s3_content_folder(input_s3_uri, doc_id)

            # Delete from DynamoDB tracking table
            table.delete_item(Key={"document_id": doc_id})
            logger.info(f"Deleted document from tracking table: {doc_id}")

            # For scraped items, also clean up scrape_jobs and scrape_urls tables
            # In the new format, document_id IS the job_id
            item_type = str(item.get("type", ""))
            if item_type == "scraped" and SCRAPE_JOBS_TABLE and SCRAPE_URLS_TABLE:
                _delete_scrape_job_records(doc_id)

            deleted_count += 1

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            failed_ids.append(doc_id)
            errors.append(f"Failed to delete {doc_id}: {error_code}")
            logger.error(f"DynamoDB error deleting {doc_id}: {e}")
        except Exception as e:
            failed_ids.append(doc_id)
            errors.append(f"Failed to delete {doc_id}: {str(e)}")
            logger.error(f"Unexpected error deleting {doc_id}: {e}")

    # Batch delete from Knowledge Base
    if kb_id and ds_id and kb_doc_identifiers:
        try:
            logger.info(f"Deleting {len(kb_doc_identifiers)} documents from KB")
            kb_response = bedrock_agent.delete_knowledge_base_documents(
                knowledgeBaseId=kb_id, dataSourceId=ds_id, documentIdentifiers=kb_doc_identifiers
            )
            # Log results
            doc_details = kb_response.get("documentDetails", [])
            for detail in doc_details:
                status_val = detail.get("status", "UNKNOWN")
                if str(status_val) == "DELETE_IN_PROGRESS":
                    logger.info(f"KB delete queued: {detail}")
                elif str(status_val) != "DELETED":
                    logger.warning(f"KB delete issue: {detail}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.error(f"Failed to delete from KB: {error_code} - {e}")
            # Don't fail the overall operation if KB delete fails
            errors.append(f"KB deletion failed: {error_code}")

    logger.info(f"Delete complete: {deleted_count} deleted, {len(failed_ids)} failed")

    return {
        "deletedCount": deleted_count,
        "failedIds": failed_ids if failed_ids else None,
        "errors": errors if errors else None,
    }


def _delete_s3_content_folder(input_s3_uri: str, doc_id: str) -> None:
    """
    Delete all files in the S3 content folder for a document.

    Content is stored as content/{doc_id}/* - this deletes the entire folder.

    Args:
        input_s3_uri: S3 URI of the input file (used to get bucket name)
        doc_id: Document ID to identify the folder
    """
    try:
        bucket, key = parse_s3_uri(input_s3_uri)

        # Determine folder prefix (content/{doc_id}/ or input/{doc_id}/)
        folder_prefix = None
        if key.startswith("content/"):
            # Extract content/{doc_id}/ prefix
            key_parts = key.split("/")
            if len(key_parts) >= 2:
                folder_prefix = f"content/{key_parts[1]}/"
        elif key.startswith("input/"):
            # For documents, delete from both input and output folders
            folder_prefix = f"input/{doc_id}/"

        if folder_prefix:
            # List and delete all objects with this prefix
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=folder_prefix):
                objects = page.get("Contents", [])
                if objects:
                    delete_keys = [{"Key": obj["Key"]} for obj in objects]
                    s3.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})  # type: ignore[typeddict-item]
                    logger.info(
                        f"Deleted {len(delete_keys)} files from s3://{bucket}/{folder_prefix}"
                    )

            # Also check for output folder if this was input
            if folder_prefix.startswith("input/"):
                output_prefix = f"output/{doc_id}/"
                for page in paginator.paginate(Bucket=bucket, Prefix=output_prefix):
                    objects = page.get("Contents", [])
                    if objects:
                        delete_keys = [{"Key": obj["Key"]} for obj in objects]
                        s3.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})  # type: ignore[typeddict-item]
                        logger.info(
                            f"Deleted {len(delete_keys)} files from s3://{bucket}/{output_prefix}"
                        )
        else:
            # Fallback: delete just the individual file
            s3.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Deleted file from S3: {key}")

    except ClientError as e:
        logger.warning(f"Failed to delete S3 content for {doc_id}: {e}")


def _delete_scrape_job_records(job_id: str) -> None:
    """
    Delete scrape job and URL records from DynamoDB.

    Cleans up both scrape_jobs table and all associated URL records
    in scrape_urls table.

    Args:
        job_id: The scrape job ID (which is also the document_id in tracking table)
    """
    try:
        # Delete from scrape_jobs table
        assert SCRAPE_JOBS_TABLE is not None
        assert SCRAPE_URLS_TABLE is not None
        jobs_table = dynamodb.Table(SCRAPE_JOBS_TABLE)
        jobs_table.delete_item(Key={"job_id": job_id})
        logger.info(f"Deleted scrape job record: {job_id}")

        # Delete all URL records for this job
        urls_table = dynamodb.Table(SCRAPE_URLS_TABLE)
        # Query all URLs for this job (job_id is the partition key)
        response = urls_table.query(
            KeyConditionExpression="job_id = :jid",
            ExpressionAttributeValues={":jid": job_id},
        )

        # Batch delete the URLs
        deleted_urls = 0
        with urls_table.batch_writer() as batch:
            for item in response.get("Items", []):
                batch.delete_item(Key={"job_id": job_id, "url": item["url"]})
                deleted_urls += 1

        # Handle pagination if there are many URLs
        while "LastEvaluatedKey" in response:
            response = urls_table.query(
                KeyConditionExpression="job_id = :jid",
                ExpressionAttributeValues={":jid": job_id},
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            with urls_table.batch_writer() as batch:
                for item in response.get("Items", []):
                    batch.delete_item(Key={"job_id": job_id, "url": item["url"]})
                    deleted_urls += 1

        logger.info(f"Deleted {deleted_urls} scrape URL records for job: {job_id}")

    except ClientError as e:
        logger.warning(f"Failed to delete scrape job records for {job_id}: {e}")


def reprocess_document(args: dict[str, Any]) -> dict[str, Any]:
    """
    Reprocess a document/image/media by triggering the appropriate pipeline.

    Documents -> Step Functions (ProcessingStateMachine)
    Images -> ProcessImageFunction Lambda
    Media -> ProcessMediaFunction Lambda
    Scrapes -> Not supported (return error with instructions)

    Args:
        args: Dictionary containing:
            - documentId: ID of the document to reprocess

    Returns:
        ReprocessResult with documentId, type, status, executionArn, error
    """
    document_id = args.get("documentId")
    logger.info(f"Reprocessing document: {document_id}")

    if not document_id:
        raise ValueError("documentId is required")

    if not is_valid_uuid(document_id):
        raise ValueError("Invalid document ID format")

    # Check if full KB reindex is in progress - block reprocess to prevent conflicts
    check_reindex_lock()

    # Get document from tracking table
    table = dynamodb.Table(TRACKING_TABLE)
    response = table.get_item(Key={"document_id": document_id})
    item = response.get("Item")

    if not item:
        raise ValueError("Document not found")

    doc_type = str(item.get("type", "document"))
    current_status = str(item.get("status", "")).lower()

    # Check if already processing
    if current_status in ("processing", "transcribing", "pending"):
        raise ValueError(f"Document is already being processed (status: {current_status})")

    # Handle scrapes - they need to be re-triggered from the scrape UI
    if doc_type in ("scrape", "scraped"):
        return {
            "documentId": document_id,
            "type": doc_type,
            "status": "ERROR",
            "executionArn": None,
            "error": "Scrape jobs cannot be reprocessed. Start a new scrape from the Scrape page.",
        }

    # Route based on document type
    if doc_type == "image":
        return _reprocess_image(document_id, item, table)
    if doc_type == "media":
        return _reprocess_media(document_id, item, table)
    # Default: document (including "document" and "scraped" types)
    return _reprocess_as_document(document_id, item, table)


def _list_kb_uris_for_document(input_s3_uri: str) -> list[str]:
    """
    List all S3 URIs in a document's content folder that should be deleted from KB.

    This handles documents with multiple ingested files (e.g., media segments,
    image caption + visual embedding). Excludes .metadata.json files which are
    just sidecars, not ingested content.

    Args:
        input_s3_uri: S3 URI of any file in the document's content folder.

    Returns:
        List of S3 URIs to delete from KB.
    """
    if not input_s3_uri or not input_s3_uri.startswith("s3://"):
        return []

    try:
        bucket, key = parse_s3_uri(input_s3_uri)

        # Determine folder prefix (content/{doc_id}/)
        folder_prefix = None
        if key.startswith("content/"):
            key_parts = key.split("/")
            if len(key_parts) >= 2:
                folder_prefix = f"content/{key_parts[1]}/"

        if not folder_prefix:
            # Not a content folder, return just the URI if it's not metadata
            if not input_s3_uri.endswith(".metadata.json"):
                return [input_s3_uri]
            return []

        # List all objects in the folder
        kb_uris = []
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=folder_prefix):
            for obj in page.get("Contents", []):
                obj_key = obj["Key"]
                # Skip metadata sidecar files - they're not ingested as documents
                if obj_key.endswith(".metadata.json"):
                    continue
                kb_uris.append(f"s3://{bucket}/{obj_key}")

        logger.info(f"Found {len(kb_uris)} KB URIs in {folder_prefix}")
        return kb_uris

    except ClientError as e:
        logger.warning(f"Failed to list KB URIs for {input_s3_uri}: {e}")
        return []


def _delete_from_kb_for_reprocess(item: dict) -> None:
    """
    Delete existing vectors from KB before reprocessing.

    This ensures a clean slate - no orphaned vectors from previous processing attempts.
    Lists all files in the content folder and deletes each from KB (excluding .metadata.json).
    Handles multi-file documents like images (caption + visual) and media (transcript + segments).
    """
    # Get KB config
    config_manager = get_config_manager()
    try:
        kb_id, ds_id = get_knowledge_base_config(config_manager)
    except ValueError:
        logger.warning("KB config not available, skipping KB deletion before reprocess")
        return

    # Get any S3 URI to determine the content folder
    input_s3_uri = str(item.get("input_s3_uri", ""))
    output_s3_uri = str(item.get("output_s3_uri", ""))
    base_uri = input_s3_uri or output_s3_uri

    if not base_uri:
        logger.info("No S3 URI found, skipping KB deletion (document may not have been indexed)")
        return

    # List all KB URIs in the content folder
    kb_uris = _list_kb_uris_for_document(base_uri)

    if not kb_uris:
        logger.info("No KB URIs found in content folder, skipping KB deletion")
        return

    try:
        doc_identifiers: list[Any] = [
            {"dataSourceType": "S3", "s3": {"uri": uri}} for uri in kb_uris
        ]
        logger.info(f"Deleting {len(doc_identifiers)} documents from KB before reprocess")
        bedrock_agent.delete_knowledge_base_documents(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            documentIdentifiers=doc_identifiers,
        )
        logger.info(f"Successfully queued KB deletion for {len(kb_uris)} documents")
    except ClientError as e:
        # Log but don't fail - the document might not exist in KB yet
        error_code = e.response.get("Error", {}).get("Code", "")
        logger.warning(f"KB deletion before reprocess failed ({error_code}): {e}")


def _reprocess_image(document_id: str, item: dict[str, Any], table: Any) -> dict[str, Any]:
    """Reprocess an image by invoking the ProcessImageFunction."""
    logger.info(f"Reprocessing image: {document_id}")

    if not PROCESS_IMAGE_FUNCTION_ARN:
        raise ValueError("Image processing not configured")

    input_s3_uri = item.get("input_s3_uri", "")
    if not input_s3_uri:
        raise ValueError("Image has no input_s3_uri in tracking record")

    # Delete old vectors from KB first
    _delete_from_kb_for_reprocess(item)

    # Update status to processing
    now = datetime.now(UTC).isoformat()
    table.update_item(
        Key={"document_id": document_id},
        UpdateExpression="SET #status = :status, updated_at = :updated_at",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "PROCESSING", ":updated_at": now},
    )

    # Build the S3 key from input_s3_uri (e.g., s3://bucket/content/uuid/file.jpg)
    _, s3_key = parse_s3_uri(input_s3_uri)

    # Invoke ProcessImageFunction
    process_event = {
        "image_id": s3_key,
        "input_s3_uri": input_s3_uri,
        "trigger_type": "reprocess",
    }

    lambda_client.invoke(
        FunctionName=PROCESS_IMAGE_FUNCTION_ARN,
        InvocationType="Event",  # Async invocation
        Payload=json.dumps(process_event),
    )

    logger.info(f"Invoked ProcessImageFunction for image: {document_id}")

    return {
        "documentId": document_id,
        "type": "image",
        "status": "PROCESSING",
        "executionArn": None,
        "error": None,
    }


def _reprocess_media(document_id: str, item: dict[str, Any], table: Any) -> dict[str, Any]:
    """Reprocess media by triggering the document processing pipeline."""
    logger.info(f"Reprocessing media: {document_id}")

    # Media goes through the same Step Functions as documents
    # The pipeline handles transcription and KB ingestion
    if not STATE_MACHINE_ARN:
        raise ValueError("Processing not configured")

    input_s3_uri = item.get("input_s3_uri", "")
    if not input_s3_uri:
        raise ValueError("Media has no input_s3_uri in tracking record")

    # Delete old vectors from KB first
    _delete_from_kb_for_reprocess(item)

    # Update status to processing
    now = datetime.now(UTC).isoformat()
    table.update_item(
        Key={"document_id": document_id},
        UpdateExpression="SET #status = :status, updated_at = :updated_at",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "PROCESSING", ":updated_at": now},
    )

    # State machine expects document_id as S3 key (input/{doc_id}/{filename})
    # because EventBridge passes the full key and ExtractDocumentId splits on '/'
    bucket, s3_key = parse_s3_uri(input_s3_uri)
    execution_input = {
        "document_id": s3_key,
        "input_s3_uri": input_s3_uri,
        "output_s3_prefix": f"s3://{bucket}/content/{document_id}/",
        "filename": item.get("filename"),
    }

    execution_response = sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=f"{document_id}-reprocess-{int(datetime.now().timestamp())}",
        input=json.dumps(execution_input),
    )

    execution_arn = execution_response.get("executionArn")
    logger.info(f"Started Step Functions execution for media: {execution_arn}")

    return {
        "documentId": document_id,
        "type": "media",
        "status": "PROCESSING",
        "executionArn": execution_arn,
        "error": None,
    }


def _reprocess_as_document(document_id: str, item: dict[str, Any], table: Any) -> dict[str, Any]:
    """Reprocess as a document via Step Functions."""
    logger.info(f"Reprocessing document: {document_id}")

    if not STATE_MACHINE_ARN:
        raise ValueError("Processing not configured")

    input_s3_uri = item.get("input_s3_uri", "")
    if not input_s3_uri:
        raise ValueError("Document has no input_s3_uri in tracking record")

    # Delete old vectors from KB first
    _delete_from_kb_for_reprocess(item)

    # Update status to processing
    now = datetime.now(UTC).isoformat()
    table.update_item(
        Key={"document_id": document_id},
        UpdateExpression="SET #status = :status, updated_at = :updated_at",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "processing", ":updated_at": now},
    )

    # State machine expects document_id as S3 key (input/{doc_id}/{filename})
    # because EventBridge passes the full key and ExtractDocumentId splits on '/'
    bucket, s3_key = parse_s3_uri(input_s3_uri)
    execution_input = {
        "document_id": s3_key,
        "input_s3_uri": input_s3_uri,
        "output_s3_prefix": f"s3://{bucket}/content/{document_id}/",
        "filename": item.get("filename"),
    }

    execution_response = sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=f"{document_id}-reprocess-{int(datetime.now().timestamp())}",
        input=json.dumps(execution_input),
    )

    execution_arn = execution_response.get("executionArn")
    logger.info(f"Started Step Functions execution for document: {execution_arn}")

    return {
        "documentId": document_id,
        "type": item.get("type", "document"),
        "status": "PROCESSING",
        "executionArn": execution_arn,
        "error": None,
    }


# File extensions for visual/media content that shouldn't be reindexed
VISUAL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
MEDIA_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".flac"}
SKIP_REINDEX_EXTENSIONS = VISUAL_EXTENSIONS | MEDIA_EXTENSIONS


def _list_text_uris_for_reindex(bucket: str, document_id: str) -> list[str]:
    """
    List all text-based S3 URIs in a document's content folder for reindexing.

    Searches content/{document_id}/ directly by document_id rather than parsing
    URIs, which avoids issues with input/ vs content/ prefixes and legacy paths.

    Excludes:
    - .metadata.json files (sidecars, not content)
    - Visual files (.jpg, .png, etc.) - visual embeddings don't need metadata re-extraction
    - Media files (.mp4, .mp3, etc.) - same reason

    Args:
        bucket: S3 bucket name.
        document_id: Document UUID.

    Returns:
        List of text-based S3 URIs to reindex.
    """
    if not bucket or not document_id:
        return []

    try:
        # Try standard path first, then legacy path (content/input/{doc_id}/)
        prefixes = [f"content/{document_id}/"]

        # Legacy format: EventBridge used to produce content/input/{doc_id}/
        # before the output_s3_prefix fix in process_document
        prefixes.append(f"content/input/{document_id}/")

        text_uris = []
        paginator = s3.get_paginator("list_objects_v2")
        for folder_prefix in prefixes:
            for page in paginator.paginate(Bucket=bucket, Prefix=folder_prefix):
                for obj in page.get("Contents", []):
                    obj_key = obj["Key"]
                    lower_key = obj_key.lower()

                    # Skip metadata sidecar files
                    if lower_key.endswith(".metadata.json"):
                        continue

                    # Skip visual/media files
                    skip = False
                    for ext in SKIP_REINDEX_EXTENSIONS:
                        if lower_key.endswith(ext):
                            skip = True
                            break
                    if skip:
                        continue

                    text_uris.append(f"s3://{bucket}/{obj_key}")

            if text_uris:
                logger.info(f"Found {len(text_uris)} text URIs for reindex in {folder_prefix}")
                return text_uris

        logger.info(f"No text URIs found for reindex of {document_id}")
        return text_uris

    except ClientError as e:
        logger.warning(f"Failed to list text URIs for {document_id}: {e}")
        return []


def _reindex_scraped_content(document_id: str, text_uris: list[str], kb_id: str, ds_id: str) -> int:
    """
    Reindex scraped content by re-extracting metadata from the base page.

    For scraped jobs on reindex:
    1. Find the base page (seed URL) content
    2. Re-extract metadata using current LLM settings
    3. Update job_metadata in scrape_jobs table
    4. Apply to all pages with their source_url

    Args:
        document_id: The document/job ID (same thing for scraped content)
        text_uris: List of S3 URIs for page content files
        kb_id: Knowledge Base ID
        ds_id: Data Source ID

    Returns:
        Number of documents successfully queued for ingestion
    """
    if not SCRAPE_JOBS_TABLE:
        logger.warning("SCRAPE_JOBS_TABLE not configured, falling back to default reindex")
        return 0

    # Get job info from scrape_jobs table (document_id IS job_id)
    jobs_table = dynamodb.Table(SCRAPE_JOBS_TABLE)
    job_response = jobs_table.get_item(Key={"job_id": document_id})
    job_item = job_response.get("Item", {})
    base_url = str(job_item.get("base_url", ""))

    if not base_url:
        logger.warning(f"No base_url found for scraped job {document_id}")

    # Build map of source_url -> content_uri by reading metadata sidecars
    source_url_map = {}  # source_url -> content_uri
    for uri in text_uris:
        try:
            metadata_uri = f"{uri}.metadata.json"
            bucket, key = parse_s3_uri(metadata_uri)

            response = s3.get_object(Bucket=bucket, Key=key)
            existing = json.loads(response["Body"].read().decode("utf-8"))
            source_url = existing.get("metadataAttributes", {}).get("source_url", "")
            # Handle case where source_url might be a list
            if isinstance(source_url, list):
                source_url = source_url[0] if source_url else ""
            if source_url:
                source_url_map[source_url] = uri
        except ClientError:
            pass  # No sidecar, skip

    # Find the base page content URI
    base_page_uri = source_url_map.get(base_url)
    if not base_page_uri and text_uris:
        # Fallback: use first page if base_url not found
        base_page_uri = text_uris[0]
        logger.warning(f"Base URL {base_url} not found in pages, using first page")

    # Re-extract metadata from base page using current settings
    job_metadata = {}
    if base_page_uri:
        try:
            base_content = read_s3_text(base_page_uri)
            if base_content and base_content.strip():
                # Create extractor with current config settings
                config = get_config_manager()
                model_id = config.get_parameter("metadata_extraction_model")
                max_keys = config.get_parameter("metadata_max_keys")
                extraction_mode = config.get_parameter("metadata_extraction_mode", default="auto")
                manual_keys = config.get_parameter("metadata_manual_keys")

                key_library = None
                if METADATA_KEY_LIBRARY_TABLE:
                    key_library = KeyLibrary(table_name=METADATA_KEY_LIBRARY_TABLE)

                extractor = MetadataExtractor(
                    key_library=key_library,
                    model_id=model_id,
                    max_keys=max_keys if max_keys else 8,
                    extraction_mode=extraction_mode,
                    manual_keys=manual_keys,
                )

                job_metadata = extractor.extract_metadata(base_content, document_id)
                logger.info(f"Re-extracted metadata from base page: {list(job_metadata.keys())}")

                # Update job_metadata in scrape_jobs table
                jobs_table.update_item(
                    Key={"job_id": document_id},
                    UpdateExpression="SET job_metadata = :metadata",
                    ExpressionAttributeValues={":metadata": job_metadata},
                )
                logger.info("Updated job_metadata in scrape_jobs table")

                # Also update extracted_metadata in tracking table for frontend display
                tracking_table = dynamodb.Table(TRACKING_TABLE)
                tracking_table.update_item(
                    Key={"document_id": document_id},
                    UpdateExpression="SET extracted_metadata = :metadata",
                    ExpressionAttributeValues={":metadata": job_metadata},
                )
                logger.info("Updated extracted_metadata in tracking table")
        except Exception as e:
            logger.error(f"Failed to extract metadata from base page: {e}")

    logger.info(
        f"Reindexing {len(text_uris)} scraped pages with metadata: {list(job_metadata.keys())}"
    )

    ingested_count = 0
    documents = []

    for uri in text_uris:
        try:
            # Get source_url for this page from the map we built earlier
            source_url = ""
            for url, content_uri in source_url_map.items():
                if content_uri == uri:
                    source_url = url
                    break

            # Combine job_metadata with page-specific fields
            page_metadata = dict(job_metadata)
            page_metadata["source_url"] = source_url
            page_metadata["content_type"] = "web_page"

            # Write updated metadata sidecar
            metadata_uri = f"{uri}.metadata.json"
            write_metadata_to_s3(uri, page_metadata)
            logger.info(f"Wrote metadata for {uri}: {list(page_metadata.keys())}")

            # Build document for ingestion
            documents.append(
                {
                    "content": {
                        "dataSourceType": "S3",
                        "s3": {"s3Location": {"uri": uri}},
                    },
                    "metadata": {
                        "type": "S3_LOCATION",
                        "s3Location": {"uri": metadata_uri},
                    },
                }
            )
            ingested_count += 1

        except Exception as e:
            logger.error(f"Failed to prepare scraped page {uri}: {e}")

    # Ingest all documents in one batch
    if documents:
        try:
            ingest_response = ingest_documents_with_retry(
                kb_id=kb_id,
                ds_id=ds_id,
                documents=documents,
            )
            logger.info(f"Ingested {len(documents)} scraped pages: {ingest_response}")
        except Exception as e:
            logger.error(f"Failed to ingest scraped pages: {e}")
            raise  # Propagate to caller so job is marked FAILED, not INDEXED

    return ingested_count


def reindex_document(args: dict[str, Any]) -> dict[str, Any]:
    """
    Reindex a document - re-extract metadata and reingest to KB without re-running OCR.

    This is faster than reprocess because it skips OCR extraction and uses the
    existing text files. Useful when metadata extraction settings have changed
    or to refresh a document's metadata.

    For multi-file documents (media with segments), reindexes all text files.
    Visual embeddings (.jpg, .mp4, etc.) are left untouched.

    Args:
        args: Dictionary containing:
            - documentId: ID of the document to reindex

    Returns:
        ReprocessResult with documentId, type, status, executionArn, error
    """
    document_id = args.get("documentId")
    logger.info(f"Reindexing document: {document_id}")

    if not document_id:
        raise ValueError("documentId is required")

    if not is_valid_uuid(document_id):
        raise ValueError("Invalid document ID format")

    # Check if full KB reindex is in progress - block individual reindex to prevent conflicts
    check_reindex_lock()

    # Get document from tracking table first to check type
    # (scraped docs don't need INGEST_TO_KB_FUNCTION_ARN)
    table = dynamodb.Table(TRACKING_TABLE)
    response = table.get_item(Key={"document_id": document_id})
    item = response.get("Item")

    if not item:
        raise ValueError("Document not found")

    doc_type = str(item.get("type", "document"))
    current_status = str(item.get("status", "")).lower()

    # Non-scraped docs need INGEST_TO_KB_FUNCTION_ARN for Lambda invocation
    if doc_type != "scraped" and not INGEST_TO_KB_FUNCTION_ARN:
        raise ValueError("Reindex not configured - INGEST_TO_KB_FUNCTION_ARN not set")

    # Check if already processing
    if current_status in ("processing", "transcribing", "pending"):
        raise ValueError(f"Document is already being processed (status: {current_status})")

    # List all text-based files to reindex (excludes visual/media files)
    # Use document_id to search content/{doc_id}/ directly
    text_uris = _list_text_uris_for_reindex(DATA_BUCKET, document_id)

    if not text_uris:
        raise ValueError("No text files found to reindex")

    logger.info(f"Found {len(text_uris)} text files to reindex for {document_id}")

    # Delete old text vectors from KB (visual embeddings stay untouched)
    config_manager = get_config_manager()
    try:
        kb_id, ds_id = get_knowledge_base_config(config_manager)
        doc_identifiers: list[Any] = [
            {"dataSourceType": "S3", "s3": {"uri": uri}} for uri in text_uris
        ]
        logger.info(f"Deleting {len(doc_identifiers)} text documents from KB before reindex")
        bedrock_agent.delete_knowledge_base_documents(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            documentIdentifiers=doc_identifiers,
        )
    except ValueError:
        logger.warning("KB config not available, skipping KB deletion before reindex")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        logger.warning(f"KB deletion before reindex failed ({error_code}): {e}")

    # Update status to processing
    now = datetime.now(UTC).isoformat()
    table.update_item(
        Key={"document_id": document_id},
        UpdateExpression="SET #status = :status, updated_at = :updated_at",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "PROCESSING", ":updated_at": now},
    )

    # Handle scraped content differently - use job_metadata, no LLM extraction
    if doc_type == "scraped":
        try:
            kb_id, ds_id = get_knowledge_base_config(config_manager)
            ingested = _reindex_scraped_content(document_id, text_uris, kb_id, ds_id)
            logger.info(f"Reindexed {ingested} scraped pages for {document_id}")

            # Update status to indexed
            table.update_item(
                Key={"document_id": document_id},
                UpdateExpression="SET #status = :status, updated_at = :updated_at",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": "INDEXED",
                    ":updated_at": datetime.now(UTC).isoformat(),
                },
            )
        except ValueError as e:
            logger.error(f"KB config not available for scraped reindex: {e}")
            # Revert status since we can't complete reindex
            table.update_item(
                Key={"document_id": document_id},
                UpdateExpression=(
                    "SET #status = :status, updated_at = :updated_at, error_message = :error"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": "FAILED",
                    ":updated_at": datetime.now(UTC).isoformat(),
                    ":error": "Reindex requires Knowledge Base configuration",
                },
            )
            raise ValueError("Reindex requires Knowledge Base configuration") from e
        except Exception as e:
            # Handle ingestion failures from _reindex_scraped_content
            logger.error(f"Scraped content reindex failed: {e}")
            table.update_item(
                Key={"document_id": document_id},
                UpdateExpression=(
                    "SET #status = :status, updated_at = :updated_at, error_message = :error"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": "FAILED",
                    ":updated_at": datetime.now(UTC).isoformat(),
                    ":error": f"Reindex failed: {str(e)[:200]}",
                },
            )
            raise
    else:
        # Regular documents: invoke IngestToKB Lambda for each text file
        for _i, uri in enumerate(text_uris):
            ingest_event = {
                "document_id": document_id,
                "output_s3_uri": uri,
                "force_extraction": True,  # Re-extract metadata on reindex
            }

            lambda_client.invoke(
                FunctionName=INGEST_TO_KB_FUNCTION_ARN,
                InvocationType="Event",  # Async invocation
                Payload=json.dumps(ingest_event),
            )
            logger.info(f"Invoked IngestToKB for {uri}")

        logger.info(f"Queued {len(text_uris)} files for reindex: {document_id}")

    # Scraped content is handled synchronously, regular docs are async
    final_status = "INDEXED" if doc_type == "scraped" else "PROCESSING"

    return {
        "documentId": document_id,
        "type": doc_type,
        "status": final_status,
        "executionArn": None,
        "error": None,
    }


def create_upload_url(args: dict[str, Any]) -> dict[str, Any]:
    """
    Create presigned URL for S3 upload.

    Returns upload URL and document ID for tracking.

    Media files (video/audio) upload directly to content/ folder.
    Documents upload to input/ folder for Step Functions processing.
    """
    # Media extensions that upload directly to content/ (skip Step Functions)
    MEDIA_EXTENSIONS = {".mp4", ".webm", ".mp3", ".wav", ".m4a", ".ogg"}

    try:
        filename = args["filename"]
        logger.info(f"Creating upload URL for file: {filename}")

        # Validate filename exists
        if not filename:
            raise ValueError("Filename is required")

        # Check for path traversal and JSON-unsafe characters (security - must reject)
        # Double-quotes break EventBridge InputTransformer JSON templates
        if "/" in filename or "\\" in filename or ".." in filename or '"' in filename:
            logger.warning(f"Filename contains invalid characters: {filename}")
            raise ValueError("Filename contains invalid characters")

        # Sanitize filename - replace invalid characters instead of rejecting
        sanitized_filename = sanitize_filename(filename)
        if sanitized_filename != filename:
            logger.info(f"Sanitized filename: '{filename}' -> '{sanitized_filename}'")
            filename = sanitized_filename

        # Validate length after sanitization
        if len(filename) > MAX_FILENAME_LENGTH:
            logger.warning(f"Invalid filename length: {len(filename)}")
            raise ValueError(f"Filename must be at most {MAX_FILENAME_LENGTH} characters")

        # Check demo mode upload quota (after validation to not consume quota for invalid requests)
        cm = get_config_manager()
        if is_demo_mode_enabled(cm):
            user_id = get_current_user_id()
            config_table = os.environ.get("CONFIGURATION_TABLE_NAME")
            if config_table:
                allowed, message = demo_quota_check_and_increment(
                    user_id or "anonymous",
                    "upload",
                    config_table,
                    dynamodb_client,
                    cm,
                )
                if not allowed:
                    raise ValueError(message)

        document_id = str(uuid4())
        logger.info(f"Generated document ID: {document_id}")

        # Check if file is media (video/audio) - these go directly to content/
        ext = Path(filename).suffix.lower()
        is_media = ext in MEDIA_EXTENSIONS

        # Media files upload directly to content/ (processed by EventBridge → ProcessMedia)
        # Documents upload to input/ (processed by Step Functions)
        if is_media:
            s3_key = f"content/{document_id}/{filename}"
            doc_type = "media"
        else:
            s3_key = f"input/{document_id}/{filename}"
            doc_type = "document"

        # Create presigned POST with demo mode file size limit if applicable
        logger.info(f"Generating presigned POST for S3 key: {s3_key} (type={doc_type})")
        demo_conditions = get_demo_upload_conditions(get_config_manager())
        presigned = s3.generate_presigned_post(
            Bucket=DATA_BUCKET,
            Key=s3_key,
            Conditions=demo_conditions,
            ExpiresIn=3600,  # 1 hour
        )

        # Create tracking record
        logger.info(f"Creating tracking record for document: {document_id}")
        now = datetime.now(UTC).isoformat()
        table = dynamodb.Table(TRACKING_TABLE)
        table.put_item(
            Item={
                "document_id": document_id,
                "filename": filename,
                "input_s3_uri": f"s3://{DATA_BUCKET}/{s3_key}",
                "status": "uploaded",
                "type": doc_type,
                "created_at": now,
                "updated_at": now,
            }
        )

        logger.info(f"Upload URL created successfully for document: {document_id}")
        return {
            "uploadUrl": presigned["url"],
            "documentId": document_id,
            "fields": json.dumps(presigned["fields"]),
        }

    except ClientError as e:
        logger.error(f"AWS service error in create_upload_url: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_upload_url: {e}")
        raise


def process_document(args: dict[str, Any]) -> dict[str, Any]:
    """
    Manually trigger document processing via Step Functions.

    Returns updated document record.
    """
    try:
        document_id = args["documentId"]
        logger.info(f"Manually triggering processing for document: {document_id}")

        # Validate document ID format
        if not is_valid_uuid(document_id):
            logger.warning(f"Invalid document ID format: {document_id}")
            raise ValueError("Invalid document ID format")

        # Check if state machine ARN is configured
        if not STATE_MACHINE_ARN:
            logger.error("STATE_MACHINE_ARN environment variable not set")
            raise ValueError("Processing not configured")

        # Get document from DynamoDB
        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={"document_id": document_id})

        item = response.get("Item")
        if not item:
            logger.warning(f"Document not found: {document_id}")
            raise ValueError("Document not found")

        # Check if document is in a state that can be reprocessed
        current_status = str(item.get("status", "")).lower()
        if current_status == "processing":
            logger.warning(f"Document already processing: {document_id}")
            raise ValueError("Document is already being processed")

        # Update status to processing
        logger.info(f"Updating document status to processing: {document_id}")
        table.update_item(
            Key={"document_id": document_id},
            UpdateExpression="SET #status = :status, updated_at = :updated_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "processing",
                ":updated_at": datetime.now(UTC).isoformat(),
            },
        )

        # Start Step Functions execution
        execution_input = {
            "document_id": document_id,
            "input_s3_uri": item.get("input_s3_uri"),
            "filename": item.get("filename"),
        }

        logger.info(f"Starting Step Functions execution for document: {document_id}")
        execution_response = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"{document_id}-{int(datetime.now().timestamp())}",
            input=json.dumps(execution_input),
        )

        logger.info(f"Step Functions execution started: {execution_response['executionArn']}")

        # Get updated document
        response = table.get_item(Key={"document_id": document_id})
        updated_item = response.get("Item")
        if not updated_item:
            raise ValueError(f"Document not found after processing: {document_id}")

        return format_document(updated_item)

    except ClientError as e:
        logger.error(f"AWS service error in process_document: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in process_document: {e}")
        raise


def format_document(item: dict[str, Any]) -> dict[str, Any]:
    """Format DynamoDB item as GraphQL Document type."""
    output_s3_uri = item.get("output_s3_uri")
    status = item.get("status", "uploaded").upper()

    # Generate preview URL for completed documents
    preview_url = None
    if status in ("OCR_COMPLETE", "EMBEDDING_COMPLETE", "INDEXED") and output_s3_uri:
        preview_url = generate_presigned_download_url(output_s3_uri)

    return {
        "documentId": item["document_id"],
        "filename": item.get("filename", ""),
        "inputS3Uri": item.get("input_s3_uri", ""),
        "outputS3Uri": output_s3_uri,
        "status": status,
        "fileType": item.get("file_type"),
        "isTextNative": item.get("is_text_native", False),
        "totalPages": item.get("total_pages", 0),
        "errorMessage": item.get("error_message"),
        "createdAt": item.get("created_at"),
        "updatedAt": item.get("updated_at"),
        "metadata": item.get("extracted_metadata"),
        "previewUrl": preview_url,
        # Media fields
        "type": item.get("type"),  # document, media, image, scrape
        "mediaType": item.get("media_type"),  # video, audio
        "durationSeconds": item.get("duration_seconds"),
    }
