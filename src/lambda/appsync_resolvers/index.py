"""
AppSync Lambda resolvers for document, scrape, image, and metadata operations.

Handles:
- getDocument
- listDocuments
- createUploadUrl
- processDocument
- getScrapeJob
- listScrapeJobs
- checkScrapeUrl
- startScrape
- cancelScrape
- createImageUploadUrl
- generateCaption
- submitImage
- getImage
- listImages
- deleteImage
- deleteDocuments
- analyzeMetadata
- getMetadataStats
- getFilterExamples
- getKeyLibrary
- checkKeySimilarity
"""

import json
import logging
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from ragstack_common.auth import check_public_access
from ragstack_common.config import ConfigurationManager, get_knowledge_base_config
from ragstack_common.demo_mode import (
    DemoModeError,
    check_demo_mode_feature_allowed,
    demo_quota_check_and_increment,
    get_demo_upload_conditions,
    is_demo_mode_enabled,
)
from ragstack_common.filter_examples import (
    generate_filter_examples,
    store_filter_examples,
    update_config_with_examples,
)
from ragstack_common.image import ImageStatus, is_supported_image, validate_image_type
from ragstack_common.ingestion import ingest_documents_with_retry
from ragstack_common.key_library import KeyLibrary
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.scraper import ScrapeStatus
from ragstack_common.storage import is_valid_uuid, read_s3_text, write_metadata_to_s3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sfn = boto3.client("stepfunctions")
lambda_client = boto3.client("lambda")
bedrock_agent = boto3.client("bedrock-agent")

# Module-level configuration manager (lazy init for resolvers that need access control)
_config_manager = None

# Module-level event storage for passing identity to resolvers
_current_event = None

# DynamoDB client for quota operations
dynamodb_client = boto3.client("dynamodb")


def get_config_manager():
    """Lazy initialization of ConfigurationManager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


def get_current_user_id() -> str | None:
    """Get user ID from current event's identity."""
    if not _current_event:
        return None
    identity = _current_event.get("identity") or {}
    return identity.get("sub") or identity.get("username")


def convert_decimals(obj):
    """Convert DynamoDB Decimal types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


# Reindex lock key - must match reindex_kb/index.py
REINDEX_LOCK_KEY = "reindex_lock"


def check_reindex_lock() -> None:
    """
    Check if a full KB reindex is in progress and raise error if so.

    This prevents individual document operations (reindex, reprocess, delete)
    from interfering with a full KB reindex operation.

    Raises:
        ValueError: If reindex is in progress.
    """
    config_table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
    if not config_table_name:
        return  # Can't check lock without config table

    try:
        table = dynamodb.Table(config_table_name)
        response = table.get_item(Key={"config_key": REINDEX_LOCK_KEY})
        lock = response.get("Item")

        if lock and lock.get("is_locked"):
            started_at = lock.get("started_at", "unknown")
            raise ValueError(
                f"Operation blocked: Knowledge Base reindex is in progress "
                f"(started: {started_at}). Please wait for the reindex to complete."
            )
    except ClientError as e:
        # Log but don't block operations if we can't check the lock
        logger.warning(f"Error checking reindex lock: {e}")
    except ValueError:
        # Re-raise ValueError (our lock error)
        raise


TRACKING_TABLE = os.environ["TRACKING_TABLE"]
DATA_BUCKET = os.environ["DATA_BUCKET"]
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID")
DATA_SOURCE_ID = os.environ.get("DATA_SOURCE_ID")

# Scrape-related environment variables (optional, only available when scraping is enabled)
SCRAPE_JOBS_TABLE = os.environ.get("SCRAPE_JOBS_TABLE")
SCRAPE_URLS_TABLE = os.environ.get("SCRAPE_URLS_TABLE")
SCRAPE_START_FUNCTION_ARN = os.environ.get("SCRAPE_START_FUNCTION_ARN")

# Metadata analyzer function (optional)
METADATA_ANALYZER_FUNCTION_ARN = os.environ.get("METADATA_ANALYZER_FUNCTION_ARN")

# Process image function for submitImage
PROCESS_IMAGE_FUNCTION_ARN = os.environ.get("PROCESS_IMAGE_FUNCTION_ARN")

# Metadata key library table (optional)
METADATA_KEY_LIBRARY_TABLE = os.environ.get("METADATA_KEY_LIBRARY_TABLE")

# Configuration table (optional, for caption generation and filter examples)
CONFIGURATION_TABLE_NAME = os.environ.get("CONFIGURATION_TABLE_NAME")

# Reindex state machine (optional, for KB reindex operations)
REINDEX_STATE_MACHINE_ARN = os.environ.get("REINDEX_STATE_MACHINE_ARN")

# Ingest to KB function for single document reindexing
INGEST_TO_KB_FUNCTION_ARN = os.environ.get("INGEST_TO_KB_FUNCTION_ARN")

# Initialize Bedrock runtime client for caption generation (use Lambda's region)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION"))

# Validation constants
MAX_FILENAME_LENGTH = 255
MAX_DOCUMENTS_LIMIT = 100
# Strip ASCII control characters (0x00-0x1F, 0x7F) — everything else is valid in S3 keys
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by stripping control characters.

    S3 keys accept any UTF-8 character, so only ASCII control characters
    are removed. Path traversal is handled separately in the upload resolvers.
    Returns "unnamed" if the result would be empty.
    """
    if not filename:
        return "unnamed"

    sanitized = CONTROL_CHARS_PATTERN.sub("", filename).strip()

    if not sanitized:
        return "unnamed"

    return sanitized


def lambda_handler(event, context):
    """
    Route to appropriate resolver based on field name.
    """
    global _current_event
    _current_event = event  # Store for use by resolvers that need identity

    logger.info(f"AppSync resolver invoked for field: {event['info']['fieldName']}")
    logger.info(f"Arguments: {json.dumps(event.get('arguments', {}))}")

    field_name = event["info"]["fieldName"]

    # Demo mode feature restrictions - block certain mutations entirely
    demo_restricted_features = {
        "startReindex": "reindex_all",
        "reprocessDocument": "reprocess",
        "deleteDocuments": "delete_documents",
    }

    if field_name in demo_restricted_features:
        try:
            check_demo_mode_feature_allowed(
                demo_restricted_features[field_name], get_config_manager()
            )
        except DemoModeError as e:
            logger.info(f"Demo mode blocked {field_name}: {e.message}")
            raise ValueError(e.message) from e

    # Check public access for upload-related resolvers
    # Map field names to their required access types
    access_requirements = {
        "createUploadUrl": "upload",
        "createImageUploadUrl": "image_upload",
        "generateCaption": "image_upload",
        "submitImage": "image_upload",
        "createZipUploadUrl": "image_upload",
        "startScrape": "scrape",
        "checkScrapeUrl": "scrape",
        "cancelScrape": "scrape",
    }

    if field_name in access_requirements:
        access_type = access_requirements[field_name]
        allowed, error_msg = check_public_access(event, access_type, get_config_manager())
        if not allowed:
            raise ValueError(error_msg)

    resolvers = {
        "getDocument": get_document,
        "listDocuments": list_documents,
        "createUploadUrl": create_upload_url,
        "processDocument": process_document,
        # Scrape resolvers
        "getScrapeJob": get_scrape_job,
        "listScrapeJobs": list_scrape_jobs,
        "checkScrapeUrl": check_scrape_url,
        "startScrape": start_scrape,
        "cancelScrape": cancel_scrape,
        # Image resolvers
        "createImageUploadUrl": create_image_upload_url,
        "generateCaption": generate_caption,
        "submitImage": submit_image,
        "getImage": get_image,
        "listImages": list_images,
        "deleteImage": delete_image,
        "createZipUploadUrl": create_zip_upload_url,
        # Document management
        "deleteDocuments": delete_documents,
        "reprocessDocument": reprocess_document,
        "reindexDocument": reindex_document,
        # Metadata analysis
        "analyzeMetadata": analyze_metadata,
        "getMetadataStats": get_metadata_stats,
        "getFilterExamples": get_filter_examples,
        "getKeyLibrary": get_key_library,
        "checkKeySimilarity": check_key_similarity,
        "regenerateFilterExamples": regenerate_filter_examples,
        "deleteMetadataKey": delete_metadata_key,
        # KB Reindex
        "startReindex": start_reindex,
    }

    resolver = resolvers.get(field_name)
    if not resolver:
        logger.error(f"Unknown field: {field_name}")
        raise ValueError(f"Unknown field: {field_name}")

    try:
        result = resolver(event["arguments"])
        logger.info(f"Resolver {field_name} completed successfully")
        return result
    except ValueError as e:
        logger.exception(f"Validation error in {field_name}: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in {field_name}: {e}")
        raise


