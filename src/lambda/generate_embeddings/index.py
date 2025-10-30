"""
Embedding Generator Lambda

Generates text and image embeddings for Knowledge Base indexing.

Input event:
{
    "document_id": "abc123",
    "output_s3_uri": "s3://output-bucket/processed/abc123/full_text.txt",
    "pages": [
        {
            "page_number": 1,
            "image_s3_uri": "s3://output-bucket/processed/abc123/page_1.jpg"
        }
    ],
    "vector_bucket": "ragstack-vectors"
}

Output:
{
    "document_id": "abc123",
    "status": "embedding_complete",
    "text_embedding_uri": "s3://vectors/abc123/text_embedding.json",
    "image_embeddings": [...]
}
"""

import json
import logging
import os
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from ragstack_common.bedrock import BedrockClient
from ragstack_common.config import ConfigurationManager
from ragstack_common.models import Status
from ragstack_common.storage import read_s3_binary, read_s3_text, update_item, write_s3_json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level initialization (reused across Lambda invocations in same container)
config_manager = ConfigurationManager()

# Text length limits (Titan Embed Text V2: max 8192 tokens ≈ 32k chars)
TEXT_CHAR_LIMIT = 30000


def update_re_embed_job_progress(job_id):
    """
    Increment processed count for re-embedding job.

    Args:
        job_id: Re-embedding job ID
    """
    if not job_id:
        return

    try:
        configuration_table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
        if not configuration_table_name:
            logger.warning("CONFIGURATION_TABLE_NAME not set, skipping job progress update")
            return

        dynamodb = boto3.resource("dynamodb")
        configuration_table = dynamodb.Table(configuration_table_name)

        # Use composite key to update the correct job
        job_key = f"ReEmbedJob#{job_id}"

        # Increment processedDocuments (conditional to prevent phantom job creation)
        response = configuration_table.update_item(
            Key={"Configuration": job_key},
            UpdateExpression="ADD processedDocuments :inc",
            ExpressionAttributeValues={":inc": 1},
            ConditionExpression="attribute_exists(#pk)",  # Require job item to exist
            ExpressionAttributeNames={"#pk": "Configuration"},
            ReturnValues="ALL_NEW",
        )

        item = response.get("Attributes", {})
        processed = item.get("processedDocuments", 0)
        total = item.get("totalDocuments", 0)

        logger.info(f"Re-embed job {job_id} progress: {processed}/{total}")

        # Check if job is complete (guard against total=0)
        if processed >= total and total > 0:
            completion_time = datetime.utcnow().isoformat() + "Z"
            # Idempotent completion: only set status if not already COMPLETED
            configuration_table.update_item(
                Key={"Configuration": job_key},
                UpdateExpression="SET #status = :status, completionTime = :time",
                ConditionExpression="attribute_not_exists(#status) OR #status <> :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "COMPLETED", ":time": completion_time},
            )
            logger.info(f"Re-embedding job {job_id} completed")

    except ClientError as e:
        logger.warning(f"Error updating re-embed job progress: {e}", exc_info=True)
    except Exception:
        logger.exception("Unexpected error updating re-embed job progress")


