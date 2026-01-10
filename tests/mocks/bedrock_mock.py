"""Bedrock API mock responses for testing.

This module provides mock response generators for Bedrock API calls,
enabling unit tests to run without live AWS calls.
"""

import json
from typing import Any
from unittest.mock import MagicMock


def create_converse_response(
    text: str,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> dict[str, Any]:
    """
    Create a mock Bedrock converse API response.

    Args:
        text: The text content to return.
        input_tokens: Simulated input token count.
        output_tokens: Simulated output token count.

    Returns:
        Mock response dictionary matching Bedrock API structure.
    """
    return {
        "response": {
            "output": {
                "message": {
                    "content": [{"text": text}],
                    "role": "assistant",
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": input_tokens,
                "outputTokens": output_tokens,
                "totalTokens": input_tokens + output_tokens,
            },
        },
        "metering": {
            "metadata_extraction/doc-123/bedrock/model-id": {
                "inputTokens": input_tokens,
                "outputTokens": output_tokens,
                "totalTokens": input_tokens + output_tokens,
            }
        },
    }


def create_metadata_extraction_response(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Create a mock response for metadata extraction.

    Args:
        metadata: The metadata dictionary to return.

    Returns:
        Mock response with JSON metadata as text content.
    """
    return create_converse_response(json.dumps(metadata))


# Pre-built responses for common test scenarios

SUCCESSFUL_IMMIGRATION_RESPONSE = create_metadata_extraction_response(
    {
        "topic": "immigration",
        "document_type": "ship_manifest",
        "date_range": "1900-1910",
        "location": "Ellis Island",
        "source_category": "government_record",
    }
)


def create_mock_bedrock_client(default_response: dict[str, Any] | None = None) -> MagicMock:
    """
    Create a fully mocked BedrockClient.

    Args:
        default_response: Default response for invoke_model calls.

    Returns:
        MagicMock configured as a BedrockClient.
    """
    mock = MagicMock()

    if default_response:
        mock.invoke_model.return_value = default_response
        mock.extract_text_from_response.return_value = (
            default_response.get("response", {})
            .get("output", {})
            .get("message", {})
            .get("content", [{}])[0]
            .get("text", "")
        )
    else:
        mock.invoke_model.return_value = SUCCESSFUL_IMMIGRATION_RESPONSE
        mock.extract_text_from_response.return_value = json.dumps(
            {
                "topic": "immigration",
                "document_type": "ship_manifest",
                "date_range": "1900-1910",
                "location": "Ellis Island",
            }
        )

    mock.metering_data = {}
    mock.get_metering_data.return_value = {}

    return mock
