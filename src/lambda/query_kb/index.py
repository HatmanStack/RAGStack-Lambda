"""
Knowledge Base Query Lambda

AppSync resolver for searching/chatting with the Knowledge Base.

Input (AppSync):
{
    "query": "What is in this document?",
    "max_results": 5
}

Output:
{
    "results": [
        {
            "content": "...",
            "source": "document_id",
            "score": 0.85
        }
    ]
}
"""

import json
import logging
import os

import boto3

from ragstack_common.config import ConfigurationManager

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level initialization (reused across Lambda invocations in same container)
config_manager = ConfigurationManager()


def lambda_handler(event, context):
    """
    Query Bedrock Knowledge Base.
    """
    # Get environment variables (moved here for testability)
    knowledge_base_id = os.environ.get("KNOWLEDGE_BASE_ID")
    if not knowledge_base_id:
        raise ValueError("KNOWLEDGE_BASE_ID environment variable is required")

    # Read response model from ConfigurationManager (runtime configuration)
    response_model_id = config_manager.get_parameter(
        "response_model_id", default="anthropic.claude-3-5-haiku-20241022-v1:0"
    )

    bedrock_agent = boto3.client("bedrock-agent-runtime")
    region = os.environ.get("AWS_REGION", "us-east-1")

    # Log safe summary (not full event payload to avoid PII/user data leakage)
    query = event.get("query", "")
    safe_summary = {
        "query_length": len(query) if isinstance(query, str) else 0,
        "has_max_results": "max_results" in event,
        "knowledge_base_id": knowledge_base_id[:8] + "..."
        if len(knowledge_base_id) > 8
        else knowledge_base_id,
    }
    logger.info(f"Querying Knowledge Base: {json.dumps(safe_summary)}")
    logger.info(f"Using response model: {response_model_id}")

    try:
        # Extract and validate query
        query = event.get("query", "")

        if not query:
            return {"results": [], "message": "No query provided"}

        if not isinstance(query, str):
            return {"results": [], "error": "Query must be a string"}

        if len(query) > 10000:
            return {"results": [], "error": "Query exceeds maximum length of 10000 characters"}

        # Extract and validate max_results
        max_results = event.get("max_results", 5)

        if not isinstance(max_results, int):
            try:
                max_results = int(max_results)
            except (ValueError, TypeError):
                return {"results": [], "error": "max_results must be an integer"}

        if max_results < 1 or max_results > 100:
            return {"results": [], "error": "max_results must be between 1 and 100"}

        # Query Knowledge Base with retrieve_and_generate API
        # This uses the configured response model to generate answers
        response = bedrock_agent.retrieve_and_generate(
            input={"text": query},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": knowledge_base_id,
                    "modelArn": f"arn:aws:bedrock:{region}::foundation-model/{response_model_id}",
                    "retrievalConfiguration": {
                        "vectorSearchConfiguration": {"numberOfResults": max_results}
                    },
                },
            },
        )

        # Parse results from retrieve_and_generate response
        # This API returns a generated output text and citations
        output_text = response.get("output", {}).get("text", "")
        citations = response.get("citations", [])

        # Extract retrieved documents from citations
        results = []
        for citation in citations:
            for reference in citation.get("retrievedReferences", []):
                results.append(
                    {
                        "content": reference.get("content", {}).get("text", ""),
                        "source": reference.get("location", {})
                        .get("s3Location", {})
                        .get("uri", ""),
                        "score": reference.get("score", 0.0),
                    }
                )

        logger.info(f"Generated response with {len(results)} source documents")

        return {
            "results": results,
            "query": query,
            "total": len(results),
            "response": output_text,  # Generated response from the model
        }

    except Exception as e:
        logger.error(f"Knowledge Base query failed: {e}", exc_info=True)
        return {"results": [], "error": str(e)}
