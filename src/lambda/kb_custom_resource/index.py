"""
Custom resource for Bedrock Knowledge Base creation.

CloudFormation doesn't natively support KB creation with S3 vectors,
so we use a custom resource to create and manage the Knowledge Base.
"""

import json
import logging
import random
import string
import time
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_agent = boto3.client("bedrock-agent")
ssm = boto3.client("ssm")


def generate_random_suffix(length=5):
    """Generate a random alphanumeric suffix for unique resource naming."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def send_response(event, context, status, data=None, reason=None, physical_resource_id=None):
    """Send response to CloudFormation."""
    response_body = {
        "Status": status,
        "Reason": reason or f"See CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": physical_resource_id or data.get("KnowledgeBaseId", "KnowledgeBase")
        if data
        else "KnowledgeBase",
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data or {},
    }

    request = Request(
        event["ResponseURL"],
        data=json.dumps(response_body).encode("utf-8"),
        headers={"Content-Type": ""},
        method="PUT",
    )

    try:
        urlopen(request)
        logger.info("Response sent successfully")
    except Exception as e:
        logger.error(f"Failed to send response: {e}")


def lambda_handler(event, context):
    """Handle custom resource lifecycle."""
    logger.info(f"Event: {json.dumps(event)}")

    request_type = event["RequestType"]
    properties = event["ResourceProperties"]

    try:
        if request_type == "Create":
            result = create_knowledge_base(properties)
            send_response(
                event, context, "SUCCESS", result, physical_resource_id=result["KnowledgeBaseId"]
            )

        elif request_type == "Update":
            # For simplicity, updates not supported - would require recreation
            kb_id = event.get("PhysicalResourceId", "KnowledgeBase")
            send_response(
                event,
                context,
                "SUCCESS",
                {"Message": "Update not implemented"},
                physical_resource_id=kb_id,
            )

        elif request_type == "Delete":
            kb_id = event.get("PhysicalResourceId", "KnowledgeBase")
            project_name = properties.get("ProjectName", "RAGStack")
            delete_knowledge_base(kb_id, project_name)
            send_response(event, context, "SUCCESS", physical_resource_id=kb_id)

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        send_response(event, context, "FAILED", reason=str(e))


def create_knowledge_base(properties):
    """Create Bedrock Knowledge Base with S3 Vectors storage."""

    kb_name = properties["KnowledgeBaseName"]
    role_arn = properties["RoleArn"]
    vector_bucket = properties["VectorBucket"]
    embed_model_arn = properties["EmbedModelArn"]
    index_name = properties.get("IndexName", "bedrock-kb-default-index")
    region = properties.get("Region", boto3.session.Session().region_name)

    logger.info(f"Creating Knowledge Base: {kb_name} with S3 Vectors")

    # Step 1: Initialize S3 Vectors bucket
    s3vectors_client = boto3.client("s3vectors", region_name=region)

    logger.info(f"Initializing S3 Vectors bucket: {vector_bucket}")
    try:
        s3vectors_client.create_vector_bucket(vectorBucketName=vector_bucket)
        logger.info(f"S3 Vectors bucket initialized: {vector_bucket}")
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_msg = str(e)
        # Bucket already exists is a non-fatal condition
        if error_code == 'ConflictException' or 'already exists' in error_msg.lower():
            logger.info(f"S3 Vectors bucket already exists: {vector_bucket}")
        else:
            # All other errors are fatal - re-raise
            logger.error(f"Failed to create S3 Vectors bucket {vector_bucket}: {e}")
            raise

    # Step 2: Verify bucket exists
    logger.info(f"Verifying S3 Vectors bucket: {vector_bucket}")
    try:
        s3vectors_client.get_vector_bucket(vectorBucketName=vector_bucket)
        logger.info(f"Verified S3 Vectors bucket exists: {vector_bucket}")
    except Exception as e:
        logger.error(f"Failed to verify S3 Vectors bucket {vector_bucket}: {e}")
        raise

    # Step 3: Create S3 Vectors index with unique suffix
    logger.info(f"Creating S3 vector index: {index_name}")
    try:
        s3vectors_client.create_index(
            vectorBucketName=vector_bucket,
            indexName=index_name,
            dataType="float32",  # Titan Embed models output float32
            dimension=1024,  # Titan Embed models output 1024 dimensions
            distanceMetric="cosine",
            metadataConfiguration={
                "nonFilterableMetadataKeys": [
                    "AMAZON_BEDROCK_METADATA",
                    "AMAZON_BEDROCK_TEXT_CHUNK",
                ]
            },
        )
        logger.info(f"Created S3 vector index: {index_name}")
    except Exception as e:
        logger.error(f"Failed to create S3 vector index: {e}")
        raise

    # Construct index ARN
    sts_client = boto3.client("sts")
    account_id = sts_client.get_caller_identity()["Account"]
    index_arn = f"arn:aws:s3vectors:{region}:{account_id}:bucket/{vector_bucket}/index/{index_name}"
    logger.info(f"Using S3 vector index ARN: {index_arn}")

    # Step 4: Create Knowledge Base with unique suffix
    logger.info(f"Creating Knowledge Base: {kb_name}")
    try:
        kb_response = bedrock_agent.create_knowledge_base(
            clientToken=f"cfn-{int(time.time())}-{'a' * 20}",  # 33+ chars required
            name=kb_name,
            description="RAGStack-Lambda Knowledge Base for document search",
            roleArn=role_arn,
            knowledgeBaseConfiguration={
                "type": "VECTOR",
                "vectorKnowledgeBaseConfiguration": {
                    "embeddingModelConfiguration": {
                        "bedrockEmbeddingModelConfiguration": {
                            "dimensions": 1024,
                            "embeddingDataType": "FLOAT32",
                        }
                    },
                    "embeddingModelArn": embed_model_arn,
                },
            },
            storageConfiguration={
                "type": "S3_VECTORS",
                "s3VectorsConfiguration": {"indexArn": index_arn},
            },
        )

        kb_id = kb_response["knowledgeBase"]["knowledgeBaseId"]
        kb_arn = kb_response["knowledgeBase"]["knowledgeBaseArn"]
        logger.info(f"Created Knowledge Base: {kb_id}")
    except Exception as e:
        logger.error(f"Failed to create Knowledge Base: {e}")
        raise

    # Step 5: Create Data Source for S3 Vector bucket
    # This allows Bedrock KB to sync vectors from the S3 Vector bucket
    data_source_name = f"{kb_name}-datasource"
    logger.info(f"Creating Data Source: {data_source_name}")

    try:
        # Get the S3 bucket ARN for the vector bucket
        sts_client = boto3.client("sts")
        account_id = sts_client.get_caller_identity()["Account"]
        vector_bucket_arn = f"arn:aws:s3:::{vector_bucket}"

        ds_response = bedrock_agent.create_data_source(
            knowledgeBaseId=kb_id,
            name=data_source_name,
            description=f"S3 Vector data source for {project_name}",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {
                    "bucketArn": vector_bucket_arn,
                    "bucketOwnerAccountId": account_id,
                },
            },
        )

        data_source_id = ds_response["dataSource"]["dataSourceId"]
        logger.info(f"Created Data Source: {data_source_id}")
    except Exception as e:
        logger.error(f"Failed to create Data Source: {e}")
        raise

    # Store KB ID in Parameter Store for easy reference
    project_name = properties.get("ProjectName", "RAGStack")
    ssm_param_name = f"/{project_name}/KnowledgeBaseId"

    try:
        ssm.put_parameter(
            Name=ssm_param_name,
            Description=f"Bedrock Knowledge Base ID for {project_name}",
            Value=kb_id,
            Type="String",
            Overwrite=True,
        )
        logger.info(f"Stored KB ID in Parameter Store: {ssm_param_name}")
    except Exception as e:
        logger.warning(f"Failed to store KB ID in Parameter Store: {e}")

    # Wait for KB and Data Source to be ready
    time.sleep(10)

    return {
        "KnowledgeBaseId": kb_id,
        "KnowledgeBaseArn": kb_arn,
        "DataSourceId": data_source_id,
        "IndexArn": index_arn,
    }


def delete_knowledge_base(kb_id, project_name="RAGStack"):
    """Delete Knowledge Base and S3 Vectors index."""
    if kb_id == "KnowledgeBase":
        logger.info("Physical ID is placeholder, skipping deletion")
        return

    try:
        # Delete Data Sources first (best practice, though KB deletion should cascade)
        try:
            ds_list = bedrock_agent.list_data_sources(knowledgeBaseId=kb_id)
            for ds in ds_list.get("dataSourceSummaries", []):
                ds_id = ds["dataSourceId"]
                logger.info(f"Deleting Data Source: {ds_id}")
                bedrock_agent.delete_data_source(
                    knowledgeBaseId=kb_id,
                    dataSourceId=ds_id
                )
                logger.info(f"Deleted Data Source: {ds_id}")
        except Exception as e:
            logger.warning(f"Error deleting Data Sources: {e}")

        # Delete Knowledge Base
        bedrock_agent.delete_knowledge_base(knowledgeBaseId=kb_id)
        logger.info(f"Deleted Knowledge Base: {kb_id}")

        # Clean up Parameter Store
        ssm_param_name = f"/{project_name}/KnowledgeBaseId"
        try:
            ssm.delete_parameter(Name=ssm_param_name)
            logger.info(f"Deleted SSM parameter: {ssm_param_name}")
        except Exception as e:
            logger.warning(f"Failed to delete Parameter Store entry: {e}")

    except Exception as e:
        logger.error(f"Failed to delete KB: {e}")
        # Don't fail deletion - best effort
