"""
Scrape Status Lambda

Returns the current status of a scrape job for Step Functions polling
and API Gateway requests.

Input event (from Step Functions):
{
    "job_id": "uuid"
}

Input event (from API Gateway):
{
    "httpMethod": "GET",
    "pathParameters": {"job_id": "uuid"},
    "queryStringParameters": {"limit": "20", "next_token": "..."}
}

Output (Step Functions):
{
    "job_id": "uuid",
    "status": "processing",
    "total_urls": 50,
    "processed_count": 25,
    "failed_count": 2,
    "discovery_complete": true,
    "processing_complete": false,
    "failure_threshold_exceeded": false
}
"""

import json
import logging
import os
from datetime import UTC, datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from ragstack_common.scraper import ScrapeStatus

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Failure threshold: abort if more than 10% of pages fail
FAILURE_THRESHOLD = 0.1


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


def lambda_handler(event, context):
    """
    Main Lambda handler - routes to appropriate handler based on event type.
    """
    # Get environment variables
    jobs_table = os.environ.get("SCRAPE_JOBS_TABLE")
    urls_table = os.environ.get("SCRAPE_URLS_TABLE")
    discovery_queue_url = os.environ.get("SCRAPE_DISCOVERY_QUEUE_URL")
    processing_queue_url = os.environ.get("SCRAPE_PROCESSING_QUEUE_URL")

    if not jobs_table:
        raise ValueError("SCRAPE_JOBS_TABLE environment variable required")

    dynamodb = boto3.resource("dynamodb")
    jobs_tbl = dynamodb.Table(jobs_table)
    urls_tbl = dynamodb.Table(urls_table) if urls_table else None

    # Determine event type (API Gateway or Step Functions)
    if "httpMethod" in event:
        return _handle_api_request(event, jobs_tbl, urls_tbl)

    # Step Functions invocation
    return _handle_step_functions(
        event, jobs_tbl, discovery_queue_url, processing_queue_url
    )


def _handle_step_functions(event, jobs_tbl, discovery_queue_url, processing_queue_url):
    """Handle Step Functions status polling."""
    job_id = event.get("job_id")
    if not job_id:
        raise ValueError("job_id is required")

    logger.info(f"Checking status for job: {job_id}")

    try:
        response = jobs_tbl.get_item(Key={"job_id": job_id})
        job_item = response.get("Item")

        if not job_item:
            raise ValueError(f"Job not found: {job_id}")

        status = job_item.get("status", ScrapeStatus.PENDING.value)
        total_urls = int(job_item.get("total_urls", 0))
        processed_count = int(job_item.get("processed_count", 0))
        failed_count = int(job_item.get("failed_count", 0))

        # Check queue depths to determine if discovery/processing are complete
        sqs = boto3.client("sqs")

        discovery_complete = True
        processing_complete = True

        if discovery_queue_url:
            try:
                queue_attrs = sqs.get_queue_attributes(
                    QueueUrl=discovery_queue_url,
                    AttributeNames=[
                        "ApproximateNumberOfMessages",
                        "ApproximateNumberOfMessagesNotVisible",
                    ],
                )
                attrs = queue_attrs.get("Attributes", {})
                visible = int(attrs.get("ApproximateNumberOfMessages", 0))
                in_flight = int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0))
                discovery_complete = visible == 0 and in_flight == 0
            except Exception as e:
                logger.warning(f"Could not check discovery queue: {e}")
                discovery_complete = False

        if processing_queue_url:
            try:
                queue_attrs = sqs.get_queue_attributes(
                    QueueUrl=processing_queue_url,
                    AttributeNames=[
                        "ApproximateNumberOfMessages",
                        "ApproximateNumberOfMessagesNotVisible",
                    ],
                )
                attrs = queue_attrs.get("Attributes", {})
                visible = int(attrs.get("ApproximateNumberOfMessages", 0))
                in_flight = int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0))
                processing_complete = visible == 0 and in_flight == 0
            except Exception as e:
                logger.warning(f"Could not check processing queue: {e}")
                processing_complete = False

        # Check failure threshold
        failure_threshold_exceeded = False
        if total_urls > 0:
            failure_rate = failed_count / total_urls
            failure_threshold_exceeded = failure_rate > FAILURE_THRESHOLD

        # Determine overall completion
        is_complete = (
            discovery_complete
            and processing_complete
            and (processed_count + failed_count) >= total_urls
            and total_urls > 0
        )

        # Update job status if complete
        if is_complete and status in [
            ScrapeStatus.DISCOVERING.value,
            ScrapeStatus.PROCESSING.value,
        ]:
            new_status = (
                ScrapeStatus.FAILED.value
                if failure_threshold_exceeded
                else ScrapeStatus.COMPLETED.value
            )
            jobs_tbl.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET #status = :status, completed_at = :ts",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": new_status,
                    ":ts": datetime.now(UTC).isoformat(),
                },
            )
            status = new_status

        result = {
            "job_id": job_id,
            "status": status,
            "total_urls": total_urls,
            "processed_count": processed_count,
            "failed_count": failed_count,
            "discovery_complete": discovery_complete,
            "processing_complete": processing_complete,
            "is_complete": is_complete,
            "failure_threshold_exceeded": failure_threshold_exceeded,
        }

        logger.info(f"Job status: {json.dumps(result)}")
        return result

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        logger.error(f"AWS error: {error_code} - {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}", exc_info=True)
        raise


