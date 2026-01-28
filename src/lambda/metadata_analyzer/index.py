"""
Metadata Analyzer Lambda

Analyzes vectors in the Knowledge Base to:
1. Sample vectors and extract metadata fields
2. Count field occurrences and calculate rates
3. Generate filter examples using LLM
4. Store results in S3 and update DynamoDB key library

Triggered via AppSync mutation by admins.

Input event: {} (no parameters required)

Output:
{
    "success": True,
    "vectorsSampled": 100,
    "keysAnalyzed": 5,
    "examplesGenerated": 5,
    "executionTimeMs": 1234,
    "error": None
}
"""

import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from ragstack_common.config import (
    get_config_manager_or_none,
    get_knowledge_base_config,
)
from ragstack_common.filter_examples import (
    generate_filter_examples,
    store_filter_examples,
    update_config_with_examples,
)
from ragstack_common.key_library import KeyLibrary

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent = boto3.client("bedrock-agent-runtime")
bedrock_runtime = boto3.client("bedrock-runtime")
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# Lazy-initialized singletons
_key_library = None

# Configuration
DEFAULT_MAX_SAMPLES = 1000
DEFAULT_FILTER_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
MAX_SAMPLE_VALUES = 10


def get_key_library() -> KeyLibrary | None:
    """Get or create KeyLibrary singleton."""
    global _key_library
    if _key_library is None:
        table_name = os.environ.get("METADATA_KEY_LIBRARY_TABLE")
        if table_name:
            _key_library = KeyLibrary(table_name=table_name)
    return _key_library


def strip_embedded_quotes(value: str) -> str:
    """
    Strip embedded quotes from values returned by S3 Vectors retrieve API.

    S3 Vectors JSON-encodes STRING_LIST values when storing, so retrieve returns
    strings like '"test-document.docx"' with literal quote characters. This
    function strips those embedded quotes.

    Args:
        value: String value that may have embedded quotes.

    Returns:
        String with leading/trailing quotes stripped.
    """
    if value and len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def infer_data_type(value: Any) -> str:
    """
    Infer the data type of a metadata value.

    Args:
        value: The metadata value.

    Returns:
        Data type string: "string", "number", "boolean", or "list".
    """
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "list"
    return "string"


def analyze_metadata_fields(metadata_list: list[dict[str, Any]]) -> dict[str, dict]:
    """
    Analyze metadata fields across all sampled vectors.

    Args:
        metadata_list: List of metadata dictionaries from vectors.

    Returns:
        Dictionary of field analysis results with counts, rates, types, and samples.
    """
    if not metadata_list:
        return {}

    total_vectors = len(metadata_list)
    field_stats: dict[str, dict] = {}

    for metadata in metadata_list:
        if not metadata:
            continue

        for key, value in metadata.items():
            # Skip internal keys
            if key.startswith(("x-amz-", "AMAZON_BEDROCK")):
                continue

            if key not in field_stats:
                field_stats[key] = {
                    "count": 0,
                    "data_type": infer_data_type(value),
                    "sample_values": set(),
                }

            field_stats[key]["count"] += 1

            # Collect sample values (up to MAX_SAMPLE_VALUES)
            # Note: S3 Vectors returns STRING_LIST values with embedded quotes
            # e.g., '"test-document.docx"' - we strip these for clean display
            if len(field_stats[key]["sample_values"]) < MAX_SAMPLE_VALUES:
                if isinstance(value, list):
                    for item in value:
                        if len(field_stats[key]["sample_values"]) >= MAX_SAMPLE_VALUES:
                            break
                        str_value = strip_embedded_quotes(str(item))[:100]
                        if str_value:
                            field_stats[key]["sample_values"].add(str_value)
                else:
                    str_value = strip_embedded_quotes(str(value))[:100]
                    if str_value:
                        field_stats[key]["sample_values"].add(str_value)

    # Calculate occurrence rates and convert sets to lists
    for _key, stats in field_stats.items():
        stats["occurrence_rate"] = stats["count"] / total_vectors if total_vectors > 0 else 0
        stats["sample_values"] = list(stats["sample_values"])

    return field_stats


