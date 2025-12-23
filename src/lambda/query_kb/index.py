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

import json
import logging
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import unquote

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from ragstack_common.auth import check_public_access
from ragstack_common.config import ConfigurationManager

# Initialize AWS clients
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level initialization (reused across Lambda invocations in same container)
config_manager = ConfigurationManager()

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

    Args:
        tracking_id (str): User identifier for per-user quota
        is_authenticated (bool): Whether user is authenticated
        region (str): AWS region

    Returns:
        str: Model ID to use (primary or fallback)
    """
    # Load quota configuration
    primary_model = config_manager.get_parameter(
        "chat_primary_model", default="us.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    fallback_model = config_manager.get_parameter(
        "chat_fallback_model", default="us.amazon.nova-micro-v1:0"
    )
    global_quota_daily = config_manager.get_parameter("chat_global_quota_daily", default=10000)
    per_user_quota_daily = config_manager.get_parameter("chat_per_user_quota_daily", default=100)

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
        dynamodb_client = boto3.client("dynamodb")
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


def build_retrieval_query(current_query, history):
    """
    Build an optimized query for KB retrieval.

    For multi-turn conversations, we expand the current query with key context
    from conversation history to help disambiguate references (e.g., "it", "that"),
    but keep it focused for effective retrieval.

    Args:
        current_query (str): The user's current question
        history (list[dict]): Previous conversation turns

    Returns:
        str: Query optimized for KB retrieval
    """
    if not history:
        return current_query

    # Extract key terms from recent conversation to help disambiguate
    # Focus on the last 2 turns for context
    recent_context = []
    for turn in history[-2:]:
        user_msg = turn.get("userMessage", "")
        if user_msg:
            recent_context.append(user_msg)

    if not recent_context:
        return current_query

    # Build a retrieval query that includes the current question
    # plus brief context for disambiguation
    context_summary = " | ".join(recent_context)

    return f"{current_query} (context: {context_summary})"


def build_conversation_messages(current_query, history, retrieved_context):
    """
    Build messages array for Bedrock Converse API with conversation history.

    Args:
        current_query (str): The user's current question
        history (list[dict]): Previous conversation turns
        retrieved_context (str): Retrieved documents from KB

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

    messages.append({"role": "user", "content": [{"text": current_message}]})

    return messages


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


