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

import boto3
from botocore.exceptions import ClientError

from ragstack_common.auth import check_public_access
from ragstack_common.config import ConfigurationManager
from ragstack_common.filter_generator import FilterGenerator
from ragstack_common.key_library import KeyLibrary
from ragstack_common.multislice_retriever import MultiSliceRetriever

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level initialization (reused across Lambda invocations)
config_manager = ConfigurationManager()
dynamodb = boto3.resource("dynamodb")
bedrock_agent = boto3.client("bedrock-agent-runtime")

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
    examples = config_manager.get_parameter("metadata_filter_examples", default=[])
    _filter_examples_cache = examples if isinstance(examples, list) else []
    _filter_examples_cache_time = now

    logger.debug(f"Loaded {len(_filter_examples_cache)} filter examples from config")
    return _filter_examples_cache


def extract_document_id_from_uri(uri):
    """Extract document_id from S3 URI like s3://bucket/output/{doc_id}/extracted_text.txt"""
    if not uri:
        return None
    # Match output/{uuid}/... or images/{uuid}/...
    match = re.search(r"(?:output|images)/([a-f0-9-]{36})/", uri)
    if match:
        return match.group(1)
    return None


def lookup_original_source(document_id, tracking_table_name):
    """Look up the original input_s3_uri from tracking table."""
    if not document_id or not tracking_table_name:
        return None, None
    try:
        table = dynamodb.Table(tracking_table_name)
        response = table.get_item(Key={"document_id": document_id})
        item = response.get("Item")
        if item:
            return item.get("input_s3_uri"), item.get("filename")
    except Exception as e:
        logger.warning(f"Failed to lookup document {document_id}: {e}")
    return None, None


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

    # Get environment variables
    knowledge_base_id = os.environ.get("KNOWLEDGE_BASE_ID")
    tracking_table_name = os.environ.get("TRACKING_TABLE")
    text_data_source_id = os.environ.get("TEXT_DATA_SOURCE_ID")
    image_data_source_id = os.environ.get("IMAGE_DATA_SOURCE_ID")
    if not knowledge_base_id:
        return {
            "query": "",
            "results": [],
            "total": 0,
            "error": "KNOWLEDGE_BASE_ID environment variable is required",
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
        # If data source IDs are configured, run separate queries for balanced results
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

        if text_data_source_id or image_data_source_id:
            # Query each data source with full maxResults for comprehensive coverage

            # Query text data source
            if text_data_source_id:
                try:
                    if multislice_enabled and generated_filter:
                        # Use multi-slice retrieval with filter
                        _, _, multislice_retriever = _get_filter_components()
                        text_results = multislice_retriever.retrieve(
                            query=query,
                            knowledge_base_id=knowledge_base_id,
                            data_source_id=text_data_source_id,
                            metadata_filter=generated_filter,
                            num_results=max_results,
                        )
                    else:
                        # Standard single-query retrieval
                        text_response = bedrock_agent.retrieve(
                            knowledgeBaseId=knowledge_base_id,
                            retrievalQuery={"text": query},
                            retrievalConfiguration={
                                "vectorSearchConfiguration": {
                                    "numberOfResults": max_results,
                                    "filter": {
                                        "equals": {
                                            "key": "x-amz-bedrock-kb-data-source-id",
                                            "value": text_data_source_id,
                                        }
                                    },
                                }
                            },
                        )
                        text_results = text_response.get("retrievalResults", [])
                    retrieval_results.extend(text_results)
                    logger.info("Retrieved %d text results", len(text_results))
                except Exception as e:
                    logger.warning(f"Text search failed: {e}")

            # Query image data source
            if image_data_source_id:
                try:
                    if multislice_enabled and generated_filter:
                        # Use multi-slice retrieval with filter
                        _, _, multislice_retriever = _get_filter_components()
                        image_results = multislice_retriever.retrieve(
                            query=query,
                            knowledge_base_id=knowledge_base_id,
                            data_source_id=image_data_source_id,
                            metadata_filter=generated_filter,
                            num_results=max_results,
                        )
                    else:
                        # Standard single-query retrieval
                        image_response = bedrock_agent.retrieve(
                            knowledgeBaseId=knowledge_base_id,
                            retrievalQuery={"text": query},
                            retrievalConfiguration={
                                "vectorSearchConfiguration": {
                                    "numberOfResults": max_results,
                                    "filter": {
                                        "equals": {
                                            "key": "x-amz-bedrock-kb-data-source-id",
                                            "value": image_data_source_id,
                                        }
                                    },
                                }
                            },
                        )
                        image_results = image_response.get("retrievalResults", [])
                    retrieval_results.extend(image_results)
                    logger.info("Retrieved %d image results", len(image_results))
                except Exception as e:
                    logger.warning(f"Image search failed: {e}")
        else:
            # Fallback: unfiltered query if no data source IDs configured
            vector_config = {"numberOfResults": max_results}
            response = bedrock_agent.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={"vectorSearchConfiguration": vector_config},
            )
            retrieval_results = response.get("retrievalResults", [])

        # Parse results
        results = []
        for item in retrieval_results:
            kb_uri = item.get("location", {}).get("s3Location", {}).get("uri", "")

            # Look up original source from tracking table
            source_uri = kb_uri  # Default to KB URI
            if tracking_table_name:
                document_id = extract_document_id_from_uri(kb_uri)
                if document_id:
                    original_uri, _ = lookup_original_source(document_id, tracking_table_name)
                    if original_uri:
                        source_uri = original_uri

            results.append(
                {
                    "content": item.get("content", {}).get("text", ""),
                    "source": source_uri,
                    "score": item.get("score", 0.0),
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
