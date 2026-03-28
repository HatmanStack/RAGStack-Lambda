"""AppSync Lambda resolver dispatcher.

Routes GraphQL field names to domain-specific resolver modules.
Shared state (clients, env vars, helpers) is defined in resolvers/shared.py
and re-exported here for backward compatibility during the resolver split.
"""

import json
import logging
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from ragstack_common.auth import check_public_access
from ragstack_common.config import ConfigurationManager, get_knowledge_base_config
from ragstack_common.demo_mode import (
    DemoModeError,
    check_demo_mode_feature_allowed,
    demo_quota_check_and_increment,
    get_demo_upload_conditions,
    is_demo_mode_enabled,
)
from ragstack_common.filter_examples import (
    generate_filter_examples,
    store_filter_examples,
    update_config_with_examples,
)
from ragstack_common.image import ImageStatus, is_supported_image, validate_image_type
from ragstack_common.ingestion import ingest_documents_with_retry
from ragstack_common.key_library import KeyLibrary
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.scraper import ScrapeStatus
from ragstack_common.storage import is_valid_uuid, parse_s3_uri, read_s3_text, write_metadata_to_s3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sfn = boto3.client("stepfunctions")
lambda_client = boto3.client("lambda")
bedrock_agent = boto3.client("bedrock-agent")

# Module-level configuration manager (lazy init for resolvers that need access control)
_config_manager: ConfigurationManager | None = None

# Module-level event storage for passing identity to resolvers
_current_event: dict[str, Any] | None = None

# DynamoDB client for quota operations
dynamodb_client = boto3.client("dynamodb")


def get_config_manager() -> ConfigurationManager:
    """Lazy initialization of ConfigurationManager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


def get_current_user_id(event: dict[str, Any] | None = None) -> str | None:
    """Get user ID from the event's identity.

    Args:
        event: The AppSync event. Falls back to _current_event if None.
    """
    evt = event if event is not None else _current_event
    if not evt:
        return None
    identity = evt.get("identity") or {}
    return identity.get("sub") or identity.get("username")


def convert_decimals(obj: Any) -> Any:
    """Convert DynamoDB Decimal types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


# Reindex lock key - must match reindex_kb/index.py
REINDEX_LOCK_KEY = "reindex_lock"


def check_reindex_lock() -> None:
    """Check if a full KB reindex is in progress and raise error if so.

    Raises:
        ValueError: If reindex is in progress.
    """
    config_table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
    if not config_table_name:
        return

    try:
        table = dynamodb.Table(config_table_name)
        response = table.get_item(Key={"Configuration": REINDEX_LOCK_KEY})
        lock = response.get("Item")

        if lock and lock.get("is_locked"):
            started_at = str(lock.get("started_at", "unknown"))
            raise ValueError(
                f"Operation blocked: Knowledge Base reindex is in progress "
                f"(started: {started_at}). Please wait for the reindex to complete."
            )
    except ClientError as e:
        logger.warning(f"Error checking reindex lock: {e}")
    except ValueError:
        raise


TRACKING_TABLE = os.environ.get("TRACKING_TABLE")
DATA_BUCKET = os.environ.get("DATA_BUCKET")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID")
DATA_SOURCE_ID = os.environ.get("DATA_SOURCE_ID")

SCRAPE_JOBS_TABLE = os.environ.get("SCRAPE_JOBS_TABLE")
SCRAPE_URLS_TABLE = os.environ.get("SCRAPE_URLS_TABLE")
SCRAPE_START_FUNCTION_ARN = os.environ.get("SCRAPE_START_FUNCTION_ARN")

METADATA_ANALYZER_FUNCTION_ARN = os.environ.get("METADATA_ANALYZER_FUNCTION_ARN")
PROCESS_IMAGE_FUNCTION_ARN = os.environ.get("PROCESS_IMAGE_FUNCTION_ARN")
QUERY_KB_FUNCTION_ARN = os.environ.get("QUERY_KB_FUNCTION_ARN")
CONVERSATION_TABLE_NAME = os.environ.get("CONVERSATION_TABLE_NAME")
METADATA_KEY_LIBRARY_TABLE = os.environ.get("METADATA_KEY_LIBRARY_TABLE")
CONFIGURATION_TABLE_NAME = os.environ.get("CONFIGURATION_TABLE_NAME")
REINDEX_STATE_MACHINE_ARN = os.environ.get("REINDEX_STATE_MACHINE_ARN")
INGEST_TO_KB_FUNCTION_ARN = os.environ.get("INGEST_TO_KB_FUNCTION_ARN")

