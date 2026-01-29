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

import contextlib
import json
import logging
import os
import re
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

from ragstack_common.auth import check_public_access
from ragstack_common.config import ConfigurationManager, get_knowledge_base_config
from ragstack_common.filter_generator import FilterGenerator
from ragstack_common.key_library import KeyLibrary
from ragstack_common.multislice_retriever import MultiSliceRetriever
from ragstack_common.storage import generate_presigned_url, parse_s3_uri

logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
        # Strip extra quotes that KB adds (e.g., '"0"' -> '0')
        return value.strip('"')
    return str(value)


# Module-level initialization (reused across Lambda invocations)
dynamodb = boto3.resource("dynamodb")
bedrock_agent = boto3.client("bedrock-agent-runtime")
s3_client = boto3.client("s3")
DATA_BUCKET = os.environ.get("DATA_BUCKET")

# Lazy-initialized config manager (avoid raising at import time)
_config_manager = None


def get_config_manager():
    """Get or create ConfigurationManager singleton (lazy initialization)."""
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
        _filter_generator = FilterGenerator(key_library=_key_library)

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


def extract_document_id_from_uri(uri):
    """Extract document_id from S3 URI like s3://bucket/content/{doc_id}/extracted_text.txt"""
    if not uri:
        return None
    # Match content/{uuid}/... (unified prefix for all KB content)
    match = re.search(r"content/([a-f0-9-]{36})/", uri)
    if match:
        return match.group(1)
    return None


def lookup_original_source(document_id, tracking_table_name):
    """Look up document details from tracking table."""
    if not document_id or not tracking_table_name:
        return {}
    try:
        table = dynamodb.Table(tracking_table_name)
        response = table.get_item(Key={"document_id": document_id})
        item = response.get("Item")
        if item:
            # Normalize type field (scrape -> scraped for consistency)
            doc_type = item.get("type") or "document"
            if doc_type == "scrape":
                doc_type = "scraped"
            return {
                "input_s3_uri": item.get("input_s3_uri"),
                "output_s3_uri": item.get("output_s3_uri"),  # transcript for media
                "filename": item.get("filename"),
                "type": doc_type,
                "media_type": item.get("media_type"),  # video, audio
                "source_url": item.get("source_url"),  # for scraped content
                "caption": item.get("caption"),  # for images
            }
    except Exception as e:
        logger.warning(f"Failed to lookup document {document_id}: {e}")
    return {}


