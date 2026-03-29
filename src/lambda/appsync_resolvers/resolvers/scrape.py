"""Scrape resolver functions for AppSync Lambda handler.

Handles scrape job creation, listing, status checking, cancellation,
and URL management operations.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from botocore.exceptions import ClientError

from ragstack_common.scraper import ScrapeStatus
from ragstack_common.storage import is_valid_uuid
from resolvers.shared import (
    DATA_BUCKET,
    MAX_DOCUMENTS_LIMIT,
    SCRAPE_JOBS_TABLE,
    SCRAPE_START_FUNCTION_ARN,
    SCRAPE_URLS_TABLE,
    dynamodb,
    lambda_client,
    s3,
    sfn,
)

logger = logging.getLogger()


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
            page_items = []
            query_kwargs: dict[str, Any] = {
                "KeyConditionExpression": "job_id = :jid",
                "ExpressionAttributeValues": {":jid": job_id},
            }
            while True:
                urls_response = urls_table.query(**query_kwargs)
                page_items.extend(urls_response.get("Items", []))
                if "LastEvaluatedKey" not in urls_response:
                    break
                query_kwargs["ExclusiveStartKey"] = urls_response["LastEvaluatedKey"]

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
                except ClientError as e:
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

        table = dynamodb.Table(SCRAPE_JOBS_TABLE)
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
    except ValueError:
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
    except (ValueError, json.JSONDecodeError):
        raise


def cancel_scrape(args: dict[str, Any]) -> dict[str, Any]:
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

        # Atomically update status to CANCELLED (only if not already terminal)
        terminal_statuses = (
            ScrapeStatus.COMPLETED.value,
            ScrapeStatus.COMPLETED_WITH_ERRORS.value,
            ScrapeStatus.FAILED.value,
            ScrapeStatus.CANCELLED.value,
        )
        try:
            table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET #status = :status, updated_at = :ts",
                ConditionExpression="NOT #status IN (:s1, :s2, :s3, :s4)",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": ScrapeStatus.CANCELLED.value,
                    ":ts": datetime.now(UTC).isoformat(),
                    ":s1": terminal_statuses[0],
                    ":s2": terminal_statuses[1],
                    ":s3": terminal_statuses[2],
                    ":s4": terminal_statuses[3],
                },
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                current_status = str(item.get("status", "unknown"))
                raise ValueError(f"Cannot cancel job with status: {current_status}") from e
            raise

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
