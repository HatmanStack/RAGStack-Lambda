"""
Scrape Discover Lambda

Processes URLs from the discovery queue, extracts links, and adds
new discovered URLs back to the queue (recursive discovery).

Input event (SQS triggered):
{
    "Records": [{
        "body": "{\"job_id\": \"uuid\", \"url\": \"https://...\", \"depth\": 0}"
    }]
}

Output:
{
    "processed": 1,
    "discovered": 5,
    "skipped": 2
}
"""

import hashlib
import json
import logging
import os
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

from ragstack_common.scraper import ScrapePage, ScrapeStatus, UrlStatus

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def lambda_handler(event, context):
    """
    Main Lambda handler - processes discovery queue messages.
    """
    # Get environment variables
    jobs_table = os.environ.get("SCRAPE_JOBS_TABLE")
    urls_table = os.environ.get("SCRAPE_URLS_TABLE")
    discovery_queue_url = os.environ.get("SCRAPE_DISCOVERY_QUEUE_URL")
    processing_queue_url = os.environ.get("SCRAPE_PROCESSING_QUEUE_URL")

    if not jobs_table:
        raise ValueError("SCRAPE_JOBS_TABLE environment variable required")
    if not urls_table:
        raise ValueError("SCRAPE_URLS_TABLE environment variable required")
    if not discovery_queue_url:
        raise ValueError("SCRAPE_DISCOVERY_QUEUE_URL environment variable required")
    if not processing_queue_url:
        raise ValueError("SCRAPE_PROCESSING_QUEUE_URL environment variable required")

    dynamodb = boto3.resource("dynamodb")
    jobs_tbl = dynamodb.Table(jobs_table)
    urls_tbl = dynamodb.Table(urls_table)
    sqs = boto3.client("sqs")

    processed = 0
    discovered = 0
    skipped = 0

    # Process SQS records
    for record in event.get("Records", []):
        try:
            message = json.loads(record["body"])
            job_id = message["job_id"]
            url = message["url"]
            depth = message.get("depth", 0)

            logger.info(f"Processing discovery: job={job_id}, url={url}, depth={depth}")

            # Check if job is still active
            job_response = jobs_tbl.get_item(Key={"job_id": job_id})
            job_item = job_response.get("Item")

            if not job_item:
                logger.warning(f"Job not found: {job_id}")
                continue

            job_status = job_item.get("status")
            if job_status in [
                ScrapeStatus.CANCELLED.value,
                ScrapeStatus.FAILED.value,
                ScrapeStatus.COMPLETED.value,
            ]:
                logger.info(f"Job {job_id} is {job_status}, skipping")
                skipped += 1
                continue

            # Compute URL hash for deduplication
            url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]

            # Check if URL already visited
            existing = urls_tbl.get_item(Key={"job_id": job_id, "url": url})
            if existing.get("Item"):
                logger.info(f"URL already visited: {url}")
                skipped += 1
                continue

            # Create page record (mark as discovered)
            page = ScrapePage(
                job_id=job_id,
                url=url,
                status=UrlStatus.PENDING,
                depth=depth,
            )

            page_data = page.to_dict()
            page_data["url_hash"] = url_hash

            urls_tbl.put_item(Item=page_data)

            # TODO: Phase 2 - Actual link extraction
            # For now, just send URL to processing queue (placeholder)
            discovered_urls = []

            logger.info(f"Placeholder: Would discover links from {url}")

            # Send URL to processing queue
            sqs.send_message(
                QueueUrl=processing_queue_url,
                MessageBody=json.dumps(
                    {
                        "job_id": job_id,
                        "url": url,
                        "depth": depth,
                    }
                ),
            )

            # Update job counters
            jobs_tbl.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET total_urls = total_urls + :inc, updated_at = :ts",
                ExpressionAttributeValues={
                    ":inc": 1,
                    ":ts": datetime.now(UTC).isoformat(),
                },
            )

            # Send discovered URLs back to discovery queue
            config = job_item.get("config", {})
            max_depth = config.get("max_depth", 3)

            for discovered_url in discovered_urls:
                if depth + 1 <= max_depth:
                    sqs.send_message(
                        QueueUrl=discovery_queue_url,
                        MessageBody=json.dumps(
                            {
                                "job_id": job_id,
                                "url": discovered_url,
                                "depth": depth + 1,
                            }
                        ),
                    )
                    discovered += 1

            processed += 1

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.error(f"AWS error processing record: {error_code} - {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing record: {e}", exc_info=True)
            raise

    return {
        "processed": processed,
        "discovered": discovered,
        "skipped": skipped,
    }
