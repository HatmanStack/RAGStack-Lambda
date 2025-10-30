"""
Bedrock client module for RAGStack-Lambda.

Provides a simplified client for invoking Amazon Bedrock models with:
- Exponential backoff retry logic
- Token usage tracking and metering
- Support for both converse API (text extraction) and embeddings
"""

import json
import logging
import os
import random
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError

logger = logging.getLogger(__name__)

# Default retry settings
DEFAULT_MAX_RETRIES = 7
DEFAULT_INITIAL_BACKOFF = 2  # seconds
DEFAULT_MAX_BACKOFF = 300  # 5 minutes


class BedrockClient:
    """Client for interacting with Amazon Bedrock models."""

    def __init__(
        self,
        region: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
        max_backoff: float = DEFAULT_MAX_BACKOFF,
    ):
        """
        Initialize a Bedrock client.

        Args:
            region: AWS region (defaults to AWS_REGION env var or us-east-1)
            max_retries: Maximum number of retry attempts
            initial_backoff: Initial backoff time in seconds
            max_backoff: Maximum backoff time in seconds
        """
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self._client = None
        self.metering_data = {}  # Track token usage

    @property
    def client(self):
        """Lazy-loaded Bedrock client."""
        if self._client is None:
            config = Config(
                connect_timeout=10,
                read_timeout=300,  # Allow time for large extractions
            )
            self._client = boto3.client("bedrock-runtime", region_name=self.region, config=config)
        return self._client

    def invoke_model(
        self,
        model_id: str,
        system_prompt: str | list[dict[str, str]],
        content: list[dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        context: str = "Unspecified",
    ) -> dict[str, Any]:
        """
        Invoke a Bedrock model with retry logic.

        Args:
            model_id: The Bedrock model ID (e.g., 'anthropic.claude-3-5-haiku-20241022-v1:0')
            system_prompt: The system prompt as string or list of content objects
            content: The content for the user message (can include text and images)
            temperature: The temperature parameter for model inference
            max_tokens: Optional max_tokens parameter
            context: Context prefix for metering key

        Returns:
            Bedrock response object with metering information
        """
        # Format system prompt if needed
        if isinstance(system_prompt, str):
            formatted_system_prompt = [{"text": system_prompt}]
        else:
            formatted_system_prompt = system_prompt

        # Build message
        message = {"role": "user", "content": content}
        messages = [message]

        # Initialize inference config
        inference_config = {"temperature": temperature}
        if max_tokens is not None:
            inference_config["maxTokens"] = max_tokens

        # Build converse parameters
        converse_params = {
            "modelId": model_id,
            "messages": messages,
            "system": formatted_system_prompt,
            "inferenceConfig": inference_config,
        }

        # Start timing
        request_start_time = time.time()

        # Call with retry
        return self._invoke_with_retry(
            model_id=model_id,
            converse_params=converse_params,
            retry_count=0,
            request_start_time=request_start_time,
            context=context,
        )

    def _invoke_with_retry(
        self,
        model_id: str,
        converse_params: dict[str, Any],
        retry_count: int,
        request_start_time: float,
        context: str = "Unspecified",
        _last_exception: Exception = None,
    ) -> dict[str, Any]:
        """
        Recursive helper method to handle retries for Bedrock invocation.
        """
        try:
            logger.info(
                f"Bedrock request attempt {retry_count + 1}/{self.max_retries + 1}: {model_id}"
            )

            # Make the API call
            response = self.client.converse(**converse_params)

            # Calculate duration
            duration = time.time() - request_start_time
            logger.info(f"Bedrock request successful. Duration: {duration:.2f}s")
            logger.info(f"Token Usage: {response.get('usage')}")

            # Track token usage in metering data
            usage = response.get("usage", {})
            metering_key = f"{context}/bedrock/{model_id}"
            if metering_key not in self.metering_data:
                self.metering_data[metering_key] = {
                    "inputTokens": 0,
                    "outputTokens": 0,
                    "totalTokens": 0,
                }

            self.metering_data[metering_key]["inputTokens"] += usage.get("inputTokens", 0)
            self.metering_data[metering_key]["outputTokens"] += usage.get("outputTokens", 0)
            self.metering_data[metering_key]["totalTokens"] += usage.get("totalTokens", 0)

            # Return response with metering
            return {"response": response, "metering": {metering_key: usage}}

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]

            retryable_errors = [
                "ThrottlingException",
                "ServiceQuotaExceededException",
                "RequestLimitExceeded",
                "TooManyRequestsException",
                "ServiceUnavailableException",
                "ModelErrorException",
                "RequestTimeout",
                "RequestTimeoutException",
            ]

            if error_code in retryable_errors:
                # Check if we've reached max retries
                if retry_count >= self.max_retries:
                    logger.error(
                        f"Max retries ({self.max_retries}) exceeded. Last error: {error_message}"
                    )
                    raise

                # Calculate backoff time
                backoff = self._calculate_backoff(retry_count)
                logger.warning(
                    f"Bedrock throttling (attempt {retry_count + 1}/{self.max_retries + 1}). "
                    f"Error: {error_message}. Backing off for {backoff:.2f}s"
                )

                # Sleep and retry
                time.sleep(backoff)

                return self._invoke_with_retry(
                    model_id=model_id,
                    converse_params=converse_params,
                    retry_count=retry_count + 1,
                    request_start_time=request_start_time,
                    context=context,
                    _last_exception=e,
                )
            logger.error(f"Non-retryable Bedrock error: {error_code} - {error_message}")
            raise

        except (ReadTimeoutError, ConnectTimeoutError) as e:
            error_message = str(e)

            # Check if we've reached max retries
            if retry_count >= self.max_retries:
                logger.error(
                    f"Max retries ({self.max_retries}) exceeded. Last timeout: {error_message}"
                )
                raise

            # Calculate backoff time
            backoff = self._calculate_backoff(retry_count)
            logger.warning(
                f"Bedrock timeout (attempt {retry_count + 1}/{self.max_retries + 1}). "
                f"Backing off for {backoff:.2f}s"
            )

            # Sleep and retry
            time.sleep(backoff)

            return self._invoke_with_retry(
                model_id=model_id,
                converse_params=converse_params,
                retry_count=retry_count + 1,
                request_start_time=request_start_time,
                context=context,
                _last_exception=e,
            )

        except Exception as e:
            logger.error(f"Unexpected Bedrock error: {str(e)}", exc_info=True)
            raise

    def generate_embedding(
        self, text: str, model_id: str = "amazon.titan-embed-text-v2:0"
    ) -> list[float]:
        """
        Generate an embedding vector for the given text.

        Args:
            text: The text to generate embeddings for
            model_id: The embedding model ID

        Returns:
            List of floats representing the embedding vector
        """
        if not text or not isinstance(text, str):
            return []

        # Normalize whitespace
        normalized_text = " ".join(text.split())

        # Prepare request body for Titan embedding models
        request_body = json.dumps({"inputText": normalized_text})

        # Call with retry
        return self._generate_embedding_with_retry(
            model_id=model_id, request_body=request_body, retry_count=0
        )

    def generate_image_embedding(
        self, image_bytes: bytes, model_id: str = "amazon.titan-embed-image-v1"
    ) -> list[float]:
        """
        Generate an embedding vector for an image.

        Args:
            image_bytes: The image file bytes
            model_id: The embedding model ID (default: Titan Embed Image V1)

        Returns:
            List of floats representing the embedding vector
        """
        if not image_bytes:
            return []

        # Encode image as base64
        import base64

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # Prepare request body for Titan image embedding model
        request_body = json.dumps({"inputImage": image_base64})

        # Call with retry
        return self._generate_embedding_with_retry(
            model_id=model_id, request_body=request_body, retry_count=0
        )

    def _generate_embedding_with_retry(
        self, model_id: str, request_body: str, retry_count: int, _last_exception: Exception = None
    ) -> list[float]:
        """
        Recursive helper for embedding generation with retry.
        """
        try:
            logger.info(
                f"Bedrock embedding request attempt {retry_count + 1}/"
                f"{self.max_retries + 1}: {model_id}"
            )

            attempt_start_time = time.time()
            response = self.client.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=request_body,
            )
            duration = time.time() - attempt_start_time

            # Extract embedding vector
            response_body = json.loads(response["body"].read())
            embedding = response_body.get("embedding", [])

            logger.info(f"Generated embedding with {len(embedding)} dimensions in {duration:.2f}s")
            return embedding

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]

            retryable_errors = [
                "ThrottlingException",
                "ServiceQuotaExceededException",
                "RequestLimitExceeded",
                "TooManyRequestsException",
                "ServiceUnavailableException",
                "RequestTimeout",
                "ReadTimeout",
            ]

            if error_code in retryable_errors:
                if retry_count >= self.max_retries:
                    logger.error(f"Max retries ({self.max_retries}) exceeded for embedding")
                    raise

                backoff = self._calculate_backoff(retry_count)
                logger.warning(f"Bedrock throttling. Backing off for {backoff:.2f}s")
                time.sleep(backoff)

                return self._generate_embedding_with_retry(
                    model_id=model_id,
                    request_body=request_body,
                    retry_count=retry_count + 1,
                    _last_exception=e,
                )
            logger.error(f"Non-retryable embedding error: {error_code} - {error_message}")
            raise

        except (ReadTimeoutError, ConnectTimeoutError) as e:
            if retry_count >= self.max_retries:
                logger.exception(f"Max retries ({self.max_retries}) exceeded for embedding timeout")
                raise

            backoff = self._calculate_backoff(retry_count)
            logger.warning(
                f"Bedrock embedding timeout (attempt {retry_count + 1}/{self.max_retries + 1}). "
                f"Backing off for {backoff:.2f}s"
            )
            time.sleep(backoff)

            return self._generate_embedding_with_retry(
                model_id=model_id,
                request_body=request_body,
                retry_count=retry_count + 1,
                _last_exception=e,
            )

        except Exception:
            logger.exception("Unexpected error generating embedding")
            raise

    def extract_text_from_response(self, response: dict[str, Any]) -> str:
        """
        Extract text from a Bedrock response with safe navigation.

        Args:
            response: Bedrock response object

        Returns:
            Extracted text content, or empty string if structure is unexpected
        """
        response_obj = response.get("response", {})
        output = response_obj.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])

        if isinstance(content, list) and len(content) > 0 and isinstance(content[0], dict):
            return content[0].get("text", "")
        return ""

    def _calculate_backoff(self, retry_count: int) -> float:
        """
        Calculate exponential backoff time with jitter.

        Args:
            retry_count: Current retry attempt (0-based)

        Returns:
            Backoff time in seconds
        """
        # Exponential backoff
        backoff_seconds = min(self.max_backoff, self.initial_backoff * (2**retry_count))

        # Add jitter
        jitter = random.random()

        return backoff_seconds + jitter

    def get_metering_data(self) -> dict[str, Any]:
        """
        Get accumulated metering data.

        Returns:
            Dictionary of metering data by context/model
        """
        return self.metering_data
