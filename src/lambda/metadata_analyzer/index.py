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

from ragstack_common.config import ConfigurationManager
from ragstack_common.key_library import KeyLibrary

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock_agent = boto3.client("bedrock-agent-runtime")
bedrock_runtime = boto3.client("bedrock-runtime")
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# Lazy-initialized singletons
_config_manager = None
_key_library = None

# Configuration
DEFAULT_MAX_SAMPLES = 1000
DEFAULT_MIN_OCCURRENCE_RATE = 0.1  # 10% minimum occurrence to include in analysis
DEFAULT_FILTER_MODEL = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
MAX_SAMPLE_VALUES = 10


def get_config_manager() -> ConfigurationManager | None:
    """Get or create ConfigurationManager singleton."""
    global _config_manager
    if _config_manager is None:
        table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
        if table_name:
            try:
                _config_manager = ConfigurationManager(table_name=table_name)
            except Exception as e:
                logger.warning(f"Failed to initialize ConfigurationManager: {e}")
                return None
    return _config_manager


def get_key_library() -> KeyLibrary | None:
    """Get or create KeyLibrary singleton."""
    global _key_library
    if _key_library is None:
        table_name = os.environ.get("METADATA_KEY_LIBRARY_TABLE")
        if table_name:
            _key_library = KeyLibrary(table_name=table_name)
    return _key_library


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
            if len(field_stats[key]["sample_values"]) < MAX_SAMPLE_VALUES:
                # Convert value to string for storage
                str_value = str(value)[:100]  # Truncate long values
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


def generate_filter_examples(
    field_analysis: dict[str, dict],
    model_id: str | None = None,
    num_examples: int = 6,
) -> list[dict]:
    """
    Generate filter examples using LLM based on discovered fields.

    Args:
        field_analysis: Dictionary of field analysis results.
        model_id: Bedrock model ID for generation.
        num_examples: Number of examples to generate.

    Returns:
        List of filter example dictionaries.
    """
    if not field_analysis:
        logger.info("No fields to generate examples for")
        return []

    if num_examples <= 0:
        logger.info("No new examples requested")
        return []

    model_id = model_id or DEFAULT_FILTER_MODEL

    # Build field description for prompt
    field_descriptions = []
    for key, stats in sorted(
        field_analysis.items(),
        key=lambda x: x[1]["count"],
        reverse=True,
    )[:10]:  # Top 10 fields
        samples = ", ".join(stats["sample_values"][:5])
        field_descriptions.append(
            f"- {key} ({stats['data_type']}): {stats['count']} occurrences, samples: [{samples}]"
        )

    fields_text = "\n".join(field_descriptions)

    prompt = f"""You are a metadata filter expert. Based on the following metadata fields
discovered in a document knowledge base, generate practical filter examples.

DISCOVERED METADATA FIELDS:
{fields_text}

FILTER SYNTAX (S3 Vectors compatible):
- Equality: {{"field": {{"$eq": "value"}}}}
- Not equals: {{"field": {{"$ne": "value"}}}}
- In list: {{"field": {{"$in": ["a", "b"]}}}}
- And: {{"$and": [condition1, condition2]}}
- Or: {{"$or": [condition1, condition2]}}

Generate exactly {num_examples} practical filter examples that users might find useful. Each example should have:
- name: Short descriptive name
- description: What this filter does
- use_case: When to use this filter
- filter: The actual filter JSON

Return ONLY a JSON array of filter examples, no explanation. Example format:
[
  {{
    "name": "PDF Documents",
    "description": "Filter for PDF document type",
    "use_case": "Finding all PDF files in the knowledge base",
    "filter": {{"document_type": {{"$eq": "pdf"}}}}
  }}
]"""

    try:
        response = bedrock_runtime.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            system=[{"text": "You are a metadata filter expert. Return only valid JSON arrays."}],
            inferenceConfig={"maxTokens": 2000, "temperature": 0.3},
        )

        # Extract response text
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        response_text = ""
        for block in content:
            if isinstance(block, dict) and "text" in block:
                response_text += block["text"]

        # Parse JSON response
        response_text = response_text.strip()
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        examples = json.loads(response_text)

        if not isinstance(examples, list):
            logger.warning("LLM response is not a list")
            return []

        logger.info(f"Generated {len(examples)} filter examples")
        return examples

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse filter examples JSON: {e}")
        return []
    except ClientError as e:
        logger.error(f"Bedrock API error generating examples: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error generating examples: {e}")
        return []


