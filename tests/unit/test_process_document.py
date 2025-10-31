"""
Unit tests for process_document Lambda function.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Set required environment variables BEFORE importing the module
os.environ["CONFIGURATION_TABLE_NAME"] = "test-config-table"
os.environ["TRACKING_TABLE"] = "test-tracking-table"
os.environ["REGION"] = "us-east-1"

# Mock the ragstack_common imports before importing index
# Create mock modules
mock_ocr = MagicMock()
mock_models = MagicMock()
mock_storage = MagicMock()
mock_config = MagicMock()

sys.modules["ragstack_common"] = MagicMock()
sys.modules["ragstack_common.ocr"] = mock_ocr
sys.modules["ragstack_common.models"] = mock_models
sys.modules["ragstack_common.storage"] = mock_storage
sys.modules["ragstack_common.config"] = mock_config

# Set up enum values
mock_models.Status = MagicMock()
mock_models.Status.PROCESSING = MagicMock(value="processing")
mock_models.Status.OCR_COMPLETE = MagicMock(value="ocr_complete")
mock_models.Status.FAILED = MagicMock(value="failed")
mock_models.OcrBackend = MagicMock()

# Use importlib to load the Lambda function with a unique module name
# This avoids sys.modules['index'] caching issues when multiple tests load different index.py files
lambda_dir = Path(__file__).parent.parent.parent / "src" / "lambda" / "process_document"
spec = importlib.util.spec_from_file_location("index_process_document", lambda_dir / "index.py")
index = importlib.util.module_from_spec(spec)
sys.modules["index_process_document"] = index
spec.loader.exec_module(index)


@pytest.fixture
def valid_event():
    """Valid input event for process_document Lambda."""
    return {
        "document_id": "test-doc-123",
        "input_s3_uri": "s3://input-bucket/test.pdf",
        "output_s3_prefix": "s3://output-bucket/processed/",
        "filename": "test.pdf",
        "ocr_backend": "textract",
    }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = "process_document"
    context.memory_limit_in_mb = 2048
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:process_document"
    context.aws_request_id = "test-request-id"
    return context


@pytest.fixture
def mock_document():
    """Mock processed document."""
    doc = Mock()
    doc.document_id = "test-doc-123"
    doc.status = mock_models.Status.OCR_COMPLETE
    doc.total_pages = 3
    doc.is_text_native = True
    doc.output_s3_uri = "s3://output-bucket/processed/test-doc-123/text.txt"
    doc.error_message = None

    # Mock pages
    page1 = Mock()
    page1.page_number = 1
    page1.text = "Page 1 content"
    page1.image_s3_uri = None
    page1.ocr_backend = "text_extraction"

    page2 = Mock()
    page2.page_number = 2
    page2.text = "Page 2 content"
    page2.image_s3_uri = None
    page2.ocr_backend = "text_extraction"

    doc.pages = [page1, page2]

    return doc


@patch.dict("os.environ", {"TRACKING_TABLE": "test-tracking-table", "AWS_REGION": "us-east-1"})
@patch("index_process_document._get_config_manager")
@patch("index_process_document.update_item")
@patch("index_process_document.OcrService")
@patch("index_process_document.Document")
def test_lambda_handler_success(
    mock_document_class,
    mock_ocr_service_class,
    mock_update_item,
    mock_get_config_manager,
    valid_event,
    lambda_context,
    mock_document,
):
    """Test successful document processing."""

    # Setup config manager mock
    mock_config_manager = Mock()
    mock_get_config_manager.return_value = mock_config_manager
    mock_config_manager.get_parameter.side_effect = lambda key, default=None: {
        "ocr_backend": "textract",
        "bedrock_ocr_model_id": "anthropic.claude-3-5-haiku-20241022-v1:0",
    }.get(key, default)

    # Setup mocks
    mock_document_class.return_value = Mock()
    mock_ocr_instance = Mock()
    mock_ocr_service_class.return_value = mock_ocr_instance
    mock_ocr_instance.process_document.return_value = mock_document

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify
    assert result["document_id"] == "test-doc-123"
    assert result["status"] == "ocr_complete"
    assert result["total_pages"] == 3
    assert result["is_text_native"]
    assert "pages" in result
    assert len(result["pages"]) == 2

    # Verify update_item was called twice (processing, then ocr_complete)
    assert mock_update_item.call_count == 2

    # Verify OCR service was initialized with correct parameters
    mock_ocr_service_class.assert_called_once_with(
        region="us-east-1",
        backend="textract",
        bedrock_model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
    )


@patch.dict("os.environ", {"TRACKING_TABLE": "test-tracking-table", "AWS_REGION": "us-east-1"})
@patch("index_process_document.update_item")
@patch("index_process_document.OcrService")
@patch("index_process_document.Document")
def test_lambda_handler_ocr_failure(
    mock_document_class, mock_ocr_service_class, mock_update_item, valid_event, lambda_context
):
    """Test handling of OCR processing failure."""

    # Setup mocks - OCR fails
    mock_document_class.return_value = Mock()
    mock_ocr_instance = Mock()
    mock_ocr_service_class.return_value = mock_ocr_instance

    failed_doc = Mock()
    failed_doc.status = mock_models.Status.FAILED
    failed_doc.error_message = "OCR processing failed"
    mock_ocr_instance.process_document.return_value = failed_doc

    # Execute and expect exception
    with pytest.raises(Exception) as exc_info:
        index.lambda_handler(valid_event, lambda_context)

    assert "OCR processing failed" in str(exc_info.value)

    # Verify status was updated to processing, then to failed
    assert mock_update_item.call_count >= 2


@patch.dict("os.environ", {"TRACKING_TABLE": "test-tracking-table", "AWS_REGION": "us-east-1"})
@patch("index_process_document.update_item")
def test_lambda_handler_missing_required_field(mock_update_item, lambda_context):
    """Test handling of missing required event fields."""

    invalid_event = {
        "document_id": "test-doc-123"
        # Missing input_s3_uri and output_s3_prefix
    }

    # Execute and expect exception
    with pytest.raises(KeyError):
        index.lambda_handler(invalid_event, lambda_context)

    # Verify failed status was recorded
    mock_update_item.assert_called()
    last_call_args = mock_update_item.call_args[0]
    assert last_call_args[1]["document_id"] == "test-doc-123"
    assert "status" in last_call_args[2]


@patch.dict("os.environ", {"TRACKING_TABLE": "test-tracking-table", "AWS_REGION": "us-east-1"})
@patch("index_process_document._get_config_manager")
@patch("index_process_document.update_item")
@patch("index_process_document.OcrService")
@patch("index_process_document.Document")
def test_lambda_handler_with_bedrock_backend(
    mock_document_class, mock_ocr_service_class, _mock_update_item, mock_get_config_manager, lambda_context, mock_document
):
    """Test Lambda with Bedrock OCR backend."""

    event = {
        "document_id": "test-doc-123",
        "input_s3_uri": "s3://input-bucket/test.pdf",
        "output_s3_prefix": "s3://output-bucket/processed/",
        "filename": "test.pdf",
        "ocr_backend": "bedrock",
        "bedrock_model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    }

    # Setup config manager mock
    mock_config_manager = Mock()
    mock_get_config_manager.return_value = mock_config_manager
    mock_config_manager.get_parameter.side_effect = lambda key, default=None: {
        "ocr_backend": "bedrock",
        "bedrock_ocr_model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    }.get(key, default)

    # Setup mocks
    mock_document_class.return_value = Mock()
    mock_ocr_instance = Mock()
    mock_ocr_service_class.return_value = mock_ocr_instance
    mock_ocr_instance.process_document.return_value = mock_document

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify Bedrock backend was used
    mock_ocr_service_class.assert_called_once_with(
        region="us-east-1",
        backend="bedrock",
        bedrock_model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    )

    assert result["document_id"] == "test-doc-123"


@patch.dict("os.environ", {"TRACKING_TABLE": "test-tracking-table", "AWS_REGION": "us-east-1"})
@patch("index_process_document.update_item")
@patch("index_process_document.OcrService")
@patch("index_process_document.Document")
def test_lambda_handler_page_text_truncation(
    mock_document_class, mock_ocr_service_class, _mock_update_item, valid_event, lambda_context
):
    """Test that page text is truncated for Step Functions output."""

    # Setup mocks with long text
    mock_document_class.return_value = Mock()
    mock_ocr_instance = Mock()
    mock_ocr_service_class.return_value = mock_ocr_instance

    doc = Mock()
    doc.status = mock_models.Status.OCR_COMPLETE
    doc.document_id = "test-doc-123"
    doc.total_pages = 1
    doc.is_text_native = False
    doc.output_s3_uri = "s3://output-bucket/test.txt"

    # Create page with >500 char text
    page = Mock()
    page.page_number = 1
    page.text = "x" * 1000  # 1000 characters
    page.image_s3_uri = "s3://bucket/image.jpg"
    page.ocr_backend = "textract"

    doc.pages = [page]
    mock_ocr_instance.process_document.return_value = doc

    # Execute
    result = index.lambda_handler(valid_event, lambda_context)

    # Verify text was truncated to 500 chars
    assert len(result["pages"][0]["text"]) == 500


@patch.dict(
    "os.environ",
    {
        "TRACKING_TABLE": "test-tracking-table",
        "AWS_REGION": "us-east-1",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    },
)
@patch("index_process_document._get_config_manager")
@patch("index_process_document.update_item")
@patch("index_process_document.OcrService")
@patch("index_process_document.Document")
def test_lambda_handler_uses_runtime_config(
    mock_document_class,
    mock_ocr_service_class,
    _mock_update_item,
    mock_get_config_manager,
    lambda_context,
    mock_document,
):
    """Test that handler reads OCR configuration from ConfigurationManager."""

    # Setup config manager mock
    mock_config_manager = Mock()
    mock_get_config_manager.return_value = mock_config_manager

    def config_side_effect(key, default=None):
        config_map = {
            "ocr_backend": "bedrock",
            "bedrock_ocr_model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        }
        return config_map.get(key, default)

    mock_config_manager.get_parameter.side_effect = config_side_effect

    # Setup other mocks
    mock_document_class.return_value = Mock()
    mock_ocr_instance = Mock()
    mock_ocr_service_class.return_value = mock_ocr_instance
    mock_ocr_instance.process_document.return_value = mock_document

    event = {
        "document_id": "test-doc-123",
        "input_s3_uri": "s3://input-bucket/test.pdf",
        "output_s3_prefix": "s3://output-bucket/processed/",
        "filename": "test.pdf",
    }

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify config_manager was called for both parameters
    assert mock_config_manager.get_parameter.call_count == 2
    mock_config_manager.get_parameter.assert_any_call("ocr_backend", default="textract")
    mock_config_manager.get_parameter.assert_any_call(
        "bedrock_ocr_model_id", default="anthropic.claude-3-5-haiku-20241022-v1:0"
    )

    # Verify OCR service was initialized with config from ConfigurationManager
    mock_ocr_service_class.assert_called_once_with(
        region="us-east-1",
        backend="bedrock",
        bedrock_model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    )

    # Verify successful result
    assert result["document_id"] == "test-doc-123"
    assert result["status"] == "ocr_complete"


@patch.dict(
    "os.environ",
    {
        "TRACKING_TABLE": "test-tracking-table",
        "AWS_REGION": "us-east-1",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    },
)
@patch("index_process_document._get_config_manager")
@patch("index_process_document.update_item")
@patch("index_process_document.OcrService")
@patch("index_process_document.Document")
def test_lambda_handler_uses_textract_from_config(
    mock_document_class,
    mock_ocr_service_class,
    _mock_update_item,
    mock_get_config_manager,
    lambda_context,
    mock_document,
):
    """Test that handler correctly uses textract backend from ConfigurationManager."""

    # Setup config manager mock - return textract
    mock_config_manager = Mock()
    mock_get_config_manager.return_value = mock_config_manager

    def config_side_effect(key, default=None):
        config_map = {
            "ocr_backend": "textract",
            "bedrock_ocr_model_id": "anthropic.claude-3-5-haiku-20241022-v1:0",
        }
        return config_map.get(key, default)

    mock_config_manager.get_parameter.side_effect = config_side_effect

    # Setup other mocks
    mock_document_class.return_value = Mock()
    mock_ocr_instance = Mock()
    mock_ocr_service_class.return_value = mock_ocr_instance
    mock_ocr_instance.process_document.return_value = mock_document

    event = {
        "document_id": "test-doc-123",
        "input_s3_uri": "s3://input-bucket/test.pdf",
        "output_s3_prefix": "s3://output-bucket/processed/",
        "filename": "test.pdf",
    }

    # Execute
    result = index.lambda_handler(event, lambda_context)

    # Verify OCR service was initialized with textract backend
    mock_ocr_service_class.assert_called_once_with(
        region="us-east-1",
        backend="textract",
        bedrock_model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
    )

    # Verify successful result
    assert result["document_id"] == "test-doc-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
