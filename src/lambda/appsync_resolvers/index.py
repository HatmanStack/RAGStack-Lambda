"""
AppSync Lambda resolvers for document and scrape operations.

Handles:
- getDocument
- listDocuments
- createUploadUrl
- processDocument
- getScrapeJob
- listScrapeJobs
- checkScrapeUrl
- startScrape
- cancelScrape
"""

import json
import logging
import os
import re
from datetime import datetime
from urllib.parse import urlparse
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from ragstack_common.scraper import ScrapeStatus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sfn = boto3.client("stepfunctions")

TRACKING_TABLE = os.environ["TRACKING_TABLE"]
INPUT_BUCKET = os.environ["INPUT_BUCKET"]
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")

# Scrape-related environment variables (optional, only available when scraping is enabled)
SCRAPE_JOBS_TABLE = os.environ.get("SCRAPE_JOBS_TABLE")
SCRAPE_URLS_TABLE = os.environ.get("SCRAPE_URLS_TABLE")
SCRAPE_START_FUNCTION_ARN = os.environ.get("SCRAPE_START_FUNCTION_ARN")

# Validation constants
MAX_FILENAME_LENGTH = 255
MAX_DOCUMENTS_LIMIT = 100
FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9._\-\s()]+$")


def lambda_handler(event, context):
    """
    Route to appropriate resolver based on field name.
    """
    logger.info(f"AppSync resolver invoked for field: {event['info']['fieldName']}")
    logger.info(f"Arguments: {json.dumps(event.get('arguments', {}))}")

    field_name = event["info"]["fieldName"]

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


def get_document(args):
    """Get document by ID."""
    try:
        document_id = args["documentId"]
        logger.info(f"Fetching document: {document_id}")

        # Validate document ID format (UUID)
        if not is_valid_uuid(document_id):
            logger.warning(f"Invalid document ID format: {document_id}")
            raise ValueError("Invalid document ID format")

        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={"document_id": document_id})

        item = response.get("Item")
        if not item:
            logger.info(f"Document not found: {document_id}")
            return None

        logger.info(f"Document found: {document_id}, status: {item.get('status')}")
        return format_document(item)

    except ClientError as e:
        logger.error(f"DynamoDB error in get_document: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_document: {e}")
        raise


def list_documents(args):
    """List all documents with pagination."""
    try:
        limit = args.get("limit", 50)
        next_token = args.get("nextToken")

        # Validate limit
        if limit < 1 or limit > MAX_DOCUMENTS_LIMIT:
            logger.warning(f"Invalid limit requested: {limit}")
            raise ValueError(f"Limit must be between 1 and {MAX_DOCUMENTS_LIMIT}")

        logger.info(f"Listing documents with limit: {limit}")

        table = dynamodb.Table(TRACKING_TABLE)

        scan_kwargs = {"Limit": limit}

        if next_token:
            try:
                scan_kwargs["ExclusiveStartKey"] = json.loads(next_token)
                logger.info("Continuing pagination with next token")
            except json.JSONDecodeError:
                logger.warning("Invalid next token provided")
                raise ValueError("Invalid pagination token") from None

        response = table.scan(**scan_kwargs)

        items = [format_document(item) for item in response.get("Items", [])]
        logger.info(f"Retrieved {len(items)} documents")

        result = {"items": items}

        if "LastEvaluatedKey" in response:
            result["nextToken"] = json.dumps(response["LastEvaluatedKey"])
            logger.info("More results available")

        return result

    except ClientError as e:
        logger.error(f"DynamoDB error in list_documents: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in list_documents: {e}")
        raise