def lambda_handler(event, context):
    """
    Search Bedrock Knowledge Base using vector similarity.

    Args:
        event['query'] (str): Search query text
        event['maxResults'] (int, optional): Maximum results to return (default: 5)

    Returns:
        dict: KBQueryResult with query, results, total, and optional error
    """
    # Check public access control
    allowed, error_msg = check_public_access(event, "search", get_config_manager())
    if not allowed:
        return {
            "query": "",
            "results": [],
            "total": 0,
            "error": error_msg,
        }

    # Get KB config from config table (with env var fallback)
    tracking_table_name = os.environ.get("TRACKING_TABLE")
    try:
        knowledge_base_id, _ = get_knowledge_base_config(get_config_manager())
    except ValueError as e:
        return {
            "query": "",
            "results": [],
            "total": 0,
            "error": str(e),
        }

    # Extract inputs from AppSync event
    # AppSync sends: {"arguments": {"query": "...", "maxResults": 5}, ...}
    arguments = event.get("arguments", event)  # Fallback to event for direct invocation
    query = arguments.get("query", "")
    max_results = arguments.get("maxResults", 25)

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
        # Single unified query with optional metadata filter (includes content_type)
        retrieval_results = []
        generated_filter = None

        # Check if filter generation is enabled
        config_manager = get_config_manager()
        filter_enabled = config_manager.get_parameter("filter_generation_enabled", default=True)
        multislice_enabled = config_manager.get_parameter("multislice_enabled", default=True)
        filtered_score_boost = float(config_manager.get_parameter(
            "multislice_filtered_boost", default=1.25
        ))

        # Generate metadata filter if enabled
        if filter_enabled:
            try:
                _, filter_generator, _ = _get_filter_components(filtered_score_boost)
                filter_examples = _get_filter_examples()
                manual_keys = config_manager.get_parameter("metadata_manual_keys", default=None)
                extraction_mode = config_manager.get_parameter(
                    "metadata_extraction_mode", default="auto"
                )
                generated_filter = filter_generator.generate_filter(
                    query,
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
                retrieval_results = multislice_retriever.retrieve(
                    query=query,
                    knowledge_base_id=knowledge_base_id,
                    data_source_id=None,  # No data source filtering with unified content/
                    metadata_filter=generated_filter,
                    num_results=max_results,
                )
            else:
                # Standard single-query retrieval
                retrieval_config = {
                    "vectorSearchConfiguration": {
                        "numberOfResults": max_results,
                    }
                }
                # Apply generated filter if available
                if generated_filter:
                    retrieval_config["vectorSearchConfiguration"]["filter"] = generated_filter

                logger.info(f"[SEARCH RETRIEVE] kb={knowledge_base_id}")
                response = bedrock_agent.retrieve(
                    knowledgeBaseId=knowledge_base_id,
                    retrievalQuery={"text": query},
                    retrievalConfiguration=retrieval_config,
                )
                retrieval_results = response.get("retrievalResults", [])
            logger.info(f"Retrieved {len(retrieval_results)} results")
            for i, r in enumerate(retrieval_results):
                uri = r.get("location", {}).get("s3Location", {}).get("uri", "N/A")
                score = r.get("score", "N/A")
                logger.info(f"[SEARCH RESULT] {i}: score={score}, uri={uri}")
        except Exception as e:
            logger.warning(f"Search failed: {e}")

        # Check if document access is enabled
        allow_document_access = config_manager.get_parameter(
            "chat_allow_document_access", default=False
        )

        # Parse results with deduplication
        results = []
        seen_sources = set()
        for item in retrieval_results:
            kb_uri = item.get("location", {}).get("s3Location", {}).get("uri", "")
            document_id = extract_document_id_from_uri(kb_uri)

            # Get metadata from KB result (includes timestamp_start for segments)
            kb_metadata = item.get("metadata", {})

            # Check if this is a segment (transcript segment or video with timestamp)
            # Transcript segments: content/<doc_id>/segment-000.txt
            # Video segments: Nova provides timestamp in metadata for auto-segmented video
            # Visual embeddings: Use native KB timestamp keys (x-amz-bedrock-kb-chunk-*)
            is_transcript_segment = "/segment-" in kb_uri
            has_timestamp_metadata = (
                kb_metadata.get("timestamp_start") is not None
                or kb_metadata.get("x-amz-bedrock-kb-chunk-start-time-in-millis") is not None
            )
            is_segment = is_transcript_segment or has_timestamp_metadata

            # Look up document details from tracking table
            doc_info = {}
            source_uri = kb_uri
            if tracking_table_name and document_id:
                doc_info = lookup_original_source(document_id, tracking_table_name)
                if doc_info.get("input_s3_uri"):
                    source_uri = doc_info["input_s3_uri"]

            # Determine content type (type is already normalized by lookup_original_source)
            doc_type = doc_info.get("type", "document")
            is_scraped = doc_type == "scraped"
            is_image = doc_type == "image"
            # Check both tracking table type and KB metadata content_type for consistency
            content_type = extract_kb_scalar(kb_metadata.get("content_type"))
            media_content_types = ("video", "audio", "transcript", "visual")
            is_media = doc_type == "media" or content_type in media_content_types

            # Get timestamp from segment metadata (KB returns as list with quoted strings)
            timestamp_start = None
            timestamp_end = None
            if is_segment or is_media:
                # Check custom metadata first (transcripts use seconds)
                ts_raw = kb_metadata.get("timestamp_start")
                ts_str = extract_kb_scalar(ts_raw)
                if ts_str is not None:
                    try:
                        timestamp_start = int(ts_str)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid timestamp_start value: {ts_raw}")
                # Fall back to native KB keys for visual embeddings (milliseconds)
                if timestamp_start is None:
                    ts_millis = extract_kb_scalar(
                        kb_metadata.get("x-amz-bedrock-kb-chunk-start-time-in-millis")
                    )
                    if ts_millis is not None:
                        with contextlib.suppress(ValueError, TypeError):
                            timestamp_start = int(ts_millis) // 1000
                    ts_millis_end = extract_kb_scalar(
                        kb_metadata.get("x-amz-bedrock-kb-chunk-end-time-in-millis")
                    )
                    if ts_millis_end is not None:
                        with contextlib.suppress(ValueError, TypeError):
                            timestamp_end = int(ts_millis_end) // 1000

            # Generate presigned URL if access is enabled
            document_url = None
            segment_url = None
            input_s3_uri = doc_info.get("input_s3_uri")
            if allow_document_access:
                # For scraped content, use source_url (original web URL)
                if is_scraped and doc_info.get("source_url"):
                    document_url = doc_info["source_url"]
                elif (is_segment or is_media) and input_s3_uri:
                    # For segments/media, create video URL with timestamp parameter
                    bucket, key = parse_s3_uri(input_s3_uri)
                    if bucket and key:
                        base_url = generate_presigned_url(bucket, key, allowed_bucket=DATA_BUCKET)
                        if base_url and timestamp_start is not None:
                            # Append timestamp for deep linking (works with HTML5 video)
                            if timestamp_end is not None:
                                segment_url = f"{base_url}#t={timestamp_start},{timestamp_end}"
                            else:
                                segment_url = f"{base_url}#t={timestamp_start}"
                        document_url = base_url  # Full video without timestamp
                elif input_s3_uri:
                    bucket, key = parse_s3_uri(input_s3_uri)
                    if bucket and key:
                        document_url = generate_presigned_url(
                            bucket, key, allowed_bucket=DATA_BUCKET
                        )

            # Deduplicate - for segments, use full KB URI; for others, use document_id
            dedup_key = kb_uri if is_segment else document_id
            if dedup_key:
                if dedup_key in seen_sources:
                    logger.debug(f"Skipping duplicate source: {dedup_key}")
                    continue
                seen_sources.add(dedup_key)

            # Get the KB content
            kb_content = item.get("content", {}).get("text", "")

            # Check if this is a visual embedding match (content_type is "visual")
            is_visual_match = content_type == "visual"

            # For visual matches, enhance with caption/transcript for context
            visual_context = None
            if is_visual_match:
                if is_image and doc_info.get("caption"):
                    # For images, use the caption as context
                    visual_context = doc_info["caption"]
                    logger.info(f"Visual image match - adding caption context for {document_id}")
                elif is_media:
                    # For video/audio, get the relevant segment transcript
                    try:
                        if is_segment and "/segment-" in kb_uri:
                            # This is a specific segment match - fetch that segment's text
                            bucket, key = parse_s3_uri(kb_uri)
                            if bucket and key:
                                response = s3_client.get_object(Bucket=bucket, Key=key)
                                visual_context = response["Body"].read().decode("utf-8")
                            logger.info(f"Visual segment match: {document_id}")
                        else:
                            # Full video match - get first segment for context
                            segment_key = f"content/{document_id}/segment-000.txt"
                            response = s3_client.get_object(Bucket=DATA_BUCKET, Key=segment_key)
                            visual_context = response["Body"].read().decode("utf-8")
                            logger.info(f"Visual video match: {document_id}")
                    except Exception as e:
                        logger.warning(f"Failed to fetch segment for {document_id}: {e}")

            # Build the result content - for visual matches, include context
            result_content = kb_content
            if is_visual_match and visual_context:
                if kb_content:
                    result_content = f"{visual_context}\n\n[Visual match from: {kb_content}]"
                else:
                    result_content = visual_context

            results.append(
                {
                    "content": result_content,
                    "source": source_uri,
                    "score": item.get("score", 0.0),
                    "documentId": document_id,
                    "filename": doc_info.get("filename"),
                    "documentUrl": document_url,
                    "documentAccessAllowed": allow_document_access,
                    "isScraped": is_scraped,
                    "sourceUrl": doc_info.get("source_url") if is_scraped else None,
                    "isImage": is_image,
                    "thumbnailUrl": document_url if is_image else None,
                    "isMedia": is_media,
                    "mediaType": doc_info.get("media_type") if is_media else None,
                    "isSegment": is_segment,
                    "segmentUrl": segment_url,
                    "timestampStart": timestamp_start,
                    "isVisualMatch": is_visual_match,
                }
            )

        logger.info(f"Found {len(results)} results")

        # Include filter info in response if a filter was generated
        response = {"query": query, "results": results, "total": len(results)}
        if generated_filter:
            response["filterApplied"] = json.dumps(generated_filter)

        return response

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
