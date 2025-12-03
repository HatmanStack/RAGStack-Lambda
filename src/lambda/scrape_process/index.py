"""
Scrape Process Lambda

Processes URLs from the processing queue, extracts content,
converts to markdown, and saves to S3 input bucket.

Input event (SQS triggered):
{
    "Records": [{
        "body": "{\"job_id\": \"uuid\", \"url\": \"https://...\", \"depth\": 0}"
    }]
}

Output:
{
    "processed": 1,
    "failed": 0,
    "skipped": 0
}
"""

import json
import logging
import os
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

from ragstack_common.scraper import ScrapeStatus, UrlStatus
from ragstack_common.scraper.dedup import DeduplicationService
from ragstack_common.scraper.extractor import extract_content
from ragstack_common.scraper.fetcher import fetch_auto
from ragstack_common.scraper.models import ScrapeConfig

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def lambda_handler(event, context):
    """
    Main Lambda handler - processes URLs and extracts content.
    """
    # Get environment variables
    jobs_table = os.environ.get("SCRAPE_JOBS_TABLE")
    urls_table = os.environ.get("SCRAPE_URLS_TABLE")
    input_bucket = os.environ.get("INPUT_BUCKET")
    request_delay_ms = int(os.environ.get("REQUEST_DELAY_MS", "500"))

    if not jobs_table:
        raise ValueError("SCRAPE_JOBS_TABLE environment variable required")
    if not urls_table:
        raise ValueError("SCRAPE_URLS_TABLE environment variable required")
    if not input_bucket:
        raise ValueError("INPUT_BUCKET environment variable required")

    dynamodb = boto3.resource("dynamodb")
    jobs_tbl = dynamodb.Table(jobs_table)
    urls_tbl = dynamodb.Table(urls_table)
    s3 = boto3.client("s3")

    # Initialize deduplication service
    dedup = DeduplicationService(urls_table)

    processed = 0
    failed = 0
    skipped = 0

    # Process SQS records
    for record in event.get("Records", []):
        message = None
        job_id = None
        url = None

        try:
            message = json.loads(record["body"])
            job_id = message["job_id"]
            url = message["url"]
            depth = message.get("depth", 0)

            logger.info(f"Processing URL: job={job_id}, url={url}")

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
            ]:
                logger.info(f"Job {job_id} is {job_status}, skipping")
                skipped += 1
                continue

            # Get job config
            config_data = job_item.get("config", {})
            config = ScrapeConfig.from_dict(config_data)

            # Update URL status to processing
            urls_tbl.update_item(
                Key={"job_id": job_id, "url": url},
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": UrlStatus.PROCESSING.value},
            )

            # Fetch content with auto SPA detection
            scrape_mode = config_data.get("scrape_mode", "auto")
            force_playwright = scrape_mode == "full"

            result = fetch_auto(
                url,
                cookies=config.cookies,
                headers=config.headers,
                force_playwright=force_playwright,
                delay_ms=request_delay_ms,
            )

            if result.error:
                raise Exception(f"Fetch failed: {result.error}")

            if not result.is_html:
                raise Exception(f"Not HTML content: {result.content_type}")

            # Extract content and convert to markdown
            extracted = extract_content(result.content, url)

            # Check for content changes (deduplication)
            if not dedup.is_content_changed(url, extracted.markdown):
                logger.info(f"Content unchanged, skipping: {url}")
                urls_tbl.update_item(
                    Key={"job_id": job_id, "url": url},
                    UpdateExpression="SET #status = :status",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={":status": UrlStatus.SKIPPED.value},
                )
                # Still count as processed for job completion
                jobs_tbl.update_item(
                    Key={"job_id": job_id},
                    UpdateExpression="SET processed_count = processed_count + :one, updated_at = :ts",
                    ExpressionAttributeValues={
                        ":one": 1,
                        ":ts": datetime.now(UTC).isoformat(),
                    },
                )
                skipped += 1
                continue

            # Generate document ID and S3 key
            document_id = str(uuid.uuid4())
            s3_key = f"{document_id}/{document_id}.scraped.md"

            # Upload to input bucket
            s3.put_object(
                Bucket=input_bucket,
                Key=s3_key,
                Body=extracted.markdown.encode("utf-8"),
                ContentType="text/markdown",
                Metadata={
                    "source_url": url,
                    "job_id": job_id,
                    "document_id": document_id,
                    "title": extracted.title[:256] if extracted.title else "Untitled",
                },
            )

            logger.info(f"Saved content to s3://{input_bucket}/{s3_key}")

            # Store hash for future deduplication
            dedup.store_hash(job_id, url, extracted.markdown)

            # Update URL record with document ID
            urls_tbl.update_item(
                Key={"job_id": job_id, "url": url},
                UpdateExpression=(
                    "SET #status = :status, document_id = :doc_id, "
                    "title = :title, processed_at = :ts, content_hash = :hash"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": UrlStatus.COMPLETED.value,
                    ":doc_id": document_id,
                    ":title": extracted.title,
                    ":ts": datetime.now(UTC).isoformat(),
                    ":hash": dedup.get_content_hash(extracted.markdown),
                },
            )

            # Update job processed count
            jobs_tbl.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET processed_count = processed_count + :one, updated_at = :ts",
                ExpressionAttributeValues={
                    ":one": 1,
                    ":ts": datetime.now(UTC).isoformat(),
                },
            )

            processed += 1
            logger.info(f"Processed: {url} -> {document_id}")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.error(f"AWS error processing record: {error_code} - {e}")
            _mark_failed(jobs_tbl, urls_tbl, job_id, url, str(e))
            failed += 1
            raise

        except Exception as e:
            logger.error(f"Error processing record: {e}", exc_info=True)
            _mark_failed(jobs_tbl, urls_tbl, job_id, url, str(e))
            failed += 1
            raise

    return {
        "processed": processed,
        "failed": failed,
        "skipped": skipped,
    }


def _mark_failed(jobs_tbl, urls_tbl, job_id: str | None, url: str | None, error: str):
    """Mark URL as failed and update job counters."""
    if not job_id or not url:
        return

    try:
        # Update URL status to failed
        urls_tbl.update_item(
            Key={"job_id": job_id, "url": url},
            UpdateExpression="SET #status = :status, error = :err",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": UrlStatus.FAILED.value,
                ":err": error[:500],  # Truncate for DynamoDB
            },
        )

        # Update job failed count
        jobs_tbl.update_item(
            Key={"job_id": job_id},
            UpdateExpression=(
                "SET failed_count = failed_count + :one, "
                "failed_urls = list_append(if_not_exists(failed_urls, :empty), :url), "
                "updated_at = :ts"
            ),
            ExpressionAttributeValues={
                ":one": 1,
                ":empty": [],
                ":url": [{"url": url, "error": error[:200]}],
                ":ts": datetime.now(UTC).isoformat(),
            },
        )
    except Exception as e:
        logger.error(f"Failed to mark URL as failed: {e}")
