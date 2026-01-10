"""
Reindex Knowledge Base Lambda Handler.

Handles the reindex workflow for regenerating Knowledge Base content:
1. Create new KB with S3 Vectors
2. Re-ingest all documents with fresh metadata
3. Delete old KB on success

This Lambda is invoked by Step Functions at different stages of the workflow.
"""

import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import boto3
from kb_migrator import KBMigrator

from ragstack_common.appsync import publish_reindex_update
from ragstack_common.config import ConfigurationManager
from ragstack_common.key_library import KeyLibrary
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.storage import read_s3_text

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb = boto3.resource("dynamodb")
bedrock_agent = boto3.client("bedrock-agent")
s3_client = boto3.client("s3")

# Lazy-initialized singletons
_key_library = None
_metadata_extractor = None
_config_manager = None


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
        # Publish failure update
        graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")
        if graphql_endpoint:
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

    1. Count documents to reindex
    2. Create new Knowledge Base
    3. Return initial state for processing loop
    """
    tracking_table_name = os.environ.get("TRACKING_TABLE")
    data_bucket = os.environ.get("DATA_BUCKET")
    vector_bucket = os.environ.get("VECTOR_BUCKET")
    stack_name = os.environ.get("STACK_NAME")
    kb_role_arn = os.environ.get("KB_ROLE_ARN")
    embedding_model_arn = os.environ.get("EMBEDDING_MODEL_ARN")
    old_kb_id = os.environ.get("KNOWLEDGE_BASE_ID")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    # Publish starting status
    publish_reindex_update(
        graphql_endpoint,
        status="PENDING",
        total_documents=0,
        processed_count=0,
    )

    # Count documents to reindex (excluding images and scraped - they have their own types)
    tracking_table = dynamodb.Table(tracking_table_name)
    documents = list_all_documents(tracking_table)

    total_documents = len(documents)
    logger.info(f"Found {total_documents} documents to reindex")

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
    Process a batch of documents.

    Re-extracts metadata and ingests each document into the new KB.
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

    # Get documents for this batch
    tracking_table = dynamodb.Table(tracking_table_name)
    documents = list_all_documents(tracking_table)

    batch_start = current_batch_index * batch_size
    batch_end = min(batch_start + batch_size, len(documents))
    batch_docs = documents[batch_start:batch_end]

    logger.info(f"Processing batch {current_batch_index}: documents {batch_start}-{batch_end}")

    # Process each document in the batch
    for doc in batch_docs:
        doc_id = doc.get("document_id")
        filename = doc.get("filename", "unknown")
        output_s3_uri = doc.get("output_s3_uri")

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
            if not output_s3_uri:
                logger.warning(f"Document {doc_id} has no output_s3_uri, skipping")
                processed_count += 1
                continue

            # Re-extract metadata
            metadata = extract_document_metadata(output_s3_uri, doc_id)

            # Add base metadata
            metadata["content_type"] = "document"

            # Write metadata to S3
            metadata_uri = write_metadata_to_s3(output_s3_uri, metadata, data_bucket)

            # Ingest to new KB
            ingest_document(new_kb_id, new_ds_id, output_s3_uri, metadata_uri)

            processed_count += 1
            logger.info(f"Reindexed document {doc_id}: {filename}")

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        except Exception as e:
            error_count += 1
            error_msg = f"{filename}: {str(e)[:100]}"
            error_messages.append(error_msg)
            logger.error(f"Failed to reindex {doc_id}: {e}")
            processed_count += 1  # Count as processed even if failed

    # Check if more batches to process
    if batch_end < len(documents):
        # More documents to process
        return {
            **event,
            "action": "process_batch",
            "processed_count": processed_count,
            "error_count": error_count,
            "error_messages": error_messages,
            "current_batch_index": current_batch_index + 1,
        }
    # All documents processed, move to finalize
    return {
        **event,
        "action": "finalize",
        "processed_count": processed_count,
        "error_count": error_count,
        "error_messages": error_messages,
    }


def handle_finalize(event: dict) -> dict:
    """
    Finalize the reindex operation.

    1. Update configuration with new KB ID
    2. Delete old KB
    3. Publish completion status
    """
    old_kb_id = event.get("old_kb_id")
    new_kb_id = event["new_kb_id"]
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

    return {
        "status": "FAILED",
        "error_message": error_message,
    }


def list_all_documents(tracking_table) -> list[dict]:
    """
    List all documents from tracking table (excluding images and scraped pages).

    Returns:
        List of document items
    """
    documents = []
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

    while True:
        response = tracking_table.scan(**scan_kwargs)
        documents.extend(response.get("Items", []))

        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    return documents


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


def write_metadata_to_s3(output_s3_uri: str, metadata: dict, data_bucket: str) -> str:
    """
    Write metadata to S3 as a .metadata.json file.

    Args:
        output_s3_uri: S3 URI of the content file
        metadata: Dictionary of metadata
        data_bucket: S3 bucket name

    Returns:
        S3 URI of the metadata file
    """
    if not output_s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {output_s3_uri}")

    path = output_s3_uri[5:]  # Remove 's3://'
    bucket, key = path.split("/", 1)

    metadata_key = f"{key}.metadata.json"
    metadata_uri = f"s3://{bucket}/{metadata_key}"

    metadata_content = {"metadataAttributes": metadata}

    s3_client.put_object(
        Bucket=bucket,
        Key=metadata_key,
        Body=json.dumps(metadata_content),
        ContentType="application/json",
    )

    logger.info(f"Wrote metadata to {metadata_uri}")
    return metadata_uri


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

    response = bedrock_agent.ingest_knowledge_base_documents(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id,
        documents=[document],
    )

    doc_details = response.get("documentDetails", [])
    if doc_details:
        status = doc_details[0].get("status", "UNKNOWN")
        logger.info(f"Ingested document: {content_uri}, status: {status}")
