"""
Process Image Lambda

Processes uploaded images and creates files for KB ingestion. Creates:
1. caption.txt + metadata - for semantic text search
2. {filename}.metadata.json - for visual embedding (triggers StartIngestionJob)

Both vectors share the same image_id, enabling cross-modal retrieval.

Trigger modes:
1. metadata.json upload (web-UI): User provides caption via submitImage
2. auto_process (API/MCP): AI generates caption automatically

Input event (from Step Functions or S3 trigger):
{
    "image_id": "abc123" or "content/abc123/image.jpg",
    "input_s3_uri": "s3://bucket/content/abc123/image.png",
    "trigger_type": "auto_process" (optional, for API/MCP uploads)
}

Output:
{
    "image_id": "abc123",
    "status": "INDEXED",
    "llm_metadata_extracted": true,
    "metadata_keys": ["document_id", "filename", ...]
}
"""

import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from ragstack_common.appsync import publish_image_update
from ragstack_common.config import ConfigurationManager, get_knowledge_base_config
from ragstack_common.image import ImageStatus
from ragstack_common.ingestion import start_ingestion_with_retry
from ragstack_common.key_library import KeyLibrary
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.storage import (
    get_file_type_from_filename,
    is_valid_uuid,
    write_metadata_to_s3,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_runtime = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION"))
bedrock_agent = boto3.client("bedrock-agent", region_name=os.environ.get("AWS_REGION"))

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

# Configuration table name (optional, for getting chat model)
CONFIGURATION_TABLE_NAME = os.environ.get("CONFIGURATION_TABLE_NAME")

# Lazy-initialized singletons
_key_library = None
_metadata_extractor = None
_config_manager = None


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


def get_key_library() -> KeyLibrary:
    """Get or create KeyLibrary singleton."""
    global _key_library
    if _key_library is None:
        table_name = os.environ.get("METADATA_KEY_LIBRARY_TABLE")
        _key_library = KeyLibrary(table_name=table_name) if table_name else KeyLibrary()
    return _key_library


def get_metadata_extractor() -> MetadataExtractor:
    """
    Get or create MetadataExtractor singleton.

    Uses configuration options for model ID and max keys.
    """
    global _metadata_extractor
    if _metadata_extractor is None:
        # Get configuration options
        model_id = None
        max_keys = None

        if CONFIGURATION_TABLE_NAME:
            try:
                config = ConfigurationManager(CONFIGURATION_TABLE_NAME)
                model_id = config.get_parameter("metadata_extraction_model")
                max_keys = config.get_parameter("metadata_max_keys")
            except Exception as e:
                logger.warning(f"Failed to get metadata extraction config: {e}")

        _metadata_extractor = MetadataExtractor(
            key_library=get_key_library(),
            model_id=model_id,
            max_keys=max_keys if max_keys else 8,
        )
    return _metadata_extractor


def get_base_image_metadata(
    image_id: str,
    filename: str,
    input_s3_uri: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    """
    Create base metadata fields for images.

    Args:
        image_id: Image identifier.
        filename: Original filename.
        input_s3_uri: S3 URI of the image file.
        item: DynamoDB tracking record.

    Returns:
        Dictionary of base metadata fields.
    """
    file_type = get_file_type_from_filename(filename)

    base_metadata = {
        "document_id": image_id,
        "filename": filename,
        "file_type": file_type,
        "s3_uri": input_s3_uri,
        "content_type": "image",
    }

    if item.get("created_at"):
        base_metadata["created_at"] = item["created_at"]

    if item.get("user_caption"):
        base_metadata["has_user_caption"] = "true"

    if item.get("ai_caption"):
        base_metadata["has_ai_caption"] = "true"

    return base_metadata


def extract_image_metadata(
    caption: str,
    image_id: str,
    filename: str,
) -> dict[str, Any]:
    """
    Extract metadata from image caption using LLM.

    Args:
        caption: Combined caption text.
        image_id: Image identifier.
        filename: Original filename.

    Returns:
        Dictionary of extracted metadata, or empty dict on failure.
    """
    if not caption or not caption.strip():
        return {}

    try:
        extractor = get_metadata_extractor()
        metadata = extractor.extract_from_caption(
            caption=caption,
            document_id=image_id,
            filename=filename,
        )
        if metadata:
            logger.info(f"Extracted metadata for image {image_id}: {list(metadata.keys())}")
        return metadata
    except Exception as e:
        logger.warning(f"Failed to extract metadata for image {image_id}: {e}")
        return {}


def lambda_handler(event, context):
    """Process image and create files for KB ingestion via StartIngestionJob."""
    tracking_table_name = os.environ.get("TRACKING_TABLE")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    if not tracking_table_name:
        raise ValueError("TRACKING_TABLE environment variable is required")

    # Extract image info from event
    # EventBridge passes image_id as path like "content/{imageId}/file.ext"
    # submitImage passes image_id as direct UUID
    raw_image_id = event.get("image_id", "")
    input_s3_uri = event.get("input_s3_uri", "")
    trigger_type = event.get("trigger_type", "")

    # Supported image extensions
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

    # Parse imageId from the key path
    image_id = None
    if raw_image_id:
        # For submit_image trigger, the image_id is already a UUID
        if trigger_type == "submit_image":
            image_id = raw_image_id
        else:
            # Skip non-image files (metadata.json, caption.txt, etc.)
            ext = raw_image_id.lower().rsplit(".", 1)[-1] if "." in raw_image_id else ""
            if f".{ext}" not in IMAGE_EXTENSIONS:
                logger.info(f"Skipping non-image file: {raw_image_id}")
                return {"status": "SKIPPED", "message": "Not an image file"}

            # Handle paths like "content/abc123/image.jpg"
            match = re.match(r"content/([^/]+)/", raw_image_id)
            if match:
                image_id = match.group(1)
            elif "/" not in raw_image_id:
                # Direct image ID (UUID format)
                image_id = raw_image_id
            else:
                # Path doesn't match expected format - skip silently
                logger.info(f"Ignoring non-content path: {raw_image_id}")
                return {"status": "SKIPPED", "message": "Not a content/ path"}

    if not image_id:
        raise ValueError("image_id is required in event (either as path or direct ID)")

    logger.info(f"Processing image {image_id}, raw_id={raw_image_id}, trigger_type={trigger_type}")

    # Get DynamoDB table
    tracking_table = dynamodb.Table(tracking_table_name)

    try:
        # Validate image record exists
        response = tracking_table.get_item(Key={"document_id": image_id})
        item = response.get("Item")

        if not item:
            raise ValueError(f"Image not found in tracking table: {image_id}")

        if item.get("type") != "image":
            raise ValueError(f"Record is not an image type: {image_id}")

        # For auto_process triggers (EventBridge on raw image upload),
        # only process if auto_process=true in DynamoDB (API/MCP uploads).
        # UI uploads should wait for submitImage to trigger processing.
        if trigger_type == "auto_process" and not item.get("auto_process"):
            logger.info(
                f"Skipping image {image_id}: auto_process not enabled, waiting for submitImage"
            )
            return {
                "image_id": image_id,
                "status": "SKIPPED",
                "message": "auto_process not enabled, waiting for submitImage",
            }

        filename = item.get("filename", "unknown")
        caption = item.get("caption", "")
        extract_text = item.get("extract_text", False)

        # Get actual image S3 URI from tracking record (not from event, which has metadata.json)
        input_s3_uri = item.get("input_s3_uri", "")
        if not input_s3_uri:
            raise ValueError(f"No input_s3_uri in tracking record for image: {image_id}")

        # Parse S3 URI to get bucket and key
        uri_path = input_s3_uri.replace("s3://", "")
        parts = uri_path.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {input_s3_uri}")

        bucket = parts[0]
        image_key = parts[1]

        # Verify image exists in S3
        try:
            s3.head_object(Bucket=bucket, Key=image_key)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404" or error_code == "NoSuchKey":
                raise ValueError(f"Image not found in S3: {input_s3_uri}") from e
            raise

        # Extract text from image if requested (OCR)
        extracted_text = ""
        if extract_text:
            logger.info(f"Extracting text from image {image_id}")
            extracted_text = extract_text_from_image(input_s3_uri)
            if extracted_text:
                # Append extracted text to caption
                if caption:
                    caption = f"{caption}\n\nExtracted text:\n{extracted_text}"
                else:
                    caption = f"Extracted text:\n{extracted_text}"
                logger.info(f"Added extracted text to caption for {image_id}")

                # Update DynamoDB with extracted text
                tracking_table.update_item(
                    Key={"document_id": image_id},
                    UpdateExpression="SET caption = :caption, extracted_text = :ext_text, "
                    "updated_at = :updated_at",
                    ExpressionAttributeValues={
                        ":caption": caption,
                        ":ext_text": extracted_text,
                        ":updated_at": datetime.now(UTC).isoformat(),
                    },
                )

        # Get base path for content files
        key_parts = image_key.rsplit("/", 1)
        base_path = key_parts[0] if len(key_parts) > 1 else image_key

        # Build metadata dict from DynamoDB record (no longer using metadata.json file)
        # This prevents KB from incorrectly indexing a standalone metadata.json file
        metadata = {
            "caption": caption,
            "userCaption": item.get("user_caption", ""),
            "aiCaption": item.get("ai_caption", ""),
            "filename": filename,
            "createdAt": item.get("created_at", datetime.now(UTC).isoformat()),
        }

        # Create caption text file for semantic text search
        text_content = build_ingestion_text(image_id, filename, caption, metadata)
        text_key = f"{base_path}/caption.txt"
        text_s3_uri = f"s3://{bucket}/{text_key}"

        s3.put_object(
            Bucket=bucket,
            Key=text_key,
            Body=text_content,
            ContentType="text/plain",
        )
        logger.info(f"Created caption file: {text_s3_uri}")

        # Build metadata for KB filtering
        # Base metadata (always included)
        base_metadata = get_base_image_metadata(image_id, filename, input_s3_uri, item)

        # LLM-extracted metadata from caption
        llm_metadata = extract_image_metadata(caption, image_id, filename)

        # Merge metadata: base fields + LLM-extracted fields
        combined_metadata = {**base_metadata, **llm_metadata}

        # Write metadata to S3 for caption (used for KB filtering)
        # The caption.txt.metadata.json file enables content_type filtering
        caption_metadata_uri = write_metadata_to_s3(text_s3_uri, combined_metadata)
        logger.info(f"Wrote {len(combined_metadata)} metadata fields to: {caption_metadata_uri}")

        # Create image metadata file for KB visual embedding
        # This triggers StartIngestionJob via EventBridge when the image file lands in content/
        # The metadata file must be alongside the image file for KB to pick it up
        visual_metadata = {
            "metadataAttributes": {
                "content_type": "visual",
                "document_id": image_id,
                "media_type": "image",
                "filename": filename,
            }
        }
        image_metadata_key = f"{base_path}/{filename}.metadata.json"
        s3.put_object(
            Bucket=bucket,
            Key=image_metadata_key,
            Body=json.dumps(visual_metadata),
            ContentType="application/json",
        )
        logger.info(f"Created image metadata at s3://{bucket}/{image_metadata_key}")

        # Start KB ingestion job for visual embeddings
        config_manager = get_config_manager()
        kb_id, ds_id = get_knowledge_base_config(config_manager)
        logger.info(f"Starting ingestion for image {image_id}: kb={kb_id}, ds={ds_id}")

        try:
            ingestion_response = start_ingestion_with_retry(kb_id, ds_id)
            job_info = ingestion_response.get("ingestionJob", {})
            job_id = job_info.get("ingestionJobId")
            logger.info(f"Started ingestion job {job_id} for image {image_id}")
        except ClientError as e:
            logger.error(f"Failed to start ingestion for image {image_id}: {e}")
            # Don't fail the whole process - files are created, ingestion can be retried
            job_id = None

        # Update image status in DynamoDB
        # Store URIs and extracted metadata
        update_expr = (
            "SET #status = :status, updated_at = :updated_at, "
            "output_s3_uri = :output_uri, caption_s3_uri = :caption_uri, "
            "extracted_metadata = :metadata"
        )
        tracking_table.update_item(
            Key={"document_id": image_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": ImageStatus.INDEXED.value,
                ":updated_at": datetime.now(UTC).isoformat(),
                ":output_uri": input_s3_uri,  # Original image
                ":caption_uri": text_s3_uri,  # Caption text file
                ":metadata": combined_metadata,
            },
        )
        logger.info(f"Updated image {image_id} status to INDEXED")

        # Publish real-time update
        if graphql_endpoint:
            try:
                publish_image_update(
                    graphql_endpoint,
                    image_id,
                    filename,
                    ImageStatus.INDEXED.value,
                    caption=caption,
                )
            except Exception as e:
                logger.warning(f"Failed to publish image update: {e}")

        return {
            "image_id": image_id,
            "status": ImageStatus.INDEXED.value,
            "llm_metadata_extracted": bool(llm_metadata),
            "metadata_keys": list(combined_metadata.keys()),
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to process image: {error_code} - {error_msg}")

        # Only update tracking if image_id is a valid UUID (prevents ghost entries)
        if is_valid_uuid(image_id):
            try:
                err_update_expr = (
                    "SET #status = :status, error_message = :error, updated_at = :updated_at"
                )
                tracking_table.update_item(
                    Key={"document_id": image_id},
                    UpdateExpression=err_update_expr,
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": ImageStatus.FAILED.value,
                        ":error": error_msg,
                        ":updated_at": datetime.now(UTC).isoformat(),
                    },
                )

                if graphql_endpoint:
                    response = tracking_table.get_item(Key={"document_id": image_id})
                    item = response.get("Item", {})
                    publish_image_update(
                        graphql_endpoint,
                        image_id,
                        item.get("filename", "unknown"),
                        ImageStatus.FAILED.value,
                        error_message=error_msg,
                    )
            except Exception:
                logger.exception("Failed to update error status")

        raise

    except Exception as e:
        logger.error(f"Unexpected error processing image: {str(e)}", exc_info=True)

        # Only update tracking if image_id is a valid UUID (prevents ghost entries)
        if is_valid_uuid(image_id):
            try:
                update_expr = (
                    "SET #status = :status, error_message = :error, updated_at = :updated_at"
                )
                tracking_table.update_item(
                    Key={"document_id": image_id},
                    UpdateExpression=update_expr,
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": ImageStatus.FAILED.value,
                        ":error": str(e),
                        ":updated_at": datetime.now(UTC).isoformat(),
                    },
                )
            except Exception:
                logger.exception("Failed to update error status")

        raise


def build_ingestion_text(image_id: str, filename: str, caption: str, metadata: dict) -> str:
    """
    Build text content for KB ingestion with searchable metadata.

    The text is structured with YAML-like frontmatter for consistent parsing
    when extracting source information during queries.

    Args:
        image_id: Unique image identifier
        filename: Original filename
        caption: Combined caption (user + AI)
        metadata: Additional metadata from metadata.json

    Returns:
        Formatted text content for KB ingestion
    """
    user_caption = metadata.get("userCaption", "")
    ai_caption = metadata.get("aiCaption", "")

    # Build structured text with frontmatter
    lines = [
        "---",
        f"image_id: {image_id}",
        f"filename: {filename}",
        "type: image",
        "source_type: uploaded_image",
    ]

    if user_caption:
        lines.append(f"user_caption: {user_caption}")
    if ai_caption:
        lines.append(f"ai_caption: {ai_caption}")

    lines.append("---")
    lines.append("")

    # Add caption as main searchable content
    if caption:
        lines.append(f"# Image: {filename}")
        lines.append("")
        lines.append(caption)
        lines.append("")

    # Add individual captions for better search matching
    if user_caption and user_caption != caption:
        lines.append(f"User description: {user_caption}")
        lines.append("")

    if ai_caption and ai_caption != caption:
        lines.append(f"AI description: {ai_caption}")
        lines.append("")

    # Add media keywords for better KB query matching
    # These help the KB recognize this content as visual media when users search
    lines.append("---")
    lines.append("Content type: image, picture, photo, photograph, visual, media, graphic, imagery")
    lines.append("This is a visual image file that can be viewed and displayed.")
    lines.append("")

    return "\n".join(lines)


def extract_text_from_image(s3_uri: str) -> str:
    """
    Extract visible text from an image using Bedrock vision model (OCR).

    This is focused purely on text extraction, not image description.
    Used when user checks "Extract text from image" option.

    Args:
        s3_uri: S3 URI of the image (s3://bucket/key)

    Returns:
        Extracted text, or empty string if no text found or on failure
    """
    try:
        # Parse S3 URI
        uri_path = s3_uri.replace("s3://", "")
        parts = uri_path.split("/", 1)
        if len(parts) != 2:
            logger.error(f"Invalid S3 URI for text extraction: {s3_uri}")
            return ""

        bucket, key = parts

        # Get image from S3
        response = s3.get_object(Bucket=bucket, Key=key)
        image_bytes = response["Body"].read()

        # Determine image format from extension
        ext = key.lower().rsplit(".", 1)[-1] if "." in key else "jpeg"
        if ext == "jpg":
            ext = "jpeg"  # Normalize for Bedrock API

        # Get OCR model from config - use same model as chat/query
        ocr_model = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        if CONFIGURATION_TABLE_NAME:
            try:
                config_mgr = ConfigurationManager(CONFIGURATION_TABLE_NAME)
                ocr_model = config_mgr.get_parameter("chat_primary_model", ocr_model)
            except Exception as e:
                logger.warning(f"Failed to get OCR model from config: {e}")

        # Call Bedrock Converse API with OCR-focused prompt
        converse_response = bedrock_runtime.converse(
            modelId=ocr_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": ext if ext in ("png", "gif", "webp", "jpeg") else "jpeg",
                                "source": {"bytes": image_bytes},
                            }
                        },
                        {
                            "text": (
                                "Extract and transcribe ALL visible text from this image. "
                                "Include: signs, labels, captions, memes, documents, "
                                "handwriting, logos, buttons, menus, etc.\n\n"
                                "Output ONLY the extracted text, preserving the layout "
                                "where possible. If no text is visible, respond with 'NO_TEXT'."
                            )
                        },
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 1000, "temperature": 0.1},
        )

        # Extract text from response
        output = converse_response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])

        for block in content:
            if "text" in block:
                extracted = block["text"].strip()
                if extracted == "NO_TEXT":
                    logger.info("No text found in image")
                    return ""
                logger.info(f"Extracted text from image: {extracted[:100]}...")
                return extracted

        logger.warning("No text content in OCR response")
        return ""

    except Exception as e:
        logger.error(f"Failed to extract text from image: {e}", exc_info=True)
        return ""