def sample_vectors_from_kb(
    knowledge_base_id: str,
    data_source_id: str | None = None,
    max_samples: int = DEFAULT_MAX_SAMPLES,
) -> list[dict]:
    """
    Sample vectors from the Knowledge Base using retrieve API.

    Uses a generic query to retrieve a sample of vectors with their metadata.

    Args:
        knowledge_base_id: Bedrock Knowledge Base ID.
        data_source_id: Optional data source ID to filter by.
        max_samples: Maximum number of samples to retrieve.

    Returns:
        List of retrieval results with metadata.
    """
    logger.info(f"Sampling up to {max_samples} vectors from KB {knowledge_base_id[:8]}...")

    all_results = []

    # Use a set of generic queries to get diverse samples
    sample_queries = [
        "*",  # Wildcard query
        "document",
        "information",
        "data",
        "content",
    ]

    for query in sample_queries:
        if len(all_results) >= max_samples:
            break

        try:
            # Build retrieval configuration
            vector_config: dict[str, Any] = {
                "numberOfResults": min(100, max_samples - len(all_results)),
            }

            # Add data source filter if provided
            if data_source_id:
                vector_config["filter"] = {
                    "equals": {
                        "key": "x-amz-bedrock-kb-data-source-id",
                        "value": data_source_id,
                    }
                }

            response = bedrock_agent.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={"vectorSearchConfiguration": vector_config},
            )

            results = response.get("retrievalResults", [])
            all_results.extend(results)
            logger.debug(f"Query '{query}' returned {len(results)} results")

        except ClientError as e:
            logger.warning(f"Retrieve query '{query}' failed: {e}")
            continue

    # Deduplicate by S3 URI
    seen_uris = set()
    unique_results = []
    for result in all_results:
        uri = result.get("location", {}).get("s3Location", {}).get("uri", "")
        if uri and uri not in seen_uris:
            seen_uris.add(uri)
            unique_results.append(result)

    logger.info(f"Sampled {len(unique_results)} unique vectors")
    return unique_results[:max_samples]


def update_key_library_counts(
    field_analysis: dict[str, dict],
    table_name: str,
    manual_keys: list[str] | None = None,
) -> None:
    """
    Update the key library with analyzed field statistics.

    Updates sample values, data types, and status for analyzed keys.
    Preserves occurrence_count from ingestion-time upsert_key() calls.

    When manual_keys is provided, only those keys are marked active;
    all other keys are marked inactive.

    Args:
        field_analysis: Dictionary of field analysis results.
        table_name: DynamoDB table name for key library.
        manual_keys: Optional list of key names. When set, only these are active.
    """
    table = dynamodb.Table(table_name)
    now = datetime.now(UTC).isoformat()

    manual_set = None
    if manual_keys:
        manual_set = {k.lower().replace(" ", "_") for k in manual_keys}

    for key_name, stats in field_analysis.items():
        # When manual keys are configured, only those are active
        # Normalize key_name for comparison against manual_set
        if manual_set is not None:
            key_name_norm = key_name.lower().replace(" ", "_")
            status = "active" if key_name_norm in manual_set else "inactive"
        else:
            status = "active"

        try:
            # Update sample values and status, but preserve occurrence_count
            # from ingestion-time upsert_key() calls
            table.update_item(
                Key={"key_name": key_name},
                UpdateExpression="""
                    SET data_type = :dtype,
                        sample_values = :samples,
                        last_analyzed = :now,
                        #status = :status,
                        occurrence_count = if_not_exists(occurrence_count, :zero),
                        first_seen = if_not_exists(first_seen, :now)
                """,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":dtype": stats["data_type"],
                    ":samples": stats["sample_values"][:MAX_SAMPLE_VALUES],
                    ":now": now,
                    ":status": status,
                    ":zero": 0,
                },
            )
            logger.debug(f"Updated key library entry: {key_name} (status={status})")
        except ClientError as e:
            logger.warning(f"Failed to update key '{key_name}': {e}")

    # Mark manual keys as active even if they weren't in the analysis
    # This handles keys that exist in the library but had no vectors sampled
    if manual_set:
        analyzed_keys_norm = {k.lower().replace(" ", "_") for k in field_analysis}
        for manual_key in manual_keys or []:
            manual_key_norm = manual_key.lower().replace(" ", "_")
            if manual_key_norm not in analyzed_keys_norm:
                try:
                    table.update_item(
                        Key={"key_name": manual_key},
                        UpdateExpression="SET #status = :status, last_analyzed = :now",
                        ExpressionAttributeNames={"#status": "status"},
                        ExpressionAttributeValues={
                            ":status": "active",
                            ":now": now,
                        },
                    )
                    logger.debug(f"Marked manual key as active: {manual_key}")
                except ClientError as e:
                    logger.warning(f"Failed to mark manual key '{manual_key}' as active: {e}")