def create_upload_url(args):
    """
    Create presigned URL for S3 upload.

    Returns upload URL and document ID for tracking.
    """
    try:
        filename = args["filename"]
        logger.info(f"Creating upload URL for file: {filename}")

        # Validate filename
        if not filename or len(filename) > MAX_FILENAME_LENGTH:
            logger.warning(f"Invalid filename length: {len(filename) if filename else 0}")
            raise ValueError(f"Filename must be between 1 and {MAX_FILENAME_LENGTH} characters")

        # Check for path traversal and invalid characters
        if "/" in filename or "\\" in filename or ".." in filename:
            logger.warning(f"Filename contains invalid characters: {filename}")
            raise ValueError("Filename contains invalid path characters")

        # Ensure filename has valid characters
        if not FILENAME_PATTERN.match(filename):
            logger.warning(f"Filename contains invalid characters: {filename}")
            raise ValueError(
                "Filename contains invalid characters "
                "(use alphanumeric, dots, dashes, underscores, spaces, parentheses only)"
            )

        document_id = str(uuid4())
        logger.info(f"Generated document ID: {document_id}")

        # Generate S3 key
        s3_key = f"{document_id}/{filename}"

        # Create presigned POST
        logger.info(f"Generating presigned POST for S3 key: {s3_key}")
        presigned = s3.generate_presigned_post(
            Bucket=INPUT_BUCKET,
            Key=s3_key,
            ExpiresIn=3600,  # 1 hour
        )

        # Create tracking record
        logger.info(f"Creating tracking record for document: {document_id}")
        now = datetime.now().isoformat()
        table = dynamodb.Table(TRACKING_TABLE)
        table.put_item(
            Item={
                "document_id": document_id,
                "filename": filename,
                "input_s3_uri": f"s3://{INPUT_BUCKET}/{s3_key}",
                "status": "uploaded",
                "created_at": now,
                "updated_at": now,
            }
        )

        logger.info(f"Upload URL created successfully for document: {document_id}")
        return {
            "uploadUrl": presigned["url"],
            "documentId": document_id,
            "fields": json.dumps(presigned["fields"]),
        }

    except ClientError as e:
        logger.error(f"AWS service error in create_upload_url: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_upload_url: {e}")
        raise


def process_document(args):
    """
    Manually trigger document processing via Step Functions.

    Returns updated document record.
    """
    try:
        document_id = args["documentId"]
        logger.info(f"Manually triggering processing for document: {document_id}")

        # Validate document ID format
        if not is_valid_uuid(document_id):
            logger.warning(f"Invalid document ID format: {document_id}")
            raise ValueError("Invalid document ID format")

        # Check if state machine ARN is configured
        if not STATE_MACHINE_ARN:
            logger.error("STATE_MACHINE_ARN environment variable not set")
            raise ValueError("Processing not configured")

        # Get document from DynamoDB
        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={"document_id": document_id})

        item = response.get("Item")
        if not item:
            logger.warning(f"Document not found: {document_id}")
            raise ValueError("Document not found")

        # Check if document is in a state that can be reprocessed
        current_status = item.get("status", "").lower()
        if current_status == "processing":
            logger.warning(f"Document already processing: {document_id}")
            raise ValueError("Document is already being processed")

        # Update status to processing
        logger.info(f"Updating document status to processing: {document_id}")
        table.update_item(
            Key={"document_id": document_id},
            UpdateExpression="SET #status = :status, updated_at = :updated_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "processing",
                ":updated_at": datetime.now().isoformat(),
            },
        )

        # Start Step Functions execution
        execution_input = {
            "document_id": document_id,
            "input_s3_uri": item.get("input_s3_uri"),
            "filename": item.get("filename"),
        }

        logger.info(f"Starting Step Functions execution for document: {document_id}")
        execution_response = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"{document_id}-{int(datetime.now().timestamp())}",
            input=json.dumps(execution_input),
        )

        logger.info(f"Step Functions execution started: {execution_response['executionArn']}")

        # Get updated document
        response = table.get_item(Key={"document_id": document_id})
        updated_item = response.get("Item")

        return format_document(updated_item)

    except ClientError as e:
        logger.error(f"AWS service error in process_document: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in process_document: {e}")
        raise


def format_document(item):
    """Format DynamoDB item as GraphQL Document type."""
    return {
        "documentId": item["document_id"],
        "filename": item.get("filename", ""),
        "inputS3Uri": item.get("input_s3_uri", ""),
        "outputS3Uri": item.get("output_s3_uri"),
        "status": item.get("status", "uploaded").upper(),
        "fileType": item.get("file_type"),
        "isTextNative": item.get("is_text_native", False),
        "totalPages": item.get("total_pages", 0),
        "errorMessage": item.get("error_message"),
        "createdAt": item.get("created_at"),
        "updatedAt": item.get("updated_at"),
        "metadata": json.dumps(item.get("metadata", {})),
    }


def is_valid_uuid(uuid_string):
    """Validate UUID format."""
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    return bool(uuid_pattern.match(uuid_string))


# =========================================================================
# Scrape Resolvers
# =========================================================================


def _check_scrape_enabled():
    """Check if scraping is enabled (tables configured)."""
    if not SCRAPE_JOBS_TABLE:
        raise ValueError("Scraping is not enabled")


