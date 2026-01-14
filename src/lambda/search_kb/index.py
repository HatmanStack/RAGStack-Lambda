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
import re
import time

import boto3
from botocore.exceptions import ClientError

from ragstack_common.auth import check_public_access
from ragstack_common.config import ConfigurationManager, get_knowledge_base_config
from ragstack_common.filter_generator import FilterGenerator
from ragstack_common.key_library import KeyLibrary
from ragstack_common.multislice_retriever import MultiSliceRetriever

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def extract_kb_scalar(value: any) -> str | None:
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
config_manager = ConfigurationManager()
dynamodb = boto3.resource("dynamodb")
bedrock_agent = boto3.client("bedrock-agent-runtime")
s3_client = boto3.client("s3")

# Filter generation components (lazy-loaded to avoid init overhead if disabled)
_key_library = None
_filter_generator = None
_multislice_retriever = None
_filter_examples_cache = None
_filter_examples_cache_time = None
FILTER_EXAMPLES_CACHE_TTL = 300  # 5 minutes


def _get_filter_components():
    """Lazy-load filter generation components."""
    global _key_library, _filter_generator, _multislice_retriever

    if _key_library is None:
        _key_library = KeyLibrary()

    if _filter_generator is None:
        _filter_generator = FilterGenerator(key_library=_key_library)

    if _multislice_retriever is None:
        _multislice_retriever = MultiSliceRetriever(bedrock_agent_client=bedrock_agent)

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
    examples = config_manager.get_parameter("metadata_filter_examples", default=[])
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
            return {
                "input_s3_uri": item.get("input_s3_uri"),
                "filename": item.get("filename"),
                "type": item.get("type"),  # document, image, media, scrape
                "media_type": item.get("media_type"),  # video, audio
                "source_url": item.get("source_url"),  # for scraped content
            }
    except Exception as e:
        logger.warning(f"Failed to lookup document {document_id}: {e}")
    return {}


def generate_presigned_url(bucket, key, expiration=3600):
    """Generate presigned URL for S3 object."""
    try:
        return s3_client.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expiration
        )
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return None


def parse_s3_uri(s3_uri):
    """Parse S3 URI into bucket and key."""
    if not s3_uri or not s3_uri.startswith("s3://"):
        return None, None
    path = s3_uri[5:]
    if "/" not in path:
        return path, ""
    bucket, key = path.split("/", 1)
    return bucket, key


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
    allowed, error_msg = check_public_access(event, "search", config_manager)
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
        knowledge_base_id, _ = get_knowledge_base_config(config_manager)
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
        # Single unified query with optional metadata filter (includes content_type)
        retrieval_results = []
        generated_filter = None

        # Check if filter generation is enabled
        filter_enabled = config_manager.get_parameter("filter_generation_enabled", default=True)
        multislice_enabled = config_manager.get_parameter("multislice_enabled", default=True)

        # Generate metadata filter if enabled
        if filter_enabled:
            try:
                _, filter_generator, _ = _get_filter_components()
                filter_examples = _get_filter_examples()
                generated_filter = filter_generator.generate_filter(
                    query,
                    filter_examples=filter_examples,
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
                _, _, multislice_retriever = _get_filter_components()
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

                response = bedrock_agent.retrieve(
                    knowledgeBaseId=knowledge_base_id,
                    retrievalQuery={"text": query},
                    retrievalConfiguration=retrieval_config,
                )
                retrieval_results = response.get("retrievalResults", [])
            logger.info(f"Retrieved {len(retrieval_results)} results")
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
            is_transcript_segment = "/segment-" in kb_uri
            has_timestamp_metadata = kb_metadata.get("timestamp_start") is not None
            is_segment = is_transcript_segment or has_timestamp_metadata

            # Look up document details from tracking table
            doc_info = {}
            source_uri = kb_uri
            if tracking_table_name and document_id:
                doc_info = lookup_original_source(document_id, tracking_table_name)
                if doc_info.get("input_s3_uri"):
                    source_uri = doc_info["input_s3_uri"]

            # Determine content type
            doc_type = doc_info.get("type", "document")
            is_scraped = doc_type == "scrape"
            is_image = doc_type == "image"
            is_media = doc_type == "media"

            # Get timestamp from segment metadata (KB returns as list with quoted strings)
            timestamp_start = None
            if is_segment:
                ts_raw = kb_metadata.get("timestamp_start")
                ts_str = extract_kb_scalar(ts_raw)
                if ts_str is not None:
                    try:
                        timestamp_start = int(ts_str)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid timestamp_start value: {ts_raw}")

            # Generate presigned URL if access is enabled
            document_url = None
            segment_url = None
            input_s3_uri = doc_info.get("input_s3_uri")
            if allow_document_access:
                # For scraped content, use source_url (original web URL)
                if is_scraped and doc_info.get("source_url"):
                    document_url = doc_info["source_url"]
                elif is_segment and input_s3_uri:
                    # For segments, create video URL with timestamp parameter
                    bucket, key = parse_s3_uri(input_s3_uri)
                    if bucket and key:
                        base_url = generate_presigned_url(bucket, key)
                        if base_url and timestamp_start is not None:
                            # Append timestamp for deep linking (works with HTML5 video)
                            segment_url = f"{base_url}#t={timestamp_start}"
                        document_url = base_url  # Full video without timestamp
                elif input_s3_uri:
                    bucket, key = parse_s3_uri(input_s3_uri)
                    if bucket and key:
                        document_url = generate_presigned_url(bucket, key)

            # Deduplicate - for segments, use full KB URI; for others, use document_id
            dedup_key = kb_uri if is_segment else document_id
            if dedup_key:
                if dedup_key in seen_sources:
                    logger.debug(f"Skipping duplicate source: {dedup_key}")
                    continue
                seen_sources.add(dedup_key)

            results.append(
                {
                    "content": item.get("content", {}).get("text", ""),
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
