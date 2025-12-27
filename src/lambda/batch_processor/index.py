"""
Batch Processor Lambda

Processes individual 10-page batches from SQS queue with globally limited concurrency.
Uses ReservedConcurrentExecutions=10 to limit concurrent Bedrock OCR calls.

Tracks page-level success/failure in DynamoDB. If 95% page success is impossible,
fails early. On last batch, triggers CombinePages if 95% threshold is met.

Input event (SQS):
{
    "Records": [{
        "body": "{\"document_id\": \"abc123\", \"batch_index\": 0, ...}"
    }]
}

Message body:
{
    "document_id": "abc123",
    "batch_index": 0,
    "input_s3_uri": "s3://bucket/input/abc123/document.pdf",
    "output_s3_prefix": "s3://bucket/output/abc123/",
    "page_start": 1,
    "page_end": 10,
    "total_batches": 15,
    "total_pages": 150
}
"""

import json
import logging
import os
from datetime import UTC, datetime

import boto3

from ragstack_common.config import ConfigurationManager
from ragstack_common.models import Document, Status
from ragstack_common.ocr import OcrService
from ragstack_common.storage import parse_s3_uri

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 95% page success threshold for proceeding with ingestion
SUCCESS_THRESHOLD = 0.95

# Module-level AWS clients (reused across warm invocations)
dynamodb = boto3.resource("dynamodb")

# Module-level initialization (lazy-initialized)
_config_manager = None