def lambda_handler(event, context):
    """
    Generate embeddings for text and images.
    """
    # Get environment variables (moved here for testability)
    tracking_table = os.environ.get("TRACKING_TABLE")
    if not tracking_table:
        raise ValueError("TRACKING_TABLE environment variable is required")

    # Read embedding models from ConfigurationManager (runtime configuration)
    text_embed_model = config_manager.get_parameter(
        "text_embed_model_id", default="amazon.titan-embed-text-v2:0"
    )
    image_embed_model = config_manager.get_parameter(
        "image_embed_model_id", default="amazon.titan-embed-image-v1"
    )

    # Log safe summary (not full event payload to avoid PII leakage)
    safe_summary = {
        "document_id": event.get("document_id"),
        "has_pages": "pages" in event and len(event.get("pages", [])) > 0,
        "page_count": len(event.get("pages", [])),
        "vector_bucket": event.get("vector_bucket"),
    }
    logger.info(f"Generating embeddings: {json.dumps(safe_summary)}")
    logger.info(f"Using text embedding model: {text_embed_model}")
    logger.info(f"Using image embedding model: {image_embed_model}")

    try:
        document_id = event["document_id"]
        output_s3_uri = event["output_s3_uri"]
        pages = event.get("pages", [])
        vector_bucket = event["vector_bucket"]

        bedrock_client = BedrockClient()

        # ===================================================================
        # Generate text embedding
        # ===================================================================

        logger.info(f"Reading text from {output_s3_uri}")
        full_text = read_s3_text(output_s3_uri)

        # Truncate if too long (Titan has input limits)
        # Titan Embed Text V2: max 8192 tokens (~32k chars)
        if len(full_text) > TEXT_CHAR_LIMIT:
            logger.warning(
                f"Text too long ({len(full_text)} chars), truncating to {TEXT_CHAR_LIMIT}"
            )
            full_text = full_text[:TEXT_CHAR_LIMIT]

        logger.info("Generating text embedding...")
        text_embedding = bedrock_client.generate_embedding(
            text=full_text, model_id=text_embed_model
        )

        # Save text embedding
        text_embed_uri = f"s3://{vector_bucket}/{document_id}/text_embedding.json"
        write_s3_json(
            text_embed_uri,
            {
                "document_id": document_id,
                "content": full_text,
                "embedding": text_embedding,
                "type": "text",
                "model": text_embed_model,
                "timestamp": datetime.now().isoformat(),
            },
        )
        logger.info(f"Saved text embedding to {text_embed_uri}")

        # ===================================================================
        # Generate image embeddings
        # ===================================================================

        image_embeddings = []

        for page in pages:
            image_s3_uri = page.get("image_s3_uri")
            if not image_s3_uri:
                continue

            page_number = page["page_number"]
            logger.info(f"Generating image embedding for page {page_number}...")

            # Read image
            image_bytes = read_s3_binary(image_s3_uri)

            # Generate embedding
            image_embedding = bedrock_client.generate_image_embedding(
                image_bytes=image_bytes, model_id=image_embed_model
            )

            # Save image embedding
            image_embed_uri = f"s3://{vector_bucket}/{document_id}/image_page_{page_number}.json"
            write_s3_json(
                image_embed_uri,
                {
                    "document_id": document_id,
                    "page_number": page_number,
                    "image_s3_uri": image_s3_uri,
                    "embedding": image_embedding,
                    "type": "image",
                    "model": image_embed_model,
                    "timestamp": datetime.now().isoformat(),
                },
            )

            image_embeddings.append({"page_number": page_number, "embedding_uri": image_embed_uri})

            logger.info(f"Saved image embedding to {image_embed_uri}")

        # ===================================================================
        # Update tracking
        # ===================================================================

        update_item(
            tracking_table,
            {"document_id": document_id},
            {"status": Status.EMBEDDING_COMPLETE.value, "updated_at": datetime.now().isoformat()},
        )

        # ===================================================================
        # Update re-embedding job progress (if applicable)
        # ===================================================================

        re_embed_job_id = event.get("reEmbedJobId")
        if re_embed_job_id:
            logger.info(f"Updating re-embedding job progress for job {re_embed_job_id}")
            update_re_embed_job_progress(re_embed_job_id)

        return {
            "document_id": document_id,
            "status": Status.EMBEDDING_COMPLETE.value,
            "text_embedding_uri": text_embed_uri,
            "image_embeddings": image_embeddings,
            "total_embeddings": 1 + len(image_embeddings),
        }

    except Exception as e:
        logger.error(f"Embedding generation failed: {e}", exc_info=True)

        try:
            tracking_table = os.environ.get("TRACKING_TABLE")
            if tracking_table:
                update_item(
                    tracking_table,
                    {"document_id": event["document_id"]},
                    {
                        "status": Status.FAILED.value,
                        "error_message": str(e),
                        "updated_at": datetime.now().isoformat(),
                    },
                )
        except Exception as update_error:
            logger.error(f"Failed to update DynamoDB: {update_error}")

        raise
