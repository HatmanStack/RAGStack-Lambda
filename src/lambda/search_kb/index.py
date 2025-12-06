"""
Knowledge Base Search Lambda

AppSync resolver for searching the Knowledge Base with raw vector search.
Returns matching documents without conversational AI processing.

Input (AppSync):
{
    "query": "What is in this document?",
    "maxResults": 5
}

Output (KBQueryResult):
{
    "query": "What is in this document?",
    "results": [
        {
            "content": "Document text content...",
            "source": "s3://bucket/document-id/pages/page-1.json",
            "score": 0.85
        }
    ],
    "total": 3,
    "error": null
}
"""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Search Bedrock Knowledge Base using vector similarity.

    Args:
        event['query'] (str): Search query text
        event['maxResults'] (int, optional): Maximum results to return (default: 5)

    Returns:
        dict: KBQueryResult with query, results, total, and optional error
    """
    # Get environment variables
    knowledge_base_id = os.environ.get("KNOWLEDGE_BASE_ID")
    if not knowledge_base_id:
        return {
            "query": "",
            "results": [],
            "total": 0,
            "error": "KNOWLEDGE_BASE_ID environment variable is required",
        }

    # Create Bedrock client
    bedrock_agent = boto3.client("bedrock-agent-runtime")

    # Extract inputs from AppSync event
    # AppSync sends: {"arguments": {"query": "...", "maxResults": 5}, ...}
    arguments = event.get("arguments", event)  # Fallback to event for direct invocation
    query = arguments.get("query", "")
    max_results = arguments.get("maxResults", 5)

    # Log safe summary
    safe_summary = {
        "query_length": len(query) if isinstance(query, str) else 0,
        "max_results": max_results,
        "knowledge_base_id": knowledge_base_id[:8] + "..."
        if len(knowledge_base_id) > 8
        else knowledge_base_id,
    }
    logger.info(f"Searching Knowledge Base: {json.dumps(safe_summary)}")

    try:
        # Validate query
        if not query:
            return {"query": "", "results": [], "total": 0, "error": "No query provided"}

        if not isinstance(query, str):
            return {
                "query": "",
                "results": [],
                "total": 0,
                "error": "Query must be a string",
            }

        if len(query) > 10000:
            # SECURITY: Return truncated query (first 100 chars) in error response instead of
            # the full query. This prevents potential data leakage if error responses are logged
            # or returned to clients - a 10,000+ character query could contain sensitive content.
            return {
                "query": query[:100] + "...",
                "results": [],
                "total": 0,
                "error": "Query exceeds maximum length of 10000 characters",
            }

        # Validate maxResults
        if not isinstance(max_results, int) or max_results < 1 or max_results > 100:
            max_results = 5  # Use default if invalid

        # Query Knowledge Base using retrieve (raw vector search)
        response = bedrock_agent.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": max_results}},
        )

        # Parse results
        results = []
        for item in response.get("retrievalResults", []):
            results.append(
                {
                    "content": item.get("content", {}).get("text", ""),
                    "source": item.get("location", {}).get("s3Location", {}).get("uri", ""),
                    "score": item.get("score", 0.0),
                }
            )

        logger.info(f"Found {len(results)} results")

        return {"query": query, "results": results, "total": len(results)}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", "")
        logger.error(f"Bedrock client error: {error_code} - {error_msg}")
        return {
            "query": query,
            "results": [],
            "total": 0,
            "error": f"Failed to search knowledge base: {error_msg}",
        }

    except Exception as e:
        logger.error(f"Error searching KB: {e}", exc_info=True)
        return {
            "query": query,
            "results": [],
            "total": 0,
            "error": "Failed to search knowledge base. Please try again.",
        }
