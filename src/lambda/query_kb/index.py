"""
Knowledge Base Query Lambda

AppSync resolver for searching/chatting with the Knowledge Base.
Supports conversation continuity via Bedrock session management.

Input (AppSync):
{
    "query": "What is in this document?",
    "sessionId": "optional-session-id-for-conversation"
}

Output (ChatResponse):
{
    "answer": "Generated response text",
    "sessionId": "session-id-from-bedrock",
    "sources": [
        {
            "documentId": "document.pdf",
            "pageNumber": 3,
            "s3Uri": "s3://...",
            "snippet": "First 200 chars..."
        }
    ],
    "error": null
}
"""

import json
import logging
import os
from urllib.parse import unquote

import boto3
from botocore.exceptions import ClientError

from ragstack_common.config import ConfigurationManager

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level initialization (reused across Lambda invocations in same container)
config_manager = ConfigurationManager()


def extract_sources(citations):
    """
    Parse Bedrock citations into structured sources.

    Args:
        citations (list): Bedrock citation objects from retrieve_and_generate

    Returns:
        list[dict]: Parsed sources with documentId, pageNumber, s3Uri, snippet

    Example citation structure:
        [{
            'retrievedReferences': [{
                'content': {'text': 'chunk text...'},
                'location': {
                    's3Location': {
                        'uri': 's3://bucket/doc-id/pages/page-1.json'
                    }
                },
                'metadata': {...}
            }]
        }]
    """
    sources = []
    seen = set()  # Deduplicate sources

    logger.info(f"Processing {len(citations)} citations")
    for idx, citation in enumerate(citations):
        logger.debug(f"Citation {idx}: {citation}")
        for ref in citation.get("retrievedReferences", []):
            # Extract S3 URI
            uri = ref.get("location", {}).get("s3Location", {}).get("uri", "")
            logger.info(f"Processing reference with URI: {uri}")
            if not uri:
                logger.warning("No URI found in reference")
                continue

            # Parse S3 URI: s3://bucket/document-id/pages/page-1.json
            # OR: s3://bucket/document-id/text_embedding.json (vector bucket format)
            try:
                parts = uri.replace("s3://", "").split("/")
                logger.info(f"URI parts: {parts}")
                if len(parts) < 2:
                    logger.warning(f"Invalid S3 URI format (too few parts): {uri}")
                    continue

                # Decode document ID (may have URL encoding)
                document_id = unquote(parts[1])
                page_num = None

                # Extract page number if available
                if "pages" in parts and len(parts) > 3:
                    page_file = parts[-1]  # e.g., "page-3.json"
                    try:
                        # Extract number from "page-3.json" -> 3
                        page_num = int(page_file.split("-")[1].split(".")[0])
                    except (IndexError, ValueError):
                        logger.debug(f"Could not extract page number from: {page_file}")

                # Extract snippet (first 200 chars)
                content_text = ref.get("content", {}).get("text", "")
                snippet = content_text[:200] if content_text else ""
                logger.info(f"Extracted snippet length: {len(snippet)}, document_id: {document_id}")

                # Deduplicate by document + page
                source_key = f"{document_id}:{page_num}"
                if source_key not in seen:
                    sources.append(
                        {
                            "documentId": document_id,
                            "pageNumber": page_num,
                            "s3Uri": uri,
                            "snippet": snippet,
                        }
                    )
                    seen.add(source_key)
                    logger.info(f"Added source: {source_key}")
                else:
                    logger.info(f"Skipping duplicate source: {source_key}")

            except Exception as e:
                logger.error(f"Failed to parse source URI {uri}: {e}", exc_info=True)
                continue

    logger.info(f"Extracted {len(sources)} unique sources from {len(citations)} citations")
    return sources


def lambda_handler(event, context):
    """
    Query Bedrock Knowledge Base with optional session for conversation continuity.

    Args:
        event['query'] (str): User's question
        event['sessionId'] (str, optional): Conversation session ID

    Returns:
        dict: ChatResponse with answer, sessionId, sources, and optional error
    """
    # Get environment variables (moved here for testability)
    knowledge_base_id = os.environ.get("KNOWLEDGE_BASE_ID")
    if not knowledge_base_id:
        return {
            "answer": "",
            "sessionId": None,
            "sources": [],
            "error": "KNOWLEDGE_BASE_ID environment variable is required",
        }

    # Read chat model from ConfigurationManager (runtime configuration)
    chat_model_id = config_manager.get_parameter("chat_model_id", default="us.amazon.nova-pro-v1:0")

    bedrock_agent = boto3.client("bedrock-agent-runtime")
    region = os.environ.get("AWS_REGION", "us-east-1")

    # Get AWS account ID from context
    # Extract from knowledge_base_id ARN format or use STS
    account_id = context.invoked_function_arn.split(":")[4] if context else None
    if not account_id:
        # Fallback: try to extract from KB ID if it's an ARN
        if knowledge_base_id.startswith("arn:"):
            account_id = knowledge_base_id.split(":")[4]
        else:
            # Last resort: use STS to get account ID
            sts = boto3.client("sts")
            account_id = sts.get_caller_identity()["Account"]

    # Extract inputs from AppSync event
    # AppSync sends: {"arguments": {"query": "...", "sessionId": "..."}, ...}
    arguments = event.get("arguments", event)  # Fallback to event for direct invocation
    query = arguments.get("query", "")
    session_id = arguments.get("sessionId")

    # Log safe summary (not full event payload to avoid PII/user data leakage)
    safe_summary = {
        "query_length": len(query) if isinstance(query, str) else 0,
        "has_session": session_id is not None,
        "knowledge_base_id": knowledge_base_id[:8] + "..."
        if len(knowledge_base_id) > 8
        else knowledge_base_id,
    }
    logger.info(f"Querying Knowledge Base: {json.dumps(safe_summary)}")
    logger.info(f"Using chat model: {chat_model_id}")

    try:
        # Validate query
        if not query:
            return {"answer": "", "sessionId": None, "sources": [], "error": "No query provided"}

        if not isinstance(query, str):
            return {
                "answer": "",
                "sessionId": None,
                "sources": [],
                "error": "Query must be a string",
            }

        if len(query) > 10000:
            return {
                "answer": "",
                "sessionId": None,
                "sources": [],
                "error": "Query exceeds maximum length of 10000 characters",
            }

        # Build request
        # Determine ARN type based on model ID format
        # Inference profiles start with region prefix (e.g., us.amazon.nova-pro-v1:0)
        # Foundation models don't (e.g., anthropic.claude-3-5-sonnet-20241022-v2:0)
        if chat_model_id.startswith(("us.", "eu.", "ap-")):
            # Inference profiles require account ID in ARN
            model_arn = f"arn:aws:bedrock:{region}:{account_id}:inference-profile/{chat_model_id}"
        else:
            # Foundation models don't use account ID
            model_arn = f"arn:aws:bedrock:{region}::foundation-model/{chat_model_id}"

        logger.info(f"Using model ARN: {model_arn}")
        logger.info(f"Account ID: {account_id}, Region: {region}")

        request = {
            "input": {"text": query},
            "retrieveAndGenerateConfiguration": {
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": knowledge_base_id,
                    "modelArn": model_arn,
                },
            },
        }

        # Add sessionId if provided (for conversation continuity)
        if session_id:
            request["sessionId"] = session_id

        # Call Bedrock
        response = bedrock_agent.retrieve_and_generate(**request)

        # Extract data
        answer = response.get("output", {}).get("text", "")
        new_session_id = response.get("sessionId")
        citations = response.get("citations", [])

        logger.info(
            f"KB query successful. SessionId: {new_session_id}, Citations: {len(citations)}"
        )

        # Parse sources
        sources = extract_sources(citations)

        return {"answer": answer, "sessionId": new_session_id, "sources": sources}

    except ClientError as e:
        # Handle session expiration specifically
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", "")

        if error_code == "ValidationException" and "session" in error_msg.lower():
            logger.warning(f"Session expired: {session_id}")
            return {
                "error": "Session expired. Please start a new conversation.",
                "answer": "",
                "sessionId": None,
                "sources": [],
            }

        # Other client errors
        logger.error(f"Bedrock client error: {error_code} - {error_msg}")
        return {
            "error": f"Failed to query knowledge base: {error_msg}",
            "answer": "",
            "sessionId": None,
            "sources": [],
        }

    except Exception as e:
        # Generic error handling
        logger.error(f"Error querying KB: {e}", exc_info=True)
        return {
            "error": "Failed to query knowledge base. Please try again.",
            "answer": "",
            "sessionId": None,
            "sources": [],
        }
