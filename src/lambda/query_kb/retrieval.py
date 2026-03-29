"""KB query building and rewriting for query_kb.

Functions for extracting ID patterns, augmenting results with DynamoDB
fallback lookups, rewriting queries with LLM context, and building
conversation messages for the Converse API.
"""

import logging
import re
from typing import Any

from botocore.exceptions import ClientError

try:
    from ._compat import (
        MAX_MESSAGE_LENGTH,
        bedrock_runtime,
        dynamodb,
        get_config_manager,
        s3_client,
    )
except ImportError:
    from _compat import (  # type: ignore[import-not-found,no-redef]
        MAX_MESSAGE_LENGTH,
        bedrock_runtime,
        dynamodb,
        get_config_manager,
        s3_client,
    )

from ragstack_common.storage import parse_s3_uri

logger = logging.getLogger()


def _extract_id_pattern(query: str) -> str | None:
    """Extract numeric ID pattern from query if present."""
    # Look for 10+ digit numbers (typical person/document IDs)
    match = re.search(r"\b(\d{10,})\b", query)
    if match:
        return match.group(1)
    return None


def _augment_with_id_lookup(
    query: str, retrieval_results: list[Any], tracking_table_name: str | None
) -> list[Any]:
    """
    Augment vector search results with DynamoDB filename lookup for ID-based queries.

    If the query contains a numeric ID pattern and vector search didn't find a
    matching document, fall back to DynamoDB lookup by filename.
    """
    if not tracking_table_name:
        return retrieval_results

    # Extract ID pattern from query
    id_pattern = _extract_id_pattern(query)
    if not id_pattern:
        return retrieval_results

    # Check if any result already matches this ID
    for result in retrieval_results:
        location = result.get("location", {})
        s3_location = location.get("s3Location", {})
        uri = s3_location.get("uri", "")
        if id_pattern in uri:
            logger.info(f"ID {id_pattern} already in results, skipping fallback")
            return retrieval_results

    # Fallback: Query DynamoDB for document with matching filename
    logger.info(f"ID {id_pattern} not in vector results, trying DynamoDB fallback")

    try:
        table = dynamodb.Table(tracking_table_name)

        # Scan for documents with filename containing the ID
        # Note: Scan is expensive for large tables - consider GSI on filename
        # We paginate to find matches across the entire table
        items: list[dict[str, Any]] = []
        scan_kwargs: dict[str, Any] = {
            "FilterExpression": "contains(filename, :id)",
            "ExpressionAttributeValues": {":id": id_pattern},
            "ProjectionExpression": "document_id, filename, output_s3_uri, input_s3_uri",
        }

        max_scan_pages = 10  # Cap scan pages to avoid expensive full-table scans
        pages_scanned = 0
        while len(items) < 3 and pages_scanned < max_scan_pages:
            response = table.scan(**scan_kwargs)
            items.extend(response.get("Items", []))
            pages_scanned += 1

            # Check for more pages
            if "LastEvaluatedKey" not in response:
                break
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        if not items:
            logger.info(f"No document found with ID {id_pattern} in filename")
            return retrieval_results

        logger.info(f"DynamoDB fallback found {len(items)} documents matching ID {id_pattern}")

        # Add matched documents to results
        for item in items:
            filename = str(item.get("filename", ""))
            doc_type = str(item.get("type", ""))
            document_id = str(item.get("document_id", ""))
            output_uri = str(item.get("output_s3_uri", "")) or ""
            input_uri = str(item.get("input_s3_uri", "")) or ""

            # Determine the S3 URI to use for the source
            # For scraped content (.md), use output_uri (input may be deleted)
            # For other content, prefer input_uri
            is_scraped = doc_type == "scraped" or filename.lower().endswith(".md")
            source_uri = (output_uri or input_uri) if is_scraped else (input_uri or output_uri)
            if not source_uri:
                continue

            # For text files, try to read content for context
            content = ""
            is_binary = doc_type == "image" or filename.lower().endswith(
                (".jpg", ".jpeg", ".png", ".gif", ".webp")
            )

            if not is_binary:
                # Try to read text content from output (extracted) or input
                uri_to_read = output_uri or input_uri
                try:
                    r_bucket, r_key = parse_s3_uri(uri_to_read)
                    s3_response = s3_client.get_object(Bucket=r_bucket, Key=r_key)
                    content = s3_response["Body"].read().decode("utf-8")[:10000]
                except UnicodeDecodeError:
                    logger.info(f"Binary file, adding as source only: {filename}")
                except ClientError as e:
                    logger.warning(f"Could not read content for {filename}: {e}")

            # Add as a retrieval result (always include in sources)
            fallback_result = {
                "content": {"text": content or f"[Document: {filename}]"},
                "location": {
                    "s3Location": {"uri": source_uri},
                },
                "metadata": {
                    "source": "dynamo_fallback",
                    "document_id": document_id,
                    "filename": filename,
                },
                "score": 1.0,
            }
            retrieval_results.insert(0, fallback_result)
            logger.info(f"Added fallback result from {filename}")

        return retrieval_results

    except ClientError as e:
        logger.warning(f"DynamoDB fallback lookup failed: {e}")
        return retrieval_results


