"""Nova Multimodal Embeddings client for video/audio segment embedding.

.. deprecated::
    This module is deprecated as of visual embeddings implementation.
    Bedrock KB creates embeddings automatically during ingestion sync.
    Kept for potential future direct embedding use cases.

Original purpose: Direct Nova Multimodal Embedding API calls.

This module provides a client for Amazon Nova Multimodal Embeddings, which
creates embeddings from video and audio content for similarity search.

The client supports:
- Direct video/audio segment embedding (up to 30 seconds)
- S3-based embedding for larger content
- Configurable embedding dimensions
- Retry logic for throttling/transient errors
"""

import base64
import json
import logging
import os
import random
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ragstack_common.exceptions import MediaProcessingError

logger = logging.getLogger(__name__)

# Default model for Nova Multimodal Embeddings
DEFAULT_MODEL_ID = "amazon.nova-embed-multimodal-v1:0"

# Default embedding dimension
DEFAULT_EMBEDDING_DIMENSION = 1024

# Retry settings
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF = 1  # seconds
DEFAULT_MAX_BACKOFF = 60  # seconds

# Retryable error codes (excluding ModelErrorException which needs targeted inspection)
RETRYABLE_ERRORS = frozenset(
    {
        "ThrottlingException",
        "ServiceQuotaExceededException",
        "RequestLimitExceeded",
        "TooManyRequestsException",
        "ServiceUnavailableException",
    }
)


def is_transient_model_error(error: ClientError) -> bool:
    """
    Check if a ModelErrorException is transient and should be retried.

    Only retries ModelErrorException when:
    - The originalStatusCode is in the 5xx range (server error)
    - The error message indicates a transient condition

    Args:
        error: The ClientError exception to check.

    Returns:
        True if the error appears transient and should be retried.
    """
    error_code = error.response.get("Error", {}).get("Code", "")
    if error_code != "ModelErrorException":
        return False

    # Check for originalStatusCode in the error response
    error_info = error.response.get("Error", {})
    message = error_info.get("Message", "")

    # Look for 5xx status codes in the error
    original_status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
    if 500 <= original_status < 600:
        return True

    # Check for transient indicators in the message
    transient_indicators = [
        "temporarily unavailable",
        "service unavailable",
        "internal server error",
        "capacity",
        "overloaded",
        "try again",
    ]
    message_lower = message.lower()
    return any(indicator in message_lower for indicator in transient_indicators)