def get_document(args):
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

        logger.info(f"Document found: {document_id}, status: {item.get('status')}")
        return format_document(item)

    except ClientError as e:
        logger.error(f"DynamoDB error in get_document: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_document: {e}")
        raise


def list_documents(args):
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
        scan_kwargs = {
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


def delete_documents(args):
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
    kb_doc_identifiers = []

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
            input_s3_uri = item.get("input_s3_uri", "")
            output_s3_uri = item.get("output_s3_uri", "")
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
            item_type = item.get("type")
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
            response = bedrock_agent.delete_knowledge_base_documents(
                knowledgeBaseId=kb_id, dataSourceId=ds_id, documentIdentifiers=kb_doc_identifiers
            )
            # Log results
            doc_details = response.get("documentDetails", [])
            for detail in doc_details:
                status = detail.get("status", "UNKNOWN")
                if status == "DELETE_IN_PROGRESS":
                    logger.info(f"KB delete queued: {detail}")
                elif status != "DELETED":
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
        uri_path = input_s3_uri.replace("s3://", "")
        parts = uri_path.split("/", 1)
        if len(parts) < 2:
            logger.warning(f"Invalid S3 URI format: {input_s3_uri}")
            return

        bucket = parts[0]
        key = parts[1]

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
                    s3.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})
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
                        s3.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})
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


def reprocess_document(args):
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

    doc_type = item.get("type", "document")
    current_status = item.get("status", "").lower()

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
        uri_path = input_s3_uri.replace("s3://", "")
        parts = uri_path.split("/", 1)
        if len(parts) < 2:
            return []

        bucket = parts[0]
        key = parts[1]

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
    input_s3_uri = item.get("input_s3_uri", "")
    output_s3_uri = item.get("output_s3_uri", "")
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
        doc_identifiers = [{"dataSourceType": "S3", "s3": {"uri": uri}} for uri in kb_uris]
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


def _reprocess_image(document_id: str, item: dict, table) -> dict:
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
    uri_path = input_s3_uri.replace("s3://", "")
    parts = uri_path.split("/", 1)
    s3_key = parts[1] if len(parts) > 1 else ""

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


