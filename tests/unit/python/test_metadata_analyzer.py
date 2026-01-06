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

# Add Lambda source directory to path
sys.path.insert(0, str(Path(__file__).parents[3] / "src" / "lambda" / "metadata_analyzer"))


class TestAnalyzeMetadataFields:
    """Tests for metadata field analysis logic."""

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "boto3": mock_boto3,
                    "boto3.dynamodb": MagicMock(),
                    "boto3.dynamodb.conditions": MagicMock(),
                },
            ),
            patch("ragstack_common.config.ConfigurationManager"),
            patch("ragstack_common.key_library.KeyLibrary"),
        ):
            yield

    def test_count_field_occurrences(self):
        """Test counting occurrences of each metadata field."""
        import importlib

        import index

        importlib.reload(index)

        sample_metadata = [
            {"topic": "genealogy", "document_type": "pdf"},
            {"topic": "immigration", "document_type": "pdf"},
            {"topic": "census", "location": "New York"},
        ]

        result = index.analyze_metadata_fields(sample_metadata)

        assert result["topic"]["count"] == 3
        assert result["document_type"]["count"] == 2
        assert result["location"]["count"] == 1

    def test_calculate_occurrence_rate(self):
        """Test occurrence rate calculation."""
        import importlib

        import index

        importlib.reload(index)

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

    def test_identify_data_type_string(self):
        """Test data type identification for string values."""
        import importlib

        import index

        importlib.reload(index)

        assert index.infer_data_type("genealogy") == "string"
        assert index.infer_data_type("New York, NY") == "string"

    def test_identify_data_type_number(self):
        """Test data type identification for numeric values."""
        import importlib

        import index

        importlib.reload(index)

        assert index.infer_data_type(1940) == "number"
        assert index.infer_data_type(3.14) == "number"
        assert index.infer_data_type("1940") == "string"  # String that looks like number

    def test_identify_data_type_boolean(self):
        """Test data type identification for boolean values."""
        import importlib

        import index

        importlib.reload(index)

        assert index.infer_data_type(True) == "boolean"
        assert index.infer_data_type(False) == "boolean"

    def test_identify_data_type_list(self):
        """Test data type identification for list values."""
        import importlib

        import index

        importlib.reload(index)

        assert index.infer_data_type(["a", "b"]) == "list"
        assert index.infer_data_type([1, 2, 3]) == "list"

    def test_collect_sample_values(self):
        """Test sample value collection."""
        import importlib

        import index

        importlib.reload(index)

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

    def test_max_sample_values(self):
        """Test that sample values are limited to 10."""
        import importlib

        import index

        importlib.reload(index)

        sample_metadata = [{"topic": f"value_{i}"} for i in range(20)]

        result = index.analyze_metadata_fields(sample_metadata)

        assert len(result["topic"]["sample_values"]) <= 10

    def test_skips_internal_keys(self):
        """Test that internal AWS keys are skipped."""
        import importlib

        import index

        importlib.reload(index)

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

    def test_empty_metadata_list(self):
        """Test handling of empty metadata list."""
        import importlib

        import index

        importlib.reload(index)

        result = index.analyze_metadata_fields([])

        assert result == {}


class TestFilterExampleGeneration:
    """Tests for LLM-based filter example generation."""

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "boto3": mock_boto3,
                    "boto3.dynamodb": MagicMock(),
                    "boto3.dynamodb.conditions": MagicMock(),
                },
            ),
            patch("ragstack_common.config.ConfigurationManager"),
            patch("ragstack_common.key_library.KeyLibrary"),
        ):
            yield

    @pytest.fixture
    def mock_bedrock_response(self):
        """Mock Bedrock converse response."""
        return {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": json.dumps(
                                [
                                    {
                                        "name": "Genealogy Documents",
                                        "description": "Filter for genealogy-related content",
                                        "use_case": "Finding family history documents",
                                        "filter": {"topic": {"$eq": "genealogy"}},
                                    },
                                    {
                                        "name": "PDF Documents",
                                        "description": "Filter for PDF document type",
                                        "use_case": "Finding PDF documents only",
                                        "filter": {"document_type": {"$eq": "pdf"}},
                                    },
                                ]
                            )
                        }
                    ]
                }
            }
        }

    def test_generate_filter_examples(self, mock_bedrock_response):
        """Test filter example generation from LLM."""
        import importlib

        import index

        importlib.reload(index)

        field_analysis = {
            "topic": {
                "count": 10,
                "occurrence_rate": 0.8,
                "data_type": "string",
                "sample_values": ["genealogy", "immigration", "census"],
            },
            "document_type": {
                "count": 8,
                "occurrence_rate": 0.6,
                "data_type": "string",
                "sample_values": ["pdf", "spreadsheet"],
            },
        }

        # Patch the bedrock_runtime client
        index.bedrock_runtime.converse.return_value = mock_bedrock_response

        examples = index.generate_filter_examples(field_analysis)

        assert len(examples) >= 1
        assert examples[0]["name"] == "Genealogy Documents"
        assert "filter" in examples[0]

    def test_filter_example_structure(self, mock_bedrock_response):
        """Test that generated examples have required fields."""
        import importlib

        import index

        importlib.reload(index)

        field_analysis = {
            "topic": {
                "count": 10,
                "occurrence_rate": 0.8,
                "data_type": "string",
                "sample_values": ["genealogy"],
            },
        }

        index.bedrock_runtime.converse.return_value = mock_bedrock_response

        examples = index.generate_filter_examples(field_analysis)

        for example in examples:
            assert "name" in example
            assert "description" in example
            assert "use_case" in example
            assert "filter" in example
            assert isinstance(example["filter"], dict)

    def test_empty_field_analysis(self):
        """Test handling of empty field analysis."""
        import importlib

        import index

        importlib.reload(index)

        examples = index.generate_filter_examples({})

        assert examples == []