def store_filter_examples(
    examples: list[dict],
    bucket: str,
    index_name: str = "default",
) -> str:
    """
    Store filter examples to S3.

    Stores both a timestamped version and a 'latest' version.

    Args:
        examples: List of filter example dictionaries.
        bucket: S3 bucket name.
        index_name: Index name for path construction.

    Returns:
        S3 URI of the stored latest file.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    base_path = f"metadata-filters/{index_name}"

    # Store timestamped version
    timestamped_key = f"{base_path}/filter-examples-{timestamp}.json"
    s3.put_object(
        Bucket=bucket,
        Key=timestamped_key,
        Body=json.dumps(examples, indent=2),
        ContentType="application/json",
    )
    logger.info(f"Stored timestamped examples: s3://{bucket}/{timestamped_key}")

    # Store latest version
    latest_key = f"{base_path}/filter-examples-latest.json"
    s3.put_object(
        Bucket=bucket,
        Key=latest_key,
        Body=json.dumps(examples, indent=2),
        ContentType="application/json",
    )
    logger.info(f"Stored latest examples: s3://{bucket}/{latest_key}")

    return f"s3://{bucket}/{latest_key}"


def update_key_library_counts(
    field_analysis: dict[str, dict],
    table_name: str,
) -> None:
    """
    Update the key library with analyzed field counts.

    Args:
        field_analysis: Dictionary of field analysis results.
        table_name: DynamoDB table name for key library.
    """
    table = dynamodb.Table(table_name)
    now = datetime.now(UTC).isoformat()

    for key_name, stats in field_analysis.items():
        try:
            # Update or create key entry
            table.update_item(
                Key={"key_name": key_name},
                UpdateExpression="""
                    SET occurrence_count = :count,
                        data_type = :dtype,
                        sample_values = :samples,
                        last_analyzed = :now,
                        #status = if_not_exists(#status, :active),
                        first_seen = if_not_exists(first_seen, :now)
                """,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":count": stats["count"],
                    ":dtype": stats["data_type"],
                    ":samples": stats["sample_values"][:MAX_SAMPLE_VALUES],
                    ":now": now,
                    ":active": "active",
                },
            )
            logger.debug(f"Updated key library entry: {key_name}")
        except ClientError as e:
            logger.warning(f"Failed to update key '{key_name}': {e}")


def update_config_with_examples(examples: list[dict], clear_disabled: bool = False) -> None:
    """
    Update configuration table with filter examples.

    Args:
        examples: List of filter example dictionaries.
        clear_disabled: If True, clear the disabled list (after replacement).
    """
    from datetime import datetime

    config_manager = get_config_manager()
    if config_manager:
        try:
            update_data = {
                "metadata_filter_examples": examples,
                "metadata_filter_examples_updated_at": datetime.now(UTC).isoformat(),
            }
            if clear_disabled:
                update_data["metadata_filter_examples_disabled"] = []
            config_manager.update_custom_config(update_data)
            logger.info(f"Updated config with {len(examples)} filter examples")
        except Exception as e:
            logger.warning(f"Failed to update config with examples: {e}")


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
        knowledge_base_id = os.environ.get("KNOWLEDGE_BASE_ID")
        if not knowledge_base_id:
            return {
                "success": False,
                "error": "KNOWLEDGE_BASE_ID environment variable not set",
                "vectorsSampled": 0,
                "keysAnalyzed": 0,
                "examplesGenerated": 0,
                "executionTimeMs": int((time.time() - start_time) * 1000),
            }

        data_bucket = os.environ.get("DATA_BUCKET")
        text_data_source_id = os.environ.get("TEXT_DATA_SOURCE_ID")
        key_library_table = os.environ.get("METADATA_KEY_LIBRARY_TABLE")

        # Get configuration options
        config = get_config_manager()
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
            data_source_id=text_data_source_id,
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

        # Step 4: Update key library with counts
        if key_library_table and field_analysis:
            update_key_library_counts(field_analysis, key_library_table)

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
                    ex for ex in current_examples
                    if ex.get("name") not in disabled_names
                ]
                logger.info(f"Preserving {len(preserved_examples)} enabled examples")

        # Step 6: Generate new examples to replace disabled ones
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