def _reprocess_media(document_id: str, item: dict, table) -> dict:
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

    # Start Step Functions execution
    execution_input = {
        "document_id": document_id,
        "input_s3_uri": input_s3_uri,
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


def _reprocess_as_document(document_id: str, item: dict, table) -> dict:
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

    # Start Step Functions execution
    execution_input = {
        "document_id": document_id,
        "input_s3_uri": input_s3_uri,
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


def _list_text_uris_for_reindex(input_s3_uri: str) -> list[str]:
    """
    List all text-based S3 URIs in a document's content folder for reindexing.

    Excludes:
    - .metadata.json files (sidecars, not content)
    - Visual files (.jpg, .png, etc.) - visual embeddings don't need metadata re-extraction
    - Media files (.mp4, .mp3, etc.) - same reason

    Args:
        input_s3_uri: S3 URI of any file in the document's content folder.

    Returns:
        List of text-based S3 URIs to reindex.
    """
    if not input_s3_uri or not input_s3_uri.startswith("s3://"):
        return []

    try:
        uri_path = input_s3_uri.replace("s3://", "")
        parts = uri_path.split("/", 1)
        if len(parts) < 2:
            return []

        bucket = parts[0]
        key = parts[1]

        # Determine folder prefix (content/{doc_id}/)
        folder_prefix = None
        if key.startswith("content/"):
            key_parts = key.split("/")
            if len(key_parts) >= 2:
                folder_prefix = f"content/{key_parts[1]}/"

        if not folder_prefix:
            # Not a content folder - check if it's a text file
            lower_uri = input_s3_uri.lower()
            if lower_uri.endswith(".metadata.json"):
                return []
            for ext in SKIP_REINDEX_EXTENSIONS:
                if lower_uri.endswith(ext):
                    return []
            return [input_s3_uri]

        # List all objects in the folder
        text_uris = []
        paginator = s3.get_paginator("list_objects_v2")
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

        logger.info(f"Found {len(text_uris)} text URIs for reindex in {folder_prefix}")
        return text_uris

    except ClientError as e:
        logger.warning(f"Failed to list text URIs for {input_s3_uri}: {e}")
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
    base_url = job_item.get("base_url", "")

    if not base_url:
        logger.warning(f"No base_url found for scraped job {document_id}")

    # Build map of source_url -> content_uri by reading metadata sidecars
    source_url_map = {}  # source_url -> content_uri
    for uri in text_uris:
        try:
            metadata_uri = f"{uri}.metadata.json"
            uri_path = metadata_uri.replace("s3://", "")
            parts = uri_path.split("/", 1)
            bucket = parts[0]
            key = parts[1]

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
            response = ingest_documents_with_retry(
                kb_id=kb_id,
                ds_id=ds_id,
                documents=documents,
            )
            logger.info(f"Ingested {len(documents)} scraped pages: {response}")
        except Exception as e:
            logger.error(f"Failed to ingest scraped pages: {e}")
            raise  # Propagate to caller so job is marked FAILED, not INDEXED

    return ingested_count


def reindex_document(args):
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

    doc_type = item.get("type", "document")
    current_status = item.get("status", "").lower()

    # Non-scraped docs need INGEST_TO_KB_FUNCTION_ARN for Lambda invocation
    if doc_type != "scraped" and not INGEST_TO_KB_FUNCTION_ARN:
        raise ValueError("Reindex not configured - INGEST_TO_KB_FUNCTION_ARN not set")

    # Check if already processing
    if current_status in ("processing", "transcribing", "pending"):
        raise ValueError(f"Document is already being processed (status: {current_status})")

    # Get base S3 URI to find content folder
    input_s3_uri = item.get("input_s3_uri", "")
    output_s3_uri = item.get("output_s3_uri", "")
    caption_s3_uri = item.get("caption_s3_uri", "")
    base_uri = input_s3_uri or output_s3_uri or caption_s3_uri

    if not base_uri:
        raise ValueError("Document has no S3 URI - it may not have been processed yet")

    # List all text-based files to reindex (excludes visual/media files)
    text_uris = _list_text_uris_for_reindex(base_uri)

    if not text_uris:
        raise ValueError("No text files found to reindex")

    logger.info(f"Found {len(text_uris)} text files to reindex for {document_id}")

    # Delete old text vectors from KB (visual embeddings stay untouched)
    config_manager = get_config_manager()
    try:
        kb_id, ds_id = get_knowledge_base_config(config_manager)
        doc_identifiers = [{"dataSourceType": "S3", "s3": {"uri": uri}} for uri in text_uris]
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


def create_upload_url(args):
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

        # Check for path traversal (security - must reject)
        if "/" in filename or "\\" in filename or ".." in filename:
            logger.warning(f"Filename contains path traversal characters: {filename}")
            raise ValueError("Filename contains invalid path characters")

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
        if is_demo_mode_enabled(get_config_manager()):
            user_id = get_current_user_id()
            config_table = os.environ.get("CONFIGURATION_TABLE_NAME")
            if config_table:
                allowed, message = demo_quota_check_and_increment(
                    user_id, "upload", config_table, dynamodb_client, get_config_manager()
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


def process_document(args):
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
        current_status = item.get("status", "").lower()
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

        return format_document(updated_item)

    except ClientError as e:
        logger.error(f"AWS service error in process_document: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in process_document: {e}")
        raise


def generate_presigned_download_url(s3_uri, expiration=3600):
    """Generate presigned URL for S3 object download."""
    if not s3_uri or not s3_uri.startswith("s3://"):
        return None
    try:
        # Parse s3://bucket/key format
        path = s3_uri.replace("s3://", "")
        parts = path.split("/", 1)
        if len(parts) != 2:
            return None
        bucket, key = parts
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration,
        )
    except ClientError as e:
        logger.warning(f"Failed to generate presigned URL for {s3_uri}: {e}")
        return None


def format_document(item):
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


# =========================================================================
# Scrape Resolvers
# =========================================================================


def _check_scrape_enabled():
    """Check if scraping is enabled (tables configured)."""
    if not SCRAPE_JOBS_TABLE:
        raise ValueError("Scraping is not enabled")


def get_scrape_job(args):
    """Get scrape job by ID with pages."""
    _check_scrape_enabled()

    try:
        job_id = args["jobId"]
        logger.info(f"Fetching scrape job: {job_id}")

        if not is_valid_uuid(job_id):
            raise ValueError("Invalid job ID format")

        jobs_table = dynamodb.Table(SCRAPE_JOBS_TABLE)
        response = jobs_table.get_item(Key={"job_id": job_id})

        item = response.get("Item")
        if not item:
            logger.info(f"Scrape job not found: {job_id}")
            return None

        # Get pages for this job
        pages = []
        if SCRAPE_URLS_TABLE:
            urls_table = dynamodb.Table(SCRAPE_URLS_TABLE)
            urls_response = urls_table.query(
                KeyConditionExpression="job_id = :jid",
                ExpressionAttributeValues={":jid": job_id},
                Limit=100,
            )
            page_items = urls_response.get("Items", [])

            # Generate content URLs directly from document_id
            # Scraped content is stored at: input/{doc_id}/{doc_id}.scraped.md
            def get_content_url(doc_id):
                if not doc_id:
                    return None
                try:
                    s3_key = f"input/{doc_id}/{doc_id}.scraped.md"
                    return s3.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": DATA_BUCKET, "Key": s3_key},
                        ExpiresIn=3600,
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate content URL for {doc_id}: {e}")
                    return None

            pages = [
                format_scrape_page(p, get_content_url(p.get("document_id"))) for p in page_items
            ]

        return {
            "job": format_scrape_job(item),
            "pages": pages,
        }

    except ClientError as e:
        logger.error(f"DynamoDB error in get_scrape_job: {e}")
        raise


def list_scrape_jobs(args):
    """List all scrape jobs with pagination."""
    _check_scrape_enabled()

    try:
        limit = args.get("limit", 50)
        next_token = args.get("nextToken")

        if limit < 1 or limit > MAX_DOCUMENTS_LIMIT:
            raise ValueError(f"Limit must be between 1 and {MAX_DOCUMENTS_LIMIT}")

        logger.info(f"Listing scrape jobs with limit: {limit}")

        table = dynamodb.Table(SCRAPE_JOBS_TABLE)
        scan_kwargs = {"Limit": limit}

        if next_token:
            try:
                scan_kwargs["ExclusiveStartKey"] = json.loads(next_token)
            except json.JSONDecodeError:
                raise ValueError("Invalid pagination token") from None

        response = table.scan(**scan_kwargs)

        items = [format_scrape_job(item) for item in response.get("Items", [])]
        logger.info(f"Retrieved {len(items)} scrape jobs")

        result = {"items": items}
        if "LastEvaluatedKey" in response:
            result["nextToken"] = json.dumps(response["LastEvaluatedKey"])

        return result

    except ClientError as e:
        logger.error(f"DynamoDB error in list_scrape_jobs: {e}")
        raise


def check_scrape_url(args):
    """Check if URL has been scraped before."""
    _check_scrape_enabled()

    try:
        url = args["url"]
        logger.info(f"Checking scrape URL: {url}")

        # Normalize URL to base
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        table = dynamodb.Table(SCRAPE_JOBS_TABLE)

        # Query using BaseUrlIndex GSI
        response = table.query(
            IndexName="BaseUrlIndex",
            KeyConditionExpression="base_url = :url",
            ExpressionAttributeValues={":url": base_url},
            ScanIndexForward=False,  # Most recent first
            Limit=1,
        )

        items = response.get("Items", [])
        if not items:
            return {"exists": False, "lastScrapedAt": None, "jobId": None, "title": None}

        job = items[0]
        return {
            "exists": True,
            "lastScrapedAt": job.get("created_at"),
            "jobId": job.get("job_id"),
            "title": job.get("title"),
        }

    except ClientError as e:
        logger.error(f"DynamoDB error in check_scrape_url: {e}")
        raise


def start_scrape(args):
    """Start a new scrape job."""
    _check_scrape_enabled()

    if not SCRAPE_START_FUNCTION_ARN:
        raise ValueError("Scrape start function not configured")

    try:
        input_data = args["input"]
        url = input_data.get("url")

        if not url:
            raise ValueError("URL is required")

        # Validate URL format
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must start with http:// or https://")

        logger.info(f"Starting scrape for URL: {url}")

        # Invoke scrape start Lambda
        event = {
            "base_url": url,
            "config": {
                "max_pages": input_data.get("maxPages", 1000),
                "max_depth": input_data.get("maxDepth", 3),
                "scope": input_data.get("scope", "subpages").lower(),
                "include_patterns": input_data.get("includePatterns", []),
                "exclude_patterns": input_data.get("excludePatterns", []),
                "force_rescrape": input_data.get("forceRescrape", False),
            },
        }

        if input_data.get("cookies"):
            event["config"]["cookies"] = input_data["cookies"]

        response = lambda_client.invoke(
            FunctionName=SCRAPE_START_FUNCTION_ARN,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        payload = json.loads(response["Payload"].read())

        if "errorMessage" in payload:
            raise ValueError(payload["errorMessage"])

        # Fetch the created job
        job_id = payload.get("job_id")
        if job_id:
            table = dynamodb.Table(SCRAPE_JOBS_TABLE)
            job_response = table.get_item(Key={"job_id": job_id})
            if job_response.get("Item"):
                return format_scrape_job(job_response["Item"])

        # Fallback: return payload data directly
        return {
            "jobId": payload.get("job_id"),
            "baseUrl": payload.get("base_url"),
            "status": payload.get("status", "DISCOVERING").upper(),
            "config": {
                "maxPages": event["config"]["max_pages"],
                "maxDepth": event["config"]["max_depth"],
                "scope": event["config"]["scope"].upper(),
            },
            "totalUrls": 0,
            "processedCount": 0,
            "failedCount": 0,
            "createdAt": datetime.now(UTC).isoformat(),
            "updatedAt": datetime.now(UTC).isoformat(),
        }

    except ClientError as e:
        logger.error(f"Error in start_scrape: {e}")
        raise


def cancel_scrape(args):
    """Cancel an in-progress scrape job."""
    _check_scrape_enabled()

    try:
        job_id = args["jobId"]
        logger.info(f"Cancelling scrape job: {job_id}")

        if not is_valid_uuid(job_id):
            raise ValueError("Invalid job ID format")

        table = dynamodb.Table(SCRAPE_JOBS_TABLE)

        # Get job
        response = table.get_item(Key={"job_id": job_id})
        item = response.get("Item")

        if not item:
            raise ValueError("Scrape job not found")

        # Check if job can be cancelled
        status = item.get("status", "")
        terminal_statuses = (
            ScrapeStatus.COMPLETED.value,
            ScrapeStatus.COMPLETED_WITH_ERRORS.value,
            ScrapeStatus.FAILED.value,
            ScrapeStatus.CANCELLED.value,
        )
        if status in terminal_statuses:
            raise ValueError(f"Cannot cancel job with status: {status}")

        # Stop Step Functions execution if running
        step_function_arn = item.get("step_function_arn")
        if step_function_arn:
            try:
                sfn.stop_execution(
                    executionArn=step_function_arn,
                    cause="Cancelled by user",
                )
                logger.info(f"Stopped Step Functions execution: {step_function_arn}")
            except ClientError as e:
                logger.warning(f"Could not stop Step Functions execution: {e}")

        # Update job status
        table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #status = :status, updated_at = :ts",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": ScrapeStatus.CANCELLED.value,
                ":ts": datetime.now(UTC).isoformat(),
            },
        )

        # Return updated job
        response = table.get_item(Key={"job_id": job_id})
        return format_scrape_job(response.get("Item"))

    except ClientError as e:
        logger.error(f"Error in cancel_scrape: {e}")
        raise


def format_scrape_job(item):
    """Format DynamoDB item as GraphQL ScrapeJob type."""
    config = item.get("config", {})
    return {
        "jobId": item["job_id"],
        "baseUrl": item.get("base_url", ""),
        "title": item.get("title"),
        "status": item.get("status", "pending").upper(),
        "config": {
            "maxPages": config.get("max_pages", 1000),
            "maxDepth": config.get("max_depth", 3),
            "scope": config.get("scope", "subpages").upper(),
            "includePatterns": config.get("include_patterns", []),
            "excludePatterns": config.get("exclude_patterns", []),
            "scrapeMode": (
                config.get("scrape_mode", "auto").upper() if config.get("scrape_mode") else None
            ),
            "cookies": json.dumps(config.get("cookies")) if config.get("cookies") else None,
        },
        "totalUrls": int(item.get("total_urls", 0)),
        "processedCount": int(item.get("processed_count", 0)),
        "failedCount": int(item.get("failed_count", 0)),
        "failedUrls": item.get("failed_urls", []),
        "jobMetadata": item.get("job_metadata"),
        "createdAt": item.get("created_at"),
        "updatedAt": item.get("updated_at"),
    }


def format_scrape_page(item, content_url=None):
    """Format DynamoDB item as GraphQL ScrapePage type."""
    return {
        "url": item["url"],
        "title": item.get("title"),
        "status": item.get("status", "pending").upper(),
        "documentId": item.get("document_id"),
        "contentUrl": content_url,
        "error": item.get("error"),
        "depth": int(item.get("depth", 0)),
    }


# =========================================================================
# Image Resolvers
# =========================================================================


def create_image_upload_url(args):
    """
    Create presigned URL for image upload.

    Returns upload URL and image ID for tracking.
    The image is stored at content/{imageId}/{filename}.

    Args:
        args: Dictionary containing:
            - filename: Image filename (required)
            - autoProcess: If True, process automatically after upload (optional)
            - userCaption: User-provided caption for auto-process (optional)
    """
    try:
        filename = args["filename"]
        auto_process = args.get("autoProcess", False)
        user_caption = args.get("userCaption", "")
        logger.info(f"Creating image upload URL for file: {filename}, autoProcess={auto_process}")

        # Validate filename length
        if not filename or len(filename) > MAX_FILENAME_LENGTH:
            logger.warning(f"Invalid filename length: {len(filename) if filename else 0}")
            raise ValueError(f"Filename must be between 1 and {MAX_FILENAME_LENGTH} characters")

        # Check for path traversal and invalid characters
        if "/" in filename or "\\" in filename or ".." in filename:
            logger.warning(f"Filename contains invalid path characters: {filename}")
            raise ValueError("Filename contains invalid path characters")

        # Validate it's a supported image type
        if not is_supported_image(filename):
            logger.warning(f"Unsupported image type: {filename}")
            is_valid, error_msg = validate_image_type(None, filename)
            if not is_valid:
                raise ValueError(error_msg)
            # Fallback error if is_supported_image fails but validate_image_type passes
            raise ValueError("Unsupported image file type")

        # Check demo mode upload quota (after validation to not consume quota for invalid requests)
        if is_demo_mode_enabled(get_config_manager()):
            user_id = get_current_user_id()
            config_table = os.environ.get("CONFIGURATION_TABLE_NAME")
            if config_table:
                allowed, message = demo_quota_check_and_increment(
                    user_id, "upload", config_table, dynamodb_client, get_config_manager()
                )
                if not allowed:
                    raise ValueError(message)

        image_id = str(uuid4())
        logger.info(f"Generated image ID: {image_id}")

        # Generate S3 key with content/ prefix (unified for all KB content)
        s3_key = f"content/{image_id}/{filename}"

        # Build presigned POST conditions and fields
        # Include metadata for auto-processing if requested
        conditions = []
        fields = {}

        # Add demo mode file size limit if applicable
        demo_conditions = get_demo_upload_conditions(get_config_manager())
        if demo_conditions:
            conditions.extend(demo_conditions)

        if auto_process:
            # Add metadata fields that will be stored with the S3 object
            fields["x-amz-meta-auto-process"] = "true"
            conditions.append({"x-amz-meta-auto-process": "true"})

            if user_caption:
                fields["x-amz-meta-caption"] = user_caption
                conditions.append({"x-amz-meta-caption": user_caption})

        # Create presigned POST with conditions
        logger.info(f"Generating presigned POST for S3 key: {s3_key}, autoProcess={auto_process}")
        presigned = s3.generate_presigned_post(
            Bucket=DATA_BUCKET,
            Key=s3_key,
            Fields=fields if fields else None,
            Conditions=conditions if conditions else None,
            ExpiresIn=3600,  # 1 hour
        )

        # Create tracking record with type="image"
        logger.info(f"Creating tracking record for image: {image_id}")
        now = datetime.now(UTC).isoformat()
        table = dynamodb.Table(TRACKING_TABLE)
        item = {
            "document_id": image_id,  # Using document_id field for consistency
            "filename": filename,
            "input_s3_uri": f"s3://{DATA_BUCKET}/{s3_key}",
            "status": ImageStatus.PENDING.value,
            "type": "image",  # Differentiate from documents
            "created_at": now,
            "updated_at": now,
        }

        # Store auto-process settings for Lambda to read
        if auto_process:
            item["auto_process"] = True
            if user_caption:
                item["user_caption"] = user_caption

        table.put_item(Item=item)

        s3_uri = f"s3://{DATA_BUCKET}/{s3_key}"
        logger.info(f"Image upload URL created successfully for image: {image_id}")
        return {
            "uploadUrl": presigned["url"],
            "imageId": image_id,
            "s3Uri": s3_uri,
            "fields": json.dumps(presigned["fields"]),
        }

    except ClientError as e:
        logger.error(f"AWS service error in create_image_upload_url: {e}")
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_image_upload_url: {e}")
        raise


def generate_caption(args):
    """
    Generate an AI caption for an image using Bedrock Converse API with vision.

    Args:
        args: Dictionary containing:
            - imageS3Uri: S3 URI of the image to caption (s3://bucket/key)

    Returns:
        CaptionResult with caption or error field
    """
    image_s3_uri = args.get("imageS3Uri", "")
    logger.info(f"Generating caption for image: {image_s3_uri[:50]}...")

    try:
        # Validate S3 URI format
        if not image_s3_uri or not image_s3_uri.startswith("s3://"):
            return {"caption": None, "error": "Invalid S3 URI format. Must start with s3://"}

        # Parse S3 URI
        uri_path = image_s3_uri.replace("s3://", "")
        parts = uri_path.split("/", 1)
        if len(parts) != 2 or not parts[1]:
            return {"caption": None, "error": "Invalid S3 URI format. Must be s3://bucket/key"}

        bucket = parts[0]
        key = parts[1]

        # Validate bucket matches DATA_BUCKET for security
        if bucket != DATA_BUCKET:
            logger.warning(f"Attempted caption for unauthorized bucket: {bucket}")
            return {"caption": None, "error": "Image must be in the configured data bucket"}

        # Get image from S3
        logger.info(f"Retrieving image from S3: bucket={bucket}, key={key}")
        try:
            response = s3.get_object(Bucket=bucket, Key=key)
            image_bytes = response["Body"].read()
            content_type = response.get("ContentType", "image/jpeg")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                return {"caption": None, "error": "Image not found in S3"}
            if error_code == "AccessDenied":
                return {"caption": None, "error": "Access denied to image in S3"}
            logger.error(f"S3 error retrieving image: {e}")
            return {"caption": None, "error": f"Failed to retrieve image: {error_code}"}

        # Get configured chat model from ConfigurationManager
        if CONFIGURATION_TABLE_NAME:
            try:
                config_manager = ConfigurationManager(CONFIGURATION_TABLE_NAME)
                chat_model_id = config_manager.get_parameter(
                    "chat_primary_model", default="us.anthropic.claude-haiku-4-5-20251001-v1:0"
                )
            except Exception as e:
                logger.warning(f"Failed to get config, using default model: {e}")
                chat_model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        else:
            chat_model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

        logger.info(f"Using model for caption: {chat_model_id}")

        # Determine image media type for Converse API
        media_type_mapping = {
            "image/png": "png",
            "image/jpeg": "jpeg",
            "image/gif": "gif",
            "image/webp": "webp",
        }
        media_type = media_type_mapping.get(content_type)
        if not media_type:
            # Try to infer from file extension
            ext = key.lower().split(".")[-1] if "." in key else ""
            ext_to_media = {
                "png": "png",
                "jpg": "jpeg",
                "jpeg": "jpeg",
                "gif": "gif",
                "webp": "webp",
            }
            media_type = ext_to_media.get(ext, "jpeg")

        # Build Converse API request with image
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": media_type,
                            "source": {"bytes": image_bytes},
                        }
                    },
                    {
                        "text": "Generate a descriptive caption for this image. "
                        "The caption should be concise (1-2 sentences) and describe "
                        "the main subject, context, and any notable details. "
                        "This caption will be used for searching and retrieving the image."
                    },
                ],
            }
        ]

        # System prompt for image captioning (configurable via DynamoDB)
        default_caption_prompt = (
            "You are an image captioning assistant. Generate concise, descriptive captions "
            "that are suitable for use as search keywords. Focus on the main subject, "
            "setting, and any notable visual elements. Keep captions under 200 characters."
        )
        if CONFIGURATION_TABLE_NAME:
            try:
                system_prompt = config_manager.get_parameter(
                    "image_caption_prompt", default=default_caption_prompt
                )
            except Exception as e:
                logger.warning(f"Failed to get caption prompt config: {e}")
                system_prompt = default_caption_prompt
        else:
            system_prompt = default_caption_prompt

        # Call Bedrock Converse API
        logger.info("Calling Bedrock Converse API for caption generation")
        try:
            converse_response = bedrock_runtime.converse(
                modelId=chat_model_id,
                messages=messages,
                system=[{"text": system_prompt}],
                inferenceConfig={
                    "maxTokens": 500,
                    "temperature": 0.3,  # Lower temperature for more consistent captions
                },
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_msg = e.response.get("Error", {}).get("Message", "")
            logger.error(f"Bedrock error: {error_code} - {error_msg}")
            return {"caption": None, "error": f"Failed to generate caption: {error_msg}"}

        # Extract caption from response
        output = converse_response.get("output", {})
        output_message = output.get("message", {})
        content_blocks = output_message.get("content", [])

        caption = ""
        for block in content_blocks:
            if isinstance(block, dict) and "text" in block:
                caption += block["text"]

        caption = caption.strip()
        if not caption:
            return {"caption": None, "error": "Model returned empty caption"}

        logger.info(f"Generated caption: {caption[:100]}...")
        return {"caption": caption, "error": None}

    except Exception as e:
        logger.error(f"Unexpected error in generate_caption: {e}", exc_info=True)
        return {"caption": None, "error": "Failed to generate caption. Please try again."}


def submit_image(args):
    """
    Submit an image with caption to finalize upload and trigger processing.

    Args:
        args: Dictionary containing:
            - input: SubmitImageInput with imageId, caption, userCaption, aiCaption

    Returns:
        Image object with updated status
    """
    input_data = args.get("input", {})
    image_id = input_data.get("imageId")
    caption = input_data.get("caption")
    user_caption = input_data.get("userCaption")
    ai_caption = input_data.get("aiCaption")
    extract_text = input_data.get("extractText", False)

    logger.info(f"Submitting image: {image_id}, extractText={extract_text}")

    try:
        # Validate imageId
        if not image_id:
            raise ValueError("imageId is required")

        if not is_valid_uuid(image_id):
            raise ValueError("Invalid imageId format")

        # Check if tracking record exists
        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={"document_id": image_id})
        item = response.get("Item")

        if not item:
            raise ValueError("Image not found")

        # Verify it's an image type
        if item.get("type") != "image":
            raise ValueError("Record is not an image")

        # Verify status is PENDING
        if item.get("status") != ImageStatus.PENDING.value:
            raise ValueError(f"Image is not in PENDING status (current: {item.get('status')})")

        # Get S3 URI and verify image exists in S3
        input_s3_uri = item.get("input_s3_uri", "")
        if not input_s3_uri.startswith("s3://"):
            raise ValueError("Invalid S3 URI in tracking record")

        # Parse S3 URI
        uri_path = input_s3_uri.replace("s3://", "")
        parts = uri_path.split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""

        # Verify image exists in S3
        try:
            head_response = s3.head_object(Bucket=bucket, Key=key)
            content_type = head_response.get("ContentType", "image/jpeg")
            file_size = head_response.get("ContentLength", 0)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404"):
                msg = "Image file not found in S3. Please upload the image first."
                raise ValueError(msg) from e
            logger.error(f"S3 error checking image: {e}")
            raise ValueError(f"Failed to verify image in S3: {error_code}") from e

        # Build combined caption (user first, AI appends)
        combined_caption = ""
        if user_caption and ai_caption:
            combined_caption = f"{user_caption}. {ai_caption}"
        elif user_caption:
            combined_caption = user_caption
        elif ai_caption:
            combined_caption = ai_caption
        elif caption:
            combined_caption = caption

        # Note: metadata.json no longer written to S3 - all data stored in DynamoDB
        # This prevents KB from incorrectly indexing the metadata file

        # Update tracking record
        now = datetime.now(UTC).isoformat()
        table.update_item(
            Key={"document_id": image_id},
            UpdateExpression=(
                "SET #status = :status, caption = :caption, user_caption = :user_caption, "
                "ai_caption = :ai_caption, extract_text = :extract_text, "
                "content_type = :content_type, file_size = :file_size, updated_at = :updated_at"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": ImageStatus.PROCESSING.value,
                ":caption": combined_caption,
                ":user_caption": user_caption,
                ":ai_caption": ai_caption,
                ":extract_text": extract_text,
                ":content_type": content_type,
                ":file_size": file_size,
                ":updated_at": now,
            },
        )

        # Invoke process_image Lambda asynchronously
        if PROCESS_IMAGE_FUNCTION_ARN:
            process_event = {
                "image_id": image_id,
                "s3_key": key,
                "bucket": bucket,
                "trigger_type": "submit_image",
                "extract_text": extract_text,
            }
            logger.info(f"Invoking process_image for {image_id}")
            lambda_client.invoke(
                FunctionName=PROCESS_IMAGE_FUNCTION_ARN,
                InvocationType="Event",  # Async invocation
                Payload=json.dumps(process_event),
            )
        else:
            logger.warning("PROCESS_IMAGE_FUNCTION_ARN not configured, skipping invocation")

        # Get updated item
        response = table.get_item(Key={"document_id": image_id})
        updated_item = response.get("Item")

        logger.info(f"Image submitted successfully: {image_id}")
        return format_image(updated_item)

    except ValueError:
        raise
    except ClientError as e:
        logger.error(f"AWS service error in submit_image: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in submit_image: {e}", exc_info=True)
        raise


