"""
Custom resource for Bedrock Knowledge Base creation.

CloudFormation doesn't natively support KB creation with S3 vectors,
so we use a custom resource to create and manage the Knowledge Base.
"""

import json
import logging
import boto3
import time
from urllib.request import urlopen, Request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_agent = boto3.client('bedrock-agent')
ssm = boto3.client('ssm')


def send_response(event, context, status, data=None, reason=None, physical_resource_id=None):
    """Send response to CloudFormation."""
    response_body = {
        'Status': status,
        'Reason': reason or f'See CloudWatch Log Stream: {context.log_stream_name}',
        'PhysicalResourceId': physical_resource_id or data.get('KnowledgeBaseId', 'KnowledgeBase') if data else 'KnowledgeBase',
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': data or {}
    }

    request = Request(
        event['ResponseURL'],
        data=json.dumps(response_body).encode('utf-8'),
        headers={'Content-Type': ''},
        method='PUT'
    )

    try:
        urlopen(request)
        logger.info('Response sent successfully')
    except Exception as e:
        logger.error(f'Failed to send response: {e}')


def lambda_handler(event, context):
    """Handle custom resource lifecycle."""
    logger.info(f'Event: {json.dumps(event)}')

    request_type = event['RequestType']
    properties = event['ResourceProperties']

    try:
        if request_type == 'Create':
            result = create_knowledge_base(properties)
            send_response(event, context, 'SUCCESS', result, physical_resource_id=result['KnowledgeBaseId'])

        elif request_type == 'Update':
            # For simplicity, updates not supported - would require recreation
            kb_id = event.get('PhysicalResourceId', 'KnowledgeBase')
            send_response(event, context, 'SUCCESS', {'Message': 'Update not implemented'}, physical_resource_id=kb_id)

        elif request_type == 'Delete':
            kb_id = event.get('PhysicalResourceId', 'KnowledgeBase')
            delete_knowledge_base(kb_id)
            send_response(event, context, 'SUCCESS', physical_resource_id=kb_id)

    except Exception as e:
        logger.error(f'Failed: {e}', exc_info=True)
        send_response(event, context, 'FAILED', reason=str(e))


def create_knowledge_base(properties):
    """Create Bedrock Knowledge Base with S3 vectors."""

    kb_name = properties['KnowledgeBaseName']
    role_arn = properties['RoleArn']
    vector_bucket = properties['VectorBucket']
    embed_model_arn = properties['EmbedModelArn']
    index_name = properties.get('IndexName', 'bedrock-kb-default-index')

    # Create Knowledge Base with S3 vector store
    logger.info(f'Creating Knowledge Base: {kb_name}')

    kb_response = bedrock_agent.create_knowledge_base(
        name=kb_name,
        description='RAGStack-Lambda Knowledge Base for document search',
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            'type': 'VECTOR',
            'vectorKnowledgeBaseConfiguration': {
                'embeddingModelArn': embed_model_arn
            }
        },
        storageConfiguration={
            'type': 'RDS',
            'rdsConfiguration': {
                'resourceArn': f'arn:aws:s3:::{vector_bucket}',
                'credentialsSecretArn': role_arn,
                'databaseName': index_name,
                'tableName': 'bedrock_integration',
                'fieldMapping': {
                    'primaryKeyField': 'id',
                    'vectorField': 'embedding',
                    'textField': 'text',
                    'metadataField': 'metadata'
                }
            }
        }
    )

    kb_id = kb_response['knowledgeBase']['knowledgeBaseId']
    kb_arn = kb_response['knowledgeBase']['knowledgeBaseArn']
    logger.info(f'Created Knowledge Base: {kb_id}')

    # Create S3 data source
    ds_response = bedrock_agent.create_data_source(
        knowledgeBaseId=kb_id,
        name=f'{kb_name}-S3DataSource',
        description='S3 bucket containing document vectors',
        dataSourceConfiguration={
            'type': 'S3',
            's3Configuration': {
                'bucketArn': f'arn:aws:s3:::{vector_bucket}',
                'inclusionPrefixes': ['vectors/']
            }
        },
        vectorIngestionConfiguration={
            'chunkingConfiguration': {
                'chunkingStrategy': 'FIXED_SIZE',
                'fixedSizeChunkingConfiguration': {
                    'maxTokens': 300,
                    'overlapPercentage': 15
                }
            }
        }
    )

    data_source_id = ds_response['dataSource']['dataSourceId']
    logger.info(f'Created Data Source: {data_source_id}')

    # Store KB ID in Parameter Store for easy reference
    try:
        ssm.put_parameter(
            Name='/RAGStack/KnowledgeBaseId',
            Description='Bedrock Knowledge Base ID for RAGStack-Lambda',
            Value=kb_id,
            Type='String',
            Overwrite=True
        )
        logger.info('Stored KB ID in Parameter Store')
    except Exception as e:
        logger.warning(f'Failed to store KB ID in Parameter Store: {e}')

    # Wait for KB to be ready
    time.sleep(10)

    return {
        'KnowledgeBaseId': kb_id,
        'KnowledgeBaseArn': kb_arn,
        'DataSourceId': data_source_id
    }


def delete_knowledge_base(kb_id):
    """Delete Knowledge Base and its data sources."""
    if kb_id == 'KnowledgeBase':
        logger.info('Physical ID is placeholder, skipping deletion')
        return

    try:
        # List and delete data sources
        data_sources = bedrock_agent.list_data_sources(knowledgeBaseId=kb_id)
        for ds in data_sources.get('dataSourceSummaries', []):
            bedrock_agent.delete_data_source(
                knowledgeBaseId=kb_id,
                dataSourceId=ds['dataSourceId']
            )
            logger.info(f"Deleted data source: {ds['dataSourceId']}")

        # Delete Knowledge Base
        bedrock_agent.delete_knowledge_base(knowledgeBaseId=kb_id)
        logger.info(f'Deleted Knowledge Base: {kb_id}')

        # Clean up Parameter Store
        try:
            ssm.delete_parameter(Name='/RAGStack/KnowledgeBaseId')
        except Exception as e:
            logger.warning(f'Failed to delete Parameter Store entry: {e}')

    except Exception as e:
        logger.error(f'Failed to delete KB: {e}')
        # Don't fail deletion - best effort
