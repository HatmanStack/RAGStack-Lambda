"""Unit tests for batch_processor Lambda."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_batch_processor_module():
    """Load the batch_processor index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src" / "lambda" / "batch_processor" / "index.py"
    ).resolve()

    if "batch_processor_index" in sys.modules:
        del sys.modules["batch_processor_index"]

    spec = importlib.util.spec_from_file_location("batch_processor_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["batch_processor_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    with patch.dict(
        os.environ,
        {
            "TRACKING_TABLE": "test-tracking-table",
            "COMBINE_PAGES_FUNCTION_ARN": "arn:aws:lambda:us-east-1:123:function:CombinePages",
            "AWS_REGION": "us-east-1",
            "CONFIGURATION_TABLE_NAME": "test-config-table",
        },
    ):
        yield


def _make_sqs_event(
    document_id="doc-123",
    batch_index=0,
    page_start=1,
    page_end=10,
    total_batches=5,
    total_pages=50,
):
    return {
        "Records": [
            {
                "messageId": "msg-001",
                "body": json.dumps({
                    "document_id": document_id,
                    "batch_index": batch_index,
                    "input_s3_uri": f"s3://bucket/input/{document_id}/report.pdf",
                    "output_s3_prefix": f"s3://bucket/content/{document_id}/",
                    "page_start": page_start,
                    "page_end": page_end,
                    "total_batches": total_batches,
                    "total_pages": total_pages,
                }),
            }
        ]
    }


class TestLambdaHandler:
    """Tests for lambda_handler."""

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("ragstack_common.ocr.OcrService")
    def test_happy_path_processes_batch(
        self, mock_ocr_class, mock_config_class, mock_resource, mock_client
    ):
        # Mock config manager
        mock_config = MagicMock()
        mock_config.get_parameter.side_effect = lambda key, default=None: {
            "ocr_backend": "textract",
            "bedrock_ocr_model_id": "model-id",
        }.get(key, default)
        mock_config_class.return_value = mock_config

        # Mock OCR service
        mock_doc = MagicMock()
        mock_doc.pages_succeeded = 10
        mock_doc.pages_failed = 0
        mock_doc.output_s3_uri = "s3://bucket/content/doc-123/pages_1-10.txt"
        mock_ocr = MagicMock()
        mock_ocr.process_document.return_value = mock_doc
        mock_ocr_class.return_value = mock_ocr

        # Mock DynamoDB
        mock_table = MagicMock()
        mock_table.update_item.return_value = {
            "Attributes": {
                "batches_remaining": 4,
                "pages_succeeded": 10,
                "pages_failed": 0,
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb

        mock_lambda = MagicMock()
        mock_client.return_value = mock_lambda

        module = load_batch_processor_module()
        with (
            patch.object(module, "dynamodb", mock_dynamodb),
            patch.object(module, "_config_manager", mock_config),
        ):
            result = module.lambda_handler(_make_sqs_event(), None)

        assert result["batchItemFailures"] == []
        mock_table.update_item.assert_called_once()

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("ragstack_common.ocr.OcrService")
    def test_last_batch_triggers_combine_pages(
        self, mock_ocr_class, mock_config_class, mock_resource, mock_client
    ):
        mock_config = MagicMock()
        mock_config.get_parameter.return_value = "textract"
        mock_config_class.return_value = mock_config

        mock_doc = MagicMock()
        mock_doc.pages_succeeded = 10
        mock_doc.pages_failed = 0
        mock_ocr = MagicMock()
        mock_ocr.process_document.return_value = mock_doc
        mock_ocr_class.return_value = mock_ocr

        mock_table = MagicMock()
        mock_table.update_item.return_value = {
            "Attributes": {
                "batches_remaining": 0,  # Last batch
                "pages_succeeded": 50,
                "pages_failed": 0,
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb

        mock_lambda = MagicMock()
        mock_client.return_value = mock_lambda

        module = load_batch_processor_module()
        with (
            patch.object(module, "dynamodb", mock_dynamodb),
            patch.object(module, "_config_manager", mock_config),
        ):
            result = module.lambda_handler(
                _make_sqs_event(batch_index=4, page_start=41, page_end=50), None
            )

        # CombinePages should be invoked
        mock_lambda.invoke.assert_called_once()
        call_kwargs = mock_lambda.invoke.call_args[1]
        assert call_kwargs["InvocationType"] == "Event"

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("ragstack_common.ocr.OcrService")
    def test_ocr_failure_marks_all_pages_failed(
        self, mock_ocr_class, mock_config_class, mock_resource, mock_client
    ):
        mock_config = MagicMock()
        mock_config.get_parameter.return_value = "textract"
        mock_config_class.return_value = mock_config

        mock_ocr = MagicMock()
        mock_ocr.process_document.side_effect = Exception("OCR crash")
        mock_ocr_class.return_value = mock_ocr

        mock_table = MagicMock()
        mock_table.update_item.return_value = {
            "Attributes": {
                "batches_remaining": 3,
                "pages_succeeded": 0,
                "pages_failed": 10,
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        mock_client.return_value = MagicMock()

        module = load_batch_processor_module()
        with (
            patch.object(module, "dynamodb", mock_dynamodb),
            patch.object(module, "_config_manager", mock_config),
        ):
            result = module.lambda_handler(_make_sqs_event(), None)

        # Should still update tracking (pages_failed = all 10)
        assert result["batchItemFailures"] == []
        # First call is the tracking update, second may be mark_failed
        first_call_kwargs = mock_table.update_item.call_args_list[0][1]
        assert first_call_kwargs["ExpressionAttributeValues"][":failed"] == 10
        assert first_call_kwargs["ExpressionAttributeValues"][":succeeded"] == 0

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("ragstack_common.ocr.OcrService")
    def test_threshold_impossible_marks_failed(
        self, mock_ocr_class, mock_config_class, mock_resource, mock_client
    ):
        mock_config = MagicMock()
        mock_config.get_parameter.return_value = "textract"
        mock_config_class.return_value = mock_config

        mock_doc = MagicMock()
        mock_doc.pages_succeeded = 0
        mock_doc.pages_failed = 10
        mock_ocr = MagicMock()
        mock_ocr.process_document.return_value = mock_doc
        mock_ocr_class.return_value = mock_ocr

        mock_table = MagicMock()
        # Simulate many failures: 40 of 50 pages failed, only 10 remaining
        # max possible = 0 + 10 = 10 out of 50 = 20% < 95%
        mock_table.update_item.return_value = {
            "Attributes": {
                "batches_remaining": 1,  # Not last batch
                "pages_succeeded": 0,
                "pages_failed": 40,
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        mock_client.return_value = MagicMock()

        module = load_batch_processor_module()
        with (
            patch.object(module, "dynamodb", mock_dynamodb),
            patch.object(module, "_config_manager", mock_config),
        ):
            result = module.lambda_handler(_make_sqs_event(), None)

        # Should call update_item a second time to mark as failed
        assert mock_table.update_item.call_count == 2

    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("ragstack_common.ocr.OcrService")
    def test_last_batch_below_threshold_marks_failed(
        self, mock_ocr_class, mock_config_class, mock_resource, mock_client
    ):
        mock_config = MagicMock()
        mock_config.get_parameter.return_value = "textract"
        mock_config_class.return_value = mock_config

        mock_doc = MagicMock()
        mock_doc.pages_succeeded = 0
        mock_doc.pages_failed = 10
        mock_ocr = MagicMock()
        mock_ocr.process_document.return_value = mock_doc
        mock_ocr_class.return_value = mock_ocr

        mock_table = MagicMock()
        mock_table.update_item.return_value = {
            "Attributes": {
                "batches_remaining": 0,  # Last batch
                "pages_succeeded": 10,  # Only 10/50 = 20%
                "pages_failed": 40,
            }
        }
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_resource.return_value = mock_dynamodb
        mock_client.return_value = MagicMock()

        module = load_batch_processor_module()
        with (
            patch.object(module, "dynamodb", mock_dynamodb),
            patch.object(module, "_config_manager", mock_config),
        ):
            result = module.lambda_handler(_make_sqs_event(), None)

        # Should mark as failed, not trigger CombinePages
        assert mock_table.update_item.call_count == 2  # tracking + mark_failed

    def test_missing_tracking_table_raises(self):
        with patch.dict(os.environ, {"TRACKING_TABLE": ""}):
            module = load_batch_processor_module()
            with pytest.raises(ValueError, match="TRACKING_TABLE"):
                module.lambda_handler(_make_sqs_event(), None)

    @patch("boto3.client")
    @patch("boto3.resource")
    def test_message_parse_error_reports_failure(self, mock_resource, mock_client):
        mock_resource.return_value = MagicMock()
        mock_client.return_value = MagicMock()

        module = load_batch_processor_module()
        event = {
            "Records": [
                {
                    "messageId": "msg-bad",
                    "body": "not valid json{",
                }
            ]
        }
        result = module.lambda_handler(event, None)
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-bad"
