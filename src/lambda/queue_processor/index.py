"""
Queue Processor Lambda

Receives SQS messages from DocumentProcessingQueue and starts Step Functions executions.
Reserved concurrency limits concurrent large document processing.

Input event (SQS):
{
    "Records": [
        {
            "body": "{\"document_id\": \"input/abc123/doc.pdf\", ...}"
        }
    ]
}
"""

import json
import logging
import os
import re

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Process SQS messages and start Step Functions executions.

    Uses reserved concurrency to limit concurrent large document processing.
    """
    sfn_client = boto3.client("stepfunctions")
    state_machine_arn = os.environ["STATE_MACHINE_ARN"]

    for record in event["Records"]:
        message = json.loads(record["body"])
        document_id = message.get("document_id", "unknown")

        # Create execution name from document_id (sanitized) + message ID
        # Step Functions execution names: 1-80 chars, alphanumeric + hyphens + underscores
        # Use messageId (unique per SQS message) instead of aws_request_id (same for batch)
        message_id_suffix = record.get("messageId", context.aws_request_id)[:12]
        max_prefix_len = 80 - 1 - len(message_id_suffix)
        sanitized_id = re.sub(r"[^a-zA-Z0-9_-]", "_", document_id)[:max_prefix_len]
        execution_name = f"{sanitized_id}-{message_id_suffix}"

        logger.info(f"Starting execution for document: {document_id}")

        sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps(message),
        )

        logger.info(f"Started execution: {execution_name}")

    return {"statusCode": 200, "body": "OK"}
