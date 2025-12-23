"""
Process Image Lambda

Processes uploaded images using Nova Multimodal Embeddings. Ingests BOTH:
1. The actual image file - for visual similarity search
2. Caption text - for semantic text search

Both vectors share the same image_id, enabling cross-modal retrieval.

Trigger modes:
1. metadata.json upload (web-UI): User provides caption via submitImage
2. auto_process (API/MCP): AI generates caption automatically

Input event (from Step Functions or S3 trigger):
{
    "image_id": "abc123" or "images/abc123/image.jpg",
    "input_s3_uri": "s3://bucket/images/abc123/image.png",
    "trigger_type": "auto_process" (optional, for API/MCP uploads)
}

Output:
{
    "image_id": "abc123",
    "status": "INDEXED",
    "image_ingestion_status": "STARTING",
    "caption_ingestion_status": "STARTING"
}
"""

import json
import logging
import os
import re
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

from ragstack_common.appsync import publish_image_update
from ragstack_common.config import ConfigurationManager
from ragstack_common.image import ImageStatus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent = boto3.client("bedrock-agent")
bedrock_runtime = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

# Configuration table name (optional, for getting chat model)
CONFIGURATION_TABLE_NAME = os.environ.get("CONFIGURATION_TABLE_NAME")


def is_valid_uuid(value: str) -> bool:
    """Check if string is a valid UUID format."""
    try:
        import uuid
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def lambda_handler(event, context):
    """Process image and ingest into Knowledge Base."""
    # Get environment variables
    kb_id = os.environ.get("KNOWLEDGE_BASE_ID")
    ds_id = os.environ.get("DATA_SOURCE_ID")
    tracking_table_name = os.environ.get("TRACKING_TABLE")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    if not kb_id or not ds_id:
        raise ValueError("KNOWLEDGE_BASE_ID and DATA_SOURCE_ID environment variables are required")

    if not tracking_table_name:
        raise ValueError("TRACKING_TABLE environment variable is required")

    # Extract image info from event
    # EventBridge passes image_id as path like "images/{imageId}/file.ext"
    raw_image_id = event.get("image_id", "")
    input_s3_uri = event.get("input_s3_uri", "")
    trigger_type = event.get("trigger_type", "")

    # Supported image extensions
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

    # Parse imageId from the key path
    image_id = None
    if raw_image_id:
        # Skip non-image files (metadata.json, caption.txt, etc.)
        ext = raw_image_id.lower().rsplit(".", 1)[-1] if "." in raw_image_id else ""
        if f".{ext}" not in IMAGE_EXTENSIONS:
            logger.info(f"Skipping non-image file: {raw_image_id}")
            return {"status": "SKIPPED", "message": "Not an image file"}

        # Handle paths like "images/abc123/image.jpg"
        match = re.match(r"images/([^/]+)/", raw_image_id)
        if match:
            image_id = match.group(1)
        elif "/" not in raw_image_id:
            # Direct image ID (UUID format)
            image_id = raw_image_id
        else:
            # Path doesn't match expected format - skip silently
            logger.info(f"Ignoring non-images path: {raw_image_id}")
            return {"status": "SKIPPED", "message": "Not an images/ path"}

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

        filename = item.get("filename", "unknown")
        caption = item.get("caption", "")
        auto_process = item.get("auto_process", False)
        user_caption = item.get("user_caption", "")

        # Handle auto_process trigger (API/MCP uploads)
        if trigger_type == "auto_process":
            if not auto_process:
                # Image uploaded but auto-process not requested - skip
                logger.info(f"Skipping image {image_id}: auto_process not enabled")
                return {
                    "image_id": image_id,
                    "status": "SKIPPED",
                    "message": "auto_process not enabled, waiting for submitImage",
                }

            # Auto-process enabled - generate caption if not provided
            if not caption and not user_caption:
                logger.info(f"Generating AI caption for image {image_id}")
                input_s3_uri = item.get("input_s3_uri", "")
                generated_caption = generate_ai_caption(input_s3_uri)
                if generated_caption:
                    caption = generated_caption
                    # Update DynamoDB with generated caption
                    update_expr = (
                        "SET caption = :caption, ai_caption = :ai_caption, updated_at = :updated_at"
                    )
                    tracking_table.update_item(
                        Key={"document_id": image_id},
                        UpdateExpression=update_expr,
                        ExpressionAttributeValues={
                            ":caption": caption,
                            ":ai_caption": caption,
                            ":updated_at": datetime.now(UTC).isoformat(),
                        },
                    )
                    logger.info(f"Generated caption for {image_id}: {caption[:100]}...")
            elif user_caption and not caption:
                # Use user-provided caption
                caption = user_caption
                tracking_table.update_item(
                    Key={"document_id": image_id},
                    UpdateExpression="SET caption = :caption, updated_at = :updated_at",
                    ExpressionAttributeValues={
                        ":caption": caption,
                        ":updated_at": datetime.now(UTC).isoformat(),
                    },
                )

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

        # Get or create metadata file
        # Metadata key: images/{imageId}/metadata.json
        key_parts = image_key.rsplit("/", 1)
        base_path = key_parts[0] if len(key_parts) > 1 else image_key
        metadata_key = f"{base_path}/metadata.json"

        metadata = {}
        try:
            metadata_response = s3.get_object(Bucket=bucket, Key=metadata_key)
            metadata = json.loads(metadata_response["Body"].read().decode("utf-8"))
            logger.info(f"Found existing metadata: {metadata_key}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                # Create default metadata if not exists
                logger.info(f"Creating default metadata for image: {image_id}")
                metadata = {
                    "caption": caption,
                    "filename": filename,
                    "createdAt": datetime.now(UTC).isoformat(),
                }
                s3.put_object(
                    Bucket=bucket,
                    Key=metadata_key,
                    Body=json.dumps(metadata),
                    ContentType="application/json",
                )
            else:
                raise

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

        # Ingest BOTH the image and caption into KB
        # Nova Multimodal Embeddings will:
        # 1. Generate visual embedding from the image file
        # 2. Generate text embedding from the caption
        # Both vectors are in the same semantic space for cross-modal search
        documents_to_ingest = [
            # Image file - for visual similarity search
            {"content": {"dataSourceType": "S3", "s3": {"s3Location": {"uri": input_s3_uri}}}},
            # Caption text - for semantic text search
            {"content": {"dataSourceType": "S3", "s3": {"s3Location": {"uri": text_s3_uri}}}},
        ]

        ingest_response = bedrock_agent.ingest_knowledge_base_documents(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            documents=documents_to_ingest,
        )

        logger.info(f"Ingestion response: {json.dumps(ingest_response, default=str)}")

        # Extract status for both documents
        doc_details = ingest_response.get("documentDetails", [])
        image_ingestion_status = "UNKNOWN"
        caption_ingestion_status = "UNKNOWN"
        if len(doc_details) >= 1:
            image_ingestion_status = doc_details[0].get("status", "UNKNOWN")
        if len(doc_details) >= 2:
            caption_ingestion_status = doc_details[1].get("status", "UNKNOWN")

        # Log warning if any ingestion didn't start as expected
        expected_statuses = ("STARTING", "IN_PROGRESS", "INDEXED")
        if image_ingestion_status not in expected_statuses:
            logger.warning(f"Image ingestion status unexpected: {image_ingestion_status}")
        if caption_ingestion_status not in expected_statuses:
            logger.warning(f"Caption ingestion status unexpected: {caption_ingestion_status}")

        # Update image status in DynamoDB
        # Store both URIs - image for display, caption for reference
        update_expr = (
            "SET #status = :status, updated_at = :updated_at, "
            "output_s3_uri = :output_uri, caption_s3_uri = :caption_uri"
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
            "image_ingestion_status": image_ingestion_status,
            "caption_ingestion_status": caption_ingestion_status,
            "knowledge_base_id": kb_id,
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
                update_expr = "SET #status = :status, error_message = :error, updated_at = :updated_at"
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


def generate_ai_caption(s3_uri: str) -> str:
    """
    Generate an AI caption for an image using Bedrock vision model.

    Args:
        s3_uri: S3 URI of the image (s3://bucket/key)

    Returns:
        Generated caption text, or empty string on failure
    """
    try:
        # Parse S3 URI
        uri_path = s3_uri.replace("s3://", "")
        parts = uri_path.split("/", 1)
        if len(parts) != 2:
            logger.error(f"Invalid S3 URI for caption generation: {s3_uri}")
            return ""

        bucket, key = parts

        # Get image from S3
        response = s3.get_object(Bucket=bucket, Key=key)
        image_bytes = response["Body"].read()

        # Determine image format from extension
        ext = key.lower().rsplit(".", 1)[-1] if "." in key else "jpeg"
        if ext == "jpg":
            ext = "jpeg"  # Normalize for Bedrock API

        # Get caption model from config - use same model as chat/query
        caption_model = "anthropic.claude-haiku-4-5-20251001-v1:0"
        if CONFIGURATION_TABLE_NAME:
            try:
                config_mgr = ConfigurationManager(CONFIGURATION_TABLE_NAME)
                caption_model = config_mgr.get_parameter("chat_primary_model", caption_model)
            except Exception as e:
                logger.warning(f"Failed to get caption model from config: {e}")

        # Call Bedrock Converse API with vision

        converse_response = bedrock_runtime.converse(
            modelId=caption_model,
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
                                "Describe this image in detail for semantic search indexing. "
                                "Include: main subjects, setting, colors, mood, any text visible, "
                                "and notable details. Be thorough but concise (2-4 sentences)."
                            )
                        },
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 300, "temperature": 0.3},
        )

        # Extract caption from response
        output = converse_response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])

        for block in content:
            if "text" in block:
                return block["text"].strip()

        logger.warning("No text content in caption response")
        return ""

    except Exception as e:
        logger.error(f"Failed to generate AI caption: {e}", exc_info=True)
        return ""