def format_image(item):
    """Format DynamoDB item as GraphQL Image type."""
    if not item:
        return None

    input_s3_uri = item.get("input_s3_uri", "")
    caption_s3_uri = item.get("caption_s3_uri", "")
    status = item.get("status", ImageStatus.PENDING.value)

    # Generate thumbnail URL for images
    thumbnail_url = None
    if input_s3_uri and input_s3_uri.startswith("s3://"):
        thumbnail_url = generate_presigned_download_url(input_s3_uri)

    # Generate presigned URL for caption.txt preview
    caption_url = None
    if caption_s3_uri and caption_s3_uri.startswith("s3://"):
        caption_url = generate_presigned_download_url(caption_s3_uri)

    # Get extracted_metadata - pass dict directly, AppSync handles AWSJSON serialization
    extracted_metadata = item.get("extracted_metadata")

    return {
        "imageId": item.get("document_id"),
        "filename": item.get("filename", ""),
        "caption": item.get("caption"),
        "userCaption": item.get("user_caption"),
        "aiCaption": item.get("ai_caption"),
        "status": status,
        "s3Uri": input_s3_uri,
        "thumbnailUrl": thumbnail_url,
        "contentType": item.get("content_type"),
        "fileSize": item.get("file_size"),
        "errorMessage": item.get("error_message"),
        "extractedText": item.get("extracted_text"),
        "extractedMetadata": extracted_metadata,
        "captionUrl": caption_url,
        "createdAt": item.get("created_at") or item.get("updated_at"),
        "updatedAt": item.get("updated_at") or item.get("created_at"),
    }


