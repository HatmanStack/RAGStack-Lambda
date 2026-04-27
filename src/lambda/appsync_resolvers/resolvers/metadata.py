"""Metadata resolver functions for AppSync Lambda handler.

Handles metadata analysis, filter examples, key library,
and KB reindex operations.
"""

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError

from ragstack_common.filter_examples import (
    generate_filter_examples,
    store_filter_examples,
    update_config_with_examples,
)
from ragstack_common.key_library import KeyLibrary
from resolvers.shared import (
    CONFIGURATION_TABLE_NAME,
    DATA_BUCKET,
    METADATA_ANALYZER_FUNCTION_ARN,
    METADATA_KEY_LIBRARY_TABLE,
    REINDEX_STATE_MACHINE_ARN,
    convert_decimals,
    dynamodb,
    get_config_manager,
    lambda_client,
    sfn,
)

logger = logging.getLogger()


def analyze_metadata(args: dict[str, Any]) -> dict[str, Any]:
    """
    Trigger metadata analysis of Knowledge Base vectors.

    Invokes the metadata analyzer Lambda which:
    - Samples vectors from Knowledge Base
    - Analyzes metadata field occurrences
    - Generates filter examples using LLM
    - Stores results in S3 and DynamoDB

    Returns:
        MetadataAnalysisResult with success status and stats
    """
    logger.info("Starting metadata analysis")

    if not METADATA_ANALYZER_FUNCTION_ARN:
        logger.error("METADATA_ANALYZER_FUNCTION_ARN not configured")
        return {
            "success": False,
            "error": "Metadata analyzer not configured",
            "vectorsSampled": 0,
            "keysAnalyzed": 0,
            "examplesGenerated": 0,
            "executionTimeMs": 0,
        }

    try:
        # Invoke metadata analyzer Lambda synchronously
        logger.info(f"Invoking metadata analyzer: {METADATA_ANALYZER_FUNCTION_ARN}")
        response = lambda_client.invoke(
            FunctionName=METADATA_ANALYZER_FUNCTION_ARN,
            InvocationType="RequestResponse",
            Payload=json.dumps({}),
        )

        # Parse response
        payload = json.loads(response["Payload"].read())

        # Check for Lambda execution error
        if response.get("FunctionError"):
            error_msg = payload.get("errorMessage", "Lambda execution failed")
            logger.error(f"Metadata analyzer failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "vectorsSampled": 0,
                "keysAnalyzed": 0,
                "examplesGenerated": 0,
                "executionTimeMs": 0,
            }

        logger.info(f"Metadata analysis complete: {payload}")

        return {
            "success": payload.get("success", False),
            "vectorsSampled": payload.get("vectorsSampled", 0),
            "keysAnalyzed": payload.get("keysAnalyzed", 0),
            "examplesGenerated": payload.get("examplesGenerated", 0),
            "executionTimeMs": payload.get("executionTimeMs", 0),
            "error": payload.get("error"),
        }

    except ClientError as e:
        logger.error(f"Error invoking metadata analyzer: {e}")
        return {
            "success": False,
            "error": f"Failed to invoke metadata analyzer: {e}",
            "vectorsSampled": 0,
            "keysAnalyzed": 0,
            "examplesGenerated": 0,
            "executionTimeMs": 0,
        }
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
        logger.error(f"Unexpected error in analyze_metadata: {e}")
        return {
            "success": False,
            "error": str(e),
            "vectorsSampled": 0,
            "keysAnalyzed": 0,
            "examplesGenerated": 0,
            "executionTimeMs": 0,
        }


