"""
Knowledge Base Migrator for reindex operations.

Handles creation and deletion of Bedrock Knowledge Bases with S3 Vectors.
Follows the same patterns as kb_custom_resource but for migration purposes.
"""

import logging
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class KBMigrator:
    """
    Manages Knowledge Base creation and deletion for reindex operations.

    Uses S3 Vectors as the vector store (same as kb_custom_resource).
    """

    def __init__(
        self,
        data_bucket: str,
        vector_bucket: str,
        stack_name: str,
        kb_role_arn: str,
        embedding_model_arn: str,
        region: str = None,
    ):
        """
        Initialize KBMigrator.

        Args:
            data_bucket: S3 bucket for document content
            vector_bucket: S3 Vectors bucket for vector storage
            stack_name: CloudFormation stack name (for resource naming)
            kb_role_arn: IAM role ARN for Knowledge Base
            embedding_model_arn: Bedrock embedding model ARN
            region: AWS region (defaults to session region)
        """
        self.data_bucket = data_bucket
        self.vector_bucket = vector_bucket
        self.stack_name = stack_name
        self.kb_role_arn = kb_role_arn
        self.embedding_model_arn = embedding_model_arn

        session = boto3.Session()
        self.region = region or session.region_name or "us-east-1"

        self.bedrock_agent = boto3.client("bedrock-agent", region_name=self.region)
        self.s3vectors = boto3.client("s3vectors", region_name=self.region)
        self.sts = boto3.client("sts", region_name=self.region)

    def create_knowledge_base(self, suffix: str = None) -> dict[str, Any]:
        """
        Create a new Knowledge Base with S3 Vectors data source.

        Args:
            suffix: Optional suffix for unique naming (e.g., timestamp)

        Returns:
            Dictionary with kb_id, data_source_id, vector_bucket_name, and status
        """
        kb_name = f"{self.stack_name}-KB"
        if suffix:
            kb_name = f"{kb_name}-{suffix}"

        logger.info(f"Creating Knowledge Base: {kb_name}")

        # Step 1: Initialize S3 Vectors bucket
        self._initialize_vector_bucket()

        # Step 2: Create S3 Vectors index
        index_name = f"{self.stack_name.lower()}-index"
        if suffix:
            index_name = f"{index_name}-{suffix}"

        vector_index_arn = self._create_s3_vectors_index(index_name)
        logger.info(f"Created S3 Vectors index: {vector_index_arn}")

        # Step 3: Create Knowledge Base
        # Note: supplementalDataStorageConfiguration uses data_bucket (for Nova Multimodal)
        # storageConfiguration uses vector_bucket (for S3 Vectors index)
        multimodal_storage_uri = f"s3://{self.data_bucket}"

        try:
            kb_response = self.bedrock_agent.create_knowledge_base(
                name=kb_name,
                description=f"RAGStack Knowledge Base for {self.stack_name}",
                roleArn=self.kb_role_arn,
                knowledgeBaseConfiguration={
                    "type": "VECTOR",
                    "vectorKnowledgeBaseConfiguration": {
                        "embeddingModelConfiguration": {
                            "bedrockEmbeddingModelConfiguration": {
                                "dimensions": 1024,
                                "embeddingDataType": "FLOAT32",
                            }
                        },
                        "embeddingModelArn": self.embedding_model_arn,
                        # Required for Nova Multimodal Embeddings
                        "supplementalDataStorageConfiguration": {
                            "storageLocations": [
                                {
                                    "type": "S3",
                                    "s3Location": {"uri": multimodal_storage_uri},
                                }
                            ]
                        },
                    },
                },
                storageConfiguration={
                    "type": "S3_VECTORS",
                    "s3VectorsConfiguration": {"indexArn": vector_index_arn},
                },
            )

            kb_id = kb_response["knowledgeBase"]["knowledgeBaseId"]
            logger.info(f"Created Knowledge Base: {kb_id}")

            # Wait for KB to be available
            self._wait_for_kb_status(kb_id, "ACTIVE")

            # Step 4: Create Data Source (reads from data_bucket)
            ds_response = self.bedrock_agent.create_data_source(
                knowledgeBaseId=kb_id,
                name=f"{kb_name}-DataSource",
                description="S3 content data source",
                dataSourceConfiguration={
                    "type": "S3",
                    "s3Configuration": {
                        "bucketArn": f"arn:aws:s3:::{self.data_bucket}",
                        "inclusionPrefixes": ["content/"],
                    },
                },
            )

            data_source_id = ds_response["dataSource"]["dataSourceId"]
            logger.info(f"Created Data Source: {data_source_id}")

            return {
                "kb_id": kb_id,
                "data_source_id": data_source_id,
                "vector_index_arn": vector_index_arn,
                "vector_bucket_name": self.vector_bucket,
                "status": "ACTIVE",
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Failed to create Knowledge Base: {error_code} - {error_msg}")
            raise

    def _initialize_vector_bucket(self) -> None:
        """
        Initialize S3 Vectors bucket.

        Creates the vector bucket if it doesn't exist.
        Follows pattern from kb_custom_resource.
        """
        logger.info(f"Initializing S3 Vectors bucket: {self.vector_bucket}")
        try:
            self.s3vectors.create_vector_bucket(vectorBucketName=self.vector_bucket)
            logger.info(f"S3 Vectors bucket initialized: {self.vector_bucket}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_msg = str(e)
            # Bucket already exists is a non-fatal condition
            if error_code == "ConflictException" or "already exists" in error_msg.lower():
                logger.info(f"S3 Vectors bucket already exists: {self.vector_bucket}")
            else:
                logger.error(f"Failed to create S3 Vectors bucket: {e}")
                raise

    def _create_s3_vectors_index(self, index_name: str) -> str:
        """
        Create S3 Vectors index for the Knowledge Base.

        Args:
            index_name: Name for the vector index

        Returns:
            ARN of the created index
        """
        try:
            # Check if index already exists
            try:
                existing = self.s3vectors.get_index(
                    vectorBucketName=self.vector_bucket, indexName=index_name
                )
                return existing["index"]["indexArn"]
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                # S3 Vectors returns NotFoundException, not ResourceNotFoundException
                if error_code not in ("ResourceNotFoundException", "NotFoundException"):
                    raise

            # Create new index in vector bucket
            account_id = self.sts.get_caller_identity()["Account"]
            self.s3vectors.create_index(
                vectorBucketName=self.vector_bucket,
                indexName=index_name,
                dataType="float32",
                dimension=1024,
                distanceMetric="cosine",
                metadataConfiguration={
                    "nonFilterableMetadataKeys": [
                        "AMAZON_BEDROCK_TEXT",
                        "AMAZON_BEDROCK_METADATA",
                    ]
                },
            )

            # Construct index ARN
            index_arn = (
                f"arn:aws:s3vectors:{self.region}:{account_id}:"
                f"bucket/{self.vector_bucket}/index/{index_name}"
            )
            logger.info(f"Created S3 Vectors index ARN: {index_arn}")

            # Wait for index to be ready
            self._wait_for_index_status(index_name, "READY")

            return index_arn

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Failed to create S3 Vectors index: {error_code}")
            raise

    def _wait_for_kb_status(
        self, kb_id: str, target_status: str, timeout: int = 300, interval: int = 10
    ) -> None:
        """Wait for Knowledge Base to reach target status."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.bedrock_agent.get_knowledge_base(knowledgeBaseId=kb_id)
                status = response["knowledgeBase"]["status"]

                if status == target_status:
                    logger.info(f"KB {kb_id} reached status: {status}")
                    return

                if status in ("FAILED", "DELETE_UNSUCCESSFUL"):
                    raise RuntimeError(f"KB {kb_id} entered failed status: {status}")

                logger.info(f"KB {kb_id} status: {status}, waiting for {target_status}...")
                time.sleep(interval)

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code == "ResourceNotFoundException" and target_status == "DELETED":
                    return
                raise

        raise TimeoutError(f"KB {kb_id} did not reach {target_status} within {timeout}s")

    def _wait_for_index_status(
        self, index_name: str, target_status: str, timeout: int = 300, interval: int = 10
    ) -> None:
        """Wait for S3 Vectors index to reach target status."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.s3vectors.get_index(
                    vectorBucketName=self.vector_bucket, indexName=index_name
                )
                # S3 Vectors doesn't return indexStatus - if get_index succeeds, index is ready
                # Check for status field (may not exist), default to READY if missing
                status = response.get("index", {}).get("indexStatus", "READY")

                if status == target_status:
                    logger.info(f"Index {index_name} reached status: {status}")
                    return

                if status == "FAILED":
                    raise RuntimeError(f"Index {index_name} creation failed")

                logger.info(f"Index {index_name} status: {status}, waiting for {target_status}...")
                time.sleep(interval)

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                # S3 Vectors returns NotFoundException, not ResourceNotFoundException
                not_found = error_code in ("ResourceNotFoundException", "NotFoundException")
                if not_found and target_status == "DELETED":
                    return
                raise

        raise TimeoutError(f"Index {index_name} did not reach {target_status} within {timeout}s")

    def delete_knowledge_base(self, kb_id: str, delete_vectors: bool = True) -> None:
        """
        Delete a Knowledge Base and optionally its vector index.

        Args:
            kb_id: Knowledge Base ID to delete
            delete_vectors: Whether to delete the S3 Vectors index
        """
        logger.info(f"Deleting Knowledge Base: {kb_id}")

        try:
            # Get KB details to find vector index
            kb_response = self.bedrock_agent.get_knowledge_base(knowledgeBaseId=kb_id)
            kb_config = kb_response.get("knowledgeBase", {})
            storage_config = kb_config.get("storageConfiguration", {})

            # Extract vector index ARN if S3 storage
            vector_index_arn = None
            if storage_config.get("type") == "S3":
                s3_config = storage_config.get("s3Configuration", {})
                vector_index_arn = s3_config.get("vectorIndexArn")

            # Delete data sources first
            try:
                ds_response = self.bedrock_agent.list_data_sources(knowledgeBaseId=kb_id)
                for ds in ds_response.get("dataSourceSummaries", []):
                    ds_id = ds["dataSourceId"]
                    logger.info(f"Deleting data source: {ds_id}")
                    self.bedrock_agent.delete_data_source(knowledgeBaseId=kb_id, dataSourceId=ds_id)
            except ClientError as e:
                logger.warning(f"Error listing/deleting data sources: {e}")

            # Delete Knowledge Base
            self.bedrock_agent.delete_knowledge_base(knowledgeBaseId=kb_id)
            logger.info(f"Delete initiated for KB: {kb_id}")

            # Wait for deletion
            self._wait_for_kb_status(kb_id, "DELETED", timeout=600)

            # Delete S3 Vectors index if requested
            if delete_vectors and vector_index_arn:
                self._delete_s3_vectors_index(vector_index_arn)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "ResourceNotFoundException":
                logger.info(f"KB {kb_id} already deleted")
                return
            logger.error(f"Failed to delete KB {kb_id}: {error_code}")
            raise

    def _delete_s3_vectors_index(self, index_arn: str) -> None:
        """
        Delete S3 Vectors index.

        Args:
            index_arn: ARN of the index to delete
        """
        # Parse index name from ARN
        # Format: arn:aws:s3vectors:region:account:bucket/index-name
        try:
            parts = index_arn.split("/")
            if len(parts) >= 2:
                index_name = parts[-1]
                bucket_part = parts[-2].split(":")[-1]

                logger.info(f"Deleting S3 Vectors index: {index_name} from {bucket_part}")

                self.s3vectors.delete_index(indexBucketName=bucket_part, indexName=index_name)

                # Wait for deletion
                self._wait_for_index_status(index_name, "DELETED", timeout=300)
            else:
                logger.warning(f"Could not parse index ARN: {index_arn}")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            # S3 Vectors returns NotFoundException, not ResourceNotFoundException
            if error_code in ("ResourceNotFoundException", "NotFoundException"):
                logger.info(f"Index already deleted: {index_arn}")
                return
            logger.warning(f"Failed to delete index {index_arn}: {e}")
