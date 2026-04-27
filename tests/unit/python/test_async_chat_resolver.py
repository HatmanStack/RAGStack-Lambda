"""Unit tests for async chat resolvers (queryKnowledgeBase mutation and getConversation query)."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class MockClientError(Exception):
    """Minimal ClientError stand-in with .response attribute for exception handling."""

    def __init__(self, code: str = "UnknownError", message: str = ""):
        super().__init__(message or code)
        self.response = {"Error": {"Code": code}}


# Add Lambda source directory to path
sys.path.insert(0, str(Path(__file__).parents[3] / "src" / "lambda" / "appsync_resolvers"))


@pytest.fixture(autouse=True)
def _mock_dependencies():
    """Mock boto3 and ragstack_common dependencies to avoid AWS initialization."""
    mock_dynamodb_resource = MagicMock()
    mock_lambda_client = MagicMock()
    mock_s3_client = MagicMock()
    mock_sfn_client = MagicMock()
    mock_bedrock_agent = MagicMock()
    mock_bedrock_runtime = MagicMock()
    mock_dynamodb_client = MagicMock()

    mock_boto3 = MagicMock()
    mock_boto3.resource.return_value = mock_dynamodb_resource
    mock_boto3.client.side_effect = lambda service, **_kwargs: {
        "lambda": mock_lambda_client,
        "s3": mock_s3_client,
        "stepfunctions": mock_sfn_client,
        "bedrock-agent": mock_bedrock_agent,
        "bedrock-runtime": mock_bedrock_runtime,
        "dynamodb": mock_dynamodb_client,
    }.get(service, MagicMock())

    mock_config_manager = MagicMock()
    mock_config_manager.get_parameter.return_value = False

    # Mock ragstack_common modules
    mock_auth = MagicMock()
    mock_auth.check_public_access.return_value = (True, None)

    mock_config = MagicMock()
    mock_config.ConfigurationManager.return_value = mock_config_manager
    mock_config.get_knowledge_base_config.return_value = ("kb-id", "ds-id")

    mock_demo = MagicMock()
    mock_demo.is_demo_mode_enabled.return_value = False
    mock_demo.DemoModeError = type("DemoModeError", (Exception,), {"message": ""})
    mock_demo.check_demo_mode_feature_allowed.return_value = None
    mock_demo.demo_quota_check_and_increment.return_value = None
    mock_demo.get_demo_upload_conditions.return_value = {}

    mock_filter_examples = MagicMock()
    mock_image_mod = MagicMock()
    mock_image_mod.is_supported_image.return_value = True
    mock_ingestion = MagicMock()
    mock_key_library = MagicMock()
    mock_metadata_extractor = MagicMock()
    mock_scraper = MagicMock()
    mock_storage = MagicMock()
    mock_storage.is_valid_uuid.return_value = True
    mock_types = MagicMock()

    with (
        patch.dict(
            "sys.modules",
            {
                "boto3": mock_boto3,
                "boto3.dynamodb": MagicMock(),
                "boto3.dynamodb.conditions": MagicMock(),
                "botocore": MagicMock(),
                "botocore.exceptions": MagicMock(ClientError=MockClientError),
                "ragstack_common": MagicMock(),
                "ragstack_common.auth": mock_auth,
                "ragstack_common.config": mock_config,
                "ragstack_common.demo_mode": mock_demo,
                "ragstack_common.filter_examples": mock_filter_examples,
                "ragstack_common.image": mock_image_mod,
                "ragstack_common.ingestion": mock_ingestion,
                "ragstack_common.key_library": mock_key_library,
                "ragstack_common.metadata_extractor": mock_metadata_extractor,
                "ragstack_common.scraper": mock_scraper,
                "ragstack_common.storage": mock_storage,
                "ragstack_common.types": mock_types,
                "ragstack_common.sources": MagicMock(),
            },
        ),
        patch.dict(
            "os.environ",
            {
                "TRACKING_TABLE": "test-tracking",
                "DATA_BUCKET": "test-bucket",
                "QUERY_KB_FUNCTION_ARN": (
                    "arn:aws:lambda:us-east-1:123456789:function:test-query-kb"
                ),
                "CONVERSATION_TABLE_NAME": "test-conversation-table",
            },
        ),
    ):
        # Clear cached modules so they reimport with mocks
        for mod_name in list(sys.modules):
            if mod_name == "index" or mod_name.startswith("resolvers"):
                del sys.modules[mod_name]

        # Ensure our path is at the front of sys.path
        appsync_path = str(Path(__file__).parents[3] / "src" / "lambda" / "appsync_resolvers")
        old_path = sys.path[:]
        # Remove any query_kb path entries that could shadow our import
        sys.path = [p for p in sys.path if "query_kb" not in p]
        if appsync_path not in sys.path:
            sys.path.insert(0, appsync_path)

        import importlib

        import index

        importlib.reload(index)

        # Make mocks accessible to tests
        index._test_dynamodb = mock_dynamodb_resource
        index._test_lambda_client = mock_lambda_client
        index._test_auth = mock_auth

        yield index

        # Cleanup
        sys.path = old_path
        for mod_name in list(sys.modules):
            if mod_name == "index" or mod_name.startswith("resolvers"):
                del sys.modules[mod_name]


class TestQueryKnowledgeBaseMutation:
    """Tests for the queryKnowledgeBase mutation resolver."""

    def test_valid_mutation_returns_pending_status(self, _mock_dependencies):
        """Valid mutation returns ChatRequest with PENDING status."""
        index = _mock_dependencies

        # Setup mock table
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        index._test_dynamodb.Table.return_value = mock_table

        args = {
            "query": "What is the capital of France?",
            "conversationId": "conv-123",
            "requestId": "req-456",
        }

        result = index.query_knowledge_base(args)

        assert result["conversationId"] == "conv-123"
        assert result["requestId"] == "req-456"
        assert result["status"] == "PENDING"

    def test_missing_query_raises_error(self, _mock_dependencies):
        """Missing query argument raises ValueError."""
        index = _mock_dependencies
        args = {
            "conversationId": "conv-123",
            "requestId": "req-456",
        }

        with pytest.raises(ValueError, match="query"):
            index.query_knowledge_base(args)

    def test_missing_conversation_id_raises_error(self, _mock_dependencies):
        """Missing conversationId argument raises ValueError."""
        index = _mock_dependencies
        args = {
            "query": "test query",
            "requestId": "req-456",
        }

        with pytest.raises(ValueError, match="conversationId"):
            index.query_knowledge_base(args)

    def test_missing_request_id_raises_error(self, _mock_dependencies):
        """Missing requestId argument raises ValueError."""
        index = _mock_dependencies
        args = {
            "query": "test query",
            "conversationId": "conv-123",
        }

        with pytest.raises(ValueError, match="requestId"):
            index.query_knowledge_base(args)

    def test_dynamodb_put_item_called_with_pending_record(self, _mock_dependencies):
        """DynamoDB put_item is called with correct PENDING record shape."""
        index = _mock_dependencies

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        index._test_dynamodb.Table.return_value = mock_table

        args = {
            "query": "test query",
            "conversationId": "conv-123",
            "requestId": "req-456",
        }

        index.query_knowledge_base(args)

        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["conversationId"] == "conv-123"
        assert item["requestId"] == "req-456"
        assert item["status"] == "PENDING"
        assert item["userMessage"] == "test query"
        assert item["assistantResponse"] == ""
        assert item["sources"] == "[]"
        assert "createdAt" in item
        assert "ttl" in item
        assert item["turnNumber"] == 1

    def test_lambda_invoke_called_with_async_payload(self, _mock_dependencies):
        """Lambda invoke is called with correct payload including asyncInvocation flag."""
        index = _mock_dependencies

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        index._test_dynamodb.Table.return_value = mock_table

        # Set identity via shared module's current event
        from resolvers.shared import set_current_event

        set_current_event({"identity": {"sub": "user-123"}})

        args = {
            "query": "test query",
            "conversationId": "conv-123",
            "requestId": "req-456",
        }

        index.query_knowledge_base(args)

        index._test_lambda_client.invoke.assert_called_once()
        call_kwargs = index._test_lambda_client.invoke.call_args[1]
        assert call_kwargs["InvocationType"] == "Event"
        expected_arn = "arn:aws:lambda:us-east-1:123456789:function:test-query-kb"
        assert call_kwargs["FunctionName"] == expected_arn

        payload = json.loads(call_kwargs["Payload"])
        assert payload["asyncInvocation"] is True
        assert payload["requestId"] == "req-456"
        assert payload["turnNumber"] == 1
        assert payload["arguments"]["query"] == "test query"
        assert payload["arguments"]["conversationId"] == "conv-123"
        assert payload["identity"] == {"sub": "user-123"}

    def test_turn_number_increments_from_existing(self, _mock_dependencies):
        """Turn number is calculated from existing turns."""
        index = _mock_dependencies

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [{"turnNumber": 3}]}
        index._test_dynamodb.Table.return_value = mock_table

        args = {
            "query": "test query",
            "conversationId": "conv-123",
            "requestId": "req-456",
        }

        index.query_knowledge_base(args)

        item = mock_table.put_item.call_args[1]["Item"]
        assert item["turnNumber"] == 4

    def test_public_access_denied_raises_error(self, _mock_dependencies):
        """Public access denied raises ValueError via lambda_handler."""
        index = _mock_dependencies

        # Set check_public_access to deny
        index._test_auth.check_public_access.return_value = (False, "Chat access is disabled")

        event = {
            "info": {"fieldName": "queryKnowledgeBase"},
            "arguments": {
                "query": "test",
                "conversationId": "conv-123",
                "requestId": "req-456",
            },
            "identity": None,
        }

        with pytest.raises(ValueError, match="Chat access is disabled"):
            index.lambda_handler(event, None)

    def test_query_too_long_raises_error(self, _mock_dependencies):
        """Query exceeding 10000 characters raises ValueError."""
        index = _mock_dependencies

        args = {
            "query": "x" * 10001,
            "conversationId": "conv-123",
            "requestId": "req-456",
        }

        with pytest.raises(ValueError, match="10000"):
            index.query_knowledge_base(args)

    def test_conditional_put_retries_on_conflict(self, _mock_dependencies):
        """ConditionalCheckFailedException retries with incremented turn number."""
        index = _mock_dependencies

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [{"turnNumber": 1}]}
        index._test_dynamodb.Table.return_value = mock_table

        conflict_error = MockClientError("ConditionalCheckFailedException")

        # First two puts fail with conflict, third succeeds
        mock_table.put_item.side_effect = [conflict_error, conflict_error, None]

        args = {
            "query": "test query",
            "conversationId": "conv-123",
            "requestId": "req-456",
        }

        result = index.query_knowledge_base(args)

        assert result["status"] == "PENDING"
        assert mock_table.put_item.call_count == 3
        # First attempt: turn 2, second: turn 3, third: turn 4
        put_calls = mock_table.put_item.call_args_list
        assert put_calls[0][1]["Item"]["turnNumber"] == 2
        assert put_calls[1][1]["Item"]["turnNumber"] == 3
        assert put_calls[2][1]["Item"]["turnNumber"] == 4

    def test_conditional_put_raises_after_max_retries(self, _mock_dependencies):
        """ConditionalCheckFailedException raises after 3 attempts."""
        index = _mock_dependencies

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [{"turnNumber": 1}]}
        index._test_dynamodb.Table.return_value = mock_table

        conflict_error = MockClientError("ConditionalCheckFailedException")
        mock_table.put_item.side_effect = [conflict_error, conflict_error, conflict_error]

        args = {
            "query": "test query",
            "conversationId": "conv-123",
            "requestId": "req-456",
        }

        # After 3 conflicts, the outer except ClientError catches and wraps as ValueError
        with pytest.raises(ValueError, match="Failed to submit chat query"):
            index.query_knowledge_base(args)

        assert mock_table.put_item.call_count == 3


class TestGetConversation:
    """Tests for the getConversation query resolver."""

    def test_returns_conversation_with_multiple_turns(self, _mock_dependencies):
        """Returns conversation with multiple turns in chronological order."""
        index = _mock_dependencies

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "conversationId": "conv-123",
                    "turnNumber": 1,
                    "requestId": "req-1",
                    "status": "COMPLETED",
                    "userMessage": "Hello",
                    "assistantResponse": "Hi there!",
                    "sources": "[]",
                    "createdAt": "2024-01-01T00:00:00",
                },
                {
                    "conversationId": "conv-123",
                    "turnNumber": 2,
                    "requestId": "req-2",
                    "status": "COMPLETED",
                    "userMessage": "How are you?",
                    "assistantResponse": "I'm good!",
                    "sources": "[]",
                    "createdAt": "2024-01-01T00:01:00",
                },
            ]
        }
        index._test_dynamodb.Table.return_value = mock_table

        result = index.get_conversation({"conversationId": "conv-123"})

        assert result["conversationId"] == "conv-123"
        assert len(result["turns"]) == 2
        assert result["turns"][0]["turnNumber"] == 1
        assert result["turns"][1]["turnNumber"] == 2

    def test_empty_conversation_returns_empty_turns(self, _mock_dependencies):
        """Empty conversation returns empty turns array."""
        index = _mock_dependencies

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        index._test_dynamodb.Table.return_value = mock_table

        result = index.get_conversation({"conversationId": "conv-123"})

        assert result["conversationId"] == "conv-123"
        assert result["turns"] == []

    def test_pending_turn_has_null_response(self, _mock_dependencies):
        """PENDING turn has null assistantResponse and empty sources."""
        index = _mock_dependencies

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "conversationId": "conv-123",
                    "turnNumber": 1,
                    "requestId": "req-1",
                    "status": "PENDING",
                    "userMessage": "Hello",
                    "assistantResponse": "",
                    "sources": "[]",
                    "createdAt": "2024-01-01T00:00:00",
                },
            ]
        }
        index._test_dynamodb.Table.return_value = mock_table

        result = index.get_conversation({"conversationId": "conv-123"})

        turn = result["turns"][0]
        assert turn["status"] == "PENDING"
        assert turn["assistantResponse"] == ""
        assert turn["sources"] == []

    def test_completed_turn_has_parsed_sources(self, _mock_dependencies):
        """COMPLETED turn has parsed sources array."""
        index = _mock_dependencies

        sources_json = json.dumps(
            [{"documentId": "doc-1", "s3Uri": "s3://bucket/doc1", "snippet": "test snippet"}]
        )

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "conversationId": "conv-123",
                    "turnNumber": 1,
                    "status": "COMPLETED",
                    "userMessage": "Hello",
                    "assistantResponse": "Hi!",
                    "sources": sources_json,
                    "createdAt": "2024-01-01T00:00:00",
                },
            ]
        }
        index._test_dynamodb.Table.return_value = mock_table

        result = index.get_conversation({"conversationId": "conv-123"})

        turn = result["turns"][0]
        assert len(turn["sources"]) == 1
        assert turn["sources"][0]["documentId"] == "doc-1"

    def test_error_turn_includes_error_message(self, _mock_dependencies):
        """ERROR turn includes errorMessage."""
        index = _mock_dependencies

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "conversationId": "conv-123",
                    "turnNumber": 1,
                    "status": "ERROR",
                    "userMessage": "Hello",
                    "assistantResponse": "",
                    "sources": "[]",
                    "errorMessage": "Something went wrong",
                    "createdAt": "2024-01-01T00:00:00",
                },
            ]
        }
        index._test_dynamodb.Table.return_value = mock_table

        result = index.get_conversation({"conversationId": "conv-123"})

        turn = result["turns"][0]
        assert turn["status"] == "ERROR"
        assert turn["error"] == "Something went wrong"

    def test_legacy_turns_default_to_completed(self, _mock_dependencies):
        """Legacy turns without status attribute default to COMPLETED."""
        index = _mock_dependencies

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "conversationId": "conv-123",
                    "turnNumber": 1,
                    "userMessage": "Hello",
                    "assistantResponse": "Hi!",
                    "sources": "[]",
                    "createdAt": "2024-01-01T00:00:00",
                    # No status or requestId fields (legacy)
                },
            ]
        }
        index._test_dynamodb.Table.return_value = mock_table

        result = index.get_conversation({"conversationId": "conv-123"})

        turn = result["turns"][0]
        assert turn["status"] == "COMPLETED"
        assert turn["requestId"] is None

    def test_missing_conversation_id_raises_error(self, _mock_dependencies):
        """Missing conversationId raises ValueError."""
        index = _mock_dependencies

        with pytest.raises(ValueError, match="conversationId"):
            index.get_conversation({})
