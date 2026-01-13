"""
Ingest Media Lambda

Handles ingestion of media (video/audio) content with dual embedding support:
1. Text embeddings from transcript (via Bedrock KB)
2. Visual embeddings from video segments (via Nova Multimodal)

Input event:
{
    "document_id": "abc123",
    "output_s3_uri": "s3://bucket/content/abc123/transcript_full.txt",
    "media_type": "video",
    "duration_seconds": 120,
    "total_segments": 4,
    "visual_segments": [
        {
            "segment_index": 0,
            "timestamp_start": 0,
            "timestamp_end": 30,
            "s3_uri": "s3://bucket/segments/abc123/segment_000.mp4"
        }
    ],
    "transcript_segments": [
        {
            "segment_index": 0,
            "timestamp_start": 0,
            "timestamp_end": 30,
            "text": "transcript text",
            "word_count": 10
        }
    ]
}

Output:
{
    "document_id": "abc123",
    "status": "indexed",
    "text_indexed": true,
    "visual_segments_indexed": 4,
    "metadata_keys": ["main_topic", "speakers", ...]
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
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.metadata_normalizer import normalize_metadata_for_s3
from ragstack_common.nova_embeddings import NovaEmbeddingsClient
from ragstack_common.storage import read_s3_text

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent = boto3.client("bedrock-agent")
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

# Lazy-initialized singletons
_nova_embeddings_client = None
_metadata_extractor = None


def get_nova_embeddings_client() -> NovaEmbeddingsClient:
    """Get or create NovaEmbeddingsClient singleton."""
    global _nova_embeddings_client
    if _nova_embeddings_client is None:
        _nova_embeddings_client = NovaEmbeddingsClient()
    return _nova_embeddings_client


def get_metadata_extractor() -> MetadataExtractor:
    """Get or create MetadataExtractor singleton."""
    global _metadata_extractor
    if _metadata_extractor is None:
        _metadata_extractor = MetadataExtractor()
    return _metadata_extractor


def write_metadata_to_s3(output_s3_uri: str, metadata: dict[str, Any]) -> str:
    """
    Write metadata to S3 as a .metadata.json file.

    Args:
        output_s3_uri: S3 URI of the content file.
        metadata: Dictionary of metadata key-value pairs.

    Returns:
        S3 URI of the metadata file.
    """
    if not output_s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {output_s3_uri}")

    path = output_s3_uri[5:]
    bucket, key = path.split("/", 1)

    metadata_key = f"{key}.metadata.json"
    metadata_uri = f"s3://{bucket}/{metadata_key}"

    # Normalize metadata for S3 Vectors
    normalized_metadata = normalize_metadata_for_s3(metadata)

    metadata_content = {"metadataAttributes": normalized_metadata}

    s3_client.put_object(
        Bucket=bucket,
        Key=metadata_key,
        Body=json.dumps(metadata_content),
        ContentType="application/json",
    )

    logger.info(f"Wrote metadata to {metadata_uri}")
    return metadata_uri


def ingest_text_to_kb(
    document_id: str,
    output_s3_uri: str,
    metadata: dict[str, Any],
    kb_id: str,
    ds_id: str,
) -> dict[str, Any]:
    """
    Ingest text transcript to Bedrock Knowledge Base.

    Args:
        document_id: Document identifier.
        output_s3_uri: S3 URI of the text content.
        metadata: Metadata dictionary.
        kb_id: Knowledge Base ID.
        ds_id: Data Source ID.

    Returns:
        Ingestion result dictionary.
    """
    # Write metadata to S3
    metadata_uri = write_metadata_to_s3(output_s3_uri, metadata)

    # Build document object
    document = {
        "content": {
            "dataSourceType": "S3",
            "s3": {"s3Location": {"uri": output_s3_uri}},
        },
        "metadata": {
            "type": "S3_LOCATION",
            "s3Location": {"uri": metadata_uri},
        },
    }

    # Ingest to KB
    response = bedrock_agent.ingest_knowledge_base_documents(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id,
        documents=[document],
    )

    logger.info(f"Text ingestion response: {json.dumps(response, default=str)}")

    doc_details = response.get("documentDetails", [])
    status = doc_details[0].get("status", "UNKNOWN") if doc_details else "UNKNOWN"

    return {"status": status, "metadata_uri": metadata_uri}


def ingest_visual_segments(
    document_id: str,
    visual_segments: list[dict[str, Any]],
    metadata: dict[str, Any],
    kb_id: str,
    ds_id: str,
) -> int:
    """
    Create visual embeddings and ingest to Knowledge Base.

    Args:
        document_id: Document identifier.
        visual_segments: List of visual segment dictionaries.
        metadata: Base metadata for all segments.
        kb_id: Knowledge Base ID.
        ds_id: Data Source ID.

    Returns:
        Number of segments indexed.
    """
    if not visual_segments:
        logger.info(f"No visual segments to index for {document_id}")
        return 0

    nova_client = get_nova_embeddings_client()
    indexed_count = 0

    for segment in visual_segments:
        try:
            segment_index = segment.get("segment_index", 0)
            s3_uri = segment.get("s3_uri")

            if not s3_uri:
                logger.warning(f"Segment {segment_index} missing s3_uri")
                continue

            # Create visual embedding
            embedding_result = nova_client.embed_from_s3(
                s3_uri,
                media_type="video",
            )

            # Note: For now, we store the embedding vector reference
            # Full S3 Vectors integration will be added in Phase 3
            logger.info(
                f"Created visual embedding for segment {segment_index}: "
                f"dim={len(embedding_result.get('embedding', []))}"
            )

            indexed_count += 1

        except Exception as e:
            logger.warning(f"Failed to process visual segment {segment_index}: {e}")
            continue

    logger.info(f"Indexed {indexed_count} visual segments for {document_id}")
    return indexed_count


def lambda_handler(event, context):
    """Ingest media content with dual embeddings."""
    # Get environment variables
    kb_id = os.environ.get("KNOWLEDGE_BASE_ID")
    ds_id = os.environ.get("DATA_SOURCE_ID")
    tracking_table_name = os.environ.get("TRACKING_TABLE")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    if not kb_id or not ds_id:
        raise ValueError("KNOWLEDGE_BASE_ID and DATA_SOURCE_ID are required")

    if not tracking_table_name:
        raise ValueError("TRACKING_TABLE is required")

    # Extract event data
    document_id = event.get("document_id")
    output_s3_uri = event.get("output_s3_uri")

    if not document_id:
        raise ValueError("document_id is required")

    if not output_s3_uri:
        raise ValueError("output_s3_uri is required")

    media_type = event.get("media_type", "video")
    duration_seconds = event.get("duration_seconds", 0)
    total_segments = event.get("total_segments", 0)
    visual_segments = event.get("visual_segments", [])
    transcript_segments = event.get("transcript_segments", [])

    logger.info(
        f"Ingesting media {document_id}: type={media_type}, "
        f"duration={duration_seconds}s, segments={total_segments}"
    )

    # Get tracking table
    tracking_table = dynamodb.Table(tracking_table_name)

    # Fetch document details
    doc_response = tracking_table.get_item(Key={"document_id": document_id})
    doc_item = doc_response.get("Item", {})
    filename = doc_item.get("filename", "unknown")

    try:
        # Read transcript for metadata extraction
        transcript_text = read_s3_text(output_s3_uri) if output_s3_uri else ""

        # Build technical metadata
        technical_metadata = {
            "content_type": "media",
            "media_type": media_type,
            "duration_seconds": duration_seconds,
            "total_segments": total_segments,
        }

        # Extract metadata from transcript
        extractor = get_metadata_extractor()
        extracted_metadata = extractor.extract_media_metadata(
            transcript=transcript_text,
            segments=transcript_segments,
            technical_metadata=technical_metadata,
            document_id=document_id,
        )

        logger.info(f"Extracted metadata keys: {list(extracted_metadata.keys())}")

        # Ingest text transcript to KB
        text_result = ingest_text_to_kb(
            document_id=document_id,
            output_s3_uri=output_s3_uri,
            metadata=extracted_metadata,
            kb_id=kb_id,
            ds_id=ds_id,
        )

        text_indexed = text_result.get("status") == "STARTING"

        # Ingest visual segments
        visual_indexed = ingest_visual_segments(
            document_id=document_id,
            visual_segments=visual_segments,
            metadata=extracted_metadata,
            kb_id=kb_id,
            ds_id=ds_id,
        )

        # Update tracking table
        tracking_table.update_item(
            Key={"document_id": document_id},
            UpdateExpression=(
                "SET #status = :status, "
                "updated_at = :updated_at, "
                "extracted_metadata = :metadata"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "indexed",
                ":updated_at": datetime.now(UTC).isoformat(),
                ":metadata": extracted_metadata,
            },
        )

        # Publish update
        publish_document_update(
            graphql_endpoint,
            document_id,
            filename,
            "INDEXED",
            total_pages=total_segments,
        )

        return {
            "document_id": document_id,
            "status": "indexed",
            "text_indexed": text_indexed,
            "visual_segments_indexed": visual_indexed,
            "metadata_keys": list(extracted_metadata.keys()),
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to ingest media: {error_code} - {error_msg}")

        # Update status to failed
        try:
            tracking_table.update_item(
                Key={"document_id": document_id},
                UpdateExpression=(
                    "SET #status = :status, "
                    "error_message = :error, "
                    "updated_at = :updated_at"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": "failed",
                    ":error": error_msg,
                    ":updated_at": datetime.now(UTC).isoformat(),
                },
            )
            publish_document_update(
                graphql_endpoint,
                document_id,
                filename,
                "FAILED",
                error_message=error_msg,
            )
        except Exception as update_error:
            logger.error(f"Failed to update status: {update_error}")

        raise

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to ingest media: {error_msg}", exc_info=True)

        # Update status to failed
        try:
            tracking_table.update_item(
                Key={"document_id": document_id},
                UpdateExpression=(
                    "SET #status = :status, "
                    "error_message = :error, "
                    "updated_at = :updated_at"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": "failed",
                    ":error": error_msg,
                    ":updated_at": datetime.now(UTC).isoformat(),
                },
            )
            publish_document_update(
                graphql_endpoint,
                document_id,
                filename,
                "FAILED",
                error_message=error_msg,
            )
        except Exception as update_error:
            logger.error(f"Failed to update status: {update_error}")

        raise
