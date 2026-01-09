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

import ipaddress
import json
import logging
import os
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

from ragstack_common.appsync import publish_scrape_update
from ragstack_common.bedrock import BedrockClient
from ragstack_common.config import ConfigurationManager
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.scraper import ScrapeConfig, ScrapeJob, ScrapeStatus
from ragstack_common.scraper.extractor import extract_content
from ragstack_common.scraper.fetcher import fetch_auto

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Blocked hostnames for SSRF protection
BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.azure.internal",
}


def validate_url_for_ssrf(url: str) -> None:
    """
    Validate URL to prevent SSRF attacks.

    Blocks:
    - Private/internal IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x)
    - Link-local addresses (169.254.x)
    - Cloud metadata endpoints
    - Localhost variations

    Raises ValueError if URL targets a blocked destination.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise ValueError("Invalid URL: no hostname found")

    # Block known dangerous hostnames
    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTNAMES:
        raise ValueError(f"URL cannot target internal service: {hostname}")

    # Block cloud metadata IP explicitly
    if "169.254.169.254" in url:
        raise ValueError("URL cannot target cloud metadata endpoint")

    # Try to parse hostname as IP address
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        # Not an IP address, it's a hostname - that's fine
        ip = None

    # Check IP properties outside try block so blocking raises propagate
    if ip is not None:
        if ip.is_private:
            raise ValueError("URL cannot target private IP addresses")
        if ip.is_loopback:
            raise ValueError("URL cannot target loopback addresses")
        if ip.is_link_local:
            raise ValueError("URL cannot target link-local addresses")
        if ip.is_reserved:
            raise ValueError("URL cannot target reserved IP addresses")


def extract_job_metadata(url: str, config: ScrapeConfig) -> dict:
    """
    Extract job-level metadata from the seed URL.

    Fetches the seed URL content, converts to markdown, and uses LLM
    to extract semantic metadata that will apply to all pages in the job.

    Args:
        url: The seed URL to extract metadata from.
        config: Scrape configuration (for cookies, headers, etc.).

    Returns:
        Dictionary of extracted metadata, or empty dict on failure.
    """
    try:
        logger.info(f"Extracting job metadata from seed URL: {url}")

        # Fetch seed URL content
        scrape_mode = config.to_dict().get("scrape_mode", "auto")
        force_playwright = scrape_mode == "full"

        result = fetch_auto(
            url,
            cookies=config.cookies,
            headers=config.headers,
            force_playwright=force_playwright,
            delay_ms=0,  # No delay for metadata extraction
        )

        if result.error or not result.is_html:
            logger.warning(f"Failed to fetch seed URL for metadata: {result.error}")
            return {}

        # Extract content and convert to markdown
        extracted = extract_content(result.content, url)
        if not extracted.markdown:
            logger.warning("No content extracted from seed URL")
            return {}

        # Get configuration for metadata extraction
        config_table = os.environ.get("CONFIGURATION_TABLE_NAME")
        config_manager = None
        model_id = None
        max_keys = 8

        if config_table:
            config_manager = ConfigurationManager(config_table)
            model_id = config_manager.get("metadata_extraction_model")
            max_keys = config_manager.get("metadata_max_keys", 8)

        # Extract metadata using LLM
        extractor = MetadataExtractor(
            bedrock_client=BedrockClient(),
            model_id=model_id,
            max_keys=max_keys,
        )

        # Use markdown content for extraction (truncate if too long)
        content_for_extraction = extracted.markdown[:8000]
        metadata = extractor.extract(content_for_extraction)

        logger.info(f"Extracted job metadata: {list(metadata.keys())}")
        return metadata

    except Exception as e:
        logger.warning(f"Job metadata extraction failed: {e}")
        return {}


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

        # SSRF protection: block private IPs, localhost, and cloud metadata endpoints
        validate_url_for_ssrf(base_url)

        # Parse config from event
        config_data = event.get("config", {})
        config = ScrapeConfig.from_dict(config_data)

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Extract job-level metadata from seed URL (1 LLM call per job)
        # This metadata will be applied to all pages in the job
        job_metadata = extract_job_metadata(base_url, config)

        # Create job record
        job = ScrapeJob(
            job_id=job_id,
            base_url=base_url,
            status=ScrapeStatus.DISCOVERING,
            config=config,
            title=event.get("title"),  # Optional title override
        )

        # Save to DynamoDB (include job_metadata)
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(jobs_table)
        job_dict = job.to_dict()
        if job_metadata:
            job_dict["job_metadata"] = job_metadata

        table.put_item(Item=job_dict)
        logger.info(f"Created job record: {job_id} with {len(job_metadata)} metadata fields")

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
