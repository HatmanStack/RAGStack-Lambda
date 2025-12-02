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
    "failed": 0
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

    processed = 0
    failed = 0

    # Process SQS records
    for record in event.get("Records", []):
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
                continue

            # Update URL status to processing
            urls_tbl.update_item(
                Key={"job_id": job_id, "url": url},
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": UrlStatus.PROCESSING.value},
            )

            # TODO: Phase 2 - Actual content extraction
            # For now, create placeholder markdown content
            document_id = str(uuid.uuid4())
            content = f"""---
source_url: {url}
scraped_at: {datetime.now(UTC).isoformat()}
job_id: {job_id}
---

# Placeholder Content

This is placeholder content for URL: {url}

Depth: {depth}

Content extraction will be implemented in Phase 2.
"""

            # Save to S3 input bucket with .scraped.md extension
            s3_key = f"{document_id}/{document_id}.scraped.md"
            s3.put_object(
                Bucket=input_bucket,
                Key=s3_key,
                Body=content.encode("utf-8"),
                ContentType="text/markdown",
                Metadata={
                    "source_url": url,
                    "job_id": job_id,
                    "document_id": document_id,
                },
            )

            logger.info(f"Saved content to s3://{input_bucket}/{s3_key}")

            # Update URL status to completed
            urls_tbl.update_item(
                Key={"job_id": job_id, "url": url},
                UpdateExpression=(
                    "SET #status = :status, document_id = :doc_id, processed_at = :ts"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": UrlStatus.COMPLETED.value,
                    ":doc_id": document_id,
                    ":ts": datetime.now(UTC).isoformat(),
                },
            )

            # Update job processed count
            jobs_tbl.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET processed_count = processed_count + :inc, updated_at = :ts",
                ExpressionAttributeValues={
                    ":inc": 1,
                    ":ts": datetime.now(UTC).isoformat(),
                },
            )

            processed += 1

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            logger.error(f"AWS error processing record: {error_code} - {e}")

            # Update URL status to failed
            try:
                urls_tbl.update_item(
                    Key={"job_id": message.get("job_id"), "url": message.get("url")},
                    UpdateExpression="SET #status = :status, error = :err",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": UrlStatus.FAILED.value,
                        ":err": str(e),
                    },
                )

                # Update job failed count
                jobs_tbl.update_item(
                    Key={"job_id": message.get("job_id")},
                    UpdateExpression="SET failed_count = failed_count + :inc, updated_at = :ts",
                    ExpressionAttributeValues={
                        ":inc": 1,
                        ":ts": datetime.now(UTC).isoformat(),
                    },
                )
            except Exception:
                pass

            failed += 1
            raise

        except Exception as e:
            logger.error(f"Error processing record: {e}", exc_info=True)

            # Update URL status to failed
            try:
                urls_tbl.update_item(
                    Key={"job_id": message.get("job_id"), "url": message.get("url")},
                    UpdateExpression="SET #status = :status, error = :err",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": UrlStatus.FAILED.value,
                        ":err": str(e),
                    },
                )

                # Update job failed count
                jobs_tbl.update_item(
                    Key={"job_id": message.get("job_id")},
                    UpdateExpression="SET failed_count = failed_count + :inc, updated_at = :ts",
                    ExpressionAttributeValues={
                        ":inc": 1,
                        ":ts": datetime.now(UTC).isoformat(),
                    },
                )
            except Exception:
                pass

            failed += 1
            raise

    return {
        "processed": processed,
        "failed": failed,
    }
