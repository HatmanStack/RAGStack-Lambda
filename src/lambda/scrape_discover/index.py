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

import json
import logging
import os
import time
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

from ragstack_common.scraper import ScrapePage, ScrapeStatus, UrlStatus
from ragstack_common.scraper.discovery import (
    extract_links,
    filter_discovered_urls,
    normalize_url,
)
from ragstack_common.scraper.fetcher import HttpFetcher
from ragstack_common.scraper.models import ScrapeConfig

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
    request_delay_ms = int(os.environ.get("REQUEST_DELAY_MS", "500"))

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

            # Normalize URL for deduplication
            normalized_url = normalize_url(url)

            # Check if URL already visited
            existing = urls_tbl.get_item(Key={"job_id": job_id, "url": normalized_url})
            if existing.get("Item"):
                logger.info(f"URL already visited: {normalized_url}")
                skipped += 1
                continue

            # Create page record (mark as discovered)
            page = ScrapePage(
                job_id=job_id,
                url=normalized_url,
                status=UrlStatus.PENDING,
                depth=depth,
            )

            page_data = page.to_dict()
            urls_tbl.put_item(Item=page_data)

            # Get job config
            config_data = job_item.get("config", {})
            config = ScrapeConfig.from_dict(config_data)
            base_url = job_item.get("base_url", url)

            # Fetch the page to extract links
            fetcher = HttpFetcher(
                delay_ms=request_delay_ms,
                cookies=config.cookies,
                headers=config.headers,
            )
            result = fetcher.fetch(normalized_url)

            if result.error:
                logger.warning(f"Fetch failed during discovery: {normalized_url} - {result.error}")
                # Mark URL as failed but continue - processing will retry
                urls_tbl.update_item(
                    Key={"job_id": job_id, "url": normalized_url},
                    UpdateExpression="SET #status = :status, error = :err",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": UrlStatus.FAILED.value,
                        ":err": result.error,
                    },
                )
                # Update job failed count
                jobs_tbl.update_item(
                    Key={"job_id": job_id},
                    UpdateExpression="SET failed_count = failed_count + :inc, updated_at = :ts",
                    ExpressionAttributeValues={
                        ":inc": 1,
                        ":ts": datetime.now(UTC).isoformat(),
                    },
                )
                continue

            # Send URL to processing queue
            sqs.send_message(
                QueueUrl=processing_queue_url,
                MessageBody=json.dumps(
                    {
                        "job_id": job_id,
                        "url": normalized_url,
                        "depth": depth,
                    }
                ),
            )

            # Update job total URLs count
            jobs_tbl.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET total_urls = total_urls + :inc, updated_at = :ts",
                ExpressionAttributeValues={
                    ":inc": 1,
                    ":ts": datetime.now(UTC).isoformat(),
                },
            )

            # Extract and filter links if within depth limit
            max_depth = config.max_depth
            max_pages = config.max_pages

            if depth < max_depth and result.is_html:
                links = extract_links(result.content, normalized_url)

                # Get visited URLs for this job (for filtering)
                # Note: This is a simplified approach; for large jobs,
                # we rely on the DynamoDB check in subsequent invocations
                visited = set()

                filtered = filter_discovered_urls(
                    urls=links,
                    base_url=base_url,
                    config=config,
                    visited=visited,
                )

                logger.info(f"Discovered {len(filtered)} new URLs from {normalized_url}")

                # Check max pages limit
                job_refresh = jobs_tbl.get_item(Key={"job_id": job_id})
                total_discovered = int(job_refresh.get("Item", {}).get("total_urls", 0))
                remaining = max_pages - total_discovered

                # Queue new URLs for discovery
                urls_to_queue = filtered[:remaining] if remaining > 0 else []

                for link in urls_to_queue:
                    sqs.send_message(
                        QueueUrl=discovery_queue_url,
                        MessageBody=json.dumps(
                            {
                                "job_id": job_id,
                                "url": link,
                                "depth": depth + 1,
                            }
                        ),
                    )
                    discovered += 1

                if remaining <= 0:
                    logger.info(f"Max pages limit ({max_pages}) reached for job {job_id}")

            processed += 1

            # Respect rate limit between pages
            time.sleep(request_delay_ms / 1000.0)

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