def _handle_api_request(event, jobs_tbl, urls_tbl):
    """Handle API Gateway requests."""
    try:
        http_method = event.get("httpMethod", "GET")
        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}
        resource = event.get("resource", "")

        job_id = path_params.get("job_id")

        if not job_id:
            return _response(400, {"error": "job_id is required"})

        if http_method == "GET":
            if "/urls" in resource:
                if not urls_tbl:
                    return _response(500, {"error": "SCRAPE_URLS_TABLE not configured"})
                return _list_urls(urls_tbl, job_id, query_params)
            return _get_status_api(jobs_tbl, job_id)

        elif http_method == "DELETE":
            return _cancel_job(jobs_tbl, job_id)

        else:
            return _response(405, {"error": f"Method {http_method} not allowed"})

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        logger.error(f"AWS error: {error_code} - {e}")
        return _response(500, {"error": "Internal server error"})
    except Exception as e:
        logger.error(f"Error handling request: {e}", exc_info=True)
        return _response(500, {"error": "Internal server error"})


def _get_status_api(jobs_tbl, job_id: str) -> dict:
    """Get job status for API response."""
    response = jobs_tbl.get_item(Key={"job_id": job_id})
    job = response.get("Item")

    if not job:
        return _response(404, {"error": f"Job not found: {job_id}"})

    total_urls = int(job.get("total_urls", 0))
    processed_count = int(job.get("processed_count", 0))
    failed_count = int(job.get("failed_count", 0))

    progress = {
        "total": total_urls,
        "processed": processed_count,
        "failed": failed_count,
        "pending": max(0, total_urls - processed_count - failed_count),
    }

    if total_urls > 0:
        progress["percent_complete"] = round(
            (processed_count + failed_count) / total_urls * 100, 1
        )
    else:
        progress["percent_complete"] = 0

    return _response(200, {
        "job_id": job_id,
        "status": job.get("status"),
        "base_url": job.get("base_url"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "completed_at": job.get("completed_at"),
        "progress": progress,
        "config": job.get("config", {}),
        "failed_urls": job.get("failed_urls", [])[:10],
    })


def _list_urls(urls_tbl, job_id: str, query_params: dict) -> dict:
    """List URLs for a job with pagination."""
    limit = min(int(query_params.get("limit", "50")), 100)
    next_token = query_params.get("next_token")
    status_filter = query_params.get("status")

    query_kwargs = {
        "KeyConditionExpression": Key("job_id").eq(job_id),
        "Limit": limit,
    }

    if next_token:
        try:
            start_key = json.loads(next_token)
            query_kwargs["ExclusiveStartKey"] = start_key
        except json.JSONDecodeError:
            return _response(400, {"error": "Invalid next_token format"})

    if status_filter:
        query_kwargs["FilterExpression"] = "#status = :status"
        query_kwargs["ExpressionAttributeNames"] = {"#status": "status"}
        query_kwargs["ExpressionAttributeValues"] = {":status": status_filter}

    response = urls_tbl.query(**query_kwargs)

    urls = []
    for item in response.get("Items", []):
        urls.append({
            "url": item.get("url"),
            "status": item.get("status"),
            "depth": int(item.get("depth", 0)),
            "title": item.get("title"),
            "document_id": item.get("document_id"),
            "processed_at": item.get("processed_at"),
            "error": item.get("error"),
        })

    result = {
        "job_id": job_id,
        "urls": urls,
        "count": len(urls),
    }

    if "LastEvaluatedKey" in response:
        result["next_token"] = json.dumps(response["LastEvaluatedKey"])

    return _response(200, result)


def _cancel_job(jobs_tbl, job_id: str) -> dict:
    """Cancel a running scrape job."""
    response = jobs_tbl.get_item(Key={"job_id": job_id})
    job = response.get("Item")

    if not job:
        return _response(404, {"error": f"Job not found: {job_id}"})

    current_status = job.get("status")

    if current_status not in [
        ScrapeStatus.PENDING.value,
        ScrapeStatus.DISCOVERING.value,
        ScrapeStatus.PROCESSING.value,
    ]:
        return _response(400, {
            "error": f"Cannot cancel job with status: {current_status}"
        })

    jobs_tbl.update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #status = :status, cancelled_at = :ts",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": ScrapeStatus.CANCELLED.value,
            ":ts": datetime.now(UTC).isoformat(),
        },
    )

    return _response(200, {
        "job_id": job_id,
        "status": ScrapeStatus.CANCELLED.value,
        "message": "Job cancelled successfully",
    })


def _response(status_code: int, body: dict) -> dict:
    """Create API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }
