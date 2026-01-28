"""Unit tests for filter_examples module in ragstack_common.

Tests the filter example generation, storage, and config update functions.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestGenerateFilterExamples:
    """Tests for LLM-based filter example generation."""

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
        with patch("ragstack_common.filter_examples.bedrock_runtime") as mock_bedrock:
            mock_bedrock.converse.return_value = mock_bedrock_response

            from ragstack_common.filter_examples import generate_filter_examples

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

            examples = generate_filter_examples(field_analysis)

            assert len(examples) >= 1
            assert examples[0]["name"] == "Genealogy Documents"
            assert "filter" in examples[0]

    def test_filter_example_structure(self, mock_bedrock_response):
        """Test that generated examples have required fields."""
        with patch("ragstack_common.filter_examples.bedrock_runtime") as mock_bedrock:
            mock_bedrock.converse.return_value = mock_bedrock_response

            from ragstack_common.filter_examples import generate_filter_examples

            field_analysis = {
                "topic": {
                    "count": 10,
                    "occurrence_rate": 0.8,
                    "data_type": "string",
                    "sample_values": ["genealogy"],
                },
            }

            examples = generate_filter_examples(field_analysis)

            for example in examples:
                assert "name" in example
                assert "description" in example
                assert "use_case" in example
                assert "filter" in example
                assert isinstance(example["filter"], dict)

    def test_empty_field_analysis(self):
        """Test handling of empty field analysis."""
        from ragstack_common.filter_examples import generate_filter_examples

        examples = generate_filter_examples({})

        assert examples == []

    def test_zero_examples_requested(self):
        """Test handling when no examples are requested."""
        from ragstack_common.filter_examples import generate_filter_examples

        field_analysis = {
            "topic": {
                "count": 10,
                "data_type": "string",
                "sample_values": ["test"],
            },
        }

        examples = generate_filter_examples(field_analysis, num_examples=0)

        assert examples == []


class TestStoreFilterExamples:
    """Tests for storing filter examples to S3."""

    def test_store_examples_to_s3(self):
        """Test storing filter examples to S3."""
        with patch("ragstack_common.filter_examples.s3") as mock_s3:
            from ragstack_common.filter_examples import store_filter_examples

            examples = [
                {"name": "Test", "filter": {"topic": {"$eq": "test"}}},
            ]

            result = store_filter_examples(
                examples=examples,
                bucket="test-bucket",
                index_name="test-index",
            )

            # Should store both timestamped and latest versions
            assert mock_s3.put_object.call_count == 2
            assert (
                result == "s3://test-bucket/metadata-filters/test-index/filter-examples-latest.json"
            )


class TestUpdateConfigWithExamples:
    """Tests for updating config with filter examples."""

    def test_update_config_success(self):
        """Test successful config update."""
        mock_config = MagicMock()

        with patch(
            "ragstack_common.filter_examples.get_config_manager_or_none",
            return_value=mock_config,
        ):
            from ragstack_common.filter_examples import update_config_with_examples

            examples = [{"name": "Test", "filter": {}}]
            update_config_with_examples(examples, clear_disabled=True)

            mock_config.update_custom_config.assert_called_once()
            call_args = mock_config.update_custom_config.call_args[0][0]
            assert "metadata_filter_examples" in call_args
            assert call_args["metadata_filter_examples"] == examples
            assert call_args["metadata_filter_examples_disabled"] == []

    def test_update_config_no_manager(self):
        """Test handling when config manager is not available."""
        with patch(
            "ragstack_common.filter_examples.get_config_manager_or_none",
            return_value=None,
        ):
            from ragstack_common.filter_examples import update_config_with_examples

            # Should not raise
            update_config_with_examples([{"name": "Test"}])
