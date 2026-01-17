"""
Ingest to Knowledge Base Lambda

Calls Bedrock Agent to ingest a document directly into the Knowledge Base.
Bedrock handles embedding generation and S3 Vectors indexing automatically.

This Lambda also extracts metadata using LLM classification and includes
it as inline attributes for the Knowledge Base, enabling metadata-filtered
searches.

Input event:
{
    "document_id": "abc123",
    "output_s3_uri": "s3://output-bucket/abc123/full_text.txt"
}

Output:
{
    "document_id": "abc123",
    "status": "INDEXED",
    "ingestion_status": "STARTING",
    "metadata_extracted": true
}
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from ragstack_common.appsync import publish_document_update
from ragstack_common.config import (
    get_config_manager_or_none,
    get_knowledge_base_config,
)
from ragstack_common.ingestion import check_document_status, ingest_documents_with_retry
from ragstack_common.key_library import KeyLibrary
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.metadata_normalizer import reduce_metadata
from ragstack_common.storage import (
    read_s3_text,
    write_metadata_to_s3,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent = boto3.client("bedrock-agent")
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

# Lazy-initialized singletons (reused across invocations)
_key_library = None
_metadata_extractor = None


def get_key_library() -> KeyLibrary:
    """Get or create KeyLibrary singleton."""
    global _key_library
    if _key_library is None:
        table_name = os.environ.get("METADATA_KEY_LIBRARY_TABLE")
        if table_name:
            _key_library = KeyLibrary(table_name=table_name)
        else:
            logger.warning("METADATA_KEY_LIBRARY_TABLE not set, using default initialization")
            _key_library = KeyLibrary()
    return _key_library


def get_metadata_extractor() -> MetadataExtractor:
    """
    Get or create MetadataExtractor singleton.

    Uses configuration options for model ID, max keys, extraction mode, and manual keys.
    """
    global _metadata_extractor
    if _metadata_extractor is None:
        # Get configuration options
        config = get_config_manager_or_none()
        model_id = None
        max_keys = None
        extraction_mode = "auto"
        manual_keys = None

        if config:
            model_id = config.get_parameter("metadata_extraction_model")
            max_keys = config.get_parameter("metadata_max_keys")
            extraction_mode = config.get_parameter("metadata_extraction_mode", default="auto")
            manual_keys = config.get_parameter("metadata_manual_keys")

        # Log the extraction mode configuration
        logger.info(
            f"Creating MetadataExtractor with mode: {extraction_mode}, manual_keys: {manual_keys}"
        )

        _metadata_extractor = MetadataExtractor(
            key_library=get_key_library(),
            model_id=model_id,
            max_keys=max_keys if max_keys else 8,
            extraction_mode=extraction_mode,
            manual_keys=manual_keys,
        )
    return _metadata_extractor


def is_metadata_extraction_enabled() -> bool:
    """Check if metadata extraction is enabled in configuration."""
    config = get_config_manager_or_none()
    if config is None:
        return True  # Default to enabled if config not available

    return config.get_parameter("metadata_extraction_enabled", default=True)


def build_inline_attributes(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert metadata dictionary to Bedrock KB inline attributes format.

    Args:
        metadata: Dictionary of metadata key-value pairs.

    Returns:
        List of inline attribute objects for Bedrock KB API.
    """
    attributes = []

    for key, value in metadata.items():
        # Skip None or empty values
        if value is None or (isinstance(value, str) and not value.strip()):
            continue

        # Convert value to string for Bedrock KB
        if isinstance(value, bool):
            str_value = str(value).lower()
        elif isinstance(value, (int, float)):
            str_value = str(value)
        elif isinstance(value, list):
            str_value = ", ".join(str(v) for v in value[:5])
        else:
            str_value = str(value)[:100]  # Truncate long values

        attributes.append({"key": key, "value": {"type": "STRING", "stringValue": str_value}})

    return attributes


