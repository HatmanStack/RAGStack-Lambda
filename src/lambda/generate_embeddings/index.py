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

from ragstack_common.bedrock import BedrockClient
from ragstack_common.storage import (
    read_s3_text, read_s3_binary, write_s3_json, update_item
)
from ragstack_common.models import Status

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TRACKING_TABLE = os.environ['TRACKING_TABLE']
TEXT_EMBED_MODEL = os.environ.get('TEXT_EMBED_MODEL', 'amazon.titan-embed-text-v2:0')
IMAGE_EMBED_MODEL = os.environ.get('IMAGE_EMBED_MODEL', 'amazon.titan-embed-image-v1')


def lambda_handler(event, context):
    """
    Generate embeddings for text and images.
    """
    logger.info(f"Generating embeddings: {json.dumps(event)}")

    try:
        document_id = event['document_id']
        output_s3_uri = event['output_s3_uri']
        pages = event.get('pages', [])
        vector_bucket = event['vector_bucket']

        bedrock_client = BedrockClient()

        # ===================================================================
        # Generate text embedding
        # ===================================================================

        logger.info(f"Reading text from {output_s3_uri}")
        full_text = read_s3_text(output_s3_uri)

        # Truncate if too long (Titan has input limits)
        # Titan Embed Text V2: max 8192 tokens (~32k chars)
        if len(full_text) > 30000:
            logger.warning(f"Text too long ({len(full_text)} chars), truncating to 30000")
            full_text = full_text[:30000]

        logger.info("Generating text embedding...")
        text_embedding = bedrock_client.generate_text_embedding(
            text=full_text,
            model_id=TEXT_EMBED_MODEL,
            document_id=document_id
        )

        # Save text embedding
        text_embed_uri = f"s3://{vector_bucket}/{document_id}/text_embedding.json"
        write_s3_json(text_embed_uri, {
            'document_id': document_id,
            'content': full_text,
            'embedding': text_embedding,
            'type': 'text',
            'model': TEXT_EMBED_MODEL,
            'timestamp': datetime.now().isoformat()
        })
        logger.info(f"Saved text embedding to {text_embed_uri}")

        # ===================================================================
        # Generate image embeddings
        # ===================================================================

        image_embeddings = []

        for page in pages:
            image_s3_uri = page.get('image_s3_uri')
            if not image_s3_uri:
                continue

            page_number = page['page_number']
            logger.info(f"Generating image embedding for page {page_number}...")

            # Read image
            image_bytes = read_s3_binary(image_s3_uri)

            # Generate embedding
            image_embedding = bedrock_client.generate_image_embedding(
                image_bytes=image_bytes,
                model_id=IMAGE_EMBED_MODEL,
                document_id=document_id
            )

            # Save image embedding
            image_embed_uri = f"s3://{vector_bucket}/{document_id}/image_page_{page_number}.json"
            write_s3_json(image_embed_uri, {
                'document_id': document_id,
                'page_number': page_number,
                'image_s3_uri': image_s3_uri,
                'embedding': image_embedding,
                'type': 'image',
                'model': IMAGE_EMBED_MODEL,
                'timestamp': datetime.now().isoformat()
            })

            image_embeddings.append({
                'page_number': page_number,
                'embedding_uri': image_embed_uri
            })

            logger.info(f"Saved image embedding to {image_embed_uri}")

        # ===================================================================
        # Update tracking
        # ===================================================================

        update_item(
            TRACKING_TABLE,
            {'document_id': document_id},
            {
                'status': Status.EMBEDDING_COMPLETE.value,
                'updated_at': datetime.now().isoformat()
            }
        )

        return {
            'document_id': document_id,
            'status': Status.EMBEDDING_COMPLETE.value,
            'text_embedding_uri': text_embed_uri,
            'image_embeddings': image_embeddings,
            'total_embeddings': 1 + len(image_embeddings)
        }

    except Exception as e:
        logger.error(f"Embedding generation failed: {e}", exc_info=True)

        update_item(
            TRACKING_TABLE,
            {'document_id': event['document_id']},
            {
                'status': Status.FAILED.value,
                'error_message': str(e),
                'updated_at': datetime.now().isoformat()
            }
        )

        raise
