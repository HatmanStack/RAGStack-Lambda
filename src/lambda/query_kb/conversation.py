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

from _clients import dynamodb
from botocore.exceptions import ClientError

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
        response = table.query(
            KeyConditionExpression=Key("conversationId").eq(conversation_id),
            ScanIndexForward=False,  # Descending order (newest first)
            Limit=MAX_HISTORY_TURNS,
            ProjectionExpression="turnNumber, userMessage, assistantResponse",
        )

        # Reverse to chronological order and convert Decimal to int
        items = response.get("Items", [])
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
    sources: list[dict[str, Any]],
) -> None:
    """
    Store a conversation turn in DynamoDB.

    Args:
        conversation_id (str): The conversation ID
        turn_number (int): The turn number (1-indexed)
        user_message (str): The user's original query
        assistant_response (str): The assistant's response
        sources (list): The source documents used
    """
    conversation_table_name = os.environ.get("CONVERSATION_TABLE_NAME")
    if not conversation_table_name or not conversation_id:
        return

    table = dynamodb.Table(conversation_table_name)

    # Calculate TTL (14 days from now)
    ttl = int(datetime.now(UTC).timestamp()) + (CONVERSATION_TTL_DAYS * 86400)

    try:
        table.put_item(
            Item={
                "conversationId": conversation_id,
                "turnNumber": turn_number,
                "userMessage": user_message,
                "assistantResponse": assistant_response,
                "sources": json.dumps(sources),  # Store as JSON string
                "createdAt": datetime.now(UTC).isoformat(),
                "ttl": ttl,
            }
        )
        logger.info(f"Stored turn {turn_number} for conversation {conversation_id[:8]}...")
    except ClientError as e:
        logger.error(f"Failed to store conversation turn: {e}")