def check_existing_metadata(output_s3_uri: str) -> dict[str, Any] | None:
    """
    Check if a metadata file already exists for this document.

    Scraped documents have their metadata pre-written by scrape_process.
    If metadata exists, return it; otherwise return None.

    Args:
        output_s3_uri: S3 URI of the content file.

    Returns:
        Metadata dictionary if file exists, None otherwise.
    """
    if not output_s3_uri.startswith("s3://"):
        return None

    path = output_s3_uri[5:]
    bucket, key = path.split("/", 1)
    metadata_key = f"{key}.metadata.json"

    try:
        response = s3_client.get_object(Bucket=bucket, Key=metadata_key)
        content = json.loads(response["Body"].read().decode("utf-8"))
        metadata = content.get("metadataAttributes", {})
        logger.info(f"Found existing metadata file: {metadata_key} with {len(metadata)} fields")
        return metadata
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchKey":
            return None
        logger.warning(f"Error checking for existing metadata: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error checking for existing metadata: {e}")
        return None


def extract_document_metadata(
    output_s3_uri: str,
    document_id: str,
) -> dict[str, Any]:
    """
    Extract metadata from document text using LLM.

    Args:
        output_s3_uri: S3 URI to the document text file.
        document_id: Document identifier.

    Returns:
        Dictionary of extracted metadata, or empty dict on failure.
    """
    try:
        # Read document text from S3
        text = read_s3_text(output_s3_uri)

        if not text or not text.strip():
            logger.warning(f"Empty document text for {document_id}")
            return {}

        # Extract metadata using LLM
        extractor = get_metadata_extractor()
        metadata = extractor.extract_metadata(text, document_id)

        logger.info(f"Extracted metadata for {document_id}: {list(metadata.keys())}")
        return metadata

    except Exception as e:
        logger.warning(f"Failed to extract metadata for {document_id}: {e}")
        return {}


