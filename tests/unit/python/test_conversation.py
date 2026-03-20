"""Unit tests for conversation.py update_conversation_turn function."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add Lambda source directory to path
sys.path.insert(0, str(Path(__file__).parents[3] / "src" / "lambda" / "query_kb"))


@pytest.fixture(autouse=True)
def _mock_dependencies():
    """Mock boto3 and ragstack_common dependencies."""
    mock_dynamodb = MagicMock()
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    # Mock the _clients module
    mock_clients = MagicMock()
    mock_clients.dynamodb = mock_dynamodb

    mock_types = MagicMock()

    with (
        patch.dict(
            "sys.modules",
            {
                "boto3": MagicMock(),
                "boto3.dynamodb": MagicMock(),
                "boto3.dynamodb.conditions": MagicMock(),
                "botocore": MagicMock(),
                "botocore.exceptions": MagicMock(),
                "ragstack_common": MagicMock(),
                "ragstack_common.types": mock_types,
                "_clients": mock_clients,
            },
        ),
        patch.dict(
            "os.environ",
            {"CONVERSATION_TABLE_NAME": "test-conversation-table"},
        ),
    ):
        # Clear cached module
        for mod_name in list(sys.modules.keys()):
            if mod_name == "conversation" or mod_name.startswith("conversation."):
                del sys.modules[mod_name]

        import importlib

        import conversation

        importlib.reload(conversation)

        # Inject the mock for direct access
        conversation._test_dynamodb = mock_dynamodb
        conversation._test_table = mock_table

        yield conversation

        # Cleanup
        for mod_name in list(sys.modules.keys()):
            if mod_name == "conversation" or mod_name.startswith("conversation."):
                del sys.modules[mod_name]


class TestUpdateConversationTurn:
    """Tests for update_conversation_turn function."""

    def test_completed_status_writes_correct_attributes(self, _mock_dependencies):
        """update_conversation_turn with COMPLETED status writes correct attributes."""
        conversation = _mock_dependencies
        mock_table = conversation._test_table

        conversation.update_conversation_turn(
            conversation_id="conv-123",
            turn_number=1,
            status="COMPLETED",
            assistant_response="Hello!",
            sources=[{"documentId": "doc-1", "s3Uri": "s3://bucket/doc1"}],
        )

        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"conversationId": "conv-123", "turnNumber": 1}
        assert ":status" in call_kwargs["ExpressionAttributeValues"]
        assert call_kwargs["ExpressionAttributeValues"][":status"] == "COMPLETED"
        assert call_kwargs["ExpressionAttributeValues"][":response"] == "Hello!"
        sources = json.loads(call_kwargs["ExpressionAttributeValues"][":sources"])
        assert len(sources) == 1
        assert sources[0]["documentId"] == "doc-1"

    def test_error_status_includes_error_message(self, _mock_dependencies):
        """update_conversation_turn with ERROR status includes errorMessage."""
        conversation = _mock_dependencies
        mock_table = conversation._test_table

        conversation.update_conversation_turn(
            conversation_id="conv-123",
            turn_number=1,
            status="ERROR",
            error_message="Something went wrong",
        )

        mock_table.update_item.assert_called_once()
        call_kwargs = mock_table.update_item.call_args[1]
        assert "errorMessage" in call_kwargs["UpdateExpression"]
        assert call_kwargs["ExpressionAttributeValues"][":error"] == "Something went wrong"

    def test_missing_table_name_returns_without_error(self, _mock_dependencies):
        """update_conversation_turn with missing table name returns without error."""
        conversation = _mock_dependencies
        mock_table = conversation._test_table

        with patch.dict("os.environ", {}, clear=True):
            conversation.update_conversation_turn(
                conversation_id="conv-123",
                turn_number=1,
                status="COMPLETED",
                assistant_response="Hello!",
            )

        mock_table.update_item.assert_not_called()

    def test_missing_conversation_id_returns_without_error(self, _mock_dependencies):
        """update_conversation_turn with missing conversation_id returns without error."""
        conversation = _mock_dependencies
        mock_table = conversation._test_table

        conversation.update_conversation_turn(
            conversation_id="",
            turn_number=1,
            status="COMPLETED",
            assistant_response="Hello!",
        )

        mock_table.update_item.assert_not_called()
