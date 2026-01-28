"""Filter example generation for metadata filtering.

This module provides functions for generating, storing, and managing
filter examples used by the query-time filter generator.
"""

import json
import logging
from datetime import UTC, datetime

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ragstack_common.config import get_config_manager_or_none

logger = logging.getLogger(__name__)

# Initialize AWS clients with consistent timeout settings (matching bedrock.py)
_bedrock_config = Config(
    connect_timeout=10,
    read_timeout=300,  # Allow time for LLM generation
)
bedrock_runtime = boto3.client("bedrock-runtime", config=_bedrock_config)
s3 = boto3.client("s3")

DEFAULT_FILTER_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


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
        key=lambda x: x[1].get("count", 0),
        reverse=True,
    )[:10]:  # Top 10 fields
        sample_values = stats.get("sample_values", []) or []
        samples = ", ".join(str(v) for v in sample_values[:5])
        data_type = stats.get("data_type", "unknown")
        count = stats.get("count", 0)
        field_descriptions.append(
            f"- {key} ({data_type}): {count} occurrences, samples: [{samples}]"
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

IMPORTANT: All filter values MUST be lowercase. Metadata is stored in lowercase.

Generate exactly {num_examples} practical filter examples that users might find useful.
Each example should have:
- name: Short descriptive name
- description: What this filter does
- use_case: When to use this filter
- filter: The actual filter JSON (all string values lowercase)

Return ONLY a JSON array of filter examples, no explanation. Example format:
[
  {{
    "name": "PDF Documents",
    "description": "Filter for PDF document type",
    "use_case": "Finding all PDF files in the knowledge base",
    "filter": {{"document_type": {{"$eq": "pdf"}}}}
  }},
  {{
    "name": "Letters from John Smith",
    "description": "Filter for letters mentioning John Smith",
    "use_case": "Finding correspondence involving a specific person",
    "filter": {{"$and": [{{"document_type": {{"$eq": "letter"}}}},
      {{"people_mentioned": {{"$eq": "john smith"}}}}]}}
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


def update_config_with_examples(examples: list[dict], clear_disabled: bool = False) -> None:
    """
    Update configuration table with filter examples.

    Args:
        examples: List of filter example dictionaries.
        clear_disabled: If True, clear the disabled list (after replacement).
    """
    config_manager = get_config_manager_or_none()
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
