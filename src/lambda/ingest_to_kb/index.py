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
    "status": "indexed",
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
from ragstack_common.config import ConfigurationManager
from ragstack_common.key_library import KeyLibrary
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.storage import read_s3_text

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent = boto3.client("bedrock-agent")
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

# Lazy-initialized singletons (reused across invocations)
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


def is_metadata_extraction_enabled() -> bool:
    """Check if metadata extraction is enabled in configuration."""
    config = get_config_manager()
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


def write_metadata_to_s3(output_s3_uri: str, metadata: dict[str, Any]) -> str:
    """
    Write metadata to S3 as a .metadata.json file alongside the content file.

    For S3 Vectors knowledge bases, metadata must be stored in S3 rather than
    provided inline. The metadata file must be in the same location as the
    content file with .metadata.json suffix.

    Args:
        output_s3_uri: S3 URI of the content file (e.g., s3://bucket/path/file.txt)
        metadata: Dictionary of metadata key-value pairs

    Returns:
        S3 URI of the metadata file
    """
    # Parse S3 URI
    if not output_s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {output_s3_uri}")

    path = output_s3_uri[5:]  # Remove 's3://'
    bucket, key = path.split("/", 1)

    # Create metadata file key (same location with .metadata.json suffix)
    metadata_key = f"{key}.metadata.json"
    metadata_uri = f"s3://{bucket}/{metadata_key}"

    # Build metadata JSON in Bedrock KB format
    metadata_content = {"metadataAttributes": metadata}

    # Write to S3
    s3_client.put_object(
        Bucket=bucket,
        Key=metadata_key,
        Body=json.dumps(metadata_content),
        ContentType="application/json",
    )

    logger.info(f"Wrote metadata to {metadata_uri}")
    return metadata_uri


def get_file_type_from_filename(filename: str) -> str:
    """
    Extract file type from filename.

    Args:
        filename: Original filename.

    Returns:
        File extension without dot, lowercase (e.g., "pdf", "jpg").
    """
    if not filename or "." not in filename:
        return "unknown"
    return filename.rsplit(".", 1)[-1].lower()


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
    # Get environment variables
    kb_id = os.environ.get("KNOWLEDGE_BASE_ID")
    ds_id = os.environ.get("DATA_SOURCE_ID")
    tracking_table_name = os.environ.get("TRACKING_TABLE")

    if not kb_id or not ds_id:
        raise ValueError("KNOWLEDGE_BASE_ID and DATA_SOURCE_ID environment variables are required")

    if not tracking_table_name:
        raise ValueError("TRACKING_TABLE environment variable is required")

    # Extract document info from event
    document_id = event.get("document_id")
    output_s3_uri = event.get("output_s3_uri")

    if not document_id or not output_s3_uri:
        raise ValueError("document_id and output_s3_uri are required in event")

    logger.info(f"Ingesting document {document_id} from {output_s3_uri}")

    # Get DynamoDB table
    tracking_table = dynamodb.Table(tracking_table_name)

    # Fetch document details first (needed for base metadata and publishing)
    doc_response = tracking_table.get_item(Key={"document_id": document_id})
    doc_item = doc_response.get("Item", {})
    filename = doc_item.get("filename", "unknown")
    total_pages = doc_item.get("total_pages", 0)

    # Check for existing metadata (e.g., from scrape_process)
    # If found, skip LLM extraction and use existing metadata
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

    # Add base metadata that's always included for filtering
    # content_type distinguishes documents from images/web_pages
    # Merge order ensures base_metadata wins (cannot be overwritten by LLM)
    base_metadata = {"content_type": "document"}
    llm_metadata = {**llm_metadata, **base_metadata}

    try:
        # Build the document object for ingestion
        document = {
            "content": {
                "dataSourceType": "S3",
                "s3": {"s3Location": {"uri": output_s3_uri}},
            }
        }

        # Add metadata reference (required for S3 Vectors KB)
        # Only LLM-extracted metadata - base fields are already in tracking table
        if llm_metadata:
            if existing_metadata:
                # Metadata file already exists (from scrape_process)
                metadata_uri = f"{output_s3_uri}.metadata.json"
                logger.info(f"Using existing metadata file: {metadata_uri}")
            else:
                # Write LLM metadata to S3 for filtering
                metadata_uri = write_metadata_to_s3(output_s3_uri, llm_metadata)
                logger.info(f"Wrote {len(llm_metadata)} metadata fields to: {metadata_uri}")

            document["metadata"] = {
                "type": "S3_LOCATION",
                "s3Location": {"uri": metadata_uri},
            }

        # Call Bedrock Agent to ingest the document
        # Bedrock will:
        # 1. Read the text from S3
        # 2. Generate embeddings using KB's configured model (Nova Multimodal)
        # 3. Write vectors to S3 Vectors index with metadata
        # 4. Make the document queryable
        response = bedrock_agent.ingest_knowledge_base_documents(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            documents=[document],
        )

        logger.info(f"Ingestion response: {json.dumps(response, default=str)}")

        # Extract status from response
        doc_details = response.get("documentDetails", [])
        ingestion_status = "UNKNOWN"
        if doc_details:
            ingestion_status = doc_details[0].get("status", "UNKNOWN")

        # Update document status in DynamoDB to 'indexed'
        # Store combined metadata for reference
        try:
            update_expression = "SET #status = :status, updated_at = :updated_at"
            expression_names = {"#status": "status"}
            expression_values = {
                ":status": "indexed",
                ":updated_at": datetime.now(UTC).isoformat(),
            }

            # Store LLM-extracted metadata for UI display
            if llm_metadata:
                update_expression += ", extracted_metadata = :metadata"
                expression_values[":metadata"] = llm_metadata

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
            "status": "indexed",
            "ingestion_status": ingestion_status,
            "knowledge_base_id": kb_id,
            "llm_metadata_extracted": llm_metadata_extracted,
            "metadata_keys": list(llm_metadata.keys()) if llm_metadata else [],
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to ingest document: {error_code} - {error_msg}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error ingesting document: {str(e)}")
        raise