class NovaEmbeddingsClient:
    """
    Client for Amazon Nova Multimodal Embeddings.

    Provides methods to embed video and audio segments for similarity search.
    Supports both direct content embedding and S3-based embedding.

    Usage:
        client = NovaEmbeddingsClient()
        result = client.embed_video_segment(video_bytes)
        embedding = result["embedding"]
    """

    def __init__(
        self,
        region: str | None = None,
        model_id: str | None = None,
        embedding_dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
        max_backoff: float = DEFAULT_MAX_BACKOFF,
    ):
        """
        Initialize the Nova Embeddings client.

        Args:
            region: AWS region (defaults to AWS_REGION env var or us-east-1).
            model_id: Nova model ID (defaults to amazon.nova-embed-multimodal-v1:0).
            embedding_dimension: Output embedding dimension (256, 512, or 1024).
            max_retries: Maximum retry attempts for throttled requests.
            initial_backoff: Initial backoff time in seconds.
            max_backoff: Maximum backoff time in seconds.
        """
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.model_id = model_id or DEFAULT_MODEL_ID
        self.embedding_dimension = embedding_dimension
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff

        # Lazy-loaded clients
        self._bedrock_client = None
        self._s3_client = None

        logger.info(
            f"Initialized NovaEmbeddingsClient: model={self.model_id}, "
            f"dimension={self.embedding_dimension}, region={self.region}"
        )

    @property
    def bedrock_client(self):
        """Lazy-load Bedrock runtime client."""
        if self._bedrock_client is None:
            config = Config(
                connect_timeout=10,
                read_timeout=120,
            )
            self._bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
                config=config,
            )
        return self._bedrock_client

    @property
    def s3_client(self):
        """Lazy-load S3 client."""
        if self._s3_client is None:
            self._s3_client = boto3.client("s3", region_name=self.region)
        return self._s3_client

    def embed_video_segment(
        self,
        video_bytes: bytes,
    ) -> dict[str, Any]:
        """
        Embed a video segment (up to 30 seconds).

        Args:
            video_bytes: Raw video bytes (MP4, MOV, WebM).

        Returns:
            Dictionary containing:
            - embedding: List of float values (embedding vector)
            - input_token_count: Number of input tokens used

        Raises:
            MediaProcessingError: If embedding fails.
        """
        # Encode video to base64
        video_b64 = base64.b64encode(video_bytes).decode("utf-8")

        # Build request body
        request_body = {
            "inputVideo": {
                "base64": video_b64,
            },
            "embeddingConfig": {
                "outputEmbeddingLength": self.embedding_dimension,
            },
        }

        return self._invoke_with_retry(request_body)

    def embed_audio_segment(
        self,
        audio_bytes: bytes,
    ) -> dict[str, Any]:
        """
        Embed an audio segment (up to 30 seconds).

        Args:
            audio_bytes: Raw audio bytes (MP3, WAV, M4A, OGG).

        Returns:
            Dictionary containing:
            - embedding: List of float values (embedding vector)
            - input_token_count: Number of input tokens used

        Raises:
            MediaProcessingError: If embedding fails.
        """
        # Encode audio to base64
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        # Build request body - Nova uses inputAudio for audio content
        request_body = {
            "inputAudio": {
                "base64": audio_b64,
            },
            "embeddingConfig": {
                "outputEmbeddingLength": self.embedding_dimension,
            },
        }

        return self._invoke_with_retry(request_body)

    def embed_from_s3(
        self,
        s3_uri: str,
        media_type: str = "video",
    ) -> dict[str, Any]:
        """
        Embed media from S3 URI.

        Downloads the content from S3 and embeds it. Use for segments
        that have already been extracted and stored in S3.

        Args:
            s3_uri: S3 URI of the media segment (s3://bucket/key).
            media_type: "video" or "audio".

        Returns:
            Dictionary containing embedding vector and metadata.

        Raises:
            MediaProcessingError: If download or embedding fails.
        """
        # Parse S3 URI
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI: {s3_uri}")

        path = s3_uri[5:]  # Remove 's3://'
        bucket, key = path.split("/", 1)

        try:
            # Download content from S3
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response["Body"].read()

            # Normalize and respect explicit media_type first
            normalized_type = (media_type or "").lower().strip()

            if normalized_type == "video":
                return self.embed_video_segment(content)
            if normalized_type == "audio":
                return self.embed_audio_segment(content)

            # Fall back to extension inference if media_type not specified
            if key.lower().endswith((".mp4", ".mov", ".webm")):
                return self.embed_video_segment(content)
            return self.embed_audio_segment(content)

        except ClientError as e:
            logger.error(f"Failed to download from S3: {e}")
            raise MediaProcessingError(f"S3 download failed: {e}") from e

    def _invoke_with_retry(
        self,
        request_body: dict,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        """
        Invoke model with retry logic for throttling errors.

        Args:
            request_body: Request body for invoke_model API.
            retry_count: Current retry attempt (0-based).

        Returns:
            Parsed embedding response.

        Raises:
            MediaProcessingError: If all retries exhausted.
            ClientError: For non-retryable errors.
        """
        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json",
            )

            # Parse response
            response_body = json.loads(response["body"].read())

            # Validate response
            if "embedding" not in response_body:
                raise MediaProcessingError(
                    f"No embedding in response: {list(response_body.keys())}"
                )

            return {
                "embedding": response_body["embedding"],
                "input_token_count": response_body.get("inputTextTokenCount", 0),
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            # Check if error is retryable (known retryable codes or transient model error)
            is_retryable = error_code in RETRYABLE_ERRORS or is_transient_model_error(e)

            if is_retryable and retry_count < self.max_retries:
                # Calculate backoff with jitter
                backoff = self._calculate_backoff(retry_count)
                logger.warning(
                    f"Retrying Nova embedding after {backoff:.2f}s "
                    f"(attempt {retry_count + 1}/{self.max_retries}): {error_code}"
                )
                time.sleep(backoff)

                return self._invoke_with_retry(request_body, retry_count + 1)

            logger.error(f"Nova embedding failed: {e}")
            raise

    def _calculate_backoff(self, retry_count: int) -> float:
        """
        Calculate exponential backoff with jitter.

        Args:
            retry_count: Current retry attempt (0-based).

        Returns:
            Backoff time in seconds.
        """
        backoff = min(self.max_backoff, self.initial_backoff * (2**retry_count))
        jitter = random.random() * 0.5  # 0-50% jitter
        return backoff * (1 + jitter)