def construct_image_uri_from_content_uri(content_s3_uri, content_text=None):
    """
    Convert caption/content.txt S3 URI to the actual image file URI.

    The caption file is stored at: images/{imageId}/caption.txt (or content.txt)
    The actual image is at: images/{imageId}/{filename}.ext

    We extract the filename from the frontmatter in the caption text.

    Args:
        content_s3_uri (str): S3 URI of the caption.txt or content.txt file
        content_text (str): Optional content text to extract filename from frontmatter

    Returns:
        str or None: S3 URI of the image file, or None if not determinable
    """
    if not content_s3_uri:
        return None

    # Check for caption.txt or content.txt
    is_caption_file = "caption.txt" in content_s3_uri or "content.txt" in content_s3_uri
    if not is_caption_file:
        return None

    try:
        # Try to extract filename from frontmatter in content
        if content_text:
            # Look for "filename: xxx" in YAML frontmatter
            filename_match = re.search(r"^filename:\s*(.+)$", content_text, re.MULTILINE)
            if filename_match:
                filename = filename_match.group(1).strip()
                # Replace caption.txt or content.txt with the actual filename
                base_uri = content_s3_uri.replace("/caption.txt", "").replace("/content.txt", "")
                return f"{base_uri}/{filename}"

        # Fallback: return base path (folder)
        return content_s3_uri.replace("/caption.txt", "").replace("/content.txt", "")
    except Exception:
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

            if not uri:
                logger.debug(f"No URI found in reference. Location: {location}")
                continue

            logger.info(f"Processing source URI: {uri}")

            # Parse S3 URI to construct the original input document URI
            # Actual structures in this project:
            # 1. PDF output: s3://bucket/output/{docId}/{docId}/extracted_text.txt
            #    Input: s3://bucket/input/{docId}/{filename}.pdf
            # 2. Scraped output: s3://bucket/output/{docId}/full_text.txt
            #    Input: s3://bucket/input/{docId}/{docId}.scraped.md
            # 3. Images: s3://bucket/images/{imageId}/caption.txt
            #    Actual image: s3://bucket/images/{imageId}/{filename}.ext
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
                if len(parts) > 2 and parts[1] == "images":
                    # Image structure: bucket/images/{imageId}/caption.txt
                    document_id = unquote(parts[2])
                    input_prefix = "images"
                    is_image = True
                    # original_filename will be extracted from frontmatter later
                    logger.info(f"Image structure detected: imageId={document_id}")

                elif len(parts) > 2 and parts[1] == "output":
                    # Output structure: bucket/output/{docId}/...
                    document_id = unquote(parts[2])
                    input_prefix = "input"

                    # Check if it's scraped content (full_text.txt) or PDF (extracted_text.txt)
                    last_part = parts[-1] if parts else ""
                    if last_part == "full_text.txt":
                        # Scraped: input filename is {docId}.scraped.md
                        original_filename = f"{document_id}.scraped.md"
                        is_scraped = True
                        logger.info(f"Scraped content detected: docId={document_id}")
                    else:
                        # PDF or other document - need to look up filename from tracking table
                        # For now, we'll need to query DynamoDB to get the original filename
                        logger.info(f"Document output detected: docId={document_id}")

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
                            logger.info(
                                f"[SOURCE] Tracking lookup SUCCESS: "
                                f"input_s3_uri={tracking_input_uri}, "
                                f"filename={original_filename}, "
                                f"source_url={tracking_source_url}, "
                                f"status={tracking_item.get('status')}, "
                                f"type={tracking_item.get('type')}"
                            )
                        else:
                            logger.warning(
                                f"[SOURCE] Tracking lookup EMPTY: "
                                f"No item found for document_id={document_id}"
                            )
                    except Exception as e:
                        logger.error(f"[SOURCE] Tracking lookup FAILED: {e}", exc_info=True)
                else:
                    logger.warning("[SOURCE] TRACKING_TABLE env var not set!")

                # Construct input document URI
                # Prefer input_s3_uri from tracking table (most reliable)
                if tracking_input_uri:
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

                # For scraped content, get source URL from tracking table or frontmatter
                source_url = None
                if is_scraped:
                    # Prefer source_url from tracking table (more reliable)
                    if tracking_source_url:
                        source_url = tracking_source_url
                        logger.info(f"[SOURCE] Using source_url from tracking: {source_url}")
                    else:
                        # Fallback: try to extract from content frontmatter
                        source_url = extract_source_url_from_content(content_text)
                        logger.info(f"[SOURCE] Extracted source_url from content: {source_url}")

                # For image content, extract caption from frontmatter
                image_caption = None
                if is_image:
                    image_caption = extract_image_caption_from_content(content_text)
                    preview = image_caption[:50] if image_caption else None
                    logger.debug(f"Image content detected, caption: {preview}...")

                # Deduplicate by document + page
                source_key = f"{document_id}:{page_num}"
                if source_key not in seen:
                    # Check if document access is allowed
                    allow_document_access = config_manager.get_parameter(
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

                    source_obj = {
                        "documentId": document_id,
                        "pageNumber": page_num,
                        "s3Uri": document_s3_uri,  # Use input bucket URI, not output
                        "snippet": snippet,
                        "documentUrl": document_url,
                        "documentAccessAllowed": allow_document_access,
                        "isScraped": is_scraped,
                        "sourceUrl": source_url,  # Original web URL for scraped content
                        # Image-specific fields
                        "isImage": is_image,
                        "thumbnailUrl": thumbnail_url,
                        "caption": image_caption,
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
    allowed, error_msg = check_public_access(event, "chat", config_manager)
    if not allowed:
        return {
            "answer": "",
            "conversationId": None,
            "sources": [],
            "error": error_msg,
        }

    # Get environment variables (moved here for testability)
    knowledge_base_id = os.environ.get("KNOWLEDGE_BASE_ID")
    if not knowledge_base_id:
        return {
            "answer": "",
            "conversationId": None,
            "sources": [],
            "error": "KNOWLEDGE_BASE_ID environment variable is required",
        }

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

        retrieve_response = bedrock_agent.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={"text": retrieval_query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": 5,  # Get top 5 relevant chunks
                }
            },
        )

        # Extract retrieved results and build context
        retrieval_results = retrieve_response.get("retrievalResults", [])
        logger.info(f"Retrieved {len(retrieval_results)} results from KB")

        # Build context from retrieved documents
        retrieved_chunks = []
        citations = []  # Build citations in the format expected by extract_sources
        for result in retrieval_results:
            content = result.get("content") or {}
            content_text = content.get("text", "") if isinstance(content, dict) else ""
            if content_text:
                retrieved_chunks.append(content_text)
                # Build citation structure for source extraction
                citations.append(
                    {
                        "retrievedReferences": [
                            {
                                "content": {"text": content_text},
                                "location": result.get("location") or {},
                                "metadata": result.get("metadata") or {},
                            }
                        ]
                    }
                )

        if retrieved_chunks:
            retrieved_context = "\n\n---\n\n".join(retrieved_chunks)
        else:
            retrieved_context = "No relevant information found in the knowledge base."

        # Parse sources from citations
        sources = extract_sources(citations)

        # STEP 2: Generate response using Converse API with conversation history
        bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)

        # Build messages with conversation history and retrieved context
        messages = build_conversation_messages(query, history, retrieved_context)

        # System prompt for the assistant
        system_prompt = (
            "You are a helpful assistant that answers questions based on information "
            "from a knowledge base. Always base your answers on the provided knowledge "
            "base information. If the provided information doesn't contain the answer, "
            "clearly state that and provide what relevant information you can. "
            "Be concise but thorough."
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

        return {"answer": answer, "conversationId": conversation_id, "sources": sources}

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