def get_image(args):
    """
    Get image by ID.

    Args:
        args: Dictionary containing:
            - imageId: Image ID to retrieve

    Returns:
        Image object or None if not found
    """
    image_id = args.get("imageId")
    logger.info(f"Getting image: {image_id}")

    try:
        if not image_id:
            raise ValueError("imageId is required")

        if not is_valid_uuid(image_id):
            raise ValueError("Invalid imageId format")

        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={"document_id": image_id})

        item = response.get("Item")
        if not item:
            logger.info(f"Image not found: {image_id}")
            return None

        # Verify it's an image type
        if item.get("type") != "image":
            logger.info(f"Record is not an image: {image_id}")
            return None

        return format_image(item)

    except ClientError as e:
        logger.error(f"DynamoDB error in get_image: {e}")
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_image: {e}")
        raise


def list_images(args):
    """
    List all images with pagination.

    Args:
        args: Dictionary containing:
            - limit: Max items to return (default 50)
            - nextToken: Pagination token

    Returns:
        ImageConnection with items and nextToken
    """
    limit = args.get("limit", 50)
    next_token = args.get("nextToken")

    logger.info(f"Listing images with limit: {limit}")

    try:
        # Validate limit
        if limit < 1 or limit > MAX_DOCUMENTS_LIMIT:
            raise ValueError(f"Limit must be between 1 and {MAX_DOCUMENTS_LIMIT}")

        table = dynamodb.Table(TRACKING_TABLE)

        # Scan with filter for type="image"
        # Note: Don't use DynamoDB Limit with FilterExpression - Limit applies BEFORE
        # filtering, which can return 0 results. Scan all and apply limit after.
        scan_kwargs = {
            "FilterExpression": "#type = :image_type",
            "ExpressionAttributeNames": {"#type": "type"},
            "ExpressionAttributeValues": {":image_type": "image"},
        }

        if next_token:
            try:
                scan_kwargs["ExclusiveStartKey"] = json.loads(next_token)
            except json.JSONDecodeError:
                raise ValueError("Invalid pagination token") from None

        # Scan and collect filtered items until we have enough
        all_items = []
        while True:
            response = table.scan(**scan_kwargs)
            all_items.extend(response.get("Items", []))

            if len(all_items) >= limit or "LastEvaluatedKey" not in response:
                break
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        items = [format_image(item) for item in all_items[:limit]]
        logger.info(f"Retrieved {len(items)} images")

        result = {"items": items}
        if len(all_items) > limit:
            last_item = all_items[limit - 1]
            result["nextToken"] = json.dumps({"document_id": last_item["document_id"]})

        return result

    except ClientError as e:
        logger.error(f"DynamoDB error in list_images: {e}")
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in list_images: {e}")
        raise


