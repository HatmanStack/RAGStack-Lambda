"""Unit tests for DLQ Replay Lambda."""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_dlq_replay_module():
    """Load the dlq_replay index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src"
        / "lambda"
        / "dlq_replay"
        / "index.py"
    ).resolve()
    spec = importlib.util.spec_from_file_location("dlq_replay_index", str(module_path))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dlq_replay_index"] = module
    spec.loader.exec_module(module)
    return module


ENV_VARS = {
    "PROCESSING_DLQ_URL": "https://sqs.us-east-1.amazonaws.com/123/processing-dlq",
    "PROCESSING_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/processing",
    "BATCH_DLQ_URL": "https://sqs.us-east-1.amazonaws.com/123/batch-dlq",
    "BATCH_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/batch",
    "SCRAPE_DISCOVERY_DLQ_URL": "https://sqs.us-east-1.amazonaws.com/123/scrape-disc-dlq",
    "SCRAPE_DISCOVERY_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/scrape-disc",
    "SCRAPE_PROCESSING_DLQ_URL": "https://sqs.us-east-1.amazonaws.com/123/scrape-proc-dlq",
    "SCRAPE_PROCESSING_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/scrape-proc",
    "SYNC_DLQ_URL": "https://sqs.us-east-1.amazonaws.com/123/sync-dlq.fifo",
    "SYNC_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/sync.fifo",
}


@pytest.fixture(autouse=True)
def set_env_vars():
    with patch.dict(os.environ, ENV_VARS):
        yield


@pytest.fixture()
def mock_sqs():
    with patch("boto3.client") as mock_boto:
        client = MagicMock()
        mock_boto.return_value = client
        # Reset the module-level client cache
        module = load_dlq_replay_module()
        module.sqs_client = None
        yield client, module


class TestDlqReplay:
    def test_replay_standard_queue(self, mock_sqs):
        """Happy path: replay 3 messages from a standard queue."""
        client, module = mock_sqs

        messages = [
            {
                "MessageId": f"msg-{i}",
                "Body": f'{{"doc_id": "doc-{i}"}}',
                "ReceiptHandle": f"handle-{i}",
            }
            for i in range(3)
        ]

        # First call returns messages, second returns empty
        client.receive_message.side_effect = [
            {"Messages": messages},
            {"Messages": []},
        ]

        result = module.lambda_handler({"dlq_name": "processing"}, None)

        assert result == {"replayed": 3, "failed": 0}
        assert client.send_message.call_count == 3
        assert client.delete_message.call_count == 3

        # Verify send was to the source queue
        send_call = client.send_message.call_args_list[0]
        assert send_call.kwargs["QueueUrl"] == ENV_VARS["PROCESSING_QUEUE_URL"]

    def test_fifo_queue_includes_group_id(self, mock_sqs):
        """FIFO queue replay includes MessageGroupId."""
        client, module = mock_sqs

        messages = [
            {
                "MessageId": "msg-fifo-1",
                "Body": '{"sync": true}',
                "ReceiptHandle": "handle-1",
                "Attributes": {
                    "MessageGroupId": "sync-group",
                    "MessageDeduplicationId": "dedup-1",
                },
            }
        ]

        client.receive_message.side_effect = [
            {"Messages": messages},
            {"Messages": []},
        ]

        result = module.lambda_handler({"dlq_name": "sync"}, None)

        assert result == {"replayed": 1, "failed": 0}
        send_call = client.send_message.call_args
        assert send_call.kwargs["MessageGroupId"] == "sync-group"
        assert send_call.kwargs["MessageDeduplicationId"] == "dedup-1"
        assert send_call.kwargs["QueueUrl"] == ENV_VARS["SYNC_QUEUE_URL"]

    def test_empty_dlq(self, mock_sqs):
        """Empty DLQ returns zero counts."""
        client, module = mock_sqs
        client.receive_message.return_value = {"Messages": []}

        result = module.lambda_handler({"dlq_name": "batch"}, None)

        assert result == {"replayed": 0, "failed": 0}

    def test_invalid_dlq_name(self, mock_sqs):
        """Invalid dlq_name raises ValueError."""
        _, module = mock_sqs

        with pytest.raises(ValueError, match="Invalid dlq_name"):
            module.lambda_handler({"dlq_name": "nonexistent"}, None)

    def test_send_failure_not_deleted(self, mock_sqs):
        """Failed send does not delete message from DLQ."""
        client, module = mock_sqs

        messages = [
            {
                "MessageId": "msg-fail",
                "Body": '{"test": true}',
                "ReceiptHandle": "handle-fail",
            }
        ]

        client.receive_message.side_effect = [
            {"Messages": messages},
            {"Messages": []},
        ]
        client.send_message.side_effect = Exception("Send failed")

        result = module.lambda_handler({"dlq_name": "processing"}, None)

        assert result == {"replayed": 0, "failed": 1}
        client.delete_message.assert_not_called()

    def test_max_iterations_stops(self, mock_sqs):
        """Replay stops after MAX_ITERATIONS even if messages remain."""
        client, module = mock_sqs
        module.MAX_ITERATIONS = 2  # Override for test

        messages = [
            {
                "MessageId": "msg-loop",
                "Body": "{}",
                "ReceiptHandle": "handle-loop",
            }
        ]

        # Always return messages (never empty)
        client.receive_message.return_value = {"Messages": messages}

        result = module.lambda_handler({"dlq_name": "processing"}, None)

        # 2 iterations x 1 message each = 2 replayed
        assert result["replayed"] == 2
        assert client.receive_message.call_count == 2

    def test_message_attributes_forwarded(self, mock_sqs):
        """Message attributes are forwarded to the source queue."""
        client, module = mock_sqs

        messages = [
            {
                "MessageId": "msg-attrs",
                "Body": "{}",
                "ReceiptHandle": "handle-attrs",
                "MessageAttributes": {
                    "CustomAttr": {
                        "StringValue": "test-value",
                        "DataType": "String",
                    }
                },
            }
        ]

        client.receive_message.side_effect = [
            {"Messages": messages},
            {"Messages": []},
        ]

        module.lambda_handler({"dlq_name": "scrape-discovery"}, None)

        send_call = client.send_message.call_args
        assert "MessageAttributes" in send_call.kwargs
        assert send_call.kwargs["MessageAttributes"]["CustomAttr"]["StringValue"] == "test-value"
