"""Unit tests for ingest_to_kb Lambda

Tests the ingest_to_kb Lambda handler with mocked AWS services.
Verifies metadata extraction integration and Bedrock KB ingestion.

Note: Since 'lambda' is a Python keyword, we use importlib to load the module.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_ingest_module():
    """Load the ingest_to_kb index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src" / "lambda" / "ingest_to_kb" / "index.py"
    ).resolve()

    spec = importlib.util.spec_from_file_location("ingest_to_kb_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_to_kb_index"] = module
    spec.loader.exec_module(module)
    return module


# Set up environment variables before importing the module
@pytest.fixture(autouse=True)
def set_env_vars():
    """Set required environment variables for all tests."""
    env_vars = {
        "KNOWLEDGE_BASE_ID": "test-kb-id",
        "DATA_SOURCE_ID": "test-ds-id",
        "TRACKING_TABLE": "test-tracking-table",
        "GRAPHQL_ENDPOINT": "https://test-appsync.amazonaws.com/graphql",
        "METADATA_KEY_LIBRARY_TABLE": "test-key-library-table",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
        "AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.function_name = "test-ingest"
    context.memory_limit_in_mb = 128
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"
    return context


@pytest.fixture
def sample_event():
    """Sample Lambda event."""
    return {
        "document_id": "test-doc-123",
        "output_s3_uri": "s3://test-bucket/output/test-doc-123/full_text.txt",
    }


class TestGetFileTypeFromFilename:
    """Tests for get_file_type_from_filename function (now in shared module)."""

    def test_extracts_pdf(self, set_env_vars):
        """Test extracting PDF file type."""
        from ragstack_common.storage import get_file_type_from_filename

        assert get_file_type_from_filename("document.pdf") == "pdf"

    def test_extracts_jpg(self, set_env_vars):
        """Test extracting JPG file type."""
        from ragstack_common.storage import get_file_type_from_filename

        assert get_file_type_from_filename("photo.JPG") == "jpg"

    def test_handles_multiple_dots(self, set_env_vars):
        """Test handling filenames with multiple dots."""
        from ragstack_common.storage import get_file_type_from_filename

        assert get_file_type_from_filename("file.name.txt") == "txt"

    def test_handles_no_extension(self, set_env_vars):
        """Test handling filenames without extension."""
        from ragstack_common.storage import get_file_type_from_filename

        assert get_file_type_from_filename("noextension") == "unknown"

    def test_handles_empty_filename(self, set_env_vars):
        """Test handling empty filename."""
        from ragstack_common.storage import get_file_type_from_filename

        assert get_file_type_from_filename("") == "unknown"


class TestBuildInlineAttributes:
    """Tests for build_inline_attributes function."""

    def test_builds_string_attributes(self, set_env_vars):
        """Test building attributes from string values."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
        ):
            module = load_ingest_module()

            metadata = {"topic": "immigration", "location": "Ellis Island"}
            result = module.build_inline_attributes(metadata)

            assert len(result) == 2
            # Check format includes type: STRING
            topic_attr = {"key": "topic", "value": {"type": "STRING", "stringValue": "immigration"}}
            location_attr = {
                "key": "location",
                "value": {"type": "STRING", "stringValue": "Ellis Island"},
            }
            assert topic_attr in result
            assert location_attr in result

    def test_skips_empty_values(self, set_env_vars):
        """Test that empty values are skipped."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
        ):
            module = load_ingest_module()

            metadata = {"topic": "immigration", "empty": "", "none": None}
            result = module.build_inline_attributes(metadata)

            assert len(result) == 1
            assert result[0]["key"] == "topic"

    def test_converts_numbers(self, set_env_vars):
        """Test conversion of numeric values."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
        ):
            module = load_ingest_module()

            metadata = {"count": 42, "score": 0.95}
            result = module.build_inline_attributes(metadata)

            assert len(result) == 2
            values = {attr["key"]: attr["value"]["stringValue"] for attr in result}
            assert values["count"] == "42"
            assert values["score"] == "0.95"

    def test_converts_booleans(self, set_env_vars):
        """Test conversion of boolean values."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
        ):
            module = load_ingest_module()

            metadata = {"verified": True, "deprecated": False}
            result = module.build_inline_attributes(metadata)

            values = {attr["key"]: attr["value"]["stringValue"] for attr in result}
            assert values["verified"] == "true"
            assert values["deprecated"] == "false"

    def test_converts_lists(self, set_env_vars):
        """Test conversion of list values."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
        ):
            module = load_ingest_module()

            metadata = {"tags": ["a", "b", "c"]}
            result = module.build_inline_attributes(metadata)

            assert len(result) == 1
            assert result[0]["value"]["stringValue"] == "a, b, c"


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    def test_successful_ingestion_with_metadata(
        self,
        set_env_vars,
        sample_event,
        lambda_context,
    ):
        """Test successful document ingestion with metadata extraction."""
        mock_bedrock = MagicMock()
        mock_bedrock.ingest_knowledge_base_documents.return_value = {
            "documentDetails": [{"status": "STARTING"}]
        }

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "test-doc-123",
                "filename": "test.pdf",
                "total_pages": 5,
            }
        }
        mock_table.update_item.return_value = {}

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with (
            patch("boto3.client", return_value=mock_bedrock),
            patch("boto3.resource", return_value=mock_dynamodb),
            patch(
                "ragstack_common.storage.read_s3_text",
                return_value="Test document content about immigration records.",
            ),
            patch("ragstack_common.appsync.publish_document_update"),
            patch("ragstack_common.key_library.boto3.resource", return_value=mock_dynamodb),
            patch("ragstack_common.metadata_extractor.BedrockClient") as mock_bedrock_client_class,
        ):
            # Set up the mock BedrockClient
            mock_extractor_bedrock = MagicMock()
            mock_extractor_bedrock.invoke_model.return_value = {
                "response": {
                    "output": {
                        "message": {
                            "content": [
                                {"text": '{"topic": "immigration", "document_type": "record"}'}
                            ]
                        }
                    }
                }
            }
            mock_extractor_bedrock.extract_text_from_response.return_value = (
                '{"topic": "immigration", "document_type": "record"}'
            )
            mock_bedrock_client_class.return_value = mock_extractor_bedrock

            # Clear cached module
            if "ingest_to_kb_index" in sys.modules:
                del sys.modules["ingest_to_kb_index"]

            module = load_ingest_module()

            # Reset singletons
            module._key_library = None
            module._metadata_extractor = None
            module._config_manager = None

            result = module.lambda_handler(sample_event, lambda_context)

            assert result["status"] == "indexed"
            assert result["document_id"] == "test-doc-123"
            assert result["knowledge_base_id"] == "test-kb-id"
            # LLM metadata status should be reported
            assert "llm_metadata_extracted" in result
            assert "metadata_keys" in result

    def test_ingestion_continues_on_metadata_extraction_failure(
        self,
        set_env_vars,
        sample_event,
        lambda_context,
    ):
        """Test that ingestion continues if metadata extraction fails."""
        mock_bedrock = MagicMock()
        mock_bedrock.ingest_knowledge_base_documents.return_value = {
            "documentDetails": [{"status": "STARTING"}]
        }

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "test-doc-123",
                "filename": "test.pdf",
                "total_pages": 5,
            }
        }
        mock_table.update_item.return_value = {}

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with (
            patch("boto3.client", return_value=mock_bedrock),
            patch("boto3.resource", return_value=mock_dynamodb),
            patch(
                "ragstack_common.storage.read_s3_text",
                side_effect=Exception("S3 read error"),
            ),
            patch("ragstack_common.appsync.publish_document_update"),
            patch("ragstack_common.key_library.boto3.resource", return_value=mock_dynamodb),
        ):
            if "ingest_to_kb_index" in sys.modules:
                del sys.modules["ingest_to_kb_index"]

            module = load_ingest_module()

            module._key_library = None
            module._metadata_extractor = None
            module._config_manager = None

            result = module.lambda_handler(sample_event, lambda_context)

            # Should still succeed, just without LLM metadata
            assert result["status"] == "indexed"
            assert result["llm_metadata_extracted"] is False
            # metadata_keys should contain at least content_type (base metadata)
            assert "content_type" in result["metadata_keys"]

    def test_missing_required_params(self, set_env_vars, lambda_context):
        """Test that missing required params raise ValueError."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
        ):
            if "ingest_to_kb_index" in sys.modules:
                del sys.modules["ingest_to_kb_index"]

            module = load_ingest_module()

            with pytest.raises(ValueError, match="document_id and output_s3_uri"):
                module.lambda_handler({}, lambda_context)

    def test_missing_kb_env_vars(self, lambda_context):
        """Test that missing KB env vars raise ValueError."""
        # Clear KB env vars
        env_vars = {
            "TRACKING_TABLE": "test-tracking-table",
            "AWS_REGION": "us-east-1",
        }
        with (
            patch.dict(os.environ, env_vars, clear=True),
            patch("boto3.client"),
            patch("boto3.resource"),
        ):
            if "ingest_to_kb_index" in sys.modules:
                del sys.modules["ingest_to_kb_index"]

            module = load_ingest_module()

            event = {
                "document_id": "test",
                "output_s3_uri": "s3://bucket/key",
            }
            with pytest.raises(ValueError, match="KNOWLEDGE_BASE_ID"):
                module.lambda_handler(event, lambda_context)


