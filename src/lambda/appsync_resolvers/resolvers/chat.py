"""Chat resolver functions for AppSync Lambda handler.

Handles async chat (queryKnowledgeBase, getConversation) operations.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError

from ragstack_common.storage import is_valid_uuid
from resolvers.shared import (
    CONVERSATION_TABLE_NAME,
    QUERY_KB_FUNCTION_ARN,
    dynamodb,
    get_current_event,
    lambda_client,
)

logger = logging.getLogger()


def query_knowledge_base(args: dict[str, Any]) -> dict[str, Any]:
    """
    Async mutation resolver: validate input, write PENDING record, async-invoke QueryKBFunction.

    Args:
        args: GraphQL arguments with query, conversationId, requestId

    Returns:
        ChatRequest dict with conversationId, requestId, status="PENDING"
    """
    from boto3.dynamodb.conditions import Key

    # Validate required arguments
    query = args.get("query", "")
    conversation_id = args.get("conversationId", "")
    request_id = args.get("requestId", "")

    if not query or not query.strip():
        raise ValueError("Missing required argument: query")
    if not conversation_id or not conversation_id.strip():
        raise ValueError("Missing required argument: conversationId")
    if not is_valid_uuid(conversation_id):
        raise ValueError("Invalid conversationId: must be a valid UUID")
    if not request_id or not request_id.strip():
        raise ValueError("Missing required argument: requestId")
    if not is_valid_uuid(request_id):
        raise ValueError("Invalid requestId: must be a valid UUID")
    if len(query) > 10000:
        raise ValueError("Query exceeds maximum length of 10000 characters")

    if not CONVERSATION_TABLE_NAME:
        raise ValueError("CONVERSATION_TABLE_NAME environment variable is not configured")
    conversation_table_name: str = CONVERSATION_TABLE_NAME

    if not QUERY_KB_FUNCTION_ARN:
        raise ValueError("QUERY_KB_FUNCTION_ARN environment variable is not configured")
    query_kb_function_arn: str = QUERY_KB_FUNCTION_ARN

    # Extract user identity for scoping conversations
    identity = get_current_event().get("identity") if get_current_event() else None
    user_id = None
    if identity:
        user_id = identity.get("sub") or identity.get("username")

    try:
        # Write PENDING record to ConversationHistoryTable
        table = dynamodb.Table(conversation_table_name)

        # Determine turn number by querying existing turns, then write with
        # a condition to prevent concurrent requests from assigning the same turn.
        # Retry with incremented turn number on conflict.
        response = table.query(
            KeyConditionExpression=Key("conversationId").eq(conversation_id),
            ScanIndexForward=False,
            Limit=1,
            ProjectionExpression="turnNumber",
        )
        existing_items = response.get("Items", [])
        next_turn = int(str(existing_items[0].get("turnNumber", 0))) + 1 if existing_items else 1

        ttl = int(datetime.now(UTC).timestamp()) + (14 * 86400)  # 14 day TTL

        max_retries = 3
        for attempt in range(max_retries):
            try:
                item: dict[str, Any] = {
                    "conversationId": conversation_id,
                    "turnNumber": next_turn + attempt,
                    "requestId": request_id,
                    "status": "PENDING",
                    "userMessage": query,
                    "assistantResponse": "",
                    "sources": "[]",
                    "createdAt": datetime.now(UTC).isoformat(),
                    "ttl": ttl,
                }
                if user_id:
                    item["userId"] = user_id
                table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(turnNumber)",
                )
                next_turn = next_turn + attempt
                break
            except ClientError as ce:
                is_conflict = ce.response["Error"]["Code"] == "ConditionalCheckFailedException"
                if is_conflict and attempt < max_retries - 1:
                    continue
                raise

        # Async-invoke QueryKBFunction
        invoke_event = {
            "arguments": {
                "query": query,
                "conversationId": conversation_id,
            },
            "requestId": request_id,
            "turnNumber": next_turn,
            "identity": identity,
            "asyncInvocation": True,
        }
        try:
            lambda_client.invoke(
                FunctionName=query_kb_function_arn,
                InvocationType="Event",
                Payload=json.dumps(invoke_event).encode(),
            )
        except ClientError as invoke_err:
            # Clean up orphaned PENDING record if async invoke fails
            try:
                table.delete_item(
                    Key={
                        "conversationId": conversation_id,
                        "turnNumber": next_turn,
                    }
                )
            except ClientError:
                logger.warning(
                    f"Failed to clean up PENDING turn {next_turn} "
                    f"for conversation {conversation_id}"
                )
            logger.error(f"Async invoke failed: {invoke_err}")
            raise ValueError("Failed to submit chat query. Please try again.") from invoke_err

        return {
            "conversationId": conversation_id,
            "requestId": request_id,
            "status": "PENDING",
        }

    except ClientError as e:
        logger.error(f"Failed to process queryKnowledgeBase mutation: {e}")
        raise ValueError("Failed to submit chat query. Please try again.") from e


def get_conversation(args: dict[str, Any]) -> dict[str, Any]:
    """
    Query resolver: read all turns for a conversationId from ConversationHistoryTable.
    Scoped to the requesting user when authenticated.

    Args:
        args: GraphQL arguments with conversationId

    Returns:
        Conversation dict with conversationId and turns array
    """
    from boto3.dynamodb.conditions import Key

    conversation_id = args.get("conversationId", "")
    if not conversation_id or not conversation_id.strip():
        raise ValueError("Missing required argument: conversationId")
    if not is_valid_uuid(conversation_id):
        raise ValueError("Invalid conversationId: must be a valid UUID")

    if not CONVERSATION_TABLE_NAME:
        raise ValueError("CONVERSATION_TABLE_NAME environment variable is not configured")
    conv_table_name: str = CONVERSATION_TABLE_NAME

    # Extract requesting user for ownership check
    identity = get_current_event().get("identity") if get_current_event() else None
    requesting_user_id = None
    if identity:
        requesting_user_id = identity.get("sub") or identity.get("username")

    table = dynamodb.Table(conv_table_name)

    # Paginate to handle conversations exceeding DynamoDB's 1 MB page limit
    all_items: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any] = {
        "KeyConditionExpression": Key("conversationId").eq(conversation_id),
        "ScanIndexForward": True,
    }
    while True:
        response = table.query(**query_kwargs)
        all_items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    turns = []
    for item in all_items:
        # Verify ownership: if the turn has a userId, deny access to
        # unauthenticated callers or callers whose id doesn't match
        item_user_id = item.get("userId")
        if item_user_id and (not requesting_user_id or str(item_user_id) != requesting_user_id):
            return {"conversationId": conversation_id, "turns": []}

        turn: dict[str, Any] = {
            "turnNumber": int(str(item.get("turnNumber", 0))),
            "requestId": item.get("requestId"),
            "status": str(item.get("status", "COMPLETED")),
            "userMessage": str(item.get("userMessage", "")),
            "assistantResponse": item.get("assistantResponse"),
            "sources": None,
            "error": item.get("errorMessage"),
            "createdAt": str(item.get("createdAt", "")),
        }
        # Parse sources from JSON string to list
        sources_raw = item.get("sources", "[]")
        sources_json = str(sources_raw) if sources_raw is not None else "[]"
        if sources_json and sources_json != "[]":
            try:
                turn["sources"] = json.loads(sources_json)
            except (json.JSONDecodeError, TypeError):
                turn["sources"] = []
        else:
            turn["sources"] = []
        turns.append(turn)

    return {
        "conversationId": conversation_id,
        "turns": turns,
    }