def _get_config_manager():
    """Get or initialize ConfigurationManager (lazy initialization)."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


def _process_batch(
    document_id: str,
    batch_index: int,
    input_s3_uri: str,
    output_s3_prefix: str,
    page_start: int,
    page_end: int,
) -> Document:
    """
    Process a single batch of pages and return the processed document.

    Returns Document with pages_succeeded and pages_failed set.
    """
    # Read configuration
    config_mgr = _get_config_manager()
    ocr_backend = config_mgr.get_parameter("ocr_backend", default="textract")
    bedrock_model_id = config_mgr.get_parameter(
        "bedrock_ocr_model_id", default="anthropic.claude-3-5-haiku-20241022-v1:0"
    )

    logger.info(f"Processing batch {batch_index}: pages {page_start}-{page_end}")
    logger.info(f"Using OCR backend: {ocr_backend}")

    # Get filename from input URI
    _, key = parse_s3_uri(input_s3_uri)
    filename = key.split("/")[-1]

    # Create Document object with page range
    document = Document(
        document_id=document_id,
        filename=filename,
        input_s3_uri=input_s3_uri,
        output_s3_uri=output_s3_prefix,
        status=Status.PROCESSING,
        page_start=page_start,
        page_end=page_end,
    )

    # Create OCR service and process document
    ocr_service = OcrService(
        region=os.environ.get("AWS_REGION"),
        backend=ocr_backend,
        bedrock_model_id=bedrock_model_id,
    )

    # Process the page range
    processed_document = ocr_service.process_document(document)

    logger.info(
        f"Batch {batch_index} complete: "
        f"{processed_document.pages_succeeded} succeeded, "
        f"{processed_document.pages_failed} failed, "
        f"output={processed_document.output_s3_uri}"
    )

    return processed_document


def _update_tracking_and_check(
    document_id: str,
    tracking_table: str,
    pages_succeeded: int,
    pages_failed: int,
    total_pages: int,
) -> dict:
    """
    Atomically update page counts and batches_remaining.

    Returns dict with:
        - batches_remaining: int
        - total_pages_succeeded: int
        - total_pages_failed: int
        - is_last_batch: bool
        - can_reach_threshold: bool
    """
    table = dynamodb.Table(tracking_table)

    response = table.update_item(
        Key={"document_id": document_id},
        UpdateExpression=(
            "SET batches_remaining = batches_remaining - :one, "
            "pages_succeeded = pages_succeeded + :succeeded, "
            "pages_failed = pages_failed + :failed, "
            "updated_at = :now"
        ),
        ExpressionAttributeValues={
            ":one": 1,
            ":succeeded": pages_succeeded,
            ":failed": pages_failed,
            ":now": datetime.now(UTC).isoformat(),
        },
        ReturnValues="ALL_NEW",
    )

    attrs = response["Attributes"]
    batches_remaining = int(attrs.get("batches_remaining", 0))
    total_succeeded = int(attrs.get("pages_succeeded", 0))
    total_failed = int(attrs.get("pages_failed", 0))

    is_last_batch = batches_remaining == 0

    # Calculate if 95% is still possible
    # pages_remaining = total - already processed (more accurate than assuming 10/batch)
    pages_processed = total_succeeded + total_failed
    pages_remaining = total_pages - pages_processed
    max_possible_succeeded = total_succeeded + pages_remaining
    can_reach_threshold = (max_possible_succeeded / total_pages) >= SUCCESS_THRESHOLD

    logger.info(
        f"Tracking update: batches_remaining={batches_remaining}, "
        f"pages_succeeded={total_succeeded}, pages_failed={total_failed}, "
        f"can_reach_threshold={can_reach_threshold}"
    )

    return {
        "batches_remaining": batches_remaining,
        "total_pages_succeeded": total_succeeded,
        "total_pages_failed": total_failed,
        "is_last_batch": is_last_batch,
        "can_reach_threshold": can_reach_threshold,
    }


def _mark_document_failed(document_id: str, tracking_table: str, reason: str) -> None:
    """Mark document as failed in DynamoDB."""
    table = dynamodb.Table(tracking_table)

    table.update_item(
        Key={"document_id": document_id},
        UpdateExpression=("SET #status = :failed, error_message = :reason, updated_at = :now"),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":failed": Status.FAILED.value,
            ":reason": reason,
            ":now": datetime.now(UTC).isoformat(),
        },
    )
    logger.info(f"Marked document {document_id} as failed: {reason}")


def _invoke_combine_pages(
    document_id: str,
    output_s3_prefix: str,
    total_pages: int,
) -> None:
    """Invoke CombinePages Lambda asynchronously."""
    combine_pages_arn = os.environ.get("COMBINE_PAGES_FUNCTION_ARN")
    if not combine_pages_arn:
        raise ValueError("COMBINE_PAGES_FUNCTION_ARN environment variable required")

    lambda_client = boto3.client("lambda")

    payload = {
        "document_id": document_id,
        "output_s3_prefix": output_s3_prefix,
        "total_pages": total_pages,
    }

    logger.info(f"Invoking CombinePages for document {document_id}")

    lambda_client.invoke(
        FunctionName=combine_pages_arn,
        InvocationType="Event",  # Async invocation
        Payload=json.dumps(payload),
    )

    logger.info("CombinePages invoked successfully")


def lambda_handler(event, context):
    """
    Process SQS messages containing batch jobs.

    Each message represents a 10-page batch to process. After processing,
    updates page success/failure counts and checks if 95% threshold can be met.
    """
    tracking_table = os.environ.get("TRACKING_TABLE")
    if not tracking_table:
        raise ValueError("TRACKING_TABLE environment variable is required")

    # Process each SQS record (batch size is 1, so typically just one)
    batch_item_failures = []

    for record in event.get("Records", []):
        message_id = record.get("messageId")

        try:
            # Parse message body
            message = json.loads(record["body"])

            document_id = message["document_id"]
            batch_index = message["batch_index"]
            input_s3_uri = message["input_s3_uri"]
            output_s3_prefix = message["output_s3_prefix"]
            page_start = message["page_start"]
            page_end = message["page_end"]
            total_pages = message["total_pages"]
            pages_in_batch = page_end - page_start + 1

            logger.info(
                f"Processing batch: document={document_id}, "
                f"batch={batch_index}, pages={page_start}-{page_end}"
            )

            # Process the batch (OCR)
            # Page-level errors are handled gracefully within OCR
            pages_succeeded = 0
            pages_failed = pages_in_batch  # Assume all failed unless successful

            try:
                processed_doc = _process_batch(
                    document_id=document_id,
                    batch_index=batch_index,
                    input_s3_uri=input_s3_uri,
                    output_s3_prefix=output_s3_prefix,
                    page_start=page_start,
                    page_end=page_end,
                )
                pages_succeeded = processed_doc.pages_succeeded
                pages_failed = processed_doc.pages_failed
                logger.info(f"Batch processed: {pages_succeeded}/{pages_in_batch} pages succeeded")
            except Exception as batch_error:
                # Entire batch failed - all pages count as failed
                logger.error(
                    f"Batch {batch_index} failed completely: {batch_error}",
                    exc_info=True,
                )

            # Update tracking and check thresholds
            result = _update_tracking_and_check(
                document_id=document_id,
                tracking_table=tracking_table,
                pages_succeeded=pages_succeeded,
                pages_failed=pages_failed,
                total_pages=total_pages,
            )

            # Check if we should fail early (95% impossible)
            if not result["can_reach_threshold"] and not result["is_last_batch"]:
                _mark_document_failed(
                    document_id=document_id,
                    tracking_table=tracking_table,
                    reason=(
                        f"Cannot reach {SUCCESS_THRESHOLD:.0%} page success threshold. "
                        f"Current: {result['total_pages_succeeded']}/{total_pages} pages "
                        f"({result['total_pages_succeeded'] / total_pages:.1%})"
                    ),
                )
                # Don't process remaining batches - they'll be ignored
                continue

            # On last batch, check final threshold
            if result["is_last_batch"]:
                final_rate = result["total_pages_succeeded"] / total_pages
                if final_rate >= SUCCESS_THRESHOLD:
                    logger.info(
                        f"Last batch complete. Success rate: {final_rate:.1%} "
                        f"({result['total_pages_succeeded']}/{total_pages}). "
                        f"Triggering CombinePages."
                    )
                    _invoke_combine_pages(
                        document_id=document_id,
                        output_s3_prefix=output_s3_prefix,
                        total_pages=total_pages,
                    )
                else:
                    _mark_document_failed(
                        document_id=document_id,
                        tracking_table=tracking_table,
                        reason=(
                            f"Below {SUCCESS_THRESHOLD:.0%} page success threshold. "
                            f"Final: {result['total_pages_succeeded']}/{total_pages} pages "
                            f"({final_rate:.1%})"
                        ),
                    )

        except Exception as e:
            logger.error(f"Failed to process message: {e}", exc_info=True)
            # Only report failure for message parsing errors
            batch_item_failures.append({"itemIdentifier": message_id})

    # Return failures for SQS to retry (ReportBatchItemFailures)
    return {"batchItemFailures": batch_item_failures}