class TestGetMetadataExtractor:
    """Tests for get_metadata_extractor function with extraction mode configuration."""

    def test_extractor_uses_config_mode_auto(self, set_env_vars):
        """Test that extractor uses auto mode when configured."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"metadata_extraction_mode": "auto"}}
        mock_dynamodb.Table.return_value = mock_table

        with (
            patch("boto3.client"),
            patch("boto3.resource", return_value=mock_dynamodb),
            patch("ragstack_common.key_library.boto3.resource", return_value=mock_dynamodb),
        ):
            if "ingest_to_kb_index" in sys.modules:
                del sys.modules["ingest_to_kb_index"]

            module = load_ingest_module()
            module._key_library = None
            module._metadata_extractor = None
            module._config_manager = None

            extractor = module.get_metadata_extractor()
            assert extractor.extraction_mode == "auto"

    def test_extractor_uses_config_mode_manual(self, set_env_vars):
        """Test that extractor uses manual mode with keys when configured."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "metadata_extraction_mode": "manual",
                "metadata_manual_keys": ["topic", "document_type"],
            }
        }
        mock_dynamodb.Table.return_value = mock_table

        with (
            patch("boto3.client"),
            patch("boto3.resource", return_value=mock_dynamodb),
            patch("ragstack_common.key_library.boto3.resource", return_value=mock_dynamodb),
        ):
            if "ingest_to_kb_index" in sys.modules:
                del sys.modules["ingest_to_kb_index"]

            module = load_ingest_module()
            module._key_library = None
            module._metadata_extractor = None
            module._config_manager = None

            extractor = module.get_metadata_extractor()
            assert extractor.extraction_mode == "manual"
            assert extractor.manual_keys == ["topic", "document_type"]

    def test_extractor_fallback_on_missing_mode(self, set_env_vars):
        """Test that extractor defaults to auto mode when mode not configured."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {}}  # No mode configured
        mock_dynamodb.Table.return_value = mock_table

        with (
            patch("boto3.client"),
            patch("boto3.resource", return_value=mock_dynamodb),
            patch("ragstack_common.key_library.boto3.resource", return_value=mock_dynamodb),
        ):
            if "ingest_to_kb_index" in sys.modules:
                del sys.modules["ingest_to_kb_index"]

            module = load_ingest_module()
            module._key_library = None
            module._metadata_extractor = None
            module._config_manager = None

            extractor = module.get_metadata_extractor()
            assert extractor.extraction_mode == "auto"
