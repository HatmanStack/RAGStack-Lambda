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

        # Create execution name from document_id (sanitized) + request ID
        # Step Functions execution names: 1-80 chars, alphanumeric + hyphens + underscores
        sanitized_id = document_id.replace("/", "-").replace(".", "-")[:60]
        execution_name = f"{sanitized_id}-{context.aws_request_id[:8]}"

        logger.info(f"Starting execution for document: {document_id}")

        sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps(message),
        )

        logger.info(f"Started execution: {execution_name}")

    return {"statusCode": 200, "body": "OK"}
