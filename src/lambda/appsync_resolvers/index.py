"""
AppSync Lambda resolvers for document, scrape, and image operations.

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
- createImageUploadUrl
- generateCaption
- submitImage
- getImage
- listImages
- deleteImage
"""

import json
import logging
import os
import re
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from ragstack_common.auth import check_public_access
from ragstack_common.config import ConfigurationManager
from ragstack_common.image import ImageStatus, is_supported_image, validate_image_type
from ragstack_common.scraper import ScrapeStatus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sfn = boto3.client("stepfunctions")

# Module-level configuration manager (lazy init for resolvers that need access control)
_config_manager = None


def get_config_manager():
    """Lazy initialization of ConfigurationManager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


TRACKING_TABLE = os.environ["TRACKING_TABLE"]
DATA_BUCKET = os.environ["DATA_BUCKET"]
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")

# Scrape-related environment variables (optional, only available when scraping is enabled)
SCRAPE_JOBS_TABLE = os.environ.get("SCRAPE_JOBS_TABLE")
SCRAPE_URLS_TABLE = os.environ.get("SCRAPE_URLS_TABLE")
SCRAPE_START_FUNCTION_ARN = os.environ.get("SCRAPE_START_FUNCTION_ARN")

# Configuration table (optional, for caption generation)
CONFIGURATION_TABLE_NAME = os.environ.get("CONFIGURATION_TABLE_NAME")

# Initialize Bedrock runtime client for caption generation (use Lambda's region)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION"))

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

        # Filter out images and scraped pages - they're listed via listImages and listScrapeJobs
        # Check both type field and input_s3_uri path for robustness
        scan_kwargs = {
            "Limit": limit,
            "FilterExpression": (
                "(attribute_not_exists(#type) OR "
                "(#type <> :image_type AND #type <> :scraped_type)) "
                "AND (attribute_not_exists(input_s3_uri) OR "
                "NOT contains(input_s3_uri, :images_prefix))"
            ),
            "ExpressionAttributeNames": {"#type": "type"},
            "ExpressionAttributeValues": {
                ":image_type": "image",
                ":scraped_type": "scraped",
                ":images_prefix": "/images/",
            },
        }

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

        # Generate S3 key with input/ prefix for DataBucket
        s3_key = f"input/{document_id}/{filename}"

        # Create presigned POST
        logger.info(f"Generating presigned POST for S3 key: {s3_key}")
        presigned = s3.generate_presigned_post(
            Bucket=DATA_BUCKET,
            Key=s3_key,
            ExpiresIn=3600,  # 1 hour
        )

        # Create tracking record
        logger.info(f"Creating tracking record for document: {document_id}")
        now = datetime.now(UTC).isoformat()
        table = dynamodb.Table(TRACKING_TABLE)
        table.put_item(
            Item={
                "document_id": document_id,
                "filename": filename,
                "input_s3_uri": f"s3://{DATA_BUCKET}/{s3_key}",
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
                ":updated_at": datetime.now(UTC).isoformat(),
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


def generate_presigned_download_url(s3_uri, expiration=3600):
    """Generate presigned URL for S3 object download."""
    if not s3_uri or not s3_uri.startswith("s3://"):
        return None
    try:
        # Parse s3://bucket/key format
        path = s3_uri.replace("s3://", "")
        parts = path.split("/", 1)
        if len(parts) != 2:
            return None
        bucket, key = parts
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration,
        )
    except ClientError as e:
        logger.warning(f"Failed to generate presigned URL for {s3_uri}: {e}")
        return None


def format_document(item):
    """Format DynamoDB item as GraphQL Document type."""
    output_s3_uri = item.get("output_s3_uri")
    status = item.get("status", "uploaded").upper()

    # Generate preview URL for completed documents
    preview_url = None
    if status in ("OCR_COMPLETE", "EMBEDDING_COMPLETE", "INDEXED") and output_s3_uri:
        preview_url = generate_presigned_download_url(output_s3_uri)

    return {
        "documentId": item["document_id"],
        "filename": item.get("filename", ""),
        "inputS3Uri": item.get("input_s3_uri", ""),
        "outputS3Uri": output_s3_uri,
        "status": status,
        "fileType": item.get("file_type"),
        "isTextNative": item.get("is_text_native", False),
        "totalPages": item.get("total_pages", 0),
        "errorMessage": item.get("error_message"),
        "createdAt": item.get("created_at"),
        "updatedAt": item.get("updated_at"),
        "metadata": json.dumps(item.get("metadata", {})),
        "previewUrl": preview_url,
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
            page_items = urls_response.get("Items", [])

            # Generate content URLs directly from document_id
            # Scraped content is stored at: input/{doc_id}/{doc_id}.scraped.md
            def get_content_url(doc_id):
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
                format_scrape_page(p, get_content_url(p.get("document_id"))) for p in page_items
            ]

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
            "createdAt": datetime.now(UTC).isoformat(),
            "updatedAt": datetime.now(UTC).isoformat(),
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
                ":ts": datetime.now(UTC).isoformat(),
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


def format_scrape_page(item, content_url=None):
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
# Image Resolvers
# =========================================================================


def create_image_upload_url(args):
    """
    Create presigned URL for image upload.

    Returns upload URL and image ID for tracking.
    The image is stored at images/{imageId}/{filename}.

    Args:
        args: Dictionary containing:
            - filename: Image filename (required)
            - autoProcess: If True, process automatically after upload (optional)
            - userCaption: User-provided caption for auto-process (optional)
    """
    try:
        filename = args["filename"]
        auto_process = args.get("autoProcess", False)
        user_caption = args.get("userCaption", "")
        logger.info(f"Creating image upload URL for file: {filename}, autoProcess={auto_process}")

        # Validate filename length
        if not filename or len(filename) > MAX_FILENAME_LENGTH:
            logger.warning(f"Invalid filename length: {len(filename) if filename else 0}")
            raise ValueError(f"Filename must be between 1 and {MAX_FILENAME_LENGTH} characters")

        # Check for path traversal and invalid characters
        if "/" in filename or "\\" in filename or ".." in filename:
            logger.warning(f"Filename contains invalid path characters: {filename}")
            raise ValueError("Filename contains invalid path characters")

        # Validate it's a supported image type
        if not is_supported_image(filename):
            logger.warning(f"Unsupported image type: {filename}")
            is_valid, error_msg = validate_image_type(None, filename)
            if not is_valid:
                raise ValueError(error_msg)
            # Fallback error if is_supported_image fails but validate_image_type passes
            raise ValueError("Unsupported image file type")

        image_id = str(uuid4())
        logger.info(f"Generated image ID: {image_id}")

        # Generate S3 key with images/ prefix
        s3_key = f"images/{image_id}/{filename}"

        # Build presigned POST conditions and fields
        # Include metadata for auto-processing if requested
        conditions = []
        fields = {}

        if auto_process:
            # Add metadata fields that will be stored with the S3 object
            fields["x-amz-meta-auto-process"] = "true"
            conditions.append({"x-amz-meta-auto-process": "true"})

            if user_caption:
                fields["x-amz-meta-caption"] = user_caption
                conditions.append({"x-amz-meta-caption": user_caption})

        # Create presigned POST with conditions
        logger.info(f"Generating presigned POST for S3 key: {s3_key}, autoProcess={auto_process}")
        presigned = s3.generate_presigned_post(
            Bucket=DATA_BUCKET,
            Key=s3_key,
            Fields=fields if fields else None,
            Conditions=conditions if conditions else None,
            ExpiresIn=3600,  # 1 hour
        )

        # Create tracking record with type="image"
        logger.info(f"Creating tracking record for image: {image_id}")
        now = datetime.now(UTC).isoformat()
        table = dynamodb.Table(TRACKING_TABLE)
        item = {
            "document_id": image_id,  # Using document_id field for consistency
            "filename": filename,
            "input_s3_uri": f"s3://{DATA_BUCKET}/{s3_key}",
            "status": ImageStatus.PENDING.value,
            "type": "image",  # Differentiate from documents
            "created_at": now,
            "updated_at": now,
        }

        # Store auto-process settings for Lambda to read
        if auto_process:
            item["auto_process"] = True
            if user_caption:
                item["user_caption"] = user_caption

        table.put_item(Item=item)

        s3_uri = f"s3://{DATA_BUCKET}/{s3_key}"
        logger.info(f"Image upload URL created successfully for image: {image_id}")
        return {
            "uploadUrl": presigned["url"],
            "imageId": image_id,
            "s3Uri": s3_uri,
            "fields": json.dumps(presigned["fields"]),
        }

    except ClientError as e:
        logger.error(f"AWS service error in create_image_upload_url: {e}")
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_image_upload_url: {e}")
        raise


def generate_caption(args):
    """
    Generate an AI caption for an image using Bedrock Converse API with vision.

    Args:
        args: Dictionary containing:
            - imageS3Uri: S3 URI of the image to caption (s3://bucket/key)

    Returns:
        CaptionResult with caption or error field
    """
    image_s3_uri = args.get("imageS3Uri", "")
    logger.info(f"Generating caption for image: {image_s3_uri[:50]}...")

    try:
        # Validate S3 URI format
        if not image_s3_uri or not image_s3_uri.startswith("s3://"):
            return {"caption": None, "error": "Invalid S3 URI format. Must start with s3://"}

        # Parse S3 URI
        uri_path = image_s3_uri.replace("s3://", "")
        parts = uri_path.split("/", 1)
        if len(parts) != 2 or not parts[1]:
            return {"caption": None, "error": "Invalid S3 URI format. Must be s3://bucket/key"}

        bucket = parts[0]
        key = parts[1]

        # Validate bucket matches DATA_BUCKET for security
        if bucket != DATA_BUCKET:
            logger.warning(f"Attempted caption for unauthorized bucket: {bucket}")
            return {"caption": None, "error": "Image must be in the configured data bucket"}

        # Get image from S3
        logger.info(f"Retrieving image from S3: bucket={bucket}, key={key}")
        try:
            response = s3.get_object(Bucket=bucket, Key=key)
            image_bytes = response["Body"].read()
            content_type = response.get("ContentType", "image/jpeg")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                return {"caption": None, "error": "Image not found in S3"}
            if error_code == "AccessDenied":
                return {"caption": None, "error": "Access denied to image in S3"}
            logger.error(f"S3 error retrieving image: {e}")
            return {"caption": None, "error": f"Failed to retrieve image: {error_code}"}

        # Get configured chat model from ConfigurationManager
        if CONFIGURATION_TABLE_NAME:
            try:
                config_manager = ConfigurationManager(CONFIGURATION_TABLE_NAME)
                chat_model_id = config_manager.get_parameter(
                    "chat_primary_model", default="anthropic.claude-haiku-4-5-20251001-v1:0"
                )
            except Exception as e:
                logger.warning(f"Failed to get config, using default model: {e}")
                chat_model_id = "anthropic.claude-haiku-4-5-20251001-v1:0"
        else:
            chat_model_id = "anthropic.claude-haiku-4-5-20251001-v1:0"

        logger.info(f"Using model for caption: {chat_model_id}")

        # Determine image media type for Converse API
        media_type_mapping = {
            "image/png": "png",
            "image/jpeg": "jpeg",
            "image/gif": "gif",
            "image/webp": "webp",
        }
        media_type = media_type_mapping.get(content_type)
        if not media_type:
            # Try to infer from file extension
            ext = key.lower().split(".")[-1] if "." in key else ""
            ext_to_media = {
                "png": "png",
                "jpg": "jpeg",
                "jpeg": "jpeg",
                "gif": "gif",
                "webp": "webp",
            }
            media_type = ext_to_media.get(ext, "jpeg")

        # Build Converse API request with image
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": media_type,
                            "source": {"bytes": image_bytes},
                        }
                    },
                    {
                        "text": "Generate a descriptive caption for this image. "
                        "The caption should be concise (1-2 sentences) and describe "
                        "the main subject, context, and any notable details. "
                        "This caption will be used for searching and retrieving the image."
                    },
                ],
            }
        ]

        system_prompt = (
            "You are an image captioning assistant. Generate concise, descriptive captions "
            "that are suitable for use as search keywords. Focus on the main subject, "
            "setting, and any notable visual elements. Keep captions under 200 characters."
        )

        # Call Bedrock Converse API
        logger.info("Calling Bedrock Converse API for caption generation")
        try:
            converse_response = bedrock_runtime.converse(
                modelId=chat_model_id,
                messages=messages,
                system=[{"text": system_prompt}],
                inferenceConfig={
                    "maxTokens": 500,
                    "temperature": 0.3,  # Lower temperature for more consistent captions
                },
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_msg = e.response.get("Error", {}).get("Message", "")
            logger.error(f"Bedrock error: {error_code} - {error_msg}")
            return {"caption": None, "error": f"Failed to generate caption: {error_msg}"}

        # Extract caption from response
        output = converse_response.get("output", {})
        output_message = output.get("message", {})
        content_blocks = output_message.get("content", [])

        caption = ""
        for block in content_blocks:
            if isinstance(block, dict) and "text" in block:
                caption += block["text"]

        caption = caption.strip()
        if not caption:
            return {"caption": None, "error": "Model returned empty caption"}

        logger.info(f"Generated caption: {caption[:100]}...")
        return {"caption": caption, "error": None}

    except Exception as e:
        logger.error(f"Unexpected error in generate_caption: {e}", exc_info=True)
        return {"caption": None, "error": "Failed to generate caption. Please try again."}


def submit_image(args):
    """
    Submit an image with caption to finalize upload and trigger processing.

    Args:
        args: Dictionary containing:
            - input: SubmitImageInput with imageId, caption, userCaption, aiCaption

    Returns:
        Image object with updated status
    """
    input_data = args.get("input", {})
    image_id = input_data.get("imageId")
    caption = input_data.get("caption")
    user_caption = input_data.get("userCaption")
    ai_caption = input_data.get("aiCaption")

    logger.info(f"Submitting image: {image_id}")

    try:
        # Validate imageId
        if not image_id:
            raise ValueError("imageId is required")

        if not is_valid_uuid(image_id):
            raise ValueError("Invalid imageId format")

        # Check if tracking record exists
        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={"document_id": image_id})
        item = response.get("Item")

        if not item:
            raise ValueError("Image not found")

        # Verify it's an image type
        if item.get("type") != "image":
            raise ValueError("Record is not an image")

        # Verify status is PENDING
        if item.get("status") != ImageStatus.PENDING.value:
            raise ValueError(f"Image is not in PENDING status (current: {item.get('status')})")

        # Get S3 URI and verify image exists in S3
        input_s3_uri = item.get("input_s3_uri", "")
        if not input_s3_uri.startswith("s3://"):
            raise ValueError("Invalid S3 URI in tracking record")

        # Parse S3 URI
        uri_path = input_s3_uri.replace("s3://", "")
        parts = uri_path.split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""

        # Verify image exists in S3
        try:
            head_response = s3.head_object(Bucket=bucket, Key=key)
            content_type = head_response.get("ContentType", "image/jpeg")
            file_size = head_response.get("ContentLength", 0)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404"):
                msg = "Image file not found in S3. Please upload the image first."
                raise ValueError(msg) from e
            logger.error(f"S3 error checking image: {e}")
            raise ValueError(f"Failed to verify image in S3: {error_code}") from e

        # Build combined caption (user first, AI appends)
        combined_caption = ""
        if user_caption and ai_caption:
            combined_caption = f"{user_caption}. {ai_caption}"
        elif user_caption:
            combined_caption = user_caption
        elif ai_caption:
            combined_caption = ai_caption
        elif caption:
            combined_caption = caption

        # Write metadata.json to S3
        metadata = {
            "caption": combined_caption,
            "userCaption": user_caption,
            "aiCaption": ai_caption,
            "filename": item.get("filename", ""),
            "contentType": content_type,
            "fileSize": file_size,
            "createdAt": item.get("created_at", datetime.now(UTC).isoformat()),
        }

        # Derive metadata key from image key
        # Image key: images/{imageId}/{filename}
        # Metadata key: images/{imageId}/metadata.json
        key_parts = key.rsplit("/", 1)
        base_path = key_parts[0] if len(key_parts) > 1 else key
        metadata_key = f"{base_path}/metadata.json"

        logger.info(f"Writing metadata to: s3://{bucket}/{metadata_key}")
        s3.put_object(
            Bucket=bucket,
            Key=metadata_key,
            Body=json.dumps(metadata),
            ContentType="application/json",
        )

        # Update tracking record
        now = datetime.now(UTC).isoformat()
        table.update_item(
            Key={"document_id": image_id},
            UpdateExpression=(
                "SET #status = :status, caption = :caption, user_caption = :user_caption, "
                "ai_caption = :ai_caption, content_type = :content_type, file_size = :file_size, "
                "updated_at = :updated_at"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": ImageStatus.PROCESSING.value,
                ":caption": combined_caption,
                ":user_caption": user_caption,
                ":ai_caption": ai_caption,
                ":content_type": content_type,
                ":file_size": file_size,
                ":updated_at": now,
            },
        )

        # Get updated item
        response = table.get_item(Key={"document_id": image_id})
        updated_item = response.get("Item")

        logger.info(f"Image submitted successfully: {image_id}")
        return format_image(updated_item)

    except ValueError:
        raise
    except ClientError as e:
        logger.error(f"AWS service error in submit_image: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in submit_image: {e}", exc_info=True)
        raise


def format_image(item):
    """Format DynamoDB item as GraphQL Image type."""
    if not item:
        return None

    input_s3_uri = item.get("input_s3_uri", "")
    status = item.get("status", ImageStatus.PENDING.value)

    # Generate thumbnail URL for images
    thumbnail_url = None
    if input_s3_uri and input_s3_uri.startswith("s3://"):
        thumbnail_url = generate_presigned_download_url(input_s3_uri)

    return {
        "imageId": item.get("document_id"),
        "filename": item.get("filename", ""),
        "caption": item.get("caption"),
        "userCaption": item.get("user_caption"),
        "aiCaption": item.get("ai_caption"),
        "status": status,
        "s3Uri": input_s3_uri,
        "thumbnailUrl": thumbnail_url,
        "contentType": item.get("content_type"),
        "fileSize": item.get("file_size"),
        "errorMessage": item.get("error_message"),
        "createdAt": item.get("created_at"),
        "updatedAt": item.get("updated_at"),
    }


def get_image(args):
    """
    Get image by ID.

    Args:
        args: Dictionary containing:
            - imageId: Image ID to retrieve

    Returns:
        Image object or None if not found
    """
    image_id = args.get("imageId")
    logger.info(f"Getting image: {image_id}")

    try:
        if not image_id:
            raise ValueError("imageId is required")

        if not is_valid_uuid(image_id):
            raise ValueError("Invalid imageId format")

        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={"document_id": image_id})

        item = response.get("Item")
        if not item:
            logger.info(f"Image not found: {image_id}")
            return None

        # Verify it's an image type
        if item.get("type") != "image":
            logger.info(f"Record is not an image: {image_id}")
            return None

        return format_image(item)

    except ClientError as e:
        logger.error(f"DynamoDB error in get_image: {e}")
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_image: {e}")
        raise


def list_images(args):
    """
    List all images with pagination.

    Args:
        args: Dictionary containing:
            - limit: Max items to return (default 50)
            - nextToken: Pagination token

    Returns:
        ImageConnection with items and nextToken
    """
    limit = args.get("limit", 50)
    next_token = args.get("nextToken")

    logger.info(f"Listing images with limit: {limit}")

    try:
        # Validate limit
        if limit < 1 or limit > MAX_DOCUMENTS_LIMIT:
            raise ValueError(f"Limit must be between 1 and {MAX_DOCUMENTS_LIMIT}")

        table = dynamodb.Table(TRACKING_TABLE)

        # Scan with filter for type="image" OR input_s3_uri contains /images/
        scan_kwargs = {
            "Limit": limit,
            "FilterExpression": "#type = :image_type OR contains(input_s3_uri, :images_prefix)",
            "ExpressionAttributeNames": {"#type": "type"},
            "ExpressionAttributeValues": {":image_type": "image", ":images_prefix": "/images/"},
        }

        if next_token:
            try:
                scan_kwargs["ExclusiveStartKey"] = json.loads(next_token)
            except json.JSONDecodeError:
                raise ValueError("Invalid pagination token") from None

        response = table.scan(**scan_kwargs)

        items = [format_image(item) for item in response.get("Items", [])]
        logger.info(f"Retrieved {len(items)} images")

        result = {"items": items}
        if "LastEvaluatedKey" in response:
            result["nextToken"] = json.dumps(response["LastEvaluatedKey"])

        return result

    except ClientError as e:
        logger.error(f"DynamoDB error in list_images: {e}")
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in list_images: {e}")
        raise


def delete_image(args):
    """
    Delete an image from S3, DynamoDB, and Knowledge Base.

    Args:
        args: Dictionary containing:
            - imageId: Image ID to delete

    Returns:
        True if deleted successfully
    """
    image_id = args.get("imageId")
    logger.info(f"Deleting image: {image_id}")

    try:
        if not image_id:
            raise ValueError("imageId is required")

        if not is_valid_uuid(image_id):
            raise ValueError("Invalid imageId format")

        table = dynamodb.Table(TRACKING_TABLE)

        # Get image record
        response = table.get_item(Key={"document_id": image_id})
        item = response.get("Item")

        if not item:
            raise ValueError("Image not found")

        # Verify it's an image type
        if item.get("type") != "image":
            raise ValueError("Record is not an image")

        input_s3_uri = item.get("input_s3_uri", "")

        # Delete files from S3
        if input_s3_uri and input_s3_uri.startswith("s3://"):
            uri_path = input_s3_uri.replace("s3://", "")
            parts = uri_path.split("/", 1)
            if len(parts) == 2:
                bucket = parts[0]
                image_key = parts[1]

                # Delete image file
                try:
                    s3.delete_object(Bucket=bucket, Key=image_key)
                    logger.info(f"Deleted image from S3: {image_key}")
                except ClientError as e:
                    logger.warning(f"Failed to delete image from S3: {e}")

                # Delete metadata.json
                key_parts = image_key.rsplit("/", 1)
                if len(key_parts) > 1:
                    metadata_key = f"{key_parts[0]}/metadata.json"
                    try:
                        s3.delete_object(Bucket=bucket, Key=metadata_key)
                        logger.info(f"Deleted metadata from S3: {metadata_key}")
                    except ClientError as e:
                        logger.warning(f"Failed to delete metadata from S3: {e}")

                    # Delete content.txt (KB ingestion file)
                    content_key = f"{key_parts[0]}/content.txt"
                    try:
                        s3.delete_object(Bucket=bucket, Key=content_key)
                        logger.info(f"Deleted content from S3: {content_key}")
                    except ClientError as e:
                        logger.warning(f"Failed to delete content from S3: {e}")

        # Delete from DynamoDB
        table.delete_item(Key={"document_id": image_id})
        logger.info(f"Deleted image from DynamoDB: {image_id}")

        # Note: KB vectors will be cleaned up on next data source sync
        # or we could call bedrock_agent.delete_knowledge_base_documents here

        return True

    except ClientError as e:
        logger.error(f"AWS service error in delete_image: {e}")
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete_image: {e}")
        raise


def create_zip_upload_url(args):
    """
    Create presigned URL for ZIP archive upload.

    Returns upload URL and upload ID for tracking batch image uploads.
    The ZIP is stored at uploads/{uploadId}/archive.zip.

    Args:
        args: Dictionary containing:
            - generateCaptions: Boolean flag to generate AI captions for images

    Returns:
        Dictionary with uploadUrl, uploadId, and fields
    """
    try:
        generate_captions = args.get("generateCaptions", False)
        logger.info(f"Creating ZIP upload URL, generateCaptions={generate_captions}")

        upload_id = str(uuid4())
        logger.info(f"Generated upload ID: {upload_id}")

        # Generate S3 key with uploads/ prefix
        s3_key = f"uploads/{upload_id}/archive.zip"

        # Create presigned POST
        logger.info(f"Generating presigned POST for S3 key: {s3_key}")
        presigned = s3.generate_presigned_post(
            Bucket=DATA_BUCKET,
            Key=s3_key,
            ExpiresIn=3600,  # 1 hour
        )

        # Create upload tracking record
        logger.info(f"Creating upload tracking record: {upload_id}")
        now = datetime.now(UTC).isoformat()
        table = dynamodb.Table(TRACKING_TABLE)
        table.put_item(
            Item={
                "document_id": upload_id,
                "type": "zip_upload",
                "status": "PENDING",
                "generate_captions": generate_captions,
                "input_s3_uri": f"s3://{DATA_BUCKET}/{s3_key}",
                "created_at": now,
                "updated_at": now,
            }
        )

        return {
            "uploadUrl": presigned["url"],
            "uploadId": upload_id,
            "fields": json.dumps(presigned["fields"]),
        }

    except ClientError as e:
        logger.error(f"AWS service error in create_zip_upload_url: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_zip_upload_url: {e}")
        raise