def build_retrieval_query(current_query: str, history: list[dict[str, Any]]) -> str:
    """
    Build an optimized query for KB retrieval.

    For queries with explicit IDs/numbers, use as-is (no LLM rewrite needed).
    For ambiguous queries with pronouns, use LLM to rewrite with context.

    Args:
        current_query (str): The user's current question
        history (list[dict]): Previous conversation turns

    Returns:
        str: Query optimized for KB retrieval
    """
    if not history:
        return current_query

    # Fast path: If query has explicit ID (10+ digits), skip LLM rewrite
    if re.search(r"\b\d{10,}\b", current_query):
        logger.info("Query has explicit ID, skipping LLM rewrite")
        return current_query

    # Fast path: If query has no ambiguous pronouns, skip LLM rewrite
    ambiguous_patterns = r"\b(it|this|that|these|those|he|she|they|him|her|them)\b"
    if not re.search(ambiguous_patterns, current_query, re.IGNORECASE):
        logger.info("Query has no ambiguous references, skipping LLM rewrite")
        return current_query

    # Extract recent conversation context
    recent_turns = []
    for turn in history[-3:]:  # Last 3 turns for context
        user_msg = turn.get("userMessage", "")
        assistant_msg = turn.get("assistantResponse", "")
        if user_msg:
            recent_turns.append(f"User: {user_msg[:200]}")
        if assistant_msg:
            recent_turns.append(f"Assistant: {assistant_msg[:200]}")

    if not recent_turns:
        return current_query

    # Use LLM to intelligently rewrite the query if needed
    try:
        rewritten = _rewrite_query_with_llm(current_query, recent_turns)
        if rewritten and rewritten != current_query:
            logger.info(f"Query rewritten: '{current_query[:50]}...' -> '{rewritten[:50]}...'")
        return rewritten or current_query
    except (ClientError, KeyError, ValueError) as e:
        logger.warning(f"Query rewrite failed, using original: {e}")
        return current_query


def _rewrite_query_with_llm(query: str, context: list[str]) -> str:
    """
    Use LLM to rewrite ambiguous queries to be self-contained.

    If the query is already self-contained (specific IDs, names, explicit topics),
    returns it unchanged. If it has ambiguous references, rewrites it using context.
    """
    context_text = "\n".join(context[-6:])  # Limit context size

    prompt = f"""Analyze this search query and conversation context.

QUERY: {query}

RECENT CONVERSATION:
{context_text}

TASK: If the query is SELF-CONTAINED (has specific IDs, names, filenames, or clear
topics), return it EXACTLY as-is. If the query has AMBIGUOUS references (pronouns
like "it", "that", "he", "she", "they", or unclear references), rewrite it to be
self-contained using the conversation context.

RULES:
- Do NOT add conversation topics that aren't relevant to the current query
- Do NOT change specific IDs, numbers, or filenames
- Return ONLY the query, no explanation

QUERY TO USE FOR SEARCH:"""

    # Use a lightweight model for query rewriting (configurable via DynamoDB)
    rewrite_model = str(
        get_config_manager().get_parameter(
            "chat_query_rewrite_model", default="us.amazon.nova-lite-v1:0"
        )
    )

    response = bedrock_runtime.converse(
        modelId=rewrite_model,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 1000, "temperature": 0},
    )

    result = response.get("output", {}).get("message", {}).get("content", [])
    if result and "text" in result[0]:
        rewritten: str = result[0]["text"].strip()
        return rewritten
    return query


def build_conversation_messages(
    current_query: str,
    history: list[dict[str, Any]],
    retrieved_context: str,
    images: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Build messages array for Bedrock Converse API with conversation history.

    Args:
        current_query (str): The user's current question
        history (list[dict]): Previous conversation turns
        retrieved_context (str): Retrieved documents from KB
        images (list[dict], optional): List of ImageBlock dicts for visual matches

    Returns:
        list[dict]: Messages array for Converse API
    """
    messages = []

    # Add conversation history (with length limits to prevent injection)
    for turn in history:
        user_msg = turn.get("userMessage", "")[:MAX_MESSAGE_LENGTH]
        assistant_msg = turn.get("assistantResponse", "")[:MAX_MESSAGE_LENGTH]

        if user_msg:
            messages.append({"role": "user", "content": [{"text": user_msg}]})

        if assistant_msg:
            messages.append({"role": "assistant", "content": [{"text": assistant_msg}]})

    # Add current question with retrieved context
    current_message = f"""Based on the following information from our knowledge base:

{retrieved_context}

Please answer this question: {current_query}

If the retrieved information doesn't contain the answer, say so and provide relevant info."""

    # Build content blocks - text first, then images
    content_blocks = [{"text": current_message}]

    # Add images if present (for visual matches)
    if images:
        for img in images:
            if img:
                content_blocks.append(img)

    messages.append({"role": "user", "content": content_blocks})

    return messages