def delete_image(args):
    """
    Delete an image from S3, DynamoDB, and Knowledge Base.

    Args:
        args: Dictionary containing:
            - imageId: Image ID to delete

    Returns:
        True if deleted successfully
    """
    image_id = args.get("imageId")
    logger.info(f"Deleting image: {image_id}")

    try:
        if not image_id:
            raise ValueError("imageId is required")

        if not is_valid_uuid(image_id):
            raise ValueError("Invalid imageId format")

        # Check if full KB reindex is in progress - block delete to prevent conflicts
        check_reindex_lock()

        table = dynamodb.Table(TRACKING_TABLE)

        # Get image record
        response = table.get_item(Key={"document_id": image_id})
        item = response.get("Item")

        if not item:
            raise ValueError("Image not found")

        # Verify it's an image type
        if item.get("type") != "image":
            raise ValueError("Record is not an image")

        input_s3_uri = item.get("input_s3_uri", "")

        # Delete files from S3
        if input_s3_uri and input_s3_uri.startswith("s3://"):
            uri_path = input_s3_uri.replace("s3://", "")
            parts = uri_path.split("/", 1)
            if len(parts) == 2:
                bucket = parts[0]
                image_key = parts[1]

                # Delete image file
                try:
                    s3.delete_object(Bucket=bucket, Key=image_key)
                    logger.info(f"Deleted image from S3: {image_key}")
                except ClientError as e:
                    logger.warning(f"Failed to delete image from S3: {e}")

                # Delete metadata.json
                key_parts = image_key.rsplit("/", 1)
                if len(key_parts) > 1:
                    metadata_key = f"{key_parts[0]}/metadata.json"
                    try:
                        s3.delete_object(Bucket=bucket, Key=metadata_key)
                        logger.info(f"Deleted metadata from S3: {metadata_key}")
                    except ClientError as e:
                        logger.warning(f"Failed to delete metadata from S3: {e}")

                    # Delete content.txt (KB ingestion file)
                    content_key = f"{key_parts[0]}/content.txt"
                    try:
                        s3.delete_object(Bucket=bucket, Key=content_key)
                        logger.info(f"Deleted content from S3: {content_key}")
                    except ClientError as e:
                        logger.warning(f"Failed to delete content from S3: {e}")

        # Delete from DynamoDB
        table.delete_item(Key={"document_id": image_id})
        logger.info(f"Deleted image from DynamoDB: {image_id}")

        # Note: KB vectors will be cleaned up on next data source sync
        # or we could call bedrock_agent.delete_knowledge_base_documents here

        return True

    except ClientError as e:
        logger.error(f"AWS service error in delete_image: {e}")
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete_image: {e}")
        raise


def create_zip_upload_url(args):
    """
    Create presigned URL for ZIP archive upload.

    Returns upload URL and upload ID for tracking batch image uploads.
    The ZIP is stored at uploads/{uploadId}/archive.zip.

    Args:
        args: Dictionary containing:
            - generateCaptions: Boolean flag to generate AI captions for images

    Returns:
        Dictionary with uploadUrl, uploadId, and fields
    """
    try:
        generate_captions = args.get("generateCaptions", False)
        logger.info(f"Creating ZIP upload URL, generateCaptions={generate_captions}")

        # Check demo mode upload quota (after args parsing, ZIP counts as a single upload)
        if is_demo_mode_enabled(get_config_manager()):
            user_id = get_current_user_id()
            config_table = os.environ.get("CONFIGURATION_TABLE_NAME")
            if config_table:
                allowed, message = demo_quota_check_and_increment(
                    user_id, "upload", config_table, dynamodb_client, get_config_manager()
                )
                if not allowed:
                    raise ValueError(message)

        upload_id = str(uuid4())
        logger.info(f"Generated upload ID: {upload_id}")

        # Generate S3 key with uploads/ prefix
        s3_key = f"uploads/{upload_id}/archive.zip"

        # Create presigned POST with demo mode file size limit if applicable
        logger.info(f"Generating presigned POST for S3 key: {s3_key}")
        demo_conditions = get_demo_upload_conditions(get_config_manager())
        presigned = s3.generate_presigned_post(
            Bucket=DATA_BUCKET,
            Key=s3_key,
            Conditions=demo_conditions,
            ExpiresIn=3600,  # 1 hour
        )

        # Create upload tracking record
        logger.info(f"Creating upload tracking record: {upload_id}")
        now = datetime.now(UTC).isoformat()
        table = dynamodb.Table(TRACKING_TABLE)
        table.put_item(
            Item={
                "document_id": upload_id,
                "type": "zip_upload",
                "status": "PENDING",
                "generate_captions": generate_captions,
                "input_s3_uri": f"s3://{DATA_BUCKET}/{s3_key}",
                "created_at": now,
                "updated_at": now,
            }
        )

        return {
            "uploadUrl": presigned["url"],
            "uploadId": upload_id,
            "fields": json.dumps(presigned["fields"]),
        }

    except ClientError as e:
        logger.error(f"AWS service error in create_zip_upload_url: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_zip_upload_url: {e}")
        raise