def lambda_handler(event: dict, context) -> dict:
    """
    Main Lambda handler for metadata analysis.

    Analyzes vectors in the Knowledge Base, extracts metadata field statistics,
    generates filter examples, and stores results.

    Args:
        event: Lambda event (no parameters required).
        context: Lambda context.

    Returns:
        Analysis result dictionary.
    """
    start_time = time.time()

    try:
        # Get configuration
        config = get_config_manager_or_none()
        try:
            knowledge_base_id, data_source_id = get_knowledge_base_config(config)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "vectorsSampled": 0,
                "keysAnalyzed": 0,
                "examplesGenerated": 0,
                "executionTimeMs": int((time.time() - start_time) * 1000),
            }

        data_bucket = os.environ.get("DATA_BUCKET")
        key_library_table = os.environ.get("METADATA_KEY_LIBRARY_TABLE")

        # Get configuration options
        config = get_config_manager_or_none()
        max_samples = DEFAULT_MAX_SAMPLES
        if config:
            max_samples = config.get_parameter(
                "metadata_analyzer_max_samples",
                default=DEFAULT_MAX_SAMPLES,
            )
            if not isinstance(max_samples, int):
                max_samples = int(max_samples) if max_samples else DEFAULT_MAX_SAMPLES

        logger.info(f"Starting metadata analysis with max_samples={max_samples}")

        # Step 1: Sample vectors from KB
        vectors = sample_vectors_from_kb(
            knowledge_base_id=knowledge_base_id,
            data_source_id=data_source_id,
            max_samples=max_samples,
        )

        if not vectors:
            logger.info("No vectors found in Knowledge Base")
            return {
                "success": True,
                "vectorsSampled": 0,
                "keysAnalyzed": 0,
                "examplesGenerated": 0,
                "executionTimeMs": int((time.time() - start_time) * 1000),
            }

        # Step 2: Extract metadata from vectors
        metadata_list = []
        for vector in vectors:
            metadata = vector.get("metadata", {})
            if metadata:
                metadata_list.append(metadata)

        logger.info(f"Extracted metadata from {len(metadata_list)} vectors")

        # Step 3: Analyze metadata fields
        field_analysis = analyze_metadata_fields(metadata_list)
        keys_analyzed = len(field_analysis)
        logger.info(f"Analyzed {keys_analyzed} metadata fields")

        # Step 4: Update key library (respects manual key mode)
        extraction_mode = None
        manual_keys = None
        if config:
            extraction_mode = config.get_parameter("metadata_extraction_mode", default="auto")
            if extraction_mode == "manual":
                manual_keys = config.get_parameter("metadata_manual_keys", default=None)

        if key_library_table and field_analysis:
            update_key_library_counts(field_analysis, key_library_table, manual_keys=manual_keys)

        # Step 5: Load existing examples and disabled list, preserve enabled ones
        preserved_examples = []
        disabled_names = set()
        target_example_count = 6  # Default target

        if config:
            current_examples = config.get_parameter("metadata_filter_examples", default=[])
            disabled_list = config.get_parameter("metadata_filter_examples_disabled", default=[])
            disabled_names = set(disabled_list) if disabled_list else set()

            # Keep examples that are NOT disabled
            if current_examples and isinstance(current_examples, list):
                preserved_examples = [
                    ex for ex in current_examples if ex.get("name") not in disabled_names
                ]
                logger.info(f"Preserving {len(preserved_examples)} enabled examples")

        # Step 6: Generate new examples to replace disabled ones (using all active keys)
        num_to_generate = max(0, target_example_count - len(preserved_examples))
        new_examples = []
        if field_analysis and num_to_generate > 0:
            new_examples = generate_filter_examples(field_analysis, num_examples=num_to_generate)
            logger.info(f"Generated {len(new_examples)} new examples")

        # Combine preserved + new
        examples = preserved_examples + new_examples

        # Step 7: Store results
        if data_bucket and examples:
            store_filter_examples(examples, data_bucket)

        # Step 8: Update config with examples and clear disabled list
        if examples:
            update_config_with_examples(examples, clear_disabled=True)

        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Analysis complete: {len(vectors)} vectors, {keys_analyzed} keys, "
            f"{len(examples)} examples in {execution_time_ms}ms"
        )

        return {
            "success": True,
            "vectorsSampled": len(vectors),
            "keysAnalyzed": keys_analyzed,
            "examplesGenerated": len(examples),
            "executionTimeMs": execution_time_ms,
        }

    except Exception as e:
        logger.exception(f"Metadata analysis failed: {e}")
        execution_time_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "error": str(e),
            "vectorsSampled": 0,
            "keysAnalyzed": 0,
            "examplesGenerated": 0,
            "executionTimeMs": execution_time_ms,
        }
