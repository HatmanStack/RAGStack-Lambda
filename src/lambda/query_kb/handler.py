"""Lambda handler orchestration for query_kb.

Contains the main lambda_handler entry point and quota management.
Coordinates retrieval, conversation history, source extraction,
and response generation.
"""

import contextlib
import json
import logging
import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

try:
    from ._clients import bedrock_agent, bedrock_runtime, dynamodb, dynamodb_client, s3_client
    from .conversation import get_conversation_history, store_conversation_turn
    from .filters import (
        _get_filter_components,
        _get_filter_examples,
        extract_kb_scalar,
        get_config_manager,
    )
    from .media import fetch_image_for_converse, format_timestamp
    from .retrieval import (
        _augment_with_id_lookup,
        build_conversation_messages,
        build_retrieval_query,
    )
    from .sources import extract_sources
except ImportError:
    from _clients import (  # type: ignore[import-not-found,no-redef]
        bedrock_agent,
        bedrock_runtime,
        dynamodb,
        dynamodb_client,
        s3_client,
    )
    from conversation import (  # type: ignore[import-not-found,no-redef]
        get_conversation_history,
        store_conversation_turn,
    )
    from filters import (  # type: ignore[import-not-found,no-redef]
        _get_filter_components,
        _get_filter_examples,
        extract_kb_scalar,
        get_config_manager,
    )
    from media import (  # type: ignore[import-not-found,no-redef]
        fetch_image_for_converse,
        format_timestamp,
    )
    from retrieval import (  # type: ignore[import-not-found,no-redef]
        _augment_with_id_lookup,
        build_conversation_messages,
        build_retrieval_query,
    )
    from sources import extract_sources  # type: ignore[import-not-found,no-redef]

from ragstack_common.auth import check_public_access
from ragstack_common.config import get_knowledge_base_config
from ragstack_common.demo_mode import is_demo_mode_enabled
from ragstack_common.storage import parse_s3_uri
from ragstack_common.types import ChatResponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Quota settings
QUOTA_TTL_DAYS = 2  # Quota counters expire after 2 days


def atomic_quota_check_and_increment(tracking_id: str, is_authenticated: bool, region: str) -> str:
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
    primary_model: str = str(
        get_config_manager().get_parameter(
            "chat_primary_model", default="us.anthropic.claude-haiku-4-5-20251001-v1:0"
        )
    )
    fallback_model: str = str(
        get_config_manager().get_parameter(
            "chat_fallback_model", default="us.amazon.nova-lite-v1:0"
        )
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

        # Add per-caller quota check (authenticated or anonymous with tracking ID)
        if tracking_id:
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
        dynamodb_client.transact_write_items(TransactItems=transact_items)  # type: ignore[arg-type]

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


def lambda_handler(event: dict[str, Any], context: Any) -> ChatResponse:
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

    try:
        # Validate query before consuming quota
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

        # Check quotas and select model (primary or fallback) — after validation
        chat_model_id = atomic_quota_check_and_increment(
            tracking_id or "", is_authenticated, region
        )

        # Log safe summary (not full event payload to avoid PII/user data leakage)
        safe_summary = {
            "query_length": len(query),
            "has_conversation": conversation_id is not None,
            "is_authenticated": is_authenticated,
            "knowledge_base_id": knowledge_base_id[:8] + "..."
            if len(knowledge_base_id) > 8
            else knowledge_base_id,
        }
        logger.info(f"Querying Knowledge Base: {json.dumps(safe_summary)}")
        logger.info(f"Using chat model: {chat_model_id}")

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

        retrieval_results: list[Any] = []
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
                    logger.debug(f"[MULTISLICE] Result {i}: score={score}, uri={uri}")
            else:
                # Standard single-query retrieval
                retrieval_config: dict[str, Any] = {
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
                    retrievalConfiguration=retrieval_config,  # type: ignore[arg-type]
                )
                retrieval_results = list(retrieve_response.get("retrievalResults", []))
            logger.info(f"Retrieved {len(retrieval_results)} results")

            # Log each result's URI and score for debugging
            for i, r in enumerate(retrieval_results):
                uri = r.get("location", {}).get("s3Location", {}).get("uri", "N/A")
                score = r.get("score", "N/A")
                logger.debug(f"[RETRIEVE] Result {i}: score={score}, uri={uri}")
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
        # Collect images for visual matches to send to LLM
        matched_images: list[dict[str, Any]] = []

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
                ts_str = extract_kb_scalar(ts_raw)
                if ts_str is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        ts_start = int(float(ts_str))
            else:
                ts_millis = metadata.get("x-amz-bedrock-kb-chunk-start-time-in-millis")
                if ts_millis is not None:
                    ts_str = extract_kb_scalar(ts_millis)
                    if ts_str is not None:
                        with contextlib.suppress(ValueError, TypeError):
                            ts_start = int(float(ts_str)) // 1000

            ts_raw = metadata.get("timestamp_end")
            if ts_raw is not None:
                ts_str = extract_kb_scalar(ts_raw)
                if ts_str is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        ts_end = int(float(ts_str))
            else:
                ts_millis = metadata.get("x-amz-bedrock-kb-chunk-end-time-in-millis")
                if ts_millis is not None:
                    ts_str = extract_kb_scalar(ts_millis)
                    if ts_str is not None:
                        with contextlib.suppress(ValueError, TypeError):
                            ts_end = int(float(ts_str)) // 1000

            # Format timestamp for display (M:SS format)
            ts_display = ""
            if ts_start is not None:
                start_fmt = format_timestamp(ts_start)
                if ts_end is not None:
                    end_fmt = format_timestamp(ts_end)
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
            logger.debug(f"[RESULT {result_rank}] visual={is_visual}, text={bool(content_text)}")

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
                        tracked_type = str(item.get("type", ""))

                        if tracked_type == "image":
                            # For images, use the caption
                            if item.get("caption"):
                                visual_context = f"\nImage caption: {str(item['caption'])}"
                            logger.info(f"Visual image match - added caption for {doc_id}")

                            # Only fetch images from top N results to send to LLM
                            # This ensures we only send the most relevant images
                            if (
                                result_rank < MAX_IMAGE_RANK
                                and len(matched_images) < MAX_IMAGES_TO_SEND
                            ):
                                input_uri = str(item.get("input_s3_uri", ""))
                                content_type_img = str(item.get("content_type", "")) or None
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
        result_response: ChatResponse = {
            "answer": answer,
            "conversationId": conversation_id,
            "sources": sources,
        }
        if generated_filter:
            result_response["filterApplied"] = json.dumps(generated_filter)

        return result_response

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