def lambda_handler(event, context):
    """Ingest document into Knowledge Base via Bedrock Agent API."""
    # Get KB config from config table (with env var fallback)
    config = get_config_manager_or_none()
    kb_id, ds_id = get_knowledge_base_config(config)
    tracking_table_name = os.environ.get("TRACKING_TABLE")

    if not tracking_table_name:
        raise ValueError("TRACKING_TABLE environment variable is required")

    # Extract document info from event
    document_id = event.get("document_id")
    output_s3_uri = event.get("output_s3_uri")
    force_extraction = event.get("force_extraction", False)

    if not document_id or not output_s3_uri:
        raise ValueError("document_id and output_s3_uri are required in event")

    logger.info(f"Ingesting document {document_id} from {output_s3_uri}")
    if force_extraction:
        logger.info("Force extraction enabled - will re-extract metadata")

    # Get DynamoDB table
    tracking_table = dynamodb.Table(tracking_table_name)

    # Fetch document details first (needed for base metadata and publishing)
    doc_response = tracking_table.get_item(Key={"document_id": document_id})
    doc_item = doc_response.get("Item", {})
    filename = doc_item.get("filename", "unknown")
    total_pages = doc_item.get("total_pages", 0)

    # Check for existing metadata (e.g., from scrape_process)
    # If found and not forcing extraction, skip LLM extraction and use existing metadata
    existing_metadata = None
    if not force_extraction:
        existing_metadata = check_existing_metadata(output_s3_uri)
    llm_metadata_extracted = False

    # LLM-extracted metadata: written to S3 for KB filtering AND stored in DynamoDB
    # Base fields (document_id, etc.) already in tracking table - no duplication
    llm_metadata = {}

    if existing_metadata:
        # Use pre-existing metadata (scraped documents have metadata from scrape_process)
        logger.info(f"Using existing metadata for {document_id}, skipping LLM extraction")
        llm_metadata = existing_metadata
    else:
        # Extract LLM-based metadata if enabled
        if is_metadata_extraction_enabled():
            llm_metadata = extract_document_metadata(output_s3_uri, document_id)
            llm_metadata_extracted = bool(llm_metadata)

    # content_type is a system field - set based on processing pipeline, not LLM
    # Scraped docs have authoritative content_type in existing_metadata (from scrape_process)
    # Regular docs default to "document" (ignore any LLM-extracted content_type)
    if not existing_metadata or "content_type" not in existing_metadata:
        llm_metadata["content_type"] = "document"

    try:
        # Retry loop for ingestion with metadata reduction on failure
        max_retries = 3
        current_metadata = llm_metadata.copy() if llm_metadata else {}
        ingestion_status = "UNKNOWN"
        ingested_metadata = current_metadata

        for attempt in range(max_retries):
            # Build the document object for ingestion
            document = {
                "content": {
                    "dataSourceType": "S3",
                    "s3": {"s3Location": {"uri": output_s3_uri}},
                }
            }

            # Add metadata reference (required for S3 Vectors KB)
            if current_metadata:
                if existing_metadata and attempt == 0:
                    # First attempt with pre-existing metadata file
                    metadata_uri = f"{output_s3_uri}.metadata.json"
                    logger.info(f"Using existing metadata file: {metadata_uri}")
                else:
                    # Write (possibly reduced) metadata to S3
                    metadata_uri = write_metadata_to_s3(output_s3_uri, current_metadata)
                    logger.info(
                        f"Wrote {len(current_metadata)} metadata fields (attempt {attempt + 1}): "
                        f"{metadata_uri}"
                    )

                document["metadata"] = {
                    "type": "S3_LOCATION",
                    "s3Location": {"uri": metadata_uri},
                }

            # Call Bedrock Agent to ingest the document (with retry for conflicts)
            response = ingest_documents_with_retry(
                kb_id=kb_id,
                ds_id=ds_id,
                documents=[document],
            )

            logger.info(
                f"Ingestion response (attempt {attempt + 1}): {json.dumps(response, default=str)}"
            )

            # Check actual ingestion status
            final_status = check_document_status(kb_id, ds_id, output_s3_uri)
            logger.info(f"Document status after ingestion (attempt {attempt + 1}): {final_status}")

            # Success or in-progress - done
            if final_status in ("INDEXED", "STARTING", "IN_PROGRESS"):
                ingestion_status = final_status
                ingested_metadata = current_metadata
                break

            # Failed - try with reduced metadata
            if final_status == "FAILED" and attempt < max_retries - 1:
                reduction_level = attempt + 2  # Start at level 2, then 3
                logger.warning(
                    f"Ingestion failed, retrying with reduced metadata (level {reduction_level})"
                )
                current_metadata = reduce_metadata(llm_metadata, reduction_level)
                continue

            # Final attempt failed or non-retryable status
            ingestion_status = final_status
            ingested_metadata = current_metadata

        # Update document status in DynamoDB to 'indexed'
        # Store actually ingested metadata for reference
        try:
            update_expression = "SET #status = :status, updated_at = :updated_at"
            expression_names = {"#status": "status"}
            expression_values = {
                ":status": "INDEXED",
                ":updated_at": datetime.now(UTC).isoformat(),
            }

            # Store actually ingested metadata for UI display
            if ingested_metadata:
                update_expression += ", extracted_metadata = :metadata"
                expression_values[":metadata"] = ingested_metadata

            tracking_table.update_item(
                Key={"document_id": document_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_names,
                ExpressionAttributeValues=expression_values,
            )
            logger.info(f"Updated document {document_id} status to 'indexed'")

            # Publish real-time update
            graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")
            publish_document_update(
                graphql_endpoint,
                document_id,
                filename,
                "INDEXED",
                total_pages=total_pages,
            )
        except ClientError as e:
            logger.error(f"Failed to update DynamoDB status for {document_id}: {str(e)}")
            # Log the error but don't fail the ingestion
            # The document was successfully ingested

        return {
            "document_id": document_id,
            "status": "INDEXED",
            "ingestion_status": ingestion_status,
            "knowledge_base_id": kb_id,
            "llm_metadata_extracted": llm_metadata_extracted,
            "metadata_keys": list(ingested_metadata.keys()) if ingested_metadata else [],
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to ingest document: {error_code} - {error_msg}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error ingesting document: {str(e)}")
        raise
