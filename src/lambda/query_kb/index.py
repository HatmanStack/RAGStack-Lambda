"""
Knowledge Base Query Lambda

AppSync resolver for searching/chatting with the Knowledge Base.
Supports conversation continuity via DynamoDB-stored conversation history.

Input (AppSync):
{
    "query": "What is in this document?",
    "conversationId": "optional-conversation-id-for-multi-turn"
}

Output (ChatResponse):
{
    "answer": "Generated response text",
    "conversationId": "conversation-id",
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

import contextlib
import json
import logging
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import unquote

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from ragstack_common.auth import check_public_access
from ragstack_common.config import ConfigurationManager, get_knowledge_base_config
from ragstack_common.demo_mode import is_demo_mode_enabled
from ragstack_common.filter_generator import FilterGenerator
from ragstack_common.key_library import KeyLibrary
from ragstack_common.multislice_retriever import MultiSliceRetriever
from ragstack_common.sources import (
    construct_image_uri_from_content_uri,  # noqa: F401 - re-exported for tests
)
from ragstack_common.storage import generate_presigned_url, parse_s3_uri

# Initialize AWS clients (reused across warm invocations)
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
dynamodb_client = boto3.client("dynamodb")
bedrock_agent = boto3.client("bedrock-agent-runtime")
bedrock_runtime = boto3.client("bedrock-runtime")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Content types recognized as media for source attribution
MEDIA_CONTENT_TYPES = ("video", "audio", "transcript", "visual")

# Maximum image size for Converse API (5MB)
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024

# Supported image formats for Bedrock Converse API
IMAGE_FORMAT_MAP = {
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


def fetch_image_for_converse(s3_uri: str, content_type: str | None = None) -> dict | None:
    """
    Fetch image from S3 and prepare for Bedrock Converse API.

    Args:
        s3_uri: S3 URI of the image (s3://bucket/key)
        content_type: Optional content type, will be inferred from extension if not provided

    Returns:
        ImageBlock dict for Converse API, or None if image cannot be fetched/processed
    """
    try:
        bucket, key = parse_s3_uri(s3_uri)
        if not bucket or not key:
            logger.warning(f"Invalid S3 URI for image: {s3_uri}")
            return None

        # Fetch image from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        image_bytes = response["Body"].read()

        # Check size limit
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            logger.warning(f"Image too large ({len(image_bytes)} bytes): {s3_uri}")
            return None

        # Determine format from content type or extension
        if not content_type:
            content_type = response.get("ContentType", "")

        image_format = IMAGE_FORMAT_MAP.get(content_type.lower())
        if not image_format:
            # Try to infer from extension
            ext = key.lower().split(".")[-1]
            ext_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
            image_format = ext_map.get(ext)

        if not image_format:
            logger.warning(f"Unsupported image format: {content_type}, {s3_uri}")
            return None

        # Return ImageBlock for Converse API
        return {"image": {"format": image_format, "source": {"bytes": image_bytes}}}

    except Exception as e:
        logger.warning(f"Failed to fetch image {s3_uri}: {e}")
        return None


def extract_kb_scalar(value: Any) -> str | None:
    """Extract scalar value from KB metadata which returns lists with quoted strings.

    KB returns metadata like: ['"0"'] or ['value1', 'value2']
    This extracts the first value and strips extra quotes.
    """
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        value = value[0]
    if isinstance(value, str):
        return value.strip('"')
    return str(value)


# Module-level lazy initialization (reused across Lambda invocations in same container)
_config_manager = None


def get_config_manager():
    """Lazy-load ConfigurationManager to avoid import-time failures."""
    global _config_manager
    if _config_manager is None:
        table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
        if table_name:
            _config_manager = ConfigurationManager(table_name=table_name)
        else:
            _config_manager = ConfigurationManager()
    return _config_manager


# Filter generation components (lazy-loaded to avoid init overhead if disabled)
_key_library = None
_filter_generator = None
_multislice_retriever = None
_filter_examples_cache = None
_filter_examples_cache_time = None
FILTER_EXAMPLES_CACHE_TTL = 300  # 5 minutes


def _get_filter_components(filtered_score_boost: float = 1.25):
    """Lazy-load filter generation components."""
    global _key_library, _filter_generator, _multislice_retriever

    if _key_library is None:
        _key_library = KeyLibrary()

    if _filter_generator is None:
        # Read configured model, falling back to default if not set
        filter_model = get_config_manager().get_parameter("filter_generation_model", default=None)
        _filter_generator = FilterGenerator(key_library=_key_library, model_id=filter_model)

    # Recreate retriever if boost changed
    boost_changed = (
        _multislice_retriever is not None
        and _multislice_retriever.filtered_score_boost != filtered_score_boost
    )
    if _multislice_retriever is None or boost_changed:
        _multislice_retriever = MultiSliceRetriever(
            bedrock_agent_client=bedrock_agent,
            filtered_score_boost=filtered_score_boost,
        )

    return _key_library, _filter_generator, _multislice_retriever


def _get_filter_examples():
    """Get filter examples from config with caching."""
    import time

    global _filter_examples_cache, _filter_examples_cache_time

    now = time.time()

    # Return cached examples if fresh
    if (
        _filter_examples_cache is not None
        and _filter_examples_cache_time is not None
        and (now - _filter_examples_cache_time) < FILTER_EXAMPLES_CACHE_TTL
    ):
        return _filter_examples_cache

    # Load from config
    examples = get_config_manager().get_parameter("metadata_filter_examples", default=[])
    _filter_examples_cache = examples if isinstance(examples, list) else []
    _filter_examples_cache_time = now

    logger.debug(f"Loaded {len(_filter_examples_cache)} filter examples from config")
    return _filter_examples_cache


# Conversation history settings
MAX_HISTORY_TURNS = 5
CONVERSATION_TTL_DAYS = 14
MAX_MESSAGE_LENGTH = 10000  # Max chars per message to prevent injection attacks

# Quota settings
QUOTA_TTL_DAYS = 2  # Quota counters expire after 2 days


def atomic_quota_check_and_increment(tracking_id, is_authenticated, region):
    """
    Atomically check and increment quotas using DynamoDB transactions.

    Uses TransactWriteItems to ensure atomic updates to both global and user
    quotas, preventing race conditions and eliminating rollback failures.

    In demo mode, applies stricter per-user quota (default 30/day) to control costs.

    Args:
        tracking_id (str): User identifier for per-user quota
        is_authenticated (bool): Whether user is authenticated
        region (str): AWS region

    Returns:
        str: Model ID to use (primary or fallback)
    """
    # Load quota configuration
    primary_model = get_config_manager().get_parameter(
        "chat_primary_model", default="us.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    fallback_model = get_config_manager().get_parameter(
        "chat_fallback_model", default="us.amazon.nova-lite-v1:0"
    )
    global_quota_daily = get_config_manager().get_parameter(
        "chat_global_quota_daily", default=10000
    )

    # In demo mode, use stricter per-user quota
    demo_mode = is_demo_mode_enabled(get_config_manager())
    if demo_mode:
        per_user_quota_daily = get_config_manager().get_parameter(
            "demo_chat_quota_daily", default=30
        )
        logger.info(f"Demo mode enabled - using quota limit: {per_user_quota_daily}/day")
    else:
        per_user_quota_daily = get_config_manager().get_parameter(
            "chat_per_user_quota_daily", default=100
        )

    # Ensure quotas are integers
    if isinstance(global_quota_daily, Decimal):
        global_quota_daily = int(global_quota_daily)
    if isinstance(per_user_quota_daily, Decimal):
        per_user_quota_daily = int(per_user_quota_daily)

    config_table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
    if not config_table_name:
        logger.warning("CONFIGURATION_TABLE_NAME not set, skipping quota check")
        return primary_model

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    ttl = int(datetime.now(UTC).timestamp()) + (QUOTA_TTL_DAYS * 86400)
    global_key = f"quota#global#{today}"

    try:
        # Build transaction items for atomic quota updates
        transact_items = [
            {
                "Update": {
                    "TableName": config_table_name,
                    "Key": {"Configuration": {"S": global_key}},
                    "UpdateExpression": "ADD #count :inc SET #ttl = :ttl",
                    "ConditionExpression": "#count < :limit OR attribute_not_exists(#count)",
                    "ExpressionAttributeNames": {"#count": "count", "#ttl": "ttl"},
                    "ExpressionAttributeValues": {
                        ":inc": {"N": "1"},
                        ":limit": {"N": str(global_quota_daily)},
                        ":ttl": {"N": str(ttl)},
                    },
                }
            }
        ]

        # Add user quota check if authenticated
        if is_authenticated and tracking_id:
            user_key = f"quota#user#{tracking_id}#{today}"
            transact_items.append(
                {
                    "Update": {
                        "TableName": config_table_name,
                        "Key": {"Configuration": {"S": user_key}},
                        "UpdateExpression": "ADD #count :inc SET #ttl = :ttl",
                        "ConditionExpression": "#count < :limit OR attribute_not_exists(#count)",
                        "ExpressionAttributeNames": {"#count": "count", "#ttl": "ttl"},
                        "ExpressionAttributeValues": {
                            ":inc": {"N": "1"},
                            ":limit": {"N": str(per_user_quota_daily)},
                            ":ttl": {"N": str(ttl)},
                        },
                    }
                }
            )

        # Execute atomic transaction
        dynamodb_client.transact_write_items(TransactItems=transact_items)

        user_prefix = tracking_id[:8] if tracking_id else "anon"
        logger.info(f"Quota transaction succeeded for {user_prefix}...")
        return primary_model

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "TransactionCanceledException":
            # Check which condition failed
            reasons = e.response.get("CancellationReasons", [])
            for i, reason in enumerate(reasons):
                if reason.get("Code") == "ConditionalCheckFailed":
                    quota_type = "global" if i == 0 else "user"
                    logger.info(f"{quota_type.capitalize()} quota exceeded, using fallback model")
            return fallback_model
        logger.error(f"Error in quota transaction: {e}")
        return fallback_model

    except Exception as e:
        logger.error(f"Error in quota check: {e}")
        # On error, default to fallback model (conservative approach)
        return fallback_model


def get_conversation_history(conversation_id):
    """
    Retrieve the last N conversation turns from DynamoDB.

    Args:
        conversation_id (str): The conversation ID

    Returns:
        list[dict]: Previous conversation turns in chronological order
    """
    conversation_table_name = os.environ.get("CONVERSATION_TABLE_NAME")
    if not conversation_table_name or not conversation_id:
        return []

    table = dynamodb.Table(conversation_table_name)

    try:
        response = table.query(
            KeyConditionExpression=Key("conversationId").eq(conversation_id),
            ScanIndexForward=False,  # Descending order (newest first)
            Limit=MAX_HISTORY_TURNS,
            ProjectionExpression="turnNumber, userMessage, assistantResponse",
        )

        # Reverse to chronological order and convert Decimal to int
        items = response.get("Items", [])
        for item in items:
            if "turnNumber" in item and isinstance(item["turnNumber"], Decimal):
                item["turnNumber"] = int(item["turnNumber"])
        items.reverse()
        return items
    except ClientError as e:
        logger.error(f"Failed to retrieve conversation history: {e}")
        return []


def store_conversation_turn(
    conversation_id, turn_number, user_message, assistant_response, sources
):
    """
    Store a conversation turn in DynamoDB.

    Args:
        conversation_id (str): The conversation ID
        turn_number (int): The turn number (1-indexed)
        user_message (str): The user's original query
        assistant_response (str): The assistant's response
        sources (list): The source documents used
    """
    conversation_table_name = os.environ.get("CONVERSATION_TABLE_NAME")
    if not conversation_table_name or not conversation_id:
        return

    table = dynamodb.Table(conversation_table_name)

    # Calculate TTL (14 days from now)
    ttl = int(datetime.now(UTC).timestamp()) + (CONVERSATION_TTL_DAYS * 86400)

    try:
        table.put_item(
            Item={
                "conversationId": conversation_id,
                "turnNumber": turn_number,
                "userMessage": user_message,
                "assistantResponse": assistant_response,
                "sources": json.dumps(sources),  # Store as JSON string
                "createdAt": datetime.now(UTC).isoformat(),
                "ttl": ttl,
            }
        )
        logger.info(f"Stored turn {turn_number} for conversation {conversation_id[:8]}...")
    except ClientError as e:
        logger.error(f"Failed to store conversation turn: {e}")


def _extract_id_pattern(query: str) -> str | None:
    """Extract numeric ID pattern from query if present."""
    # Look for 10+ digit numbers (typical person/document IDs)
    match = re.search(r"\b(\d{10,})\b", query)
    if match:
        return match.group(1)
    return None


def _augment_with_id_lookup(
    query: str, retrieval_results: list, tracking_table_name: str | None
) -> list:
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
        items = []
        scan_kwargs = {
            "FilterExpression": "contains(filename, :id)",
            "ExpressionAttributeValues": {":id": id_pattern},
            "ProjectionExpression": "document_id, filename, output_s3_uri, input_s3_uri",
        }

        while len(items) < 3:  # Find up to 3 matching documents
            response = table.scan(**scan_kwargs)
            items.extend(response.get("Items", []))

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
            filename = item.get("filename", "")
            doc_type = item.get("type", "")
            document_id = item.get("document_id", "")
            output_uri = item.get("output_s3_uri")
            input_uri = item.get("input_s3_uri")

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
                    uri_path = uri_to_read.replace("s3://", "")
                    parts = uri_path.split("/", 1)
                    if len(parts) == 2:
                        bucket, key = parts
                        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
                        content = s3_response["Body"].read().decode("utf-8")[:10000]
                except UnicodeDecodeError:
                    logger.info(f"Binary file, adding as source only: {filename}")
                except Exception as e:
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

    except Exception as e:
        logger.warning(f"DynamoDB fallback lookup failed: {e}")
        return retrieval_results


def build_retrieval_query(current_query, history):
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
    except Exception as e:
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

    response = bedrock_runtime.converse(
        modelId="us.amazon.nova-lite-v1:0",
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 1000, "temperature": 0},
    )

    result = response.get("output", {}).get("message", {}).get("content", [])
    if result and "text" in result[0]:
        return result[0]["text"].strip()
    return query


def build_conversation_messages(current_query, history, retrieved_context, images=None):
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


def format_timestamp(seconds):
    """
    Format seconds into M:SS or MM:SS display format.

    Args:
        seconds (int | float | Decimal): Time in seconds

    Returns:
        str: Formatted timestamp like "1:30" or "10:00"
    """
    if seconds is None:
        return None
    seconds = int(seconds)
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def generate_media_url(bucket, key, timestamp_start, timestamp_end, expiration=3600):
    """
    Generate presigned URL for media with optional timestamp fragment.

    For media sources, appends HTML5 media fragment (#t=start,end) to enable
    direct seeking in video/audio players.

    Args:
        bucket (str): S3 bucket name
        key (str): S3 object key
        timestamp_start (int|None): Start time in seconds
        timestamp_end (int|None): End time in seconds
        expiration (int): URL expiration time in seconds (default 1 hour)

    Returns:
        str: Presigned URL with optional timestamp fragment, or None on error
    """
    try:
        base_url = s3_client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expiration
        )
        if not base_url:
            return None

        # Append HTML5 media fragment for timestamp seeking
        if timestamp_start is not None:
            if timestamp_end is not None:
                return f"{base_url}#t={timestamp_start},{timestamp_end}"
            return f"{base_url}#t={timestamp_start}"
        return base_url
    except Exception as e:
        logger.error(f"Failed to generate media URL for {bucket}/{key}: {e}")
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


def extract_image_caption_from_content(content_text):
    """
    Extract caption from image content frontmatter.

    Args:
        content_text (str): Content text that may contain frontmatter

    Returns:
        str or None: Caption if found, None otherwise
    """
    if not content_text:
        return None

    # Look for caption in content (usually after frontmatter)
    # Image content format:
    # ---
    # image_id: ...
    # filename: ...
    # ---
    # # Image: filename
    # <caption text>

    # First try to extract from frontmatter-style format
    lines = content_text.split("\n")
    in_frontmatter = False
    frontmatter_ended = False

    for line in lines:
        stripped = line.strip()

        # Track frontmatter boundaries
        if stripped == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            frontmatter_ended = True
            in_frontmatter = False
            continue

        # Look for user_caption or ai_caption in frontmatter
        if in_frontmatter:
            if stripped.startswith("user_caption:"):
                caption = stripped.split(":", 1)[1].strip()
                if caption:
                    return caption
            if stripped.startswith("ai_caption:"):
                caption = stripped.split(":", 1)[1].strip()
                if caption:
                    return caption

        # After frontmatter, look for actual content
        if frontmatter_ended and stripped and not stripped.startswith("#"):
            # Return first non-header line as caption snippet
            return stripped[:200] if len(stripped) > 200 else stripped

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
            # Extract S3 URI - handle both retrieve and retrieve_and_generate response formats
            location = ref.get("location") or {}
            s3_location = location.get("s3Location") or {}
            uri = s3_location.get("uri", "")
            # Extract relevance score from KB response (0-1 range)
            relevance_score = ref.get("score")

            if not uri:
                logger.debug(f"No URI found in reference. Location: {location}")
                continue

            logger.info(f"Processing source URI: {uri}")

            # Parse S3 URI to construct the original input document URI
            # All content now uses unified content/ prefix:
            # 1. PDF/document: s3://bucket/content/{docId}/extracted_text.txt
            #    Input: s3://bucket/input/{docId}/{filename}.pdf
            # 2. Scraped: s3://bucket/content/{docId}/full_text.txt
            #    Input: s3://bucket/input/{docId}/{docId}.scraped.md
            # 3. Images: s3://bucket/content/{imageId}/caption.txt
            #    Actual image: s3://bucket/content/{imageId}/{filename}.ext
            try:
                uri_path = uri.replace("s3://", "")
                parts = uri_path.split("/")
                logger.info(f"Parsing URI: {uri}, parts count: {len(parts)}")

                if len(parts) < 3:
                    logger.warning(f"Invalid S3 URI format (too few parts): {parts}")
                    continue

                bucket = parts[0]
                document_id = None
                original_filename = None
                input_prefix = None
                is_scraped = False
                is_image = False

                # Detect structure based on path prefix
                if len(parts) > 2 and parts[1] == "content":
                    # Unified content structure: bucket/content/{docId}/...
                    document_id = unquote(parts[2])

                    # Determine content type from filename
                    last_part = parts[-1] if parts else ""
                    last_part_lower = last_part.lower()
                    if last_part == "caption.txt":
                        # Image caption (text embedding)
                        input_prefix = "content"
                        is_image = True
                        logger.info(f"Image caption detected: imageId={document_id}")
                    elif last_part_lower.endswith((".jpeg", ".jpg", ".png", ".gif", ".webp")):
                        # Image file directly (visual embedding)
                        input_prefix = "content"
                        is_image = True
                        logger.info(f"Image file detected: imageId={document_id}, file={last_part}")
                    elif last_part == "full_text.txt":
                        # Old format scraped content
                        input_prefix = "input"
                        original_filename = f"{document_id}.scraped.md"
                        is_scraped = True
                        logger.info(f"Scraped content detected (old format): docId={document_id}")
                    elif last_part_lower.endswith(".md"):
                        # Possible new format scraped content: content/{job_id}/{url_slug}.md
                        # Will confirm via tracking table lookup (doc_type == "scraped")
                        input_prefix = "content"
                        original_filename = last_part
                        # Don't set is_scraped here - wait for tracking table confirmation
                        logger.info(
                            f"Markdown in content/ detected: doc_id={document_id}, "
                            f"file={last_part} (will confirm type from tracking table)"
                        )
                    else:
                        # PDF or other document
                        input_prefix = "input"
                        logger.info(f"Document content detected: docId={document_id}")

                elif len(parts) > 3 and parts[1] == "input":
                    # Input structure: bucket/input/{docId}/{filename}
                    document_id = unquote(parts[2])
                    original_filename = unquote(parts[3]) if len(parts) > 3 else None
                    input_prefix = "input"
                    # Check if scraped based on filename
                    if original_filename and original_filename.endswith(".md"):
                        is_scraped = True
                    logger.info(f"Input structure: docId={document_id}, file={original_filename}")

                else:
                    # Fallback: try to parse as generic structure
                    document_id = unquote(parts[1]) if len(parts) > 1 else None
                    original_filename = unquote(parts[2]) if len(parts) > 2 else None
                    logger.info(f"Generic structure detected: docId={document_id}")

                logger.info(f"Parsed: bucket={bucket}, doc={document_id}, file={original_filename}")

                # Validate extracted values
                if not document_id or len(document_id) < 5:
                    logger.warning(f"Invalid document_id: {document_id}")
                    continue

                # Extract content text early - needed for filename extraction
                content_text = ref.get("content", {}).get("text", "")

                # ============================================================
                # SOURCE URI RESOLUTION - Comprehensive logging for debugging
                # ============================================================
                logger.info(f"[SOURCE] ===== Processing source: {document_id} =====")
                logger.info(f"[SOURCE] KB citation URI: {uri}")
                logger.info(f"[SOURCE] is_scraped={is_scraped}, is_image={is_image}")
                logger.info(f"[SOURCE] Parsed - bucket: {bucket}, input_prefix: {input_prefix}")

                # Look up input_s3_uri, filename, and source_url from tracking table
                # This gives us the actual source document URI (PDF, image, scraped web page)
                tracking_input_uri = None
                tracking_source_url = None
                tracking_item = None
                tracking_table_name = os.environ.get("TRACKING_TABLE")
                logger.info(f"[SOURCE] Tracking table: {tracking_table_name}")
                if tracking_table_name:
                    try:
                        tracking_table = dynamodb.Table(tracking_table_name)
                        response = tracking_table.get_item(Key={"document_id": document_id})
                        tracking_item = response.get("Item")
                        if tracking_item:
                            tracking_input_uri = tracking_item.get("input_s3_uri")
                            tracking_source_url = tracking_item.get("source_url")
                            original_filename = tracking_item.get("filename")
                            # Get document type for media detection (normalize scrape -> scraped)
                            doc_type = tracking_item.get("type") or "document"
                            if doc_type == "scrape":
                                doc_type = "scraped"
                            logger.info(
                                f"[SOURCE] Tracking lookup SUCCESS: "
                                f"input_s3_uri={tracking_input_uri}, "
                                f"filename={original_filename}, "
                                f"source_url={tracking_source_url}, "
                                f"status={tracking_item.get('status')}, "
                                f"type={tracking_item.get('type')}"
                            )
                        else:
                            doc_type = "document"  # Default when no tracking item
                            logger.warning(
                                f"[SOURCE] Tracking lookup EMPTY: "
                                f"No item found for document_id={document_id}"
                            )
                    except Exception as e:
                        doc_type = "document"  # Default on error
                        logger.error(f"[SOURCE] Tracking lookup FAILED: {e}", exc_info=True)
                else:
                    doc_type = "document"  # Default when no tracking table
                    logger.warning("[SOURCE] TRACKING_TABLE env var not set!")

                # Confirm is_scraped from tracking table doc_type (authoritative)
                # This handles new format scraped content: content/{job_id}/{slug}.md
                if doc_type == "scraped":
                    is_scraped = True
                    logger.info("[SOURCE] Confirmed scraped content from tracking table")

                # Construct document URI
                # For scraped content, use output URI (input may be deleted after processing)
                # For other content, prefer input_s3_uri from tracking table
                if is_scraped:
                    # Scraped content: use the output full_text.txt or the KB citation URI
                    document_s3_uri = uri  # KB citation already points to output
                    logger.info(f"[SOURCE] Scraped content, using KB URI: {document_s3_uri}")
                elif tracking_input_uri:
                    document_s3_uri = tracking_input_uri
                    logger.info(f"[SOURCE] Using tracking input_s3_uri: {document_s3_uri}")
                elif original_filename and len(original_filename) > 0:
                    if input_prefix:
                        document_s3_uri = (
                            f"s3://{bucket}/{input_prefix}/{document_id}/{original_filename}"
                        )
                    else:
                        document_s3_uri = f"s3://{bucket}/{document_id}/{original_filename}"
                    logger.info(
                        f"[SOURCE] Constructed URI from filename: {document_s3_uri} "
                        f"(input_prefix={input_prefix}, filename={original_filename})"
                    )
                else:
                    # Fallback if filename missing
                    document_s3_uri = uri
                    logger.warning(
                        f"[SOURCE] FALLBACK to KB URI (no input_s3_uri or filename): "
                        f"{document_s3_uri}"
                    )

                logger.info(f"[SOURCE] Final document_s3_uri: {document_s3_uri}")

                # Extract page number if available (from metadata or filename)
                page_num = None
                if "pages" in parts and len(parts) > 3:
                    page_file = parts[-1]  # e.g., "page-3.json"
                    try:
                        page_num = int(page_file.split("-")[1].split(".")[0])
                    except (IndexError, ValueError):
                        logger.debug(f"Could not extract page number from: {page_file}")

                # Extract snippet (content_text already extracted above)
                snippet = content_text[:200] if content_text else ""

                # For scraped content, get source URL from metadata sidecar, tracking table,
                # or frontmatter
                source_url = None
                if is_scraped:
                    # For new format, read source_url from metadata sidecar file
                    # URI: s3://bucket/content/{job_id}/{slug}.md
                    # Metadata: {slug}.md.metadata.json
                    if uri.endswith(".md"):
                        metadata_uri = f"{uri}.metadata.json"
                        try:
                            metadata_path = metadata_uri.replace("s3://", "")
                            meta_parts = metadata_path.split("/", 1)
                            if len(meta_parts) == 2:
                                meta_response = s3_client.get_object(
                                    Bucket=meta_parts[0], Key=meta_parts[1]
                                )
                                meta_body = meta_response["Body"].read().decode("utf-8")
                                meta_content = json.loads(meta_body)
                                source_url = meta_content.get("metadataAttributes", {}).get(
                                    "source_url"
                                )
                                # Handle case where source_url is stored as a list
                                if isinstance(source_url, list):
                                    source_url = source_url[0] if source_url else None
                                if source_url:
                                    logger.info(
                                        f"[SOURCE] Got source_url from metadata: {source_url}"
                                    )
                        except Exception as e:
                            logger.debug(f"[SOURCE] Could not read metadata sidecar: {e}")

                    # Fallback: try tracking table (old format has source_url per-page)
                    if not source_url and tracking_source_url:
                        source_url = tracking_source_url
                        logger.info(f"[SOURCE] Using source_url from tracking: {source_url}")

                    # Last fallback: try to extract from content frontmatter
                    if not source_url:
                        source_url = extract_source_url_from_content(content_text)
                        logger.info(f"[SOURCE] Extracted source_url from content: {source_url}")

                # For image content, extract caption from frontmatter
                image_caption = None
                if is_image:
                    image_caption = extract_image_caption_from_content(content_text)
                    preview = image_caption[:50] if image_caption else None
                    logger.debug(f"Image content detected, caption: {preview}...")

                # Extract KB chunk timestamps early (needed for deduplication)
                # These are in milliseconds for visual embeddings from native KB chunking
                kb_metadata = ref.get("metadata", {})
                kb_chunk_start_ms = extract_kb_scalar(
                    kb_metadata.get("x-amz-bedrock-kb-chunk-start-time-in-millis")
                )

                # Deduplicate sources:
                # - Video/media segments: use URI + timestamp (each chunk is unique)
                # - PDF pages: use document_id:page_num
                # - Scraped pages: use source_url (each page has a unique URL)
                # - Other content: use document_id
                is_segment = doc_type == "media" or "segment-" in uri or uri.endswith(".mp4")
                if is_segment:
                    # Each video segment is a unique source (include timestamp for KB chunks)
                    if kb_chunk_start_ms is not None:
                        source_key = f"{uri}:{kb_chunk_start_ms}"
                    else:
                        source_key = uri
                elif page_num is not None:
                    source_key = f"{document_id}:{page_num}"
                elif is_scraped and source_url:
                    # Each scraped page has a unique source URL
                    source_key = source_url
                else:
                    source_key = document_id

                if source_key not in seen:
                    # Check if document access is allowed
                    allow_document_access = get_config_manager().get_parameter(
                        "chat_allow_document_access", default=False
                    )
                    logger.info(f"[SOURCE] Document access allowed: {allow_document_access}")

                    # Generate presigned URL if access is enabled
                    document_url = None
                    if (
                        allow_document_access
                        and document_s3_uri
                        and document_s3_uri.startswith("s3://")
                    ):
                        # Parse S3 URI to get bucket and key
                        s3_path = document_s3_uri.replace("s3://", "")
                        s3_match = s3_path.split("/", 1)
                        if len(s3_match) == 2 and s3_match[1]:
                            bucket = s3_match[0]
                            key = s3_match[1]
                            # Validate key looks reasonable (has document ID and filename)
                            if "/" in key and len(key) > 10:
                                logger.info(
                                    f"[SOURCE] Generating presigned URL: bucket={bucket}, key={key}"
                                )
                                document_url = generate_presigned_url(bucket, key)
                                if document_url:
                                    logger.info(
                                        f"[SOURCE] Presigned URL generated: {document_url[:80]}..."
                                    )
                                else:
                                    logger.warning("[SOURCE] Presigned URL returned None")
                            else:
                                logger.warning(f"[SOURCE] Skipping malformed key: {key}")
                        else:
                            logger.warning(f"[SOURCE] Could not parse S3 URI: {document_s3_uri}")
                    else:
                        logger.info(
                            f"[SOURCE] Skipping presigned URL: access={allow_document_access}, "
                            f"uri={document_s3_uri[:50] if document_s3_uri else 'None'}..."
                        )

                    # For images, use the same presigned URL as document_url
                    # (document_s3_uri now points to actual image, not caption.txt)
                    thumbnail_url = None
                    if is_image and allow_document_access and document_url:
                        thumbnail_url = document_url
                        logger.info("[SOURCE] Image thumbnail URL set from document_url")

                    # For scraped content, use the original web URL as documentUrl
                    # so users can click through to the source website
                    if is_scraped and source_url:
                        document_url = source_url
                        logger.info(f"[SOURCE] Scraped content - using source URL: {source_url}")

                    # Check for media sources (video/audio content types or tracking type)
                    # KB metadata comes as lists with quoted strings, extract scalars
                    metadata = ref.get("metadata", {})
                    content_type = extract_kb_scalar(metadata.get("content_type"))
                    is_media = content_type in MEDIA_CONTENT_TYPES or doc_type == "media"
                    # Get media_type from metadata or derive from content_type
                    if is_media:
                        media_type_raw = extract_kb_scalar(metadata.get("media_type"))
                        if media_type_raw in ("video", "audio"):
                            media_type = media_type_raw
                        elif content_type in ("video", "audio"):
                            media_type = content_type
                        else:
                            media_type = None
                    else:
                        media_type = None

                    # Extract timestamp fields (convert to int for URL generation)
                    timestamp_start = None
                    timestamp_end = None
                    if is_media:
                        # Check custom metadata first (transcripts use seconds)
                        # Note: values may be floats, need int(float()) to convert
                        ts_start_str = extract_kb_scalar(metadata.get("timestamp_start"))
                        ts_end_str = extract_kb_scalar(metadata.get("timestamp_end"))
                        if ts_start_str is not None:
                            with contextlib.suppress(ValueError, TypeError):
                                timestamp_start = int(float(ts_start_str))
                        if ts_end_str is not None:
                            with contextlib.suppress(ValueError, TypeError):
                                timestamp_end = int(float(ts_end_str))
                        # Fall back to native KB keys for visual embeddings (milliseconds)
                        # Note: KB returns floats like 30000.0, need int(float()) to convert
                        if timestamp_start is None:
                            ts_millis = extract_kb_scalar(
                                metadata.get("x-amz-bedrock-kb-chunk-start-time-in-millis")
                            )
                            if ts_millis is not None:
                                with contextlib.suppress(ValueError, TypeError):
                                    timestamp_start = int(float(ts_millis)) // 1000
                        if timestamp_end is None:
                            ts_millis = extract_kb_scalar(
                                metadata.get("x-amz-bedrock-kb-chunk-end-time-in-millis")
                            )
                            if ts_millis is not None:
                                with contextlib.suppress(ValueError, TypeError):
                                    timestamp_end = int(float(ts_millis)) // 1000

                    speaker = extract_kb_scalar(metadata.get("speaker")) if is_media else None
                    segment_index = None
                    if is_media:
                        seg_idx_str = extract_kb_scalar(metadata.get("segment_index"))
                        if seg_idx_str is not None:
                            with contextlib.suppress(ValueError, TypeError):
                                segment_index = int(seg_idx_str)

                    # For media sources, generate both full URL and segment URL with timestamp
                    segment_url = None
                    if is_media and allow_document_access and document_s3_uri:
                        s3_path = document_s3_uri.replace("s3://", "")
                        s3_match = s3_path.split("/", 1)
                        if len(s3_match) == 2 and s3_match[1]:
                            media_bucket = s3_match[0]
                            media_key = s3_match[1]
                            # Full video URL (no timestamp)
                            document_url = generate_presigned_url(media_bucket, media_key)
                            # Segment URL with timestamp fragment for deep linking
                            if document_url and timestamp_start is not None:
                                if timestamp_end is not None:
                                    ts_frag = f"#t={timestamp_start},{timestamp_end}"
                                else:
                                    ts_frag = f"#t={timestamp_start}"
                                segment_url = f"{document_url}{ts_frag}"
                                logger.info(
                                    f"[SOURCE] Media URLs: full={document_url[:50]}..., "
                                    f"segment=#t={timestamp_start},{timestamp_end}"
                                )

                    # Format timestamp display for media sources
                    timestamp_display = None
                    if is_media and timestamp_start is not None:
                        start_fmt = format_timestamp(timestamp_start)
                        end_fmt = format_timestamp(timestamp_end) if timestamp_end else ""
                        timestamp_display = f"{start_fmt}-{end_fmt}" if end_fmt else start_fmt

                    source_obj = {
                        "documentId": document_id,
                        "pageNumber": page_num,
                        "s3Uri": document_s3_uri,  # Use input bucket URI, not output
                        "snippet": snippet,
                        "documentUrl": document_url,
                        "documentAccessAllowed": allow_document_access,
                        "score": relevance_score,  # KB relevance score (0-1)
                        "filename": original_filename,  # Original filename
                        "isScraped": is_scraped,
                        "sourceUrl": source_url,  # Original web URL for scraped content
                        # Image-specific fields
                        "isImage": is_image,
                        "thumbnailUrl": thumbnail_url,
                        "caption": image_caption,
                        # Media-specific fields (matches search_kb structure)
                        "isMedia": is_media if is_media else None,
                        "isSegment": is_segment,
                        "segmentUrl": segment_url,  # URL with #t=start,end for deep linking
                        "mediaType": media_type,
                        "contentType": content_type if is_media else None,
                        "timestampStart": timestamp_start,
                        "timestampEnd": timestamp_end,
                        "timestampDisplay": timestamp_display,
                        "speaker": speaker,
                        "segmentIndex": segment_index,
                    }
                    # Log the complete source object for debugging
                    doc_url_preview = (
                        document_url[:60] + "..."
                        if document_url and len(document_url) > 60
                        else document_url
                    )
                    logger.info(f"[SOURCE] FINAL: docId={document_id}, s3Uri={document_s3_uri}")
                    logger.info(
                        f"[SOURCE] FINAL: documentUrl={doc_url_preview}, "
                        f"isScraped={is_scraped}, isImage={is_image}"
                    )
                    logger.info(f"[SOURCE] ===== End source {document_id} =====")
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
    Query Bedrock Knowledge Base with DynamoDB-stored conversation history.

    Args:
        event['query'] (str): User's question
        event['conversationId'] (str, optional): Conversation ID for multi-turn context

    Returns:
        dict: ChatResponse with answer, conversationId, sources, and optional error
    """
    # Check public access control
    allowed, error_msg = check_public_access(event, "chat", get_config_manager())
    if not allowed:
        return {
            "answer": "",
            "conversationId": None,
            "sources": [],
            "error": error_msg,
        }

    # Get KB config from config table (with env var fallback)
    try:
        knowledge_base_id, _ = get_knowledge_base_config(get_config_manager())
    except ValueError as e:
        return {
            "answer": "",
            "conversationId": None,
            "sources": [],
            "error": str(e),
        }

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
    # AppSync sends: {"arguments": {"query": "...", "conversationId": "..."}, ...}
    arguments = event.get("arguments", event)  # Fallback to event for direct invocation
    query = arguments.get("query", "")
    conversation_id = arguments.get("conversationId")

    # Extract user identity for quota tracking
    # AppSync Cognito auth provides identity in event
    # API key auth returns None for identity, so we need to handle that
    identity = event.get("identity") or {}
    user_id = identity.get("sub") or identity.get("username") if identity else None
    is_authenticated = user_id is not None

    # Use conversationId as fallback tracking ID for anonymous users
    tracking_id = user_id or (f"anon:{conversation_id}" if conversation_id else None)

    # Check quotas and select model (primary or fallback)
    chat_model_id = atomic_quota_check_and_increment(tracking_id, is_authenticated, region)

    # Log safe summary (not full event payload to avoid PII/user data leakage)
    safe_summary = {
        "query_length": len(query) if isinstance(query, str) else 0,
        "has_conversation": conversation_id is not None,
        "is_authenticated": is_authenticated,
        "knowledge_base_id": knowledge_base_id[:8] + "..."
        if len(knowledge_base_id) > 8
        else knowledge_base_id,
    }
    logger.info(f"Querying Knowledge Base: {json.dumps(safe_summary)}")
    logger.info(f"Using chat model: {chat_model_id}")

    try:
        # Validate query
        if not query:
            return {
                "answer": "",
                "conversationId": None,
                "sources": [],
                "error": "No query provided",
            }

        if not isinstance(query, str):
            return {
                "answer": "",
                "conversationId": None,
                "sources": [],
                "error": "Query must be a string",
            }

        if len(query) > 10000:
            return {
                "answer": "",
                "conversationId": None,
                "sources": [],
                "error": "Query exceeds maximum length of 10000 characters",
            }

        # Retrieve conversation history for multi-turn context
        history = []
        if conversation_id:
            history = get_conversation_history(conversation_id)
            logger.info(f"Retrieved {len(history)} turns for conversation {conversation_id[:8]}...")

        logger.info(f"Using model: {chat_model_id} in region {region}")

        # STEP 1: Retrieve relevant documents from KB
        # Use a focused query with minimal context for effective retrieval
        retrieval_query = build_retrieval_query(query, history)
        logger.info(f"Retrieval query: {retrieval_query[:100]}...")

        retrieval_results = []
        generated_filter = None

        # Check if filter generation is enabled
        filter_enabled = get_config_manager().get_parameter(
            "filter_generation_enabled", default=True
        )
        multislice_enabled = get_config_manager().get_parameter("multislice_enabled", default=True)
        filtered_score_boost = float(
            get_config_manager().get_parameter("multislice_filtered_boost", default=1.25)
        )

        # Generate metadata filter if enabled (includes content_type filtering)
        if filter_enabled:
            try:
                _, filter_generator, _ = _get_filter_components(filtered_score_boost)
                filter_examples = _get_filter_examples()
                cfg = get_config_manager()
                manual_keys = cfg.get_parameter("metadata_manual_keys", default=None)
                extraction_mode = cfg.get_parameter("metadata_extraction_mode", default="auto")
                generated_filter = filter_generator.generate_filter(
                    retrieval_query,
                    filter_examples=filter_examples,
                    manual_keys=manual_keys if extraction_mode == "manual" else None,
                )
                if generated_filter:
                    logger.info(f"Generated filter: {json.dumps(generated_filter)}")
                else:
                    logger.info("No filter intent detected in query")
            except Exception as e:
                logger.warning(f"Filter generation failed, proceeding without filter: {e}")

        # Single unified query with optional metadata filter
        try:
            if multislice_enabled and generated_filter:
                # Use multi-slice retrieval with filter
                _, _, multislice_retriever = _get_filter_components(filtered_score_boost)
                logger.info(
                    f"[MULTISLICE REQUEST] kb_id={knowledge_base_id}, filter={generated_filter}"
                )
                retrieval_results = multislice_retriever.retrieve(
                    query=retrieval_query,
                    knowledge_base_id=knowledge_base_id,
                    data_source_id=None,  # No data source filtering with unified content/
                    metadata_filter=generated_filter,
                    num_results=25,
                )
                logger.info(f"[MULTISLICE] Retrieved {len(retrieval_results)} results")
                for i, r in enumerate(retrieval_results):
                    uri = r.get("location", {}).get("s3Location", {}).get("uri", "N/A")
                    score = r.get("score", "N/A")
                    logger.info(f"[MULTISLICE] Result {i}: score={score}, uri={uri}")
            else:
                # Standard single-query retrieval
                retrieval_config = {
                    "vectorSearchConfiguration": {
                        "numberOfResults": 25,
                    }
                }
                # Apply generated filter if available
                if generated_filter:
                    retrieval_config["vectorSearchConfiguration"]["filter"] = generated_filter

                # Log exactly what we're sending to the KB
                logger.info(f"[RETRIEVE REQUEST] kb={knowledge_base_id}")

                retrieve_response = bedrock_agent.retrieve(
                    knowledgeBaseId=knowledge_base_id,
                    retrievalQuery={"text": retrieval_query},
                    retrievalConfiguration=retrieval_config,
                )
                retrieval_results = retrieve_response.get("retrievalResults", [])
            logger.info(f"Retrieved {len(retrieval_results)} results")

            # Log each result's URI and score for debugging
            for i, r in enumerate(retrieval_results):
                uri = r.get("location", {}).get("s3Location", {}).get("uri", "N/A")
                score = r.get("score", "N/A")
                logger.info(f"[RETRIEVE] Result {i}: score={score}, uri={uri}")
        except Exception as e:
            logger.warning(f"Retrieval failed: {e}")

        logger.info(f"Retrieved {len(retrieval_results)} total results from KB")

        # Fallback: If query contains an ID pattern, try DynamoDB filename lookup
        tracking_table = os.environ.get("TRACKING_TABLE")
        retrieval_results = _augment_with_id_lookup(
            retrieval_query, retrieval_results, tracking_table
        )

        # Build context from retrieved documents
        retrieved_chunks = []
        citations = []  # Build citations in the format expected by extract_sources
        matched_images = []  # Collect images for visual matches to send to LLM

        # Only send images from top 3 most relevant results (already sorted by score)
        # Limit to 1 image to control costs and context size
        MAX_IMAGE_RANK = 3  # Only consider images in top 3 results
        MAX_IMAGES_TO_SEND = 1  # Only send 1 image to the model

        for result_rank, result in enumerate(retrieval_results):
            content = result.get("content") or {}
            metadata = result.get("metadata") or {}
            location = result.get("location") or {}

            # Extract metadata for context enrichment
            content_type = extract_kb_scalar(metadata.get("content_type"))
            filename = extract_kb_scalar(metadata.get("filename"))

            # Get timestamps (custom keys in seconds, native KB keys in milliseconds)
            ts_start = None
            ts_end = None
            # Note: KB returns floats like 30000.0, need int(float()) to convert
            ts_raw = metadata.get("timestamp_start")
            if ts_raw is not None:
                with contextlib.suppress(ValueError, TypeError):
                    ts_start = int(float(extract_kb_scalar(ts_raw)))
            else:
                ts_millis = metadata.get("x-amz-bedrock-kb-chunk-start-time-in-millis")
                if ts_millis is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        ts_start = int(float(extract_kb_scalar(ts_millis))) // 1000

            ts_raw = metadata.get("timestamp_end")
            if ts_raw is not None:
                with contextlib.suppress(ValueError, TypeError):
                    ts_end = int(float(extract_kb_scalar(ts_raw)))
            else:
                ts_millis = metadata.get("x-amz-bedrock-kb-chunk-end-time-in-millis")
                if ts_millis is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        ts_end = int(float(extract_kb_scalar(ts_millis))) // 1000

            # Format timestamp for display (M:SS format)
            ts_display = ""
            if ts_start is not None:
                start_fmt = f"{ts_start // 60}:{ts_start % 60:02d}"
                if ts_end is not None:
                    end_fmt = f"{ts_end // 60}:{ts_end % 60:02d}"
                    ts_display = f", {start_fmt}-{end_fmt}"
                else:
                    ts_display = f", {start_fmt}"

            # Build source header for context enrichment
            source_header = f"[Source: {filename}{ts_display}]\n" if filename else ""

            content_text = content.get("text", "") if isinstance(content, dict) else ""
            s3_uri = location.get("s3Location", {}).get("uri", "")
            uri_lower = s3_uri.lower()
            # Detect visual content by metadata OR by file extension (for visual embeddings)
            visual_extensions = (".jpeg", ".jpg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi")
            is_visual = (
                content_type == "visual"
                or content.get("type") == "VIDEO"
                or uri_lower.endswith(visual_extensions)
            )
            logger.info(f"[RESULT {result_rank}] visual={is_visual}, text={bool(content_text)}")

            if is_visual:
                # Visual match - get additional context (caption for images, transcript for videos)
                visual_context = ""
                tracked_type = ""  # Track the type from DynamoDB for labeling

                # Extract document_id from URI (content/{docId}/...)
                doc_id = None
                if s3_uri:
                    uri_parts = s3_uri.replace("s3://", "").split("/")
                    if len(uri_parts) >= 3 and uri_parts[1] == "content":
                        doc_id = uri_parts[2]

                if doc_id and tracking_table:
                    try:
                        table = dynamodb.Table(tracking_table)
                        response = table.get_item(Key={"document_id": doc_id})
                        item = response.get("Item", {})
                        tracked_type = item.get("type", "")

                        if tracked_type == "image":
                            # For images, use the caption
                            if item.get("caption"):
                                visual_context = f"\nImage caption: {item['caption']}"
                            logger.info(f"Visual image match - added caption for {doc_id}")

                            # Only fetch images from top N results to send to LLM
                            # This ensures we only send the most relevant images
                            if (
                                result_rank < MAX_IMAGE_RANK
                                and len(matched_images) < MAX_IMAGES_TO_SEND
                            ):
                                input_uri = item.get("input_s3_uri")
                                content_type_img = item.get("content_type")
                                if input_uri:
                                    img_block = fetch_image_for_converse(
                                        input_uri, content_type_img
                                    )
                                    if img_block:
                                        matched_images.append(img_block)
                                        logger.info(
                                            f"Fetched image for LLM (rank {result_rank}): {doc_id}"
                                        )
                        elif tracked_type == "media":
                            # For video/audio, get the relevant segment transcript
                            is_segment = "/segment-" in s3_uri
                            if is_segment:
                                # Specific segment - fetch that segment's text
                                bucket, key = parse_s3_uri(s3_uri)
                                if bucket and key:
                                    resp = s3_client.get_object(Bucket=bucket, Key=key)
                                    txt = resp["Body"].read().decode("utf-8")
                                    visual_context = f"\nTranscript: {txt}"
                                    logger.info(f"Visual segment match: {doc_id}")
                            else:
                                # Full video match - get first segment
                                data_bucket = os.environ.get("DATA_BUCKET")
                                if data_bucket:
                                    seg_key = f"content/{doc_id}/segment-000.txt"
                                    resp = s3_client.get_object(Bucket=data_bucket, Key=seg_key)
                                    txt = resp["Body"].read().decode("utf-8")
                                    visual_context = f"\nTranscript (first segment): {txt}"
                                    logger.info(f"Visual video match: {doc_id}")
                    except Exception as e:
                        logger.warning(f"Failed to get visual context for {doc_id}: {e}")

                # Build visual hint with context - use tracking table type for label
                media_type = "Image" if tracked_type == "image" else "Video"
                visual_hint = (
                    f"{source_header}"
                    f"{media_type.upper()} VISUAL MATCH: This {media_type.lower()}'s visual "
                    f'content matches the query "{query}". The visual content was analyzed '
                    f"and found to be semantically relevant.{visual_context}"
                )
                retrieved_chunks.append(visual_hint)
                # For sources display, use shorter text
                source_text = f'{media_type} visual match for: "{query}"'
                result_score = result.get("score")
                citations.append(
                    {
                        "retrievedReferences": [
                            {
                                "content": {"text": source_text},
                                "location": location,
                                "metadata": metadata,
                                "score": result_score,
                            }
                        ]
                    }
                )
            elif content_text:
                # Text content - enrich with source metadata
                enriched_text = f"{source_header}{content_text}"
                retrieved_chunks.append(enriched_text)
                result_score = result.get("score")
                citations.append(
                    {
                        "retrievedReferences": [
                            {
                                "content": {"text": content_text},
                                "location": location,
                                "metadata": metadata,
                                "score": result_score,
                            }
                        ]
                    }
                )

        # Limit to top 5 sources for both LLM context and UI display
        MAX_SOURCES = 5
        if retrieved_chunks:
            retrieved_context = "\n\n---\n\n".join(retrieved_chunks[:MAX_SOURCES])
        else:
            retrieved_context = "No relevant information found in the knowledge base."

        # Parse sources from citations (limited to top 5)
        sources = extract_sources(citations[:MAX_SOURCES])

        # STEP 2: Generate response using Converse API with conversation history
        # Build messages with conversation history and retrieved context
        messages = build_conversation_messages(
            query, history, retrieved_context, images=matched_images
        )

        # System prompt for the assistant (configurable via DynamoDB)
        default_prompt = (
            "You are a helpful assistant that answers questions based on information "
            "from a knowledge base. Always base your answers on the provided knowledge "
            "base information. If the provided information doesn't contain the answer, "
            "clearly state that and provide what relevant information you can. "
            "Be concise but thorough.\n\n"
            "IMPORTANT: When you see 'VISUAL MATCH' in the context, images or videos from "
            "the knowledge base matched the query. For image matches, the actual image is "
            "included - describe what you see. For video matches, a transcript is provided. "
            "Use this visual information to answer the question."
        )
        system_prompt = get_config_manager().get_parameter(
            "chat_system_prompt", default=default_prompt
        )

        # Call Converse API
        converse_response = bedrock_runtime.converse(
            modelId=chat_model_id,
            messages=messages,
            system=[{"text": system_prompt}],
            inferenceConfig={
                "maxTokens": 2048,
                "temperature": 0.7,
            },
        )

        # Extract answer from response
        answer = ""
        output = converse_response.get("output") or {}
        output_message = output.get("message") or {} if isinstance(output, dict) else {}
        if isinstance(output_message, dict):
            content_blocks = output_message.get("content", [])
        else:
            content_blocks = []
        for content_block in content_blocks:
            if isinstance(content_block, dict) and "text" in content_block:
                answer += content_block["text"]

        logger.info(f"KB query done. Retrieved: {len(retrieval_results)}, Sources: {len(sources)}")

        # Store conversation turn for future context
        if conversation_id:
            next_turn = len(history) + 1
            store_conversation_turn(
                conversation_id=conversation_id,
                turn_number=next_turn,
                user_message=query,  # Store original query, not enhanced
                assistant_response=answer,
                sources=sources,
            )

        # Include filter info in response if a filter was generated
        response = {
            "answer": answer,
            "conversationId": conversation_id,
            "sources": sources,
        }
        if generated_filter:
            response["filterApplied"] = json.dumps(generated_filter)

        return response

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", "")
        logger.error(f"Bedrock client error: {error_code} - {error_msg}")
        return {
            "error": f"Failed to query knowledge base: {error_msg}",
            "answer": "",
            "conversationId": conversation_id,
            "sources": [],
        }

    except Exception as e:
        # Generic error handling
        logger.error(f"Error querying KB: {e}", exc_info=True)
        return {
            "error": "Failed to query knowledge base. Please try again.",
            "answer": "",
            "conversationId": conversation_id,
            "sources": [],
        }