# =========================================================================
# Metadata Analysis Resolvers
# =========================================================================


def analyze_metadata(args):
    """
    Trigger metadata analysis of Knowledge Base vectors.

    Invokes the metadata analyzer Lambda which:
    - Samples vectors from Knowledge Base
    - Analyzes metadata field occurrences
    - Generates filter examples using LLM
    - Stores results in S3 and DynamoDB

    Returns:
        MetadataAnalysisResult with success status and stats
    """
    logger.info("Starting metadata analysis")

    if not METADATA_ANALYZER_FUNCTION_ARN:
        logger.error("METADATA_ANALYZER_FUNCTION_ARN not configured")
        return {
            "success": False,
            "error": "Metadata analyzer not configured",
            "vectorsSampled": 0,
            "keysAnalyzed": 0,
            "examplesGenerated": 0,
            "executionTimeMs": 0,
        }

    try:
        # Invoke metadata analyzer Lambda synchronously
        logger.info(f"Invoking metadata analyzer: {METADATA_ANALYZER_FUNCTION_ARN}")
        response = lambda_client.invoke(
            FunctionName=METADATA_ANALYZER_FUNCTION_ARN,
            InvocationType="RequestResponse",
            Payload=json.dumps({}),
        )

        # Parse response
        payload = json.loads(response["Payload"].read())

        # Check for Lambda execution error
        if response.get("FunctionError"):
            error_msg = payload.get("errorMessage", "Lambda execution failed")
            logger.error(f"Metadata analyzer failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "vectorsSampled": 0,
                "keysAnalyzed": 0,
                "examplesGenerated": 0,
                "executionTimeMs": 0,
            }

        logger.info(f"Metadata analysis complete: {payload}")

        return {
            "success": payload.get("success", False),
            "vectorsSampled": payload.get("vectorsSampled", 0),
            "keysAnalyzed": payload.get("keysAnalyzed", 0),
            "examplesGenerated": payload.get("examplesGenerated", 0),
            "executionTimeMs": payload.get("executionTimeMs", 0),
            "error": payload.get("error"),
        }

    except ClientError as e:
        logger.error(f"Error invoking metadata analyzer: {e}")
        return {
            "success": False,
            "error": f"Failed to invoke metadata analyzer: {e}",
            "vectorsSampled": 0,
            "keysAnalyzed": 0,
            "examplesGenerated": 0,
            "executionTimeMs": 0,
        }
    except Exception as e:
        logger.error(f"Unexpected error in analyze_metadata: {e}")
        return {
            "success": False,
            "error": str(e),
            "vectorsSampled": 0,
            "keysAnalyzed": 0,
            "examplesGenerated": 0,
            "executionTimeMs": 0,
        }


def get_metadata_stats(args):
    """
    Get metadata key statistics from the key library.

    Returns all keys with their occurrence counts and sample values.

    Returns:
        MetadataStatsResponse with keys array and stats
    """
    logger.info("Getting metadata statistics")

    if not METADATA_KEY_LIBRARY_TABLE:
        logger.warning("METADATA_KEY_LIBRARY_TABLE not configured")
        return {
            "keys": [],
            "totalKeys": 0,
            "lastAnalyzed": None,
            "error": "Metadata key library not configured",
        }

    try:
        table = dynamodb.Table(METADATA_KEY_LIBRARY_TABLE)

        # Scan all keys from the library
        all_items = []
        scan_kwargs: dict = {}

        while True:
            response = table.scan(**scan_kwargs)
            all_items.extend(response.get("Items", []))

            if "LastEvaluatedKey" not in response:
                break
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        # Format keys for GraphQL response
        keys = []
        last_analyzed = None

        for item in all_items:
            key_analyzed = item.get("last_analyzed")
            if key_analyzed and (not last_analyzed or key_analyzed > last_analyzed):
                last_analyzed = key_analyzed

            keys.append(
                {
                    "keyName": item.get("key_name", ""),
                    "dataType": item.get("data_type", "string"),
                    "occurrenceCount": int(item.get("occurrence_count", 0)),
                    "sampleValues": item.get("sample_values", [])[:10],
                    "lastAnalyzed": key_analyzed,
                    "status": item.get("status", "active"),
                }
            )

        # Sort by occurrence count descending
        keys.sort(key=lambda x: x["occurrenceCount"], reverse=True)

        logger.info(f"Retrieved {len(keys)} metadata keys")

        return {
            "keys": keys,
            "totalKeys": len(keys),
            "lastAnalyzed": last_analyzed,
            "error": None,
        }

    except ClientError as e:
        logger.error(f"DynamoDB error getting metadata stats: {e}")
        return {
            "keys": [],
            "totalKeys": 0,
            "lastAnalyzed": None,
            "error": f"Failed to get metadata stats: {e}",
        }
    except Exception as e:
        logger.error(f"Unexpected error in get_metadata_stats: {e}")
        return {
            "keys": [],
            "totalKeys": 0,
            "lastAnalyzed": None,
            "error": str(e),
        }