def get_scrape_job(args):
    """Get scrape job by ID with pages."""
    _check_scrape_enabled()

    try:
        job_id = args["jobId"]
        logger.info(f"Fetching scrape job: {job_id}")

        if not is_valid_uuid(job_id):
            raise ValueError("Invalid job ID format")

        jobs_table = dynamodb.Table(SCRAPE_JOBS_TABLE)
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
            pages = [format_scrape_page(p) for p in urls_response.get("Items", [])]

        return {
            "job": format_scrape_job(item),
            "pages": pages,
        }

    except ClientError as e:
        logger.error(f"DynamoDB error in get_scrape_job: {e}")
        raise


def list_scrape_jobs(args):
    """List all scrape jobs with pagination."""
    _check_scrape_enabled()

    try:
        limit = args.get("limit", 50)
        next_token = args.get("nextToken")

        if limit < 1 or limit > MAX_DOCUMENTS_LIMIT:
            raise ValueError(f"Limit must be between 1 and {MAX_DOCUMENTS_LIMIT}")

        logger.info(f"Listing scrape jobs with limit: {limit}")

        table = dynamodb.Table(SCRAPE_JOBS_TABLE)
        scan_kwargs = {"Limit": limit}

        if next_token:
            try:
                scan_kwargs["ExclusiveStartKey"] = json.loads(next_token)
            except json.JSONDecodeError:
                raise ValueError("Invalid pagination token") from None

        response = table.scan(**scan_kwargs)

        items = [format_scrape_job(item) for item in response.get("Items", [])]
        logger.info(f"Retrieved {len(items)} scrape jobs")

        result = {"items": items}
        if "LastEvaluatedKey" in response:
            result["nextToken"] = json.dumps(response["LastEvaluatedKey"])

        return result

    except ClientError as e:
        logger.error(f"DynamoDB error in list_scrape_jobs: {e}")
        raise


def check_scrape_url(args):
    """Check if URL has been scraped before."""
    _check_scrape_enabled()

    try:
        url = args["url"]
        logger.info(f"Checking scrape URL: {url}")

        # Normalize URL to base
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        table = dynamodb.Table(SCRAPE_JOBS_TABLE)

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


def start_scrape(args):
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
        lambda_client = boto3.client("lambda")
        event = {
            "base_url": url,
            "config": {
                "max_pages": input_data.get("maxPages", 1000),
                "max_depth": input_data.get("maxDepth", 3),
                "scope": input_data.get("scope", "subpages").lower(),
                "include_patterns": input_data.get("includePatterns", []),
                "exclude_patterns": input_data.get("excludePatterns", []),
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
            table = dynamodb.Table(SCRAPE_JOBS_TABLE)
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
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
        }

    except ClientError as e:
        logger.error(f"Error in start_scrape: {e}")
        raise


def cancel_scrape(args):
    """Cancel an in-progress scrape job."""
    _check_scrape_enabled()

    try:
        job_id = args["jobId"]
        logger.info(f"Cancelling scrape job: {job_id}")

        if not is_valid_uuid(job_id):
            raise ValueError("Invalid job ID format")

        table = dynamodb.Table(SCRAPE_JOBS_TABLE)

        # Get job
        response = table.get_item(Key={"job_id": job_id})
        item = response.get("Item")

        if not item:
            raise ValueError("Scrape job not found")

        # Check if job can be cancelled
        status = item.get("status", "")
        terminal_statuses = (
            ScrapeStatus.COMPLETED.value,
            ScrapeStatus.COMPLETED_WITH_ERRORS.value,
            ScrapeStatus.FAILED.value,
            ScrapeStatus.CANCELLED.value,
        )
        if status in terminal_statuses:
            raise ValueError(f"Cannot cancel job with status: {status}")

        # Stop Step Functions execution if running
        step_function_arn = item.get("step_function_arn")
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
                ":ts": datetime.now().isoformat(),
            },
        )

        # Return updated job
        response = table.get_item(Key={"job_id": job_id})
        return format_scrape_job(response.get("Item"))

    except ClientError as e:
        logger.error(f"Error in cancel_scrape: {e}")
        raise


def format_scrape_job(item):
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
        "createdAt": item.get("created_at"),
        "updatedAt": item.get("updated_at"),
    }


def format_scrape_page(item):
    """Format DynamoDB item as GraphQL ScrapePage type."""
    return {
        "url": item["url"],
        "title": item.get("title"),
        "status": item.get("status", "pending").upper(),
        "documentId": item.get("document_id"),
        "error": item.get("error"),
        "depth": int(item.get("depth", 0)),
    }