def get_metadata_stats(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get metadata key statistics from the key library.

    Returns all keys with their occurrence counts and sample values.

    Returns:
        MetadataStatsResponse with keys array and stats
    """
    logger.info("Getting metadata statistics")

    if not METADATA_KEY_LIBRARY_TABLE:
        logger.warning("METADATA_KEY_LIBRARY_TABLE not configured")
        return {
            "keys": [],
            "totalKeys": 0,
            "lastAnalyzed": None,
            "error": "Metadata key library not configured",
        }

    try:
        table = dynamodb.Table(METADATA_KEY_LIBRARY_TABLE)

        # Scan all keys from the library
        all_items = []
        scan_kwargs: dict[str, Any] = {}

        while True:
            scan_response = table.scan(**scan_kwargs)
            all_items.extend(scan_response.get("Items", []))

            if "LastEvaluatedKey" not in scan_response:
                break
            scan_kwargs["ExclusiveStartKey"] = scan_response["LastEvaluatedKey"]

        # Format keys for GraphQL response
        keys: list[dict[str, Any]] = []
        last_analyzed: str | None = None

        for item in all_items:
            key_analyzed = str(item.get("last_analyzed", "")) or None
            if key_analyzed and (not last_analyzed or key_analyzed > last_analyzed):
                last_analyzed = key_analyzed

            sample_vals = item.get("sample_values", [])
            keys.append(
                {
                    "keyName": str(item.get("key_name", "")),
                    "dataType": str(item.get("data_type", "string")),
                    "occurrenceCount": int(str(item.get("occurrence_count", 0))),
                    "sampleValues": (
                        list(sample_vals)[:10] if isinstance(sample_vals, (list, tuple)) else []
                    ),
                    "lastAnalyzed": key_analyzed,
                    "status": str(item.get("status", "active")),
                }
            )

        # Sort by occurrence count descending
        keys.sort(key=lambda x: x["occurrenceCount"], reverse=True)

        logger.info(f"Retrieved {len(keys)} metadata keys")

        return {
            "keys": keys,
            "totalKeys": len(keys),
            "lastAnalyzed": last_analyzed,
            "error": None,
        }

    except ClientError as e:
        logger.error(f"DynamoDB error getting metadata stats: {e}")
        return {
            "keys": [],
            "totalKeys": 0,
            "lastAnalyzed": None,
            "error": f"Failed to get metadata stats: {e}",
        }
    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Unexpected error in get_metadata_stats: {e}")
        return {
            "keys": [],
            "totalKeys": 0,
            "lastAnalyzed": None,
            "error": str(e),
        }


def get_filter_examples(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get filter examples from configuration.

    Returns generated filter examples for use in the UI filter builder.

    Returns:
        FilterExamplesResponse with examples array
    """
    logger.info("Getting filter examples")

    if not CONFIGURATION_TABLE_NAME:
        logger.warning("CONFIGURATION_TABLE_NAME not configured")
        return {
            "examples": [],
            "totalExamples": 0,
            "lastGenerated": None,
            "error": "Configuration not available",
        }

    try:
        # Get examples from config manager
        config_manager = get_config_manager()
        examples_data = config_manager.get_parameter("metadata_filter_examples", default=[])

        if not examples_data or not isinstance(examples_data, list):
            logger.info("No filter examples found in configuration")
            return {
                "examples": [],
                "totalExamples": 0,
                "lastGenerated": None,
                "error": None,
            }

        # Format examples for GraphQL response
        examples = []
        for ex in examples_data:
            if isinstance(ex, dict) and "name" in ex and "filter" in ex:
                examples.append(
                    {
                        "name": ex.get("name", ""),
                        "description": ex.get("description", ""),
                        "useCase": ex.get("use_case", ""),
                        "filter": json.dumps(convert_decimals(ex.get("filter", {}))),
                    }
                )

        # Get last generated timestamp from config
        last_generated = config_manager.get_parameter(
            "metadata_filter_examples_updated_at", default=None
        )

        logger.info(f"Retrieved {len(examples)} filter examples")

        return {
            "examples": examples,
            "totalExamples": len(examples),
            "lastGenerated": last_generated,
            "error": None,
        }

    except (ClientError, ValueError, KeyError, json.JSONDecodeError) as e:
        logger.error(f"Error getting filter examples: {e}")
        return {
            "examples": [],
            "totalExamples": 0,
            "lastGenerated": None,
            "error": str(e),
        }


def get_key_library(args: dict[str, Any]) -> Any:
    """
    Get active metadata keys from the key library.

    Returns list of keys for use in manual mode key selection.

    Returns:
        List of MetadataKey objects with key names and metadata
    """
    logger.info("Getting key library")

    if not METADATA_KEY_LIBRARY_TABLE:
        logger.warning("METADATA_KEY_LIBRARY_TABLE not configured")
        return []

    try:
        table = dynamodb.Table(METADATA_KEY_LIBRARY_TABLE)

        # Scan all keys from the library
        all_items: list[dict[str, Any]] = []
        scan_kwargs: dict[str, Any] = {}

        while True:
            scan_response = table.scan(**scan_kwargs)
            all_items.extend(scan_response.get("Items", []))

            if "LastEvaluatedKey" not in scan_response:
                break
            scan_kwargs["ExclusiveStartKey"] = scan_response["LastEvaluatedKey"]

        # Filter to only active keys and format for GraphQL
        keys: list[dict[str, Any]] = []
        for item in all_items:
            status = str(item.get("status", "active"))
            if status != "active":
                continue

            sample_vals = item.get("sample_values", [])
            keys.append(
                {
                    "keyName": str(item.get("key_name", "")),
                    "dataType": str(item.get("data_type", "string")),
                    "occurrenceCount": int(item.get("occurrence_count", 0)),
                    "sampleValues": list(sample_vals)[:5] if sample_vals else [],
                    "status": status,
                }
            )

        # Sort by occurrence count descending
        keys.sort(key=lambda x: int(x["occurrenceCount"]), reverse=True)

        logger.info(f"Retrieved {len(keys)} active keys from library")
        return keys

    except ClientError as e:
        logger.error(f"DynamoDB error getting key library: {e}")
        return []
    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Unexpected error in get_key_library: {e}")
        return []


def check_key_similarity(args: dict[str, Any]) -> dict[str, Any]:
    """
    Check if a proposed key is similar to existing keys.

    Helps prevent duplicate or inconsistent key names by suggesting
    existing keys that are similar to what the user is proposing.

    Args:
        args: Dictionary containing:
            - keyName: The proposed key name to check
            - threshold: Optional similarity threshold (0-1, default 0.8)

    Returns:
        KeySimilarityResult with proposedKey, similarKeys, and hasSimilar
    """
    key_name = args.get("keyName", "")
    threshold = args.get("threshold", 0.8)

    logger.info(f"Checking similarity for key: {key_name}")

    if not key_name:
        raise ValueError("keyName is required")

    # Validate threshold
    if threshold < 0 or threshold > 1:
        raise ValueError("threshold must be between 0 and 1")

    if not METADATA_KEY_LIBRARY_TABLE:
        logger.warning("METADATA_KEY_LIBRARY_TABLE not configured")
        return {
            "proposedKey": key_name,
            "similarKeys": [],
            "hasSimilar": False,
        }

    try:
        key_library = KeyLibrary(table_name=METADATA_KEY_LIBRARY_TABLE)
        similar_keys = key_library.check_key_similarity(key_name, threshold=threshold)

        logger.info(f"Found {len(similar_keys)} similar keys for '{key_name}'")

        return {
            "proposedKey": key_name,
            "similarKeys": similar_keys,
            "hasSimilar": len(similar_keys) > 0,
        }

    except ClientError as e:
        logger.error(f"DynamoDB error checking key similarity: {e}")
        return {
            "proposedKey": key_name,
            "similarKeys": [],
            "hasSimilar": False,
        }
    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Unexpected error in check_key_similarity: {e}")
        return {
            "proposedKey": key_name,
            "similarKeys": [],
            "hasSimilar": False,
        }


def regenerate_filter_examples(args: dict[str, Any]) -> dict[str, Any]:
    """
    Regenerate filter examples using only the configured filter keys.

    Reads metadata_filter_keys from config and generates new examples
    using only those keys. Replaces all existing examples.

    Returns:
        FilterExamplesResult with success, examplesGenerated, executionTimeMs, error
    """

    start_time = time.time()

    try:
        config_manager = get_config_manager()

        # Get filter keys from config (empty list if not set)
        filter_keys = config_manager.get_parameter("metadata_filter_keys", default=[])

        if not filter_keys:
            return {
                "success": False,
                "examplesGenerated": 0,
                "executionTimeMs": int((time.time() - start_time) * 1000),
                "error": "No filter keys configured. Add keys to generate examples.",
            }

        # Get key library to fetch key details
        if not METADATA_KEY_LIBRARY_TABLE:
            return {
                "success": False,
                "examplesGenerated": 0,
                "executionTimeMs": int((time.time() - start_time) * 1000),
                "error": "Key library table not configured",
            }

        # Fetch active keys and filter to only allowed ones
        key_library = KeyLibrary(table_name=METADATA_KEY_LIBRARY_TABLE)
        active_keys = key_library.get_active_keys()

        # Normalize filter keys for comparison (skip non-string entries)
        filter_keys_norm = {k.lower().replace(" ", "_") for k in filter_keys if isinstance(k, str)}

        # Filter to only keys in the allowlist
        allowed_keys = [
            k
            for k in active_keys
            if k.get("key_name", "").lower().replace(" ", "_") in filter_keys_norm
        ]

        if not allowed_keys:
            return {
                "success": False,
                "examplesGenerated": 0,
                "executionTimeMs": int((time.time() - start_time) * 1000),
                "error": "None of the configured filter keys are active in the library",
            }

        # Build field analysis format expected by generate_filter_examples
        field_analysis: dict[str, dict[str, Any]] = {}
        for key in allowed_keys:
            field_analysis[str(key.get("key_name", ""))] = {
                "count": key.get("occurrence_count", 0),
                "data_type": key.get("data_type", "string"),
                "sample_values": key.get("sample_values", []),
            }

        # Generate examples using the shared library function
        examples = generate_filter_examples(field_analysis, num_examples=6)

        # Store to S3 if bucket configured
        if DATA_BUCKET and examples:
            store_filter_examples(examples, DATA_BUCKET)

        # Update config with new examples (clears disabled list)
        if examples:
            update_config_with_examples(examples, clear_disabled=True)

        execution_time_ms = int((time.time() - start_time) * 1000)

        logger.info(f"Regenerated {len(examples)} filter examples in {execution_time_ms}ms")

        return {
            "success": True,
            "examplesGenerated": len(examples),
            "executionTimeMs": execution_time_ms,
            "error": None,
        }

    except (ClientError, ValueError, KeyError, TypeError) as e:
        logger.exception(f"Failed to regenerate filter examples: {e}")
        return {
            "success": False,
            "examplesGenerated": 0,
            "executionTimeMs": int((time.time() - start_time) * 1000),
            "error": str(e),
        }


def delete_metadata_key(args: dict[str, Any]) -> dict[str, Any]:
    """Delete a metadata key from the key library and filter allowlist."""
    key_name = args.get("keyName", "")
    if not key_name:
        return {"success": False, "keyName": "", "error": "keyName is required"}

    if not METADATA_KEY_LIBRARY_TABLE:
        return {"success": False, "keyName": key_name, "error": "Key library not configured"}

    try:
        key_library = KeyLibrary(table_name=METADATA_KEY_LIBRARY_TABLE)
        success = key_library.delete_key(key_name)

        # Also remove from filter keys allowlist if present
        try:
            config_manager = get_config_manager()
            if config_manager:
                current_filter_keys = config_manager.get_parameter(
                    "metadata_filter_keys", default=[]
                )
                if current_filter_keys:
                    # Normalize for comparison (skip non-string entries)
                    key_name_norm = key_name.lower().replace(" ", "_")
                    updated_filter_keys = [
                        k
                        for k in current_filter_keys
                        if not isinstance(k, str) or k.lower().replace(" ", "_") != key_name_norm
                    ]
                    # Only update if something was removed
                    if len(updated_filter_keys) != len(current_filter_keys):
                        config_manager.update_custom_config(
                            {"metadata_filter_keys": updated_filter_keys}
                        )
                        logger.info(f"Removed '{key_name}' from filter keys allowlist")
        except (ClientError, ValueError, KeyError) as e:
            # Non-critical - log but don't fail the deletion
            logger.warning(f"Failed to remove key from filter allowlist: {e}")

        return {"success": success, "keyName": key_name, "error": None}
    except (ClientError, ValueError, KeyError, TypeError) as e:
        logger.error(f"Error deleting metadata key '{key_name}': {e}")
        return {"success": False, "keyName": key_name, "error": str(e)}


def start_reindex(args: dict[str, Any]) -> dict[str, Any]:
    """
    Start a Knowledge Base reindex operation.

    Initiates a Step Functions workflow that:
    1. Creates a new Knowledge Base
    2. Re-extracts metadata for all documents
    3. Re-ingests documents into the new KB
    4. Deletes the old KB

    This is an admin-only operation (requires Cognito auth).

    Returns:
        ReindexJob with executionArn, status, and startedAt
    """
    logger.info("Starting KB reindex operation")

    if not REINDEX_STATE_MACHINE_ARN:
        logger.error("REINDEX_STATE_MACHINE_ARN not configured")
        raise ValueError("Reindex feature is not enabled")

    try:
        # Start the Step Functions execution
        import uuid

        short_id = uuid.uuid4().hex[:6]
        execution_name = f"reindex-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{short_id}"

        response = sfn.start_execution(
            stateMachineArn=REINDEX_STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps({"action": "init"}),
        )

        execution_arn = response["executionArn"]
        started_at = response["startDate"].isoformat()

        logger.info(f"Started reindex execution: {execution_arn}")

        return {
            "executionArn": execution_arn,
            "status": "PENDING",
            "startedAt": started_at,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"Failed to start reindex: {error_code} - {error_msg}")

        if error_code == "ExecutionAlreadyExists":
            raise ValueError("A reindex operation is already in progress") from e

        raise ValueError(f"Failed to start reindex: {error_msg}") from e
    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Unexpected error starting reindex: {e}")
        raise ValueError(f"Failed to start reindex: {str(e)}") from e