def get_filter_examples(args):
    """
    Get filter examples from configuration.

    Returns generated filter examples for use in the UI filter builder.

    Returns:
        FilterExamplesResponse with examples array
    """
    logger.info("Getting filter examples")

    if not CONFIGURATION_TABLE_NAME:
        logger.warning("CONFIGURATION_TABLE_NAME not configured")
        return {
            "examples": [],
            "totalExamples": 0,
            "lastGenerated": None,
            "error": "Configuration not available",
        }

    try:
        # Get examples from config manager
        config_manager = get_config_manager()
        examples_data = config_manager.get_parameter("metadata_filter_examples", default=[])

        if not examples_data or not isinstance(examples_data, list):
            logger.info("No filter examples found in configuration")
            return {
                "examples": [],
                "totalExamples": 0,
                "lastGenerated": None,
                "error": None,
            }

        # Format examples for GraphQL response
        examples = []
        for ex in examples_data:
            if isinstance(ex, dict) and "name" in ex and "filter" in ex:
                examples.append(
                    {
                        "name": ex.get("name", ""),
                        "description": ex.get("description", ""),
                        "useCase": ex.get("use_case", ""),
                        "filter": json.dumps(convert_decimals(ex.get("filter", {}))),
                    }
                )

        # Get last generated timestamp from config
        last_generated = config_manager.get_parameter(
            "metadata_filter_examples_updated_at", default=None
        )

        logger.info(f"Retrieved {len(examples)} filter examples")

        return {
            "examples": examples,
            "totalExamples": len(examples),
            "lastGenerated": last_generated,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Error getting filter examples: {e}")
        return {
            "examples": [],
            "totalExamples": 0,
            "lastGenerated": None,
            "error": str(e),
        }


def get_key_library(args):
    """
    Get active metadata keys from the key library.

    Returns list of keys for use in manual mode key selection.

    Returns:
        List of MetadataKey objects with key names and metadata
    """
    logger.info("Getting key library")

    if not METADATA_KEY_LIBRARY_TABLE:
        logger.warning("METADATA_KEY_LIBRARY_TABLE not configured")
        return []

    try:
        table = dynamodb.Table(METADATA_KEY_LIBRARY_TABLE)

        # Scan all keys from the library
        all_items = []
        scan_kwargs: dict = {}

        while True:
            response = table.scan(**scan_kwargs)
            all_items.extend(response.get("Items", []))

            if "LastEvaluatedKey" not in response:
                break
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        # Filter to only active keys and format for GraphQL
        keys = []
        for item in all_items:
            status = item.get("status", "active")
            if status != "active":
                continue

            keys.append(
                {
                    "keyName": item.get("key_name", ""),
                    "dataType": item.get("data_type", "string"),
                    "occurrenceCount": int(item.get("occurrence_count", 0)),
                    "sampleValues": item.get("sample_values", [])[:5],
                    "status": status,
                }
            )

        # Sort by occurrence count descending
        keys.sort(key=lambda x: x["occurrenceCount"], reverse=True)

        logger.info(f"Retrieved {len(keys)} active keys from library")
        return keys

    except ClientError as e:
        logger.error(f"DynamoDB error getting key library: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_key_library: {e}")
        return []


def check_key_similarity(args):
    """
    Check if a proposed key is similar to existing keys.

    Helps prevent duplicate or inconsistent key names by suggesting
    existing keys that are similar to what the user is proposing.

    Args:
        args: Dictionary containing:
            - keyName: The proposed key name to check
            - threshold: Optional similarity threshold (0-1, default 0.8)

    Returns:
        KeySimilarityResult with proposedKey, similarKeys, and hasSimilar
    """
    key_name = args.get("keyName", "")
    threshold = args.get("threshold", 0.8)

    logger.info(f"Checking similarity for key: {key_name}")

    if not key_name:
        raise ValueError("keyName is required")

    # Validate threshold
    if threshold < 0 or threshold > 1:
        raise ValueError("threshold must be between 0 and 1")

    if not METADATA_KEY_LIBRARY_TABLE:
        logger.warning("METADATA_KEY_LIBRARY_TABLE not configured")
        return {
            "proposedKey": key_name,
            "similarKeys": [],
            "hasSimilar": False,
        }

    try:
        key_library = KeyLibrary(table_name=METADATA_KEY_LIBRARY_TABLE)
        similar_keys = key_library.check_key_similarity(key_name, threshold=threshold)

        logger.info(f"Found {len(similar_keys)} similar keys for '{key_name}'")

        return {
            "proposedKey": key_name,
            "similarKeys": similar_keys,
            "hasSimilar": len(similar_keys) > 0,
        }

    except ClientError as e:
        logger.error(f"DynamoDB error checking key similarity: {e}")
        return {
            "proposedKey": key_name,
            "similarKeys": [],
            "hasSimilar": False,
        }
    except Exception as e:
        logger.error(f"Unexpected error in check_key_similarity: {e}")
        return {
            "proposedKey": key_name,
            "similarKeys": [],
            "hasSimilar": False,
        }


def regenerate_filter_examples(args):
    """
    Regenerate filter examples using only the configured filter keys.

    Reads metadata_filter_keys from config and generates new examples
    using only those keys. Replaces all existing examples.

    Returns:
        FilterExamplesResult with success, examplesGenerated, executionTimeMs, error
    """
    import time

    start_time = time.time()

    try:
        # Get config manager
        config_manager = get_config_manager()
        if not config_manager:
            return {
                "success": False,
                "examplesGenerated": 0,
                "executionTimeMs": 0,
                "error": "Configuration not available",
            }

        # Get filter keys from config (empty list if not set)
        filter_keys = config_manager.get_parameter("metadata_filter_keys", default=[])

        if not filter_keys:
            return {
                "success": False,
                "examplesGenerated": 0,
                "executionTimeMs": int((time.time() - start_time) * 1000),
                "error": "No filter keys configured. Add keys to generate examples.",
            }

        # Get key library to fetch key details
        if not METADATA_KEY_LIBRARY_TABLE:
            return {
                "success": False,
                "examplesGenerated": 0,
                "executionTimeMs": int((time.time() - start_time) * 1000),
                "error": "Key library table not configured",
            }

        # Fetch active keys and filter to only allowed ones
        key_library = KeyLibrary(table_name=METADATA_KEY_LIBRARY_TABLE)
        active_keys = key_library.get_active_keys()

        # Normalize filter keys for comparison
        filter_keys_norm = {k.lower().replace(" ", "_") for k in filter_keys}

        # Filter to only keys in the allowlist
        allowed_keys = [
            k
            for k in active_keys
            if k.get("key_name", "").lower().replace(" ", "_") in filter_keys_norm
        ]

        if not allowed_keys:
            return {
                "success": False,
                "examplesGenerated": 0,
                "executionTimeMs": int((time.time() - start_time) * 1000),
                "error": "None of the configured filter keys are active in the library",
            }

        # Build field analysis format expected by generate_filter_examples
        field_analysis = {}
        for key in allowed_keys:
            field_analysis[key.get("key_name")] = {
                "count": key.get("occurrence_count", 0),
                "data_type": key.get("data_type", "string"),
                "sample_values": key.get("sample_values", []),
            }

        # Generate examples using the shared library function
        examples = generate_filter_examples(field_analysis, num_examples=6)

        # Store to S3 if bucket configured
        if DATA_BUCKET and examples:
            store_filter_examples(examples, DATA_BUCKET)

        # Update config with new examples (clears disabled list)
        if examples:
            update_config_with_examples(examples, clear_disabled=True)

        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.info(f"Regenerated {len(examples)} filter examples in {execution_time_ms}ms")

        return {
            "success": True,
            "examplesGenerated": len(examples),
            "executionTimeMs": execution_time_ms,
            "error": None,
        }

    except Exception as e:
        logger.exception(f"Failed to regenerate filter examples: {e}")
        return {
            "success": False,
            "examplesGenerated": 0,
            "executionTimeMs": int((time.time() - start_time) * 1000),
            "error": str(e),
        }


def delete_metadata_key(args):
    """Delete a metadata key from the key library and filter allowlist."""
    key_name = args.get("keyName", "")
    if not key_name:
        return {"success": False, "keyName": "", "error": "keyName is required"}

    if not METADATA_KEY_LIBRARY_TABLE:
        return {"success": False, "keyName": key_name, "error": "Key library not configured"}

    try:
        key_library = KeyLibrary(table_name=METADATA_KEY_LIBRARY_TABLE)
        success = key_library.delete_key(key_name)

        # Also remove from filter keys allowlist if present
        try:
            config_manager = get_config_manager()
            if config_manager:
                current_filter_keys = config_manager.get_parameter(
                    "metadata_filter_keys", default=[]
                )
                if current_filter_keys:
                    # Normalize for comparison
                    key_name_norm = key_name.lower().replace(" ", "_")
                    updated_filter_keys = [
                        k
                        for k in current_filter_keys
                        if k.lower().replace(" ", "_") != key_name_norm
                    ]
                    # Only update if something was removed
                    if len(updated_filter_keys) != len(current_filter_keys):
                        config_manager.update_custom_config(
                            {"metadata_filter_keys": updated_filter_keys}
                        )
                        logger.info(f"Removed '{key_name}' from filter keys allowlist")
        except Exception as e:
            # Non-critical - log but don't fail the deletion
            logger.warning(f"Failed to remove key from filter allowlist: {e}")

        return {"success": success, "keyName": key_name, "error": None}
    except Exception as e:
        logger.error(f"Error deleting metadata key '{key_name}': {e}")
        return {"success": False, "keyName": key_name, "error": str(e)}


# =========================================================================
# KB Reindex Resolvers
# =========================================================================


def start_reindex(args):
    """
    Start a Knowledge Base reindex operation.

    Initiates a Step Functions workflow that:
    1. Creates a new Knowledge Base
    2. Re-extracts metadata for all documents
    3. Re-ingests documents into the new KB
    4. Deletes the old KB

    This is an admin-only operation (requires Cognito auth).

    Returns:
        ReindexJob with executionArn, status, and startedAt
    """
    logger.info("Starting KB reindex operation")

    if not REINDEX_STATE_MACHINE_ARN:
        logger.error("REINDEX_STATE_MACHINE_ARN not configured")
        raise ValueError("Reindex feature is not enabled")

    try:
        # Start the Step Functions execution
        execution_name = f"reindex-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

        response = sfn.start_execution(
            stateMachineArn=REINDEX_STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps({"action": "init"}),
        )

        execution_arn = response["executionArn"]
        started_at = response["startDate"].isoformat()

        logger.info(f"Started reindex execution: {execution_arn}")

        return {
            "executionArn": execution_arn,
            "status": "PENDING",
            "startedAt": started_at,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to start reindex: {error_code} - {error_msg}")

        if error_code == "ExecutionAlreadyExists":
            raise ValueError("A reindex operation is already in progress") from e

        raise ValueError(f"Failed to start reindex: {error_msg}") from e
    except Exception as e:
        logger.error(f"Unexpected error starting reindex: {e}")
        raise ValueError(f"Failed to start reindex: {str(e)}") from e
