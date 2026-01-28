"""Unit tests for Metadata Analyzer Lambda

Tests the metadata analysis functionality including:
- Vector sampling from Bedrock KB
- Metadata field counting and analysis
- Occurrence rate calculation
- Filter example generation
- Results storage in S3 and DynamoDB
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Path to metadata_analyzer Lambda
METADATA_ANALYZER_PATH = str(Path(__file__).parents[3] / "src" / "lambda" / "metadata_analyzer")


@pytest.fixture
def metadata_analyzer_module():
    """Import metadata_analyzer index module with proper path setup and cleanup."""
    # Add path temporarily
    sys.path.insert(0, METADATA_ANALYZER_PATH)

    # Remove cached index if it exists from another Lambda
    if "index" in sys.modules:
        del sys.modules["index"]

    # Mock boto3 clients to avoid AWS initialization
    mock_boto3 = MagicMock()
    mock_dynamodb = MagicMock()

    with (
        patch.dict(
            "sys.modules",
            {
                "boto3": mock_boto3,
                "boto3.dynamodb": mock_dynamodb,
                "boto3.dynamodb.conditions": MagicMock(),
            },
        ),
        patch("ragstack_common.config.ConfigurationManager"),
        patch("ragstack_common.key_library.KeyLibrary"),
    ):
        import importlib

        import index

        importlib.reload(index)
        yield index

    # Cleanup
    if "index" in sys.modules:
        del sys.modules["index"]
    if METADATA_ANALYZER_PATH in sys.path:
        sys.path.remove(METADATA_ANALYZER_PATH)


class TestAnalyzeMetadataFields:
    """Tests for metadata field analysis logic."""

    def test_count_field_occurrences(self, metadata_analyzer_module):
        """Test counting occurrences of each metadata field."""
        index = metadata_analyzer_module

        sample_metadata = [
            {"topic": "genealogy", "document_type": "pdf"},
            {"topic": "immigration", "document_type": "pdf"},
            {"topic": "census", "location": "New York"},
        ]

        result = index.analyze_metadata_fields(sample_metadata)

        assert result["topic"]["count"] == 3
        assert result["document_type"]["count"] == 2
        assert result["location"]["count"] == 1

    def test_calculate_occurrence_rate(self, metadata_analyzer_module):
        """Test occurrence rate calculation."""
        index = metadata_analyzer_module

        sample_metadata = [
            {"topic": "genealogy"},
            {"topic": "immigration"},
            {},  # Empty metadata
        ]

        result = index.analyze_metadata_fields(sample_metadata)

        # topic appears in 2 out of 3 vectors = 66.7%
        assert result["topic"]["count"] == 2
        # Rate is calculated as count / total_vectors
        assert result["topic"]["occurrence_rate"] == pytest.approx(2 / 3, rel=0.01)

    def test_identify_data_type_string(self, metadata_analyzer_module):
        """Test data type identification for string values."""
        index = metadata_analyzer_module

        assert index.infer_data_type("genealogy") == "string"
        assert index.infer_data_type("New York, NY") == "string"

    def test_identify_data_type_number(self, metadata_analyzer_module):
        """Test data type identification for numeric values."""
        index = metadata_analyzer_module

        assert index.infer_data_type(1940) == "number"
        assert index.infer_data_type(3.14) == "number"
        assert index.infer_data_type("1940") == "string"  # String that looks like number

    def test_identify_data_type_boolean(self, metadata_analyzer_module):
        """Test data type identification for boolean values."""
        index = metadata_analyzer_module

        assert index.infer_data_type(True) == "boolean"
        assert index.infer_data_type(False) == "boolean"

    def test_identify_data_type_list(self, metadata_analyzer_module):
        """Test data type identification for list values."""
        index = metadata_analyzer_module

        assert index.infer_data_type(["a", "b"]) == "list"
        assert index.infer_data_type([1, 2, 3]) == "list"

    def test_collect_sample_values(self, metadata_analyzer_module):
        """Test sample value collection."""
        index = metadata_analyzer_module

        sample_metadata = [
            {"topic": "genealogy"},
            {"topic": "immigration"},
            {"topic": "census"},
            {"topic": "genealogy"},  # Duplicate
        ]

        result = index.analyze_metadata_fields(sample_metadata)

        # Should collect unique sample values (up to 10)
        assert "genealogy" in result["topic"]["sample_values"]
        assert "immigration" in result["topic"]["sample_values"]
        assert "census" in result["topic"]["sample_values"]
        assert len(result["topic"]["sample_values"]) == 3  # Deduplicated

    def test_max_sample_values(self, metadata_analyzer_module):
        """Test that sample values are limited to 10."""
        index = metadata_analyzer_module

        sample_metadata = [{"topic": f"value_{i}"} for i in range(20)]

        result = index.analyze_metadata_fields(sample_metadata)

        assert len(result["topic"]["sample_values"]) <= 10

    def test_skips_internal_keys(self, metadata_analyzer_module):
        """Test that internal AWS keys are skipped."""
        index = metadata_analyzer_module

        sample_metadata = [
            {
                "topic": "test",
                "x-amz-bedrock-kb-data-source-id": "ds-123",
                "AMAZON_BEDROCK_TEXT": "chunk data",
            },
        ]

        result = index.analyze_metadata_fields(sample_metadata)

        assert "topic" in result
        assert "x-amz-bedrock-kb-data-source-id" not in result
        assert "AMAZON_BEDROCK_TEXT" not in result

    def test_empty_metadata_list(self, metadata_analyzer_module):
        """Test handling of empty metadata list."""
        index = metadata_analyzer_module

        result = index.analyze_metadata_fields([])

        assert result == {}


class TestResultsStorage:
    """Tests for storing analysis results."""

    def test_update_key_library_counts(self, metadata_analyzer_module):
        """Test updating key library with occurrence counts."""
        index = metadata_analyzer_module

        field_analysis = {
            "topic": {"count": 50, "data_type": "string", "sample_values": ["a", "b"]},
            "document_type": {"count": 30, "data_type": "string", "sample_values": ["pdf"]},
        }

        # Mock the table
        mock_table = MagicMock()
        index.dynamodb.Table.return_value = mock_table

        index.update_key_library_counts(
            field_analysis=field_analysis,
            table_name="test-key-library",
        )

        # Should update each key
        assert mock_table.update_item.call_count == 2


class TestVectorSampling:
    """Tests for vector sampling from Knowledge Base."""

    def test_sample_vectors_uses_retrieve_api(self, metadata_analyzer_module):
        """Test that vector sampling uses the retrieve API."""
        index = metadata_analyzer_module

        index.bedrock_agent.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "test"},
                    "metadata": {"topic": "test"},
                    "location": {"s3Location": {"uri": "s3://bucket/doc1.txt"}},
                }
            ]
        }

        results = index.sample_vectors_from_kb(
            knowledge_base_id="kb-123",
            data_source_id="ds-456",
            max_samples=100,
        )

        assert len(results) == 1
        assert index.bedrock_agent.retrieve.call_count >= 1

    def test_sample_vectors_respects_max_samples(self, metadata_analyzer_module):
        """Test that sampling respects max_samples limit."""
        index = metadata_analyzer_module

        # Return many results
        index.bedrock_agent.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": f"test{i}"},
                    "metadata": {},
                    "location": {"s3Location": {"uri": f"s3://bucket/doc{i}.txt"}},
                }
                for i in range(100)
            ]
        }

        results = index.sample_vectors_from_kb(
            knowledge_base_id="kb-123",
            data_source_id=None,
            max_samples=50,
        )

        assert len(results) <= 50

    def test_sample_vectors_deduplicates(self, metadata_analyzer_module):
        """Test that sampling deduplicates by S3 URI."""
        index = metadata_analyzer_module

        # Return duplicates
        index.bedrock_agent.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "test"},
                    "metadata": {"topic": "test"},
                    "location": {"s3Location": {"uri": "s3://bucket/same.txt"}},
                },
                {
                    "content": {"text": "test2"},
                    "metadata": {"topic": "test2"},
                    "location": {"s3Location": {"uri": "s3://bucket/same.txt"}},  # Same URI
                },
            ]
        }

        results = index.sample_vectors_from_kb(
            knowledge_base_id="kb-123",
            data_source_id=None,
            max_samples=100,
        )

        # Should deduplicate
        assert len(results) == 1


class TestLambdaHandler:
    """Tests for the main Lambda handler."""

    @pytest.fixture(autouse=True)
    def _mock_env(self, monkeypatch):
        """Set up environment variables."""
        monkeypatch.setenv("CONFIGURATION_TABLE_NAME", "test-config-table")
        monkeypatch.setenv("METADATA_KEY_LIBRARY_TABLE", "test-key-library")
        monkeypatch.setenv("KNOWLEDGE_BASE_ID", "kb-test123")
        monkeypatch.setenv("DATA_BUCKET", "test-data-bucket")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("TEXT_DATA_SOURCE_ID", "ds-text-123")

    def test_handler_returns_success(self, metadata_analyzer_module):
        """Test handler returns success response."""
        index = metadata_analyzer_module

        # Mock the functions
        index.bedrock_agent.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "test"},
                    "metadata": {"topic": "test"},
                    "location": {"s3Location": {"uri": "s3://bucket/doc.txt"}},
                }
            ]
        }
        index.bedrock_runtime.converse.return_value = {
            "output": {"message": {"content": [{"text": "[]"}]}}
        }
        index.dynamodb.Table.return_value = MagicMock()

        result = index.lambda_handler({}, None)

        assert result["success"] is True
        assert "vectorsSampled" in result
        assert "keysAnalyzed" in result
        assert "examplesGenerated" in result

    def test_handler_handles_empty_vectors(self, metadata_analyzer_module):
        """Test handler handles case with no vectors."""
        index = metadata_analyzer_module

        index.bedrock_agent.retrieve.return_value = {"retrievalResults": []}

        result = index.lambda_handler({}, None)

        assert result["success"] is True
        assert result["vectorsSampled"] == 0
        assert result["keysAnalyzed"] == 0

    def test_handler_returns_execution_time(self, metadata_analyzer_module):
        """Test handler returns execution time in milliseconds."""
        index = metadata_analyzer_module

        index.bedrock_agent.retrieve.return_value = {"retrievalResults": []}

        result = index.lambda_handler({}, None)

        assert "executionTimeMs" in result
        assert isinstance(result["executionTimeMs"], int)
        assert result["executionTimeMs"] >= 0

    def test_handler_missing_kb_id(self, metadata_analyzer_module, monkeypatch):
        """Test handler returns error when KB config not available."""
        index = metadata_analyzer_module

        # Remove both env var and config table to trigger error
        monkeypatch.delenv("KNOWLEDGE_BASE_ID", raising=False)
        monkeypatch.delenv("DATA_SOURCE_ID", raising=False)
        monkeypatch.delenv("CONFIGURATION_TABLE_NAME", raising=False)

        # Reload to pick up env change
        import importlib

        importlib.reload(index)

        result = index.lambda_handler({}, None)

        assert result["success"] is False
        assert "Knowledge Base configuration not found" in result["error"]