bedrock_runtime = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION"))

# Validation constants
MAX_FILENAME_LENGTH = 255
MAX_DOCUMENTS_LIMIT = 100
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by stripping control characters.

    S3 keys accept any UTF-8 character, so only ASCII control characters
    are removed. Path traversal is handled separately in the upload resolvers.
    Returns "unnamed" if the result would be empty.
    """
    if not filename:
        return "unnamed"

    sanitized = CONTROL_CHARS_PATTERN.sub("", filename).strip()

    if not sanitized:
        return "unnamed"

    return sanitized


def generate_presigned_download_url(s3_uri: str, expiration: int = 3600) -> str | None:
    """Generate presigned URL for S3 object download."""
    if not s3_uri or not s3_uri.startswith("s3://"):
        return None
    try:
        bucket, key = parse_s3_uri(s3_uri)
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration,
        )
    except ClientError as e:
        logger.warning(f"Failed to generate presigned URL: {e}")
        return None


from resolvers.documents import (  # noqa: E402
    create_upload_url,
    delete_documents,
    format_document,
    get_document,
    list_documents,
    process_document,
    reindex_document,
    reprocess_document,
)
from resolvers.images import (  # noqa: E402
    create_image_upload_url,
    create_zip_upload_url,
    delete_image,
    generate_caption,
    get_image,
    list_images,
    submit_image,
)


def lambda_handler(event: dict[str, Any], context: Any) -> Any:
    """
    Route to appropriate resolver based on field name.
    """
    global _current_event
    _current_event = event  # Store for use by resolvers that need identity

    # Also set event in shared module for domain resolver modules
    try:
        from resolvers.shared import set_current_event

        set_current_event(event)
    except ImportError:
        pass

    # Validate required environment variables
    if not TRACKING_TABLE:
        raise ValueError("TRACKING_TABLE environment variable is required")
    if not DATA_BUCKET:
        raise ValueError("DATA_BUCKET environment variable is required")

    # Clear config cache at handler entry to ensure fresh reads per invocation
    if _config_manager is not None:
        _config_manager.clear_cache()

    field_name_for_log = event["info"]["fieldName"]
    logger.info(f"AppSync resolver invoked for field: {field_name_for_log}")
    # Redact user query content from logs to avoid writing chat prompts to CloudWatch
    log_args = event.get("arguments", {})
    if field_name_for_log == "queryKnowledgeBase" and "query" in log_args:
        log_args = {**log_args, "query": "<REDACTED>"}
    logger.info(f"Arguments: {json.dumps(log_args)}")

    field_name = event["info"]["fieldName"]

    # Demo mode feature restrictions - block certain mutations entirely
    demo_restricted_features = {
        "startReindex": "reindex_all",
        "reprocessDocument": "reprocess",
        "deleteDocuments": "delete_documents",
    }

    if field_name in demo_restricted_features:
        try:
            check_demo_mode_feature_allowed(
                demo_restricted_features[field_name], get_config_manager()
            )
        except DemoModeError as e:
            logger.info(f"Demo mode blocked {field_name}: {e.message}")
            raise ValueError(e.message) from e

    # Check public access for upload-related resolvers
    # Map field names to their required access types
    access_requirements = {
        "createUploadUrl": "upload",
        "createImageUploadUrl": "image_upload",
        "generateCaption": "image_upload",
        "submitImage": "image_upload",
        "createZipUploadUrl": "image_upload",
        "startScrape": "scrape",
        "checkScrapeUrl": "scrape",
        "cancelScrape": "scrape",
        "queryKnowledgeBase": "chat",
        "getConversation": "chat",
    }

    if field_name in access_requirements:
        access_type = access_requirements[field_name]
        allowed, error_msg = check_public_access(event, access_type, get_config_manager())
        if not allowed:
            raise ValueError(error_msg)

    resolvers = {
        "getDocument": get_document,
        "listDocuments": list_documents,
        "createUploadUrl": create_upload_url,
        "processDocument": process_document,
        # Scrape resolvers
        "getScrapeJob": get_scrape_job,
        "listScrapeJobs": list_scrape_jobs,
        "checkScrapeUrl": check_scrape_url,
        "startScrape": start_scrape,
        "cancelScrape": cancel_scrape,
        # Image resolvers
        "createImageUploadUrl": create_image_upload_url,
        "generateCaption": generate_caption,
        "submitImage": submit_image,
        "getImage": get_image,
        "listImages": list_images,
        "deleteImage": delete_image,
        "createZipUploadUrl": create_zip_upload_url,
        # Document management
        "deleteDocuments": delete_documents,
        "reprocessDocument": reprocess_document,
        "reindexDocument": reindex_document,
        # Metadata analysis
        "analyzeMetadata": analyze_metadata,
        "getMetadataStats": get_metadata_stats,
        "getFilterExamples": get_filter_examples,
        "getKeyLibrary": get_key_library,
        "checkKeySimilarity": check_key_similarity,
        "regenerateFilterExamples": regenerate_filter_examples,
        "deleteMetadataKey": delete_metadata_key,
        # KB Reindex
        "startReindex": start_reindex,
        # Async chat
        "queryKnowledgeBase": query_knowledge_base,
        "getConversation": get_conversation,
    }

    resolver = resolvers.get(field_name)
    if not resolver:
        logger.error(f"Unknown field: {field_name}")
        raise ValueError(f"Unknown field: {field_name}")

    try:
        result = resolver(event["arguments"])
        logger.info(f"Resolver {field_name} completed successfully")
        return result
    except ValueError as e:
        logger.exception(f"Validation error in {field_name}: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in {field_name}: {e}")
        raise


# =========================================================================
# Scrape Resolvers
# =========================================================================


def _check_scrape_enabled() -> None:
    """Check if scraping is enabled (tables configured)."""
    if not SCRAPE_JOBS_TABLE:
        raise ValueError("Scraping is not enabled")


def get_scrape_job(args: dict[str, Any]) -> dict[str, Any] | None:
    """Get scrape job by ID with pages."""
    _check_scrape_enabled()

    try:
        job_id = args["jobId"]
        logger.info(f"Fetching scrape job: {job_id}")

        if not is_valid_uuid(job_id):
            raise ValueError("Invalid job ID format")

        jobs_table = dynamodb.Table(SCRAPE_JOBS_TABLE)  # type: ignore[arg-type]
        response = jobs_table.get_item(Key={"job_id": job_id})

        item = response.get("Item")
        if not item:
            logger.info(f"Scrape job not found: {job_id}")
            return None

        # Get pages for this job
        pages = []
        if SCRAPE_URLS_TABLE:
            urls_table = dynamodb.Table(SCRAPE_URLS_TABLE)
            urls_response = urls_table.query(
                KeyConditionExpression="job_id = :jid",
                ExpressionAttributeValues={":jid": job_id},
                Limit=100,
            )
            page_items = urls_response.get("Items", [])

            # Generate content URLs directly from document_id
            # Scraped content is stored at: input/{doc_id}/{doc_id}.scraped.md
            def get_content_url(doc_id: str) -> str | None:
                if not doc_id:
                    return None
                try:
                    s3_key = f"input/{doc_id}/{doc_id}.scraped.md"
                    return s3.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": DATA_BUCKET, "Key": s3_key},
                        ExpiresIn=3600,
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate content URL for {doc_id}: {e}")
                    return None

            pages = [
                format_scrape_page(p, get_content_url(str(p.get("document_id", ""))))
                for p in page_items
            ]

        return {
            "job": format_scrape_job(item),
            "pages": pages,
        }

    except ClientError as e:
        logger.error(f"DynamoDB error in get_scrape_job: {e}")
        raise


def list_scrape_jobs(args: dict[str, Any]) -> dict[str, Any]:
    """List all scrape jobs with pagination."""
    _check_scrape_enabled()

    try:
        limit = args.get("limit", 50)
        next_token = args.get("nextToken")

        if limit < 1 or limit > MAX_DOCUMENTS_LIMIT:
            raise ValueError(f"Limit must be between 1 and {MAX_DOCUMENTS_LIMIT}")

        logger.info(f"Listing scrape jobs with limit: {limit}")

        table = dynamodb.Table(SCRAPE_JOBS_TABLE)  # type: ignore[arg-type]
        scan_kwargs: dict[str, Any] = {"Limit": limit}

        if next_token:
            try:
                scan_kwargs["ExclusiveStartKey"] = json.loads(next_token)
            except json.JSONDecodeError:
                raise ValueError("Invalid pagination token") from None

        response = table.scan(**scan_kwargs)

        items = [format_scrape_job(item) for item in response.get("Items", [])]
        logger.info(f"Retrieved {len(items)} scrape jobs")

        result: dict[str, Any] = {"items": items}
        if "LastEvaluatedKey" in response:
            result["nextToken"] = json.dumps(response["LastEvaluatedKey"])

        return result

    except ClientError as e:
        logger.error(f"DynamoDB error in list_scrape_jobs: {e}")
        raise


def check_scrape_url(args: dict[str, Any]) -> dict[str, Any]:
    """Check if URL has been scraped before."""
    _check_scrape_enabled()

    try:
        url = args["url"]
        logger.info(f"Checking scrape URL: {url}")

        # Normalize URL to base
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        table = dynamodb.Table(SCRAPE_JOBS_TABLE)  # type: ignore[arg-type]

        # Query using BaseUrlIndex GSI
        response = table.query(
            IndexName="BaseUrlIndex",
            KeyConditionExpression="base_url = :url",
            ExpressionAttributeValues={":url": base_url},
            ScanIndexForward=False,  # Most recent first
            Limit=1,
        )

        items = response.get("Items", [])
        if not items:
            return {"exists": False, "lastScrapedAt": None, "jobId": None, "title": None}

        job = items[0]
        return {
            "exists": True,
            "lastScrapedAt": job.get("created_at"),
            "jobId": job.get("job_id"),
            "title": job.get("title"),
        }

    except ClientError as e:
        logger.error(f"DynamoDB error in check_scrape_url: {e}")
        raise


def start_scrape(args: dict[str, Any]) -> dict[str, Any]:
    """Start a new scrape job."""
    _check_scrape_enabled()

    if not SCRAPE_START_FUNCTION_ARN:
        raise ValueError("Scrape start function not configured")

    try:
        input_data = args["input"]
        url = input_data.get("url")

        if not url:
            raise ValueError("URL is required")

        # Validate URL format
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must start with http:// or https://")

        logger.info(f"Starting scrape for URL: {url}")

        # Invoke scrape start Lambda
        event = {
            "base_url": url,
            "config": {
                "max_pages": input_data.get("maxPages", 1000),
                "max_depth": input_data.get("maxDepth", 3),
                "scope": input_data.get("scope", "subpages").lower(),
                "include_patterns": input_data.get("includePatterns", []),
                "exclude_patterns": input_data.get("excludePatterns", []),
                "force_rescrape": input_data.get("forceRescrape", False),
            },
        }

        if input_data.get("cookies"):
            event["config"]["cookies"] = input_data["cookies"]

        response = lambda_client.invoke(
            FunctionName=SCRAPE_START_FUNCTION_ARN,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        payload = json.loads(response["Payload"].read())

        if "errorMessage" in payload:
            raise ValueError(payload["errorMessage"])

        # Fetch the created job
        job_id = payload.get("job_id")
        if job_id:
            table = dynamodb.Table(SCRAPE_JOBS_TABLE)  # type: ignore[arg-type]
            job_response = table.get_item(Key={"job_id": job_id})
            if job_response.get("Item"):
                return format_scrape_job(job_response["Item"])

        # Fallback: return payload data directly
        return {
            "jobId": payload.get("job_id"),
            "baseUrl": payload.get("base_url"),
            "status": payload.get("status", "DISCOVERING").upper(),
            "config": {
                "maxPages": event["config"]["max_pages"],
                "maxDepth": event["config"]["max_depth"],
                "scope": event["config"]["scope"].upper(),
            },
            "totalUrls": 0,
            "processedCount": 0,
            "failedCount": 0,
            "createdAt": datetime.now(UTC).isoformat(),
            "updatedAt": datetime.now(UTC).isoformat(),
        }

    except ClientError as e:
        logger.error(f"Error in start_scrape: {e}")
        raise


def cancel_scrape(args: dict[str, Any]) -> dict[str, Any]:
    """Cancel an in-progress scrape job."""
    _check_scrape_enabled()

    try:
        job_id = args["jobId"]
        logger.info(f"Cancelling scrape job: {job_id}")

        if not is_valid_uuid(job_id):
            raise ValueError("Invalid job ID format")

        table = dynamodb.Table(SCRAPE_JOBS_TABLE)  # type: ignore[arg-type]

        # Get job
        response = table.get_item(Key={"job_id": job_id})
        item = response.get("Item")

        if not item:
            raise ValueError("Scrape job not found")

        # Check if job can be cancelled
        status = str(item.get("status", ""))
        terminal_statuses = (
            ScrapeStatus.COMPLETED.value,
            ScrapeStatus.COMPLETED_WITH_ERRORS.value,
            ScrapeStatus.FAILED.value,
            ScrapeStatus.CANCELLED.value,
        )
        if status in terminal_statuses:
            raise ValueError(f"Cannot cancel job with status: {status}")

        # Stop Step Functions execution if running
        step_function_arn = str(item.get("step_function_arn", ""))
        if step_function_arn:
            try:
                sfn.stop_execution(
                    executionArn=step_function_arn,
                    cause="Cancelled by user",
                )
                logger.info(f"Stopped Step Functions execution: {step_function_arn}")
            except ClientError as e:
                logger.warning(f"Could not stop Step Functions execution: {e}")

        # Update job status
        table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #status = :status, updated_at = :ts",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": ScrapeStatus.CANCELLED.value,
                ":ts": datetime.now(UTC).isoformat(),
            },
        )

        # Return updated job
        response = table.get_item(Key={"job_id": job_id})
        updated_item = response.get("Item")
        if not updated_item:
            raise ValueError(f"Job not found after cancel: {job_id}")
        return format_scrape_job(updated_item)

    except ClientError as e:
        logger.error(f"Error in cancel_scrape: {e}")
        raise


def format_scrape_job(item: dict[str, Any]) -> dict[str, Any]:
    """Format DynamoDB item as GraphQL ScrapeJob type."""
    config = item.get("config", {})
    return {
        "jobId": item["job_id"],
        "baseUrl": item.get("base_url", ""),
        "title": item.get("title"),
        "status": item.get("status", "pending").upper(),
        "config": {
            "maxPages": config.get("max_pages", 1000),
            "maxDepth": config.get("max_depth", 3),
            "scope": config.get("scope", "subpages").upper(),
            "includePatterns": config.get("include_patterns", []),
            "excludePatterns": config.get("exclude_patterns", []),
            "scrapeMode": (
                config.get("scrape_mode", "auto").upper() if config.get("scrape_mode") else None
            ),
            "cookies": json.dumps(config.get("cookies")) if config.get("cookies") else None,
        },
        "totalUrls": int(item.get("total_urls", 0)),
        "processedCount": int(item.get("processed_count", 0)),
        "failedCount": int(item.get("failed_count", 0)),
        "failedUrls": item.get("failed_urls", []),
        "jobMetadata": item.get("job_metadata"),
        "createdAt": item.get("created_at"),
        "updatedAt": item.get("updated_at"),
    }


def format_scrape_page(item: dict[str, Any], content_url: str | None = None) -> dict[str, Any]:
    """Format DynamoDB item as GraphQL ScrapePage type."""
    return {
        "url": item["url"],
        "title": item.get("title"),
        "status": item.get("status", "pending").upper(),
        "documentId": item.get("document_id"),
        "contentUrl": content_url,
        "error": item.get("error"),
        "depth": int(item.get("depth", 0)),
    }


# =========================================================================
# Metadata Analysis Resolvers
# =========================================================================


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
    except Exception as e:
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
    except Exception as e:
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

    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    import time

    start_time = time.time()

    try:
        # Get config manager
        config_manager = get_config_manager()
        if not config_manager:
            return {
                "success": False,
                "examplesGenerated": 0,
                "executionTimeMs": 0,
                "error": "Configuration not available",
            }

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

        # Normalize filter keys for comparison
        filter_keys_norm = {k.lower().replace(" ", "_") for k in filter_keys}

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

    except Exception as e:
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
                    # Normalize for comparison
                    key_name_norm = key_name.lower().replace(" ", "_")
                    updated_filter_keys = [
                        k
                        for k in current_filter_keys
                        if k.lower().replace(" ", "_") != key_name_norm
                    ]
                    # Only update if something was removed
                    if len(updated_filter_keys) != len(current_filter_keys):
                        config_manager.update_custom_config(
                            {"metadata_filter_keys": updated_filter_keys}
                        )
                        logger.info(f"Removed '{key_name}' from filter keys allowlist")
        except Exception as e:
            # Non-critical - log but don't fail the deletion
            logger.warning(f"Failed to remove key from filter allowlist: {e}")

        return {"success": success, "keyName": key_name, "error": None}
    except Exception as e:
        logger.error(f"Error deleting metadata key '{key_name}': {e}")
        return {"success": False, "keyName": key_name, "error": str(e)}


# =========================================================================
# KB Reindex Resolvers
# =========================================================================


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
        execution_name = f"reindex-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

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
    except Exception as e:
        logger.error(f"Unexpected error starting reindex: {e}")
        raise ValueError(f"Failed to start reindex: {str(e)}") from e


# =========================================================================
# Async Chat Resolvers
# =========================================================================


def query_knowledge_base(args: dict[str, Any]) -> dict[str, Any]:
    """
    Async mutation resolver: validate input, write PENDING record, async-invoke QueryKBFunction.

    Args:
        args: GraphQL arguments with query, conversationId, requestId

    Returns:
        ChatRequest dict with conversationId, requestId, status="PENDING"
    """
    from boto3.dynamodb.conditions import Key

    # Validate required arguments
    query = args.get("query", "")
    conversation_id = args.get("conversationId", "")
    request_id = args.get("requestId", "")

    if not query or not query.strip():
        raise ValueError("Missing required argument: query")
    if not conversation_id or not conversation_id.strip():
        raise ValueError("Missing required argument: conversationId")
    if not is_valid_uuid(conversation_id):
        raise ValueError("Invalid conversationId: must be a valid UUID")
    if not request_id or not request_id.strip():
        raise ValueError("Missing required argument: requestId")
    if not is_valid_uuid(request_id):
        raise ValueError("Invalid requestId: must be a valid UUID")
    if len(query) > 10000:
        raise ValueError("Query exceeds maximum length of 10000 characters")

    if not CONVERSATION_TABLE_NAME:
        raise ValueError("CONVERSATION_TABLE_NAME environment variable is not configured")
    conversation_table_name: str = CONVERSATION_TABLE_NAME

    # Extract user identity for scoping conversations
    identity = _current_event.get("identity") if _current_event else None
    user_id = None
    if identity:
        user_id = identity.get("sub") or identity.get("username")

    try:
        # Write PENDING record to ConversationHistoryTable
        table = dynamodb.Table(conversation_table_name)

        # Determine turn number by querying existing turns, then write with
        # a condition to prevent concurrent requests from assigning the same turn.
        # Retry with incremented turn number on conflict.
        response = table.query(
            KeyConditionExpression=Key("conversationId").eq(conversation_id),
            ScanIndexForward=False,
            Limit=1,
            ProjectionExpression="turnNumber",
        )
        existing_items = response.get("Items", [])
        next_turn = int(str(existing_items[0].get("turnNumber", 0))) + 1 if existing_items else 1

        ttl = int(datetime.now(UTC).timestamp()) + (14 * 86400)  # 14 day TTL

        max_retries = 3
        for attempt in range(max_retries):
            try:
                item: dict[str, Any] = {
                    "conversationId": conversation_id,
                    "turnNumber": next_turn + attempt,
                    "requestId": request_id,
                    "status": "PENDING",
                    "userMessage": query,
                    "assistantResponse": "",
                    "sources": "[]",
                    "createdAt": datetime.now(UTC).isoformat(),
                    "ttl": ttl,
                }
                if user_id:
                    item["userId"] = user_id
                table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(turnNumber)",
                )
                next_turn = next_turn + attempt
                break
            except ClientError as ce:
                is_conflict = ce.response["Error"]["Code"] == "ConditionalCheckFailedException"
                if is_conflict and attempt < max_retries - 1:
                    continue
                raise

        # Async-invoke QueryKBFunction
        invoke_event = {
            "arguments": {
                "query": query,
                "conversationId": conversation_id,
            },
            "requestId": request_id,
            "turnNumber": next_turn,
            "identity": identity,
            "asyncInvocation": True,
        }
        try:
            lambda_client.invoke(
                FunctionName=QUERY_KB_FUNCTION_ARN,
                InvocationType="Event",
                Payload=json.dumps(invoke_event).encode(),
            )
        except Exception as invoke_err:
            # Clean up orphaned PENDING record if async invoke fails
            try:
                table.delete_item(
                    Key={
                        "conversationId": conversation_id,
                        "turnNumber": next_turn,
                    }
                )
            except ClientError:
                logger.warning(
                    f"Failed to clean up PENDING turn {next_turn} "
                    f"for conversation {conversation_id}"
                )
            logger.error(f"Async invoke failed: {invoke_err}")
            raise ValueError("Failed to submit chat query. Please try again.") from invoke_err

        return {
            "conversationId": conversation_id,
            "requestId": request_id,
            "status": "PENDING",
        }

    except ClientError as e:
        logger.error(f"Failed to process queryKnowledgeBase mutation: {e}")
        raise ValueError("Failed to submit chat query. Please try again.") from e


def get_conversation(args: dict[str, Any]) -> dict[str, Any]:
    """
    Query resolver: read all turns for a conversationId from ConversationHistoryTable.
    Scoped to the requesting user when authenticated.

    Args:
        args: GraphQL arguments with conversationId

    Returns:
        Conversation dict with conversationId and turns array
    """
    from boto3.dynamodb.conditions import Key

    conversation_id = args.get("conversationId", "")
    if not conversation_id or not conversation_id.strip():
        raise ValueError("Missing required argument: conversationId")
    if not is_valid_uuid(conversation_id):
        raise ValueError("Invalid conversationId: must be a valid UUID")

    if not CONVERSATION_TABLE_NAME:
        raise ValueError("CONVERSATION_TABLE_NAME environment variable is not configured")
    conv_table_name: str = CONVERSATION_TABLE_NAME

    # Extract requesting user for ownership check
    identity = _current_event.get("identity") if _current_event else None
    requesting_user_id = None
    if identity:
        requesting_user_id = identity.get("sub") or identity.get("username")

    table = dynamodb.Table(conv_table_name)

    # Paginate to handle conversations exceeding DynamoDB's 1 MB page limit
    all_items: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any] = {
        "KeyConditionExpression": Key("conversationId").eq(conversation_id),
        "ScanIndexForward": True,
    }
    while True:
        response = table.query(**query_kwargs)
        all_items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    turns = []
    for item in all_items:
        # Verify ownership: if the turn has a userId, deny access to
        # unauthenticated callers or callers whose id doesn't match
        item_user_id = item.get("userId")
        if item_user_id and (not requesting_user_id or str(item_user_id) != requesting_user_id):
            return {"conversationId": conversation_id, "turns": []}

        turn: dict[str, Any] = {
            "turnNumber": int(str(item.get("turnNumber", 0))),
            "requestId": item.get("requestId"),
            "status": str(item.get("status", "COMPLETED")),
            "userMessage": str(item.get("userMessage", "")),
            "assistantResponse": item.get("assistantResponse"),
            "sources": None,
            "error": item.get("errorMessage"),
            "createdAt": str(item.get("createdAt", "")),
        }
        # Parse sources from JSON string to list
        sources_raw = item.get("sources", "[]")
        sources_json = str(sources_raw) if sources_raw is not None else "[]"
        if sources_json and sources_json != "[]":
            try:
                turn["sources"] = json.loads(sources_json)
            except (json.JSONDecodeError, TypeError):
                turn["sources"] = []
        else:
            turn["sources"] = []
        turns.append(turn)

    return {
        "conversationId": conversation_id,
        "turns": turns,
    }
