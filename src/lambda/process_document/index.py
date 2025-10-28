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

# Import from shared package (installed via pip)
from ragstack_common.ocr import OcrService
from ragstack_common.models import Document, Status, OcrBackend
from ragstack_common.storage import put_item, update_item, get_item
from ragstack_common.config import ConfigurationManager

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level initialization (reused across Lambda invocations in same container)
config_manager = ConfigurationManager()


def lambda_handler(event, context):
    """
    Main Lambda handler.
    """
    # Get environment variables (moved here for testability)
    tracking_table = os.environ.get('TRACKING_TABLE')
    if not tracking_table:
        raise ValueError("TRACKING_TABLE environment variable is required")

    logger.info(f"Processing document: {json.dumps(event)}")

    try:
        # Extract event data
        document_id = event['document_id']
        input_s3_uri = event['input_s3_uri']
        output_s3_prefix = event['output_s3_prefix']
        filename = event.get('filename', 'document.pdf')

        # Read configuration from ConfigurationManager (runtime configuration)
        ocr_backend = config_manager.get_parameter('ocr_backend', default='textract')
        bedrock_model_id = config_manager.get_parameter(
            'bedrock_ocr_model_id',
            default='anthropic.claude-3-5-haiku-20241022-v1:0'
        )

        logger.info(f"Using OCR backend: {ocr_backend}")
        if ocr_backend == 'bedrock':
            logger.info(f"Using Bedrock OCR model: {bedrock_model_id}")

        # Update status to processing
        update_item(
            tracking_table,
            {'document_id': document_id},
            {
                'status': Status.PROCESSING.value,
                'updated_at': datetime.now().isoformat()
            }
        )

        # Create Document object (Phase 1 API)
        document = Document(
            document_id=document_id,
            filename=filename,
            input_s3_uri=input_s3_uri,
            output_s3_uri=output_s3_prefix,  # Will be updated by OcrService
            status=Status.PROCESSING
        )

        # Create OCR service and process document (Phase 1 API)
        ocr_service = OcrService(
            region=os.environ.get('AWS_REGION'),
            backend=ocr_backend,
            bedrock_model_id=bedrock_model_id
        )

        # Process document - returns updated Document object
        processed_document = ocr_service.process_document(document)

        # Check for processing errors
        if processed_document.status == Status.FAILED:
            raise Exception(processed_document.error_message or "OCR processing failed")

        # Update DynamoDB with results
        update_item(
            tracking_table,
            {'document_id': document_id},
            {
                'status': Status.OCR_COMPLETE.value,
                'total_pages': processed_document.total_pages,
                'is_text_native': processed_document.is_text_native or False,
                'output_s3_uri': processed_document.output_s3_uri,
                'updated_at': datetime.now().isoformat()
            }
        )

        # Return results for Step Functions
        return {
            'document_id': document_id,
            'status': Status.OCR_COMPLETE.value,
            'total_pages': processed_document.total_pages,
            'is_text_native': processed_document.is_text_native or False,
            'output_s3_uri': processed_document.output_s3_uri,
            'pages': [
                {
                    'page_number': p.page_number,
                    'text': p.text[:500] if p.text else '',  # Truncate for Step Functions
                    'image_s3_uri': getattr(p, 'image_s3_uri', None),
                    'ocr_backend': p.ocr_backend
                }
                for p in processed_document.pages
            ]
        }

    except Exception as e:
        logger.error(f"Document processing failed: {e}", exc_info=True)

        # Update status to failed
        try:
            tracking_table = os.environ.get('TRACKING_TABLE')
            if tracking_table:
                update_item(
                    tracking_table,
                    {'document_id': event['document_id']},
                    {
                        'status': Status.FAILED.value,
                        'error_message': str(e),
                        'updated_at': datetime.now().isoformat()
                    }
                )
        except Exception as update_error:
            logger.error(f"Failed to update DynamoDB: {update_error}")

        raise
