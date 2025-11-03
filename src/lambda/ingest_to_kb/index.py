"""
Ingest to Knowledge Base Lambda

Calls Bedrock Agent to ingest a document directly into the Knowledge Base.
Bedrock handles embedding generation and S3 Vectors indexing automatically.

Input event:
{
    "document_id": "abc123",
    "output_s3_uri": "s3://output-bucket/abc123/full_text.txt"
}

Output:
{
    "document_id": "abc123",
    "status": "completed",
    "ingestion_status": "STARTING"
}
"""

import json
import logging
import os
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent = boto3.client('bedrock-agent')
dynamodb = boto3.resource('dynamodb')


def lambda_handler(event, context):
    """Ingest document into Knowledge Base via Bedrock Agent API."""
    # Get environment variables
    kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
    ds_id = os.environ.get('DATA_SOURCE_ID')
    tracking_table_name = os.environ.get('TRACKING_TABLE')

    if not kb_id or not ds_id:
        raise ValueError('KNOWLEDGE_BASE_ID and DATA_SOURCE_ID environment variables are required')

    if not tracking_table_name:
        raise ValueError('TRACKING_TABLE environment variable is required')

    # Extract document info from event
    document_id = event.get('document_id')
    output_s3_uri = event.get('output_s3_uri')

    if not document_id or not output_s3_uri:
        raise ValueError('document_id and output_s3_uri are required in event')

    logger.info(f"Ingesting document {document_id} from {output_s3_uri}")

    # Get DynamoDB table
    tracking_table = dynamodb.Table(tracking_table_name)

    try:
        # Call Bedrock Agent to ingest the document
        # Bedrock will:
        # 1. Read the text from S3
        # 2. Generate embeddings using Titan models
        # 3. Write vectors to S3 Vectors index
        # 4. Make the document queryable
        response = bedrock_agent.ingest_knowledge_base_documents(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            documents=[{
                'content': {
                    'dataSourceType': 'S3',
                    's3': {
                        's3Location': {
                            'uri': output_s3_uri
                        }
                    }
                }
            }]
        )

        logger.info(f"Ingestion response: {json.dumps(response, default=str)}")

        # Extract status from response
        doc_details = response.get('documentDetails', [])
        ingestion_status = 'UNKNOWN'
        if doc_details:
            ingestion_status = doc_details[0].get('status', 'UNKNOWN')

        # Update document status in DynamoDB to 'completed'
        try:
            tracking_table.update_item(
                Key={'documentId': document_id},
                UpdateExpression='SET #status = :status, updatedAt = :updated_at',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'completed',
                    ':updated_at': datetime.utcnow().isoformat() + 'Z'
                }
            )
            logger.info(f"Updated document {document_id} status to 'completed'")
        except ClientError as e:
            logger.error(f"Failed to update DynamoDB status: {str(e)}")
            # Don't fail the whole ingestion if status update fails
            pass

        return {
            'document_id': document_id,
            'status': 'completed',
            'ingestion_status': ingestion_status,
            'knowledge_base_id': kb_id
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"Failed to ingest document: {error_code} - {error_msg}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error ingesting document: {str(e)}")
        raise
