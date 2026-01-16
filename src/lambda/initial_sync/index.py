"""
Initial Sync Custom Resource Lambda

Triggers StartIngestionJob on stack creation to initialize the KB sync tracking mechanism.
This ensures incremental sync works correctly from the first deployment.

On CREATE: Starts an ingestion job (empty bucket = instant completion, establishes baseline)
On UPDATE: No-op (sync tracking already established)
On DELETE: No-op (KB deletion handles cleanup)
"""

import json
import logging
import urllib.request

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_agent = boto3.client("bedrock-agent")


def send_response(event: dict, context, status: str, reason: str = "", data: dict = None):
    """Send response to CloudFormation."""
    response_body = {
        "Status": status,
        "Reason": reason or f"See CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": event.get("PhysicalResourceId", context.log_stream_name),
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data or {},
    }

    response_url = event["ResponseURL"]
    logger.info(f"Sending {status} response to {response_url}")

    try:
        request = urllib.request.Request(
            response_url,
            data=json.dumps(response_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            logger.info(f"Response sent: {response.status}")
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
        raise


def lambda_handler(event: dict, context):
    """Handle CloudFormation custom resource events."""
    logger.info(f"Event: {json.dumps(event)}")

    request_type = event.get("RequestType")
    properties = event.get("ResourceProperties", {})
    kb_id = properties.get("KnowledgeBaseId")
    ds_id = properties.get("DataSourceId")

    try:
        if request_type == "Create":
            if not kb_id or not ds_id:
                send_response(event, context, "FAILED", "Missing KnowledgeBaseId or DataSourceId")
                return

            logger.info(f"Starting initial sync for KB {kb_id}, DS {ds_id}")

            try:
                response = bedrock_agent.start_ingestion_job(
                    knowledgeBaseId=kb_id,
                    dataSourceId=ds_id,
                )
                job_id = response.get("ingestionJob", {}).get("ingestionJobId", "unknown")
                logger.info(f"Initial sync started: job_id={job_id}")

                send_response(
                    event,
                    context,
                    "SUCCESS",
                    data={"IngestionJobId": job_id},
                )
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                error_msg = e.response.get("Error", {}).get("Message", str(e))
                logger.error(f"Failed to start initial sync: {error_code} - {error_msg}")
                # Don't fail the stack deployment for sync issues
                send_response(
                    event,
                    context,
                    "SUCCESS",
                    reason=f"Initial sync skipped: {error_msg}",
                )

        elif request_type in ("Update", "Delete"):
            # No action needed for updates or deletes
            logger.info(f"No action for {request_type}")
            send_response(event, context, "SUCCESS")

        else:
            send_response(event, context, "FAILED", f"Unknown request type: {request_type}")

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        send_response(event, context, "FAILED", str(e))
