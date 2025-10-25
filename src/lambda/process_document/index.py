"""
Document Processor Lambda

Handles document validation, OCR, text extraction, and image extraction.

Input event:
{
    "document_id": "abc123",
    "input_s3_uri": "s3://input-bucket/uploads/doc.pdf",
    "output_s3_prefix": "s3://output-bucket/processed/abc123/",
    "ocr_backend": "textract",  # or "bedrock"
    "bedrock_model_id": "anthropic.claude-3-5-haiku-20241022-v1:0"
}

Output:
{
    "document_id": "abc123",
    "status": "ocr_complete",
    "total_pages": 5,
    "is_text_native": true,
    "output_s3_uri": "s3://output-bucket/processed/abc123/full_text.txt",
    "pages": [...]
}
"""

import json
import logging
import os
from datetime import datetime

# Import from Lambda layer
from ragstack_common.ocr import OcrService, OcrConfig
from ragstack_common.models import Document, Status, OcrBackend
from ragstack_common.storage import put_item, update_item, get_item

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
TRACKING_TABLE = os.environ['TRACKING_TABLE']


def lambda_handler(event, context):
    """
    Main Lambda handler.
    """
    logger.info(f"Processing document: {json.dumps(event)}")

    try:
        # Extract event data
        document_id = event['document_id']
        input_s3_uri = event['input_s3_uri']
        output_s3_prefix = event['output_s3_prefix']
        ocr_backend = OcrBackend(event.get('ocr_backend', 'textract'))
        bedrock_model_id = event.get('bedrock_model_id', 'anthropic.claude-3-5-haiku-20241022-v1:0')

        # Update status to processing
        update_item(
            TRACKING_TABLE,
            {'document_id': document_id},
            {
                'status': Status.PROCESSING.value,
                'updated_at': datetime.now().isoformat()
            }
        )

        # Create OCR config
        config = OcrConfig(
            backend=ocr_backend,
            bedrock_model_id=bedrock_model_id,
            extract_text_native=True
        )

        # Process document
        ocr_service = OcrService(config)
        pages, is_text_native = ocr_service.process_document(
            input_s3_uri=input_s3_uri,
            output_s3_prefix=output_s3_prefix,
            document_id=document_id
        )

        # Prepare output
        output_s3_uri = f"{output_s3_prefix.rstrip('/')}/full_text.txt"

        # Update DynamoDB with results
        update_item(
            TRACKING_TABLE,
            {'document_id': document_id},
            {
                'status': Status.OCR_COMPLETE.value,
                'total_pages': len(pages),
                'is_text_native': is_text_native,
                'output_s3_uri': output_s3_uri,
                'updated_at': datetime.now().isoformat()
            }
        )

        # Return results for Step Functions
        return {
            'document_id': document_id,
            'status': Status.OCR_COMPLETE.value,
            'total_pages': len(pages),
            'is_text_native': is_text_native,
            'output_s3_uri': output_s3_uri,
            'pages': [
                {
                    'page_number': p.page_number,
                    'text': p.text[:500],  # Truncate for Step Functions
                    'image_s3_uri': p.image_s3_uri,
                    'ocr_backend': p.ocr_backend
                }
                for p in pages
            ]
        }

    except Exception as e:
        logger.error(f"Document processing failed: {e}", exc_info=True)

        # Update status to failed
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
