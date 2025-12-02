"""
Scrape Status Lambda

Returns the current status of a scrape job for Step Functions polling.
Used to determine when discovery and processing phases are complete.

Input event (from Step Functions):
{
    "job_id": "uuid"
}

Output:
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

import boto3
from botocore.exceptions import ClientError

from ragstack_common.scraper import ScrapeStatus

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Failure threshold: abort if more than 10% of pages fail
FAILURE_THRESHOLD = 0.1


def lambda_handler(event, context):
    """
    Main Lambda handler - returns job status for polling.
    """
    # Get environment variables
    jobs_table = os.environ.get("SCRAPE_JOBS_TABLE")
    discovery_queue_url = os.environ.get("SCRAPE_DISCOVERY_QUEUE_URL")
    processing_queue_url = os.environ.get("SCRAPE_PROCESSING_QUEUE_URL")

    if not jobs_table:
        raise ValueError("SCRAPE_JOBS_TABLE environment variable required")

    job_id = event.get("job_id")
    if not job_id:
        raise ValueError("job_id is required")

    logger.info(f"Checking status for job: {job_id}")

    try:
        # Get job record
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(jobs_table)

        response = table.get_item(Key={"job_id": job_id})
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
