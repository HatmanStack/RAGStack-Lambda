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

# Initialize AWS clients
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level initialization (reused across Lambda invocations in same container)
config_manager = ConfigurationManager()


def generate_presigned_url(bucket, key, expiration=3600):
    """
    Generate presigned URL for S3 object download.

    Args:
        bucket (str): S3 bucket name
        key (str): S3 object key
        expiration (int): URL expiration time in seconds (default 1 hour)

    Returns:
        str: Presigned URL or None if generation fails
    """
    try:
        return s3_client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expiration
        )
    except Exception as e:
        logger.error(f"Failed to generate presigned URL for {bucket}/{key}: {e}")
        return None


def extract_source_url_from_content(content_text):
    """
    Extract source_url from scraped markdown frontmatter.

    Args:
        content_text (str): Content text that may contain frontmatter

    Returns:
        str or None: Source URL if found, None otherwise
    """
    if not content_text:
        return None

    # Look for source_url in YAML frontmatter
    if "source_url:" in content_text:
        for line in content_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("source_url:"):
                url = stripped.split(":", 1)[1].strip()
                # Remove quotes if present
                if url.startswith(("'", '"')) and url.endswith(("'", '"')):
                    url = url[1:-1]
                return url
    return None


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
        logger.debug(f"Processing citation {idx}")
        for ref in citation.get("retrievedReferences", []):
            # Extract S3 URI
            uri = ref.get("location", {}).get("s3Location", {}).get("uri", "")
            if not uri:
                logger.debug("No URI found in reference")
                continue

            # Parse S3 URI from output bucket to construct input bucket URI
            # Output URI: s3://project-output-suffix/doc-id/filename.pdf/doc-id/extracted_text.txt
            # Input URI:  s3://project-input-suffix/doc-id/filename.pdf
            try:
                parts = uri.replace("s3://", "").split("/")
                if len(parts) < 3:
                    logger.warning(f"Invalid S3 URI format (too few parts): {len(parts)}")
                    continue

                # Extract components
                output_bucket = parts[0]  # e.g., "chat-fix-output-mvm4c"
                document_id = unquote(parts[1])  # e.g., "f8e9d9fc-..."
                original_filename = unquote(parts[2]) if len(parts) > 2 else None  # e.g., "doc.pdf"

                # Check if this is scraped content (ends with .scraped.md)
                is_scraped = original_filename and original_filename.endswith(".scraped.md")

                # Construct input bucket URI (replace -output- with -input-)
                input_bucket = output_bucket.replace("-output-", "-input-")
                if original_filename:
                    document_s3_uri = f"s3://{input_bucket}/{document_id}/{original_filename}"
                else:
                    # Fallback if filename missing
                    document_s3_uri = uri

                # Extract page number if available (from metadata or filename)
                page_num = None
                if "pages" in parts and len(parts) > 3:
                    page_file = parts[-1]  # e.g., "page-3.json"
                    try:
                        page_num = int(page_file.split("-")[1].split(".")[0])
                    except (IndexError, ValueError):
                        logger.debug(f"Could not extract page number from: {page_file}")

                # Extract snippet and source URL (for scraped content)
                content_text = ref.get("content", {}).get("text", "")
                snippet = content_text[:200] if content_text else ""

                # For scraped content, try to extract source URL from frontmatter
                source_url = None
                if is_scraped:
                    source_url = extract_source_url_from_content(content_text)
                    logger.debug(f"Scraped content detected, source_url: {source_url}")

                # Deduplicate by document + page
                source_key = f"{document_id}:{page_num}"
                if source_key not in seen:
                    # Check if document access is allowed
                    allow_document_access = config_manager.get_parameter(
                        "chat_allow_document_access", default=False
                    )

                    # Generate presigned URL if access is enabled
                    document_url = None
                    if allow_document_access and document_s3_uri:
                        # Parse S3 URI to get bucket and key
                        s3_match = document_s3_uri.replace("s3://", "").split("/", 1)
                        if len(s3_match) == 2:
                            bucket = s3_match[0]
                            key = s3_match[1]
                            document_url = generate_presigned_url(bucket, key)
                            logger.debug(f"Generated presigned URL for {document_id}")

                    source_obj = {
                        "documentId": document_id,
                        "pageNumber": page_num,
                        "s3Uri": document_s3_uri,  # Use input bucket URI, not output
                        "snippet": snippet,
                        "documentUrl": document_url,
                        "documentAccessAllowed": allow_document_access,
                        "isScraped": is_scraped,
                        "sourceUrl": source_url,  # Original web URL for scraped content
                    }
                    logger.debug(f"Added source: {source_key}")
                    sources.append(source_obj)
                    seen.add(source_key)
                else:
                    logger.debug(f"Skipping duplicate source: {source_key}")

            except Exception as e:
                logger.error(f"Failed to parse source: {e}")
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
    account_id = None
    try:
        if context and hasattr(context, "invoked_function_arn"):
            arn_parts = context.invoked_function_arn.split(":")
            if len(arn_parts) >= 5:
                account_id = arn_parts[4]
    except (AttributeError, IndexError) as e:
        logger.debug(f"Could not extract account ID from context: {e}")

    if not account_id:
        # Fallback: try to extract from KB ID if it's an ARN
        try:
            if knowledge_base_id.startswith("arn:"):
                arn_parts = knowledge_base_id.split(":")
                if len(arn_parts) >= 5:
                    account_id = arn_parts[4]
        except (AttributeError, IndexError) as e:
            logger.debug(f"Could not extract account ID from KB ID: {e}")

    if not account_id:
        # Last resort: use STS to get account ID
        try:
            sts = boto3.client("sts")
            account_id = sts.get_caller_identity()["Account"]
        except Exception as e:
            logger.error(f"Failed to get account ID from STS: {e}")
            raise ValueError("Could not determine AWS account ID for ARN construction") from e

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
        if chat_model_id.startswith(("us.", "eu.", "ap-", "global.")):
            # Inference profiles require account ID in ARN
            if not account_id:
                msg = f"Account ID is required for inference profile model {chat_model_id}"
                raise ValueError(msg)
            model_arn = f"arn:aws:bedrock:{region}:{account_id}:inference-profile/{chat_model_id}"
        else:
            # Foundation models don't use account ID
            model_arn = f"arn:aws:bedrock:{region}::foundation-model/{chat_model_id}"

        logger.info(f"Using model: {chat_model_id} in region {region}")

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
