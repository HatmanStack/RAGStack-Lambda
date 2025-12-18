"""
Scrape Start Lambda

Initiates a new web scraping job by creating job record and sending
the initial URL to the discovery queue.

Input event (from GraphQL mutation):
{
    "base_url": "https://docs.example.com",
    "config": {
        "max_pages": 100,
        "max_depth": 3,
        "scope": "subpages",
        ...
    }
}

Output:
{
    "job_id": "uuid",
    "status": "discovering",
    "step_function_arn": "arn:aws:states:..."
}
"""

import json
import logging
import os
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

from ragstack_common.appsync import publish_scrape_update
from ragstack_common.scraper import ScrapeConfig, ScrapeJob, ScrapeStatus

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def lambda_handler(event, context):
    """
    Main Lambda handler - initiates scrape job.
    """
    # Get environment variables
    jobs_table = os.environ.get("SCRAPE_JOBS_TABLE")
    discovery_queue_url = os.environ.get("SCRAPE_DISCOVERY_QUEUE_URL")
    state_machine_arn = os.environ.get("SCRAPE_STATE_MACHINE_ARN")

    if not jobs_table:
        raise ValueError("SCRAPE_JOBS_TABLE environment variable required")
    if not discovery_queue_url:
        raise ValueError("SCRAPE_DISCOVERY_QUEUE_URL environment variable required")
    if not state_machine_arn:
        raise ValueError("SCRAPE_STATE_MACHINE_ARN environment variable required")

    logger.info(f"Starting scrape job: {json.dumps(event)}")

    try:
        # Extract event data
        base_url = event.get("base_url")
        if not base_url:
            raise ValueError("base_url is required")

        # Validate URL format
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")

        # Parse config from event
        config_data = event.get("config", {})
        config = ScrapeConfig.from_dict(config_data)

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Create job record
        job = ScrapeJob(
            job_id=job_id,
            base_url=base_url,
            status=ScrapeStatus.DISCOVERING,
            config=config,
            title=event.get("title"),  # Optional title override
        )

        # Save to DynamoDB
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(jobs_table)

        table.put_item(Item=job.to_dict())
        logger.info(f"Created job record: {job_id}")

        # Send initial URL to discovery queue
        sqs = boto3.client("sqs")
        message = {
            "job_id": job_id,
            "url": base_url,
            "depth": 0,
        }

        send_params = {
            "QueueUrl": discovery_queue_url,
            "MessageBody": json.dumps(message),
        }
        # Only add MessageGroupId for FIFO queues
        if discovery_queue_url.endswith(".fifo"):
            send_params["MessageGroupId"] = job_id

        sqs.send_message(**send_params)
        logger.info(f"Sent initial URL to discovery queue: {base_url}")

        # Start Step Functions execution
        sfn = boto3.client("stepfunctions")
        execution_input = {
            "job_id": job_id,
            "base_url": base_url,
            "config": config.to_dict(),
        }

        execution_response = sfn.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"scrape-{job_id}",
            input=json.dumps(execution_input),
        )

        step_function_arn = execution_response["executionArn"]
        logger.info(f"Started Step Functions execution: {step_function_arn}")

        # Update job with execution ARN
        table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET step_function_arn = :arn, updated_at = :ts",
            ExpressionAttributeValues={
                ":arn": step_function_arn,
                ":ts": datetime.now(UTC).isoformat(),
            },
        )

        # Publish real-time update to subscribers
        graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")
        publish_scrape_update(
            graphql_endpoint=graphql_endpoint,
            job_id=job_id,
            base_url=base_url,
            title=job.title or base_url,
            status=ScrapeStatus.DISCOVERING.value,
            total_urls=0,
            processed_count=0,
            failed_count=0,
        )

        return {
            "job_id": job_id,
            "base_url": base_url,
            "status": ScrapeStatus.DISCOVERING.value,
            "step_function_arn": step_function_arn,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        logger.error(f"AWS error: {error_code} - {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to start scrape job: {e}", exc_info=True)
        raise
