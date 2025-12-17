"""
Process ZIP Lambda

Processes ZIP archives containing images and an optional captions.json manifest.
Extracts images, applies captions, and creates tracking records for each image.

Input event (from S3 trigger via EventBridge):
{
    "bucket": "my-bucket",
    "key": "uploads/abc123/archive.zip"
}

The upload_id is extracted from the key (format: uploads/{upload_id}/archive.zip).
The generate_captions flag is retrieved from the tracking record in DynamoDB,
which was set by the createZipUploadUrl resolver.

Output:
{
    "upload_id": "abc123",
    "status": "COMPLETED",
    "total_images": 5,
    "processed_images": 5,
    "failed_images": 0,
    "errors": []
}
"""

import io
import json
import logging
import os
import uuid
import zipfile
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

from ragstack_common.appsync import publish_image_update
from ragstack_common.image import ImageStatus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
bedrock_runtime = boto3.client("bedrock-runtime")

# Supported image extensions
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_CAPTION_LENGTH = 2000


def lambda_handler(event, context):
    """Process ZIP archive and extract images with captions."""
    tracking_table_name = os.environ.get("TRACKING_TABLE")
    data_bucket = os.environ.get("DATA_BUCKET")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    if not tracking_table_name:
        raise ValueError("TRACKING_TABLE environment variable is required")
    if not data_bucket:
        raise ValueError("DATA_BUCKET environment variable is required")

    tracking_table = dynamodb.Table(tracking_table_name)

    # Extract event parameters
    bucket = event.get("bucket")
    key = event.get("key")

    if not bucket or not key:
        raise ValueError("bucket and key are required in event")

    # Extract upload_id from key (format: uploads/{upload_id}/archive.zip)
    upload_id = event.get("upload_id")
    if not upload_id:
        # Parse from key: uploads/{upload_id}/archive.zip
        key_parts = key.split("/")
        if len(key_parts) >= 2 and key_parts[0] == "uploads":
            upload_id = key_parts[1]
        else:
            raise ValueError(f"Cannot extract upload_id from key: {key}")

    # Look up generate_captions from tracking record (set by createZipUploadUrl resolver)
    generate_captions = event.get("generate_captions", False)
    if not generate_captions:
        try:
            tracking_response = tracking_table.get_item(Key={"document_id": upload_id})
            tracking_item = tracking_response.get("Item", {})
            generate_captions = tracking_item.get("generate_captions", False)
            logger.info(f"Retrieved generate_captions={generate_captions} from tracking record")
        except ClientError as e:
            logger.warning(f"Could not retrieve tracking record for {upload_id}: {e}")

    logger.info(f"Processing ZIP: upload_id={upload_id}, key={key}, generate_captions={generate_captions}")

    result = {
        "upload_id": upload_id,
        "status": "PROCESSING",
        "total_images": 0,
        "processed_images": 0,
        "failed_images": 0,
        "errors": [],
    }

    try:
        # Download ZIP file from S3
        zip_response = s3.get_object(Bucket=bucket, Key=key)
        zip_bytes = zip_response["Body"].read()
        zip_buffer = io.BytesIO(zip_bytes)

        with zipfile.ZipFile(zip_buffer, "r") as zip_file:
            # Parse captions.json if present
            captions = {}
            if "captions.json" in zip_file.namelist():
                try:
                    captions_data = zip_file.read("captions.json")
                    captions = json.loads(captions_data.decode("utf-8"))
                    logger.info(f"Loaded captions for {len(captions)} files")
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"Failed to parse captions.json: {e}")
                    result["errors"].append(f"Failed to parse captions.json: {str(e)}")

            # Find image files
            image_files = [
                name
                for name in zip_file.namelist()
                if is_supported_image(name) and not name.startswith("__MACOSX")
            ]
            result["total_images"] = len(image_files)
            logger.info(f"Found {len(image_files)} images in ZIP")

            # Process each image
            for filename in image_files:
                try:
                    image_data = zip_file.read(filename)
                    base_filename = os.path.basename(filename)

                    # Get caption from manifest
                    user_caption = captions.get(filename) or captions.get(base_filename)

                    # Generate AI caption if requested and no user caption
                    ai_caption = None
                    if generate_captions:
                        try:
                            ai_caption = generate_image_caption(image_data, base_filename)
                        except Exception as e:
                            logger.warning(f"Failed to generate caption for {filename}: {e}")

                    # Combine captions
                    final_caption = combine_captions(user_caption, ai_caption)

                    # Create image record
                    image_id = create_image_record(
                        tracking_table=tracking_table,
                        data_bucket=data_bucket,
                        image_data=image_data,
                        filename=base_filename,
                        caption=final_caption,
                        user_caption=user_caption,
                        ai_caption=ai_caption,
                        upload_id=upload_id,
                    )

                    # Publish real-time update
                    if graphql_endpoint:
                        try:
                            publish_image_update(
                                graphql_endpoint,
                                image_id,
                                base_filename,
                                ImageStatus.PENDING.value,
                                caption=final_caption,
                            )
                        except Exception as e:
                            logger.warning(f"Failed to publish image update: {e}")

                    result["processed_images"] += 1
                    logger.info(f"Processed image: {filename} -> {image_id}")

                except Exception as e:
                    result["failed_images"] += 1
                    error_msg = f"Failed to process {filename}: {str(e)}"
                    result["errors"].append(error_msg)
                    logger.error(error_msg, exc_info=True)

        result["status"] = "COMPLETED" if result["failed_images"] == 0 else "COMPLETED_WITH_ERRORS"

    except zipfile.BadZipFile as e:
        result["status"] = "FAILED"
        result["errors"].append(f"Invalid ZIP file: {str(e)}")
        logger.error(f"Invalid ZIP file: {e}")

    except ClientError as e:
        result["status"] = "FAILED"
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        result["errors"].append(f"S3 error: {error_msg}")
        logger.error(f"S3 error: {e}")

    except Exception as e:
        result["status"] = "FAILED"
        result["errors"].append(f"Unexpected error: {str(e)}")
        logger.error(f"Unexpected error: {e}", exc_info=True)

    logger.info(f"ZIP processing complete: {result}")
    return result


