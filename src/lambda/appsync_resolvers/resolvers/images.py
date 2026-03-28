"""Image resolver functions for AppSync Lambda handler.

Handles image upload, caption generation, submit, list, get, delete,
and ZIP archive upload operations.
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from botocore.exceptions import ClientError

from ragstack_common.config import ConfigurationManager
from ragstack_common.demo_mode import (
    demo_quota_check_and_increment,
    get_demo_upload_conditions,
    is_demo_mode_enabled,
)
from ragstack_common.image import ImageStatus, is_supported_image, validate_image_type
from ragstack_common.storage import is_valid_uuid, parse_s3_uri
from resolvers.shared import (
    CONFIGURATION_TABLE_NAME,
    DATA_BUCKET,
    MAX_DOCUMENTS_LIMIT,
    MAX_FILENAME_LENGTH,
    PROCESS_IMAGE_FUNCTION_ARN,
    TRACKING_TABLE,
    bedrock_runtime,
    check_reindex_lock,
    dynamodb,
    dynamodb_client,
    generate_presigned_download_url,
    get_config_manager,
    get_current_user_id,
    lambda_client,
    s3,
)

logger = logging.getLogger()


def create_image_upload_url(args: dict[str, Any]) -> dict[str, Any]:
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

        # Check for path traversal and JSON-unsafe characters
        if "/" in filename or "\\" in filename or ".." in filename or '"' in filename:
            logger.warning(f"Filename contains invalid characters: {filename}")
            raise ValueError("Filename contains invalid characters")

        # Validate it's a supported image type
        if not is_supported_image(filename):
            logger.warning(f"Unsupported image type: {filename}")
            is_valid, error_msg = validate_image_type(None, filename)
            if not is_valid:
                raise ValueError(error_msg)
            # Fallback error if is_supported_image fails but validate_image_type passes
            raise ValueError("Unsupported image file type")

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

        image_id = str(uuid4())
        logger.info(f"Generated image ID: {image_id}")

        # Generate S3 key with content/ prefix (unified for all KB content)
        s3_key = f"content/{image_id}/{filename}"

        # Build presigned POST conditions and fields
        # Include metadata for auto-processing if requested
        conditions: list[Any] = []
        fields: dict[str, str] = {}

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


def generate_caption(args: dict[str, Any]) -> dict[str, Any]:
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
        try:
            bucket, key = parse_s3_uri(image_s3_uri)
        except ValueError:
            return {"caption": None, "error": "Invalid S3 URI format. Must be s3://bucket/key"}

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


def submit_image(args: dict[str, Any]) -> dict[str, Any] | None:
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
        if str(item.get("type", "")) != "image":
            raise ValueError("Record is not an image")

        # Verify status is PENDING
        if str(item.get("status", "")) != ImageStatus.PENDING.value:
            current = str(item.get("status", ""))
            raise ValueError(f"Image is not in PENDING status (current: {current})")

        # Get S3 URI and verify image exists in S3
        input_s3_uri = str(item.get("input_s3_uri", ""))
        if not input_s3_uri.startswith("s3://"):
            raise ValueError("Invalid S3 URI in tracking record")

        # Parse S3 URI
        bucket, key = parse_s3_uri(input_s3_uri)

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
        if not updated_item:
            raise ValueError(f"Image not found after submit: {image_id}")

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


def format_image(item: dict[str, Any]) -> dict[str, Any] | None:
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


def get_image(args: dict[str, Any]) -> dict[str, Any] | None:
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


def list_images(args: dict[str, Any]) -> dict[str, Any]:
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
        scan_kwargs: dict[str, Any] = {
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

        result: dict[str, Any] = {"items": items}
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


def delete_image(args: dict[str, Any]) -> Any:
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
        if str(item.get("type", "")) != "image":
            raise ValueError("Record is not an image")

        input_s3_uri = str(item.get("input_s3_uri", ""))

        # Delete files from S3
        if input_s3_uri and input_s3_uri.startswith("s3://"):
            bucket, image_key = parse_s3_uri(input_s3_uri)
            if image_key:
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


def create_zip_upload_url(args: dict[str, Any]) -> dict[str, Any]:
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