class TestResultsStorage:
    """Tests for storing analysis results."""

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "boto3": mock_boto3,
                    "boto3.dynamodb": MagicMock(),
                    "boto3.dynamodb.conditions": MagicMock(),
                },
            ),
            patch("ragstack_common.config.ConfigurationManager"),
            patch("ragstack_common.key_library.KeyLibrary"),
        ):
            yield

    def test_store_examples_to_s3(self):
        """Test storing filter examples to S3."""
        import importlib

        import index

        importlib.reload(index)

        examples = [
            {"name": "Test", "filter": {"topic": {"$eq": "test"}}},
        ]

        result = index.store_filter_examples(
            examples=examples,
            bucket="test-bucket",
            index_name="test-index",
        )

        # Should store both timestamped and latest versions
        assert index.s3.put_object.call_count >= 2
        assert result == "s3://test-bucket/metadata-filters/test-index/filter-examples-latest.json"

    def test_update_key_library_counts(self):
        """Test updating key library with occurrence counts."""
        import importlib

        import index

        importlib.reload(index)

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

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "boto3": mock_boto3,
                    "boto3.dynamodb": MagicMock(),
                    "boto3.dynamodb.conditions": MagicMock(),
                },
            ),
            patch("ragstack_common.config.ConfigurationManager"),
            patch("ragstack_common.key_library.KeyLibrary"),
        ):
            yield

    def test_sample_vectors_uses_retrieve_api(self):
        """Test that vector sampling uses the retrieve API."""
        import importlib

        import index

        importlib.reload(index)

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

    def test_sample_vectors_respects_max_samples(self):
        """Test that sampling respects max_samples limit."""
        import importlib

        import index

        importlib.reload(index)

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

    def test_sample_vectors_deduplicates(self):
        """Test that sampling deduplicates by S3 URI."""
        import importlib

        import index

        importlib.reload(index)

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

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "boto3": mock_boto3,
                    "boto3.dynamodb": MagicMock(),
                    "boto3.dynamodb.conditions": MagicMock(),
                },
            ),
            patch("ragstack_common.config.ConfigurationManager"),
            patch("ragstack_common.key_library.KeyLibrary"),
        ):
            yield

    def test_handler_returns_success(self):
        """Test handler returns success response."""
        import importlib

        import index

        importlib.reload(index)

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

    def test_handler_handles_empty_vectors(self):
        """Test handler handles case with no vectors."""
        import importlib

        import index

        importlib.reload(index)

        index.bedrock_agent.retrieve.return_value = {"retrievalResults": []}

        result = index.lambda_handler({}, None)

        assert result["success"] is True
        assert result["vectorsSampled"] == 0
        assert result["keysAnalyzed"] == 0

    def test_handler_returns_execution_time(self):
        """Test handler returns execution time in milliseconds."""
        import importlib

        import index

        importlib.reload(index)

        index.bedrock_agent.retrieve.return_value = {"retrievalResults": []}

        result = index.lambda_handler({}, None)

        assert "executionTimeMs" in result
        assert isinstance(result["executionTimeMs"], int)
        assert result["executionTimeMs"] >= 0

    def test_handler_missing_kb_id(self, monkeypatch):
        """Test handler returns error when KNOWLEDGE_BASE_ID not set."""
        import importlib

        import index

        monkeypatch.delenv("KNOWLEDGE_BASE_ID", raising=False)
        importlib.reload(index)

        result = index.lambda_handler({}, None)

        assert result["success"] is False
        assert "KNOWLEDGE_BASE_ID" in result["error"]