def is_supported_image(filename: str) -> bool:
    """Check if filename has a supported image extension."""
    ext = os.path.splitext(filename.lower())[1]
    return ext in SUPPORTED_EXTENSIONS


def generate_image_caption(image_data: bytes, filename: str) -> str | None:
    """Generate AI caption for image using Bedrock."""
    model_id = os.environ.get("CAPTION_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

    # Detect content type from filename
    ext = os.path.splitext(filename.lower())[1]
    content_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = content_type_map.get(ext, "image/jpeg")

    import base64

    image_base64 = base64.b64encode(image_data).decode("utf-8")

    try:
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": image_base64,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": "Describe this image in 1-2 sentences for use as a search caption. Focus on the main subject and key visual elements.",
                                },
                            ],
                        }
                    ],
                }
            ),
        )

        response_body = json.loads(response["body"].read())
        content = response_body.get("content", [])
        if content and content[0].get("type") == "text":
            caption = content[0].get("text", "").strip()
            return caption[:MAX_CAPTION_LENGTH] if caption else None

    except Exception as e:
        logger.warning(f"Caption generation failed: {e}")

    return None


def combine_captions(user_caption: str | None, ai_caption: str | None) -> str:
    """Combine user and AI captions, user first."""
    parts = []
    if user_caption:
        parts.append(user_caption.strip())
    if ai_caption:
        parts.append(ai_caption.strip())
    return ". ".join(parts) if parts else ""


def create_image_record(
    tracking_table,
    data_bucket: str,
    image_data: bytes,
    filename: str,
    caption: str,
    user_caption: str | None,
    ai_caption: str | None,
    upload_id: str,
) -> str:
    """Create tracking record and upload image to S3."""
    image_id = str(uuid.uuid4())
    timestamp = datetime.now(UTC).isoformat()

    # Detect content type
    ext = os.path.splitext(filename.lower())[1]
    content_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    content_type = content_type_map.get(ext, "application/octet-stream")

    # Upload image to S3
    image_key = f"images/{image_id}/{filename}"
    s3.put_object(
        Bucket=data_bucket,
        Key=image_key,
        Body=image_data,
        ContentType=content_type,
    )

    # Create metadata.json
    metadata = {
        "caption": caption,
        "userCaption": user_caption or "",
        "aiCaption": ai_caption or "",
        "filename": filename,
        "sourceUploadId": upload_id,
        "createdAt": timestamp,
    }
    metadata_key = f"images/{image_id}/metadata.json"
    s3.put_object(
        Bucket=data_bucket,
        Key=metadata_key,
        Body=json.dumps(metadata),
        ContentType="application/json",
    )

    # Create tracking record
    tracking_item = {
        "document_id": image_id,
        "type": "image",
        "filename": filename,
        "status": ImageStatus.PENDING.value,
        "caption": caption,
        "user_caption": user_caption or "",
        "ai_caption": ai_caption or "",
        "input_s3_uri": f"s3://{data_bucket}/{image_key}",
        "content_type": content_type,
        "file_size": len(image_data),
        "source_upload_id": upload_id,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    tracking_table.put_item(Item=tracking_item)

    logger.info(f"Created image record: {image_id}")
    return image_id
