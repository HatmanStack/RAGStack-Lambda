"""Conversation history management for query_kb.

Handles storing and retrieving conversation turns from DynamoDB
for multi-turn chat continuity.
"""

import json
import logging
import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

from ragstack_common.types import SourceInfo

try:
    from ._clients import dynamodb
except ImportError:
    from _clients import dynamodb  # type: ignore[import-not-found,no-redef]

logger = logging.getLogger()

# Conversation history settings
MAX_HISTORY_TURNS = 5
CONVERSATION_TTL_DAYS = 14
MAX_MESSAGE_LENGTH = 10000  # Max chars per message to prevent injection attacks


def get_conversation_history(conversation_id: str) -> list[dict[str, Any]]:
    """
    Retrieve the last N conversation turns from DynamoDB.

    Args:
        conversation_id (str): The conversation ID

    Returns:
        list[dict]: Previous conversation turns in chronological order
    """
    from boto3.dynamodb.conditions import Key

    conversation_table_name = os.environ.get("CONVERSATION_TABLE_NAME")
    if not conversation_table_name or not conversation_id:
        return []

    table = dynamodb.Table(conversation_table_name)

    try:
        from boto3.dynamodb.conditions import Attr

        response = table.query(
            KeyConditionExpression=Key("conversationId").eq(conversation_id),
            FilterExpression=Attr("status").ne("PENDING") | Attr("status").not_exists(),
            ScanIndexForward=False,  # Descending order (newest first)
            ProjectionExpression="turnNumber, userMessage, assistantResponse, #s",
            ExpressionAttributeNames={"#s": "status"},
        )

        # Trim to MAX_HISTORY_TURNS after filtering (Limit caps scanned rows,
        # not returned rows, so filtering + Limit can return fewer than expected)
        items: list[dict[str, Any]] = response.get("Items", [])[:MAX_HISTORY_TURNS]
        for item in items:
            if "turnNumber" in item and isinstance(item["turnNumber"], Decimal):
                item["turnNumber"] = int(item["turnNumber"])
        items.reverse()
        return items
    except ClientError as e:
        logger.error(f"Failed to retrieve conversation history: {e}")
        return []


def store_conversation_turn(
    conversation_id: str,
    turn_number: int,
    user_message: str,
    assistant_response: str,
    sources: list[SourceInfo],
    user_id: str | None = None,
) -> None:
    """
    Store a conversation turn in DynamoDB.

    Args:
        conversation_id (str): The conversation ID
        turn_number (int): The turn number (1-indexed)
        user_message (str): The user's original query
        assistant_response (str): The assistant's response
        sources (list): The source documents used
        user_id (str | None): The user ID for ownership scoping
    """
    conversation_table_name = os.environ.get("CONVERSATION_TABLE_NAME")
    if not conversation_table_name or not conversation_id:
        return

    table = dynamodb.Table(conversation_table_name)

    # Calculate TTL (14 days from now)
    ttl = int(datetime.now(UTC).timestamp()) + (CONVERSATION_TTL_DAYS * 86400)

    item: dict[str, Any] = {
        "conversationId": conversation_id,
        "turnNumber": turn_number,
        "userMessage": user_message,
        "assistantResponse": assistant_response,
        "sources": json.dumps(sources),  # Store as JSON string
        "status": "COMPLETED",
        "createdAt": datetime.now(UTC).isoformat(),
        "ttl": ttl,
    }
    if user_id:
        item["userId"] = user_id

    try:
        table.put_item(Item=item)
        logger.info(f"Stored turn {turn_number} for conversation {conversation_id[:8]}...")
    except ClientError as e:
        logger.error(f"Failed to store conversation turn: {e}")


def update_conversation_turn(
    conversation_id: str,
    turn_number: int,
    status: str,
    assistant_response: str = "",
    sources: list[SourceInfo] | None = None,
    error_message: str | None = None,
) -> None:
    """
    Update an existing conversation turn with the async result.

    Args:
        conversation_id: The conversation ID
        turn_number: The turn number to update
        status: "COMPLETED" or "ERROR"
        assistant_response: The assistant's response (for COMPLETED)
        sources: The source documents used (for COMPLETED)
        error_message: Error details (for ERROR)
    """
    conversation_table_name = os.environ.get("CONVERSATION_TABLE_NAME")
    if not conversation_table_name or not conversation_id:
        return

    table = dynamodb.Table(conversation_table_name)

    update_expr = "SET #status = :status, assistantResponse = :response, sources = :sources"
    expr_values: dict[str, Any] = {
        ":status": status,
        ":response": assistant_response,
        ":sources": json.dumps(sources or []),
    }
    expr_names = {"#status": "status"}

    if error_message:
        update_expr += ", errorMessage = :error"
        expr_values[":error"] = error_message

    try:
        table.update_item(
            Key={
                "conversationId": conversation_id,
                "turnNumber": turn_number,
            },
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
        )
        logger.info(f"Updated turn {turn_number} for {conversation_id[:8]}... to {status}")
    except ClientError as e:
        logger.error(f"Failed to update conversation turn: {e}")
