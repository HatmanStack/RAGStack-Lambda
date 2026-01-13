"""
Integration tests for media query functionality.

Tests the complete flow from query_kb Lambda processing citations
with media metadata to the correct source extraction.

Requires:
- Deployed stack with media documents ingested
- Set STACK_NAME environment variable

Run with: pytest tests/integration/test_media_query_integration.py -v
"""

import json
import os

import boto3
import pytest

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def stack_outputs():
    """Get CloudFormation stack outputs for the deployed stack."""
    stack_name = os.environ.get("STACK_NAME")
    if not stack_name:
        pytest.skip("STACK_NAME environment variable not set")

    cfn = boto3.client("cloudformation")
    try:
        response = cfn.describe_stacks(StackName=stack_name)
        outputs = response["Stacks"][0]["Outputs"]
        return {o["OutputKey"]: o["OutputValue"] for o in outputs}
    except Exception as e:
        pytest.skip(f"Could not get stack outputs: {e}")


@pytest.fixture(scope="module")
def lambda_client():
    """Create Lambda client."""
    return boto3.client("lambda")


@pytest.fixture(scope="module")
def query_function_name(stack_outputs):
    """Get the query Lambda function name from stack outputs."""
    # Function name typically follows pattern: {stack-name}-query-{suffix}
    stack_name = os.environ.get("STACK_NAME")
    lambda_client = boto3.client("lambda")

    # List functions and find the query function
    paginator = lambda_client.get_paginator("list_functions")
    for page in paginator.paginate():
        for func in page["Functions"]:
            if stack_name in func["FunctionName"] and "query" in func["FunctionName"].lower():
                return func["FunctionName"]

    pytest.skip("Could not find query Lambda function")


class TestMediaSourceExtraction:
    """Integration tests for media source extraction in queries."""

    def test_query_returns_media_fields_for_media_source(self, lambda_client, query_function_name):
        """Test that queries about media content return proper media fields."""
        # This test requires actual media content in the knowledge base
        # It verifies the complete flow works end-to-end

        event = {
            "arguments": {
                "query": "What was discussed in the video?",
                "conversationId": "test-media-integration",
            }
        }

        response = lambda_client.invoke(
            FunctionName=query_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        result = json.loads(response["Payload"].read().decode("utf-8"))

        # The response should be valid
        assert "answer" in result or "error" in result

        # If there are sources, verify they have the expected structure
        sources = result.get("sources", [])
        for source in sources:
            # All sources should have these base fields
            assert "documentId" in source
            assert "snippet" in source or source.get("isMedia")

            # Media sources should have additional fields
            if source.get("isMedia"):
                assert source.get("mediaType") in ["video", "audio"]
                assert source.get("contentType") in ["transcript", "visual"]
                # Timestamps should be numbers when present
                if source.get("timestampStart") is not None:
                    assert isinstance(source["timestampStart"], (int, float))
                if source.get("timestampEnd") is not None:
                    assert isinstance(source["timestampEnd"], (int, float))
                # timestampDisplay should be formatted string
                if source.get("timestampDisplay"):
                    assert ":" in source["timestampDisplay"]

    def test_document_url_includes_timestamp_fragment(self, lambda_client, query_function_name):
        """Test that media source URLs include timestamp fragments."""
        event = {
            "arguments": {
                "query": "What was mentioned at the beginning?",
                "conversationId": "test-media-timestamp",
            }
        }

        response = lambda_client.invoke(
            FunctionName=query_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        result = json.loads(response["Payload"].read().decode("utf-8"))
        sources = result.get("sources", [])

        for source in sources:
            # If media source with URL and timestamps, URL should have fragment
            if (
                source.get("isMedia")
                and source.get("documentUrl")
                and source.get("timestampStart") is not None
            ):
                assert "#t=" in source["documentUrl"]


class TestMediaSourceBackwardsCompatibility:
    """Ensure existing document/image sources still work correctly."""

    def test_regular_document_sources_unchanged(self, lambda_client, query_function_name):
        """Test that regular document queries still work."""
        event = {
            "arguments": {
                "query": "test query",
                "conversationId": "test-backwards-compat",
            }
        }

        response = lambda_client.invoke(
            FunctionName=query_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        result = json.loads(response["Payload"].read().decode("utf-8"))

        # Response should be valid
        assert "answer" in result or "error" in result

        # Sources should be an array
        sources = result.get("sources", [])
        assert isinstance(sources, list)

        for source in sources:
            # Regular documents should NOT have isMedia set
            if not source.get("isMedia"):
                # These should not have media-specific fields set
                assert source.get("mediaType") is None
                assert source.get("timestampStart") is None


class TestMediaSourceFormatting:
    """Test timestamp formatting and display."""

    def test_timestamp_display_format(self, lambda_client, query_function_name):
        """Test that timestampDisplay follows expected format."""
        event = {
            "arguments": {
                "query": "Search for content",
                "conversationId": "test-timestamp-format",
            }
        }

        response = lambda_client.invoke(
            FunctionName=query_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        result = json.loads(response["Payload"].read().decode("utf-8"))
        sources = result.get("sources", [])

        for source in sources:
            if source.get("isMedia") and source.get("timestampDisplay"):
                display = source["timestampDisplay"]
                # Should be in format "M:SS-M:SS" or "M:SS"
                assert ":" in display
                # Each part should be numeric except for the dash
                parts = display.replace("-", ":").split(":")
                for part in parts:
                    assert part.isdigit(), f"Non-numeric part in timestamp: {part}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
