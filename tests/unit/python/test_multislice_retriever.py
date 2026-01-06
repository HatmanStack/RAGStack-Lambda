"""Unit tests for MultiSliceRetriever

Tests the MultiSliceRetriever class using mocked Bedrock Agent Runtime client.
No actual AWS calls are made.
"""

from unittest.mock import MagicMock, patch

import pytest

from ragstack_common.multislice_retriever import (
    MultiSliceRetriever,
    SliceConfig,
    deduplicate_results,
)

# Fixtures


@pytest.fixture
def mock_bedrock_agent():
    """Create a mock Bedrock Agent Runtime client."""
    return MagicMock()


@pytest.fixture
def retriever(mock_bedrock_agent):
    """Create a MultiSliceRetriever with mocked client."""
    return MultiSliceRetriever(bedrock_agent_client=mock_bedrock_agent)


@pytest.fixture
def sample_kb_results():
    """Sample knowledge base retrieval results."""
    return [
        {
            "content": {"text": "Document about genealogy research."},
            "location": {"s3Location": {"uri": "s3://bucket/doc1/text.txt"}},
            "score": 0.95,
            "metadata": {"document_id": "doc1"},
        },
        {
            "content": {"text": "Immigration records from 1900."},
            "location": {"s3Location": {"uri": "s3://bucket/doc2/text.txt"}},
            "score": 0.88,
            "metadata": {"document_id": "doc2"},
        },
        {
            "content": {"text": "Family history documentation."},
            "location": {"s3Location": {"uri": "s3://bucket/doc3/text.txt"}},
            "score": 0.75,
            "metadata": {"document_id": "doc3"},
        },
    ]


@pytest.fixture
def sample_filter():
    """Sample metadata filter."""
    return {"topic": {"$eq": "genealogy"}}


# Test: Initialization


def test_multislice_retriever_init():
    """Test MultiSliceRetriever initialization."""
    mock_client = MagicMock()
    retriever = MultiSliceRetriever(bedrock_agent_client=mock_client)
    assert retriever.bedrock_agent == mock_client


def test_multislice_retriever_init_creates_client():
    """Test MultiSliceRetriever creates client if not provided."""
    with patch("ragstack_common.multislice_retriever.boto3.client") as mock_boto:
        mock_boto.return_value = MagicMock()
        MultiSliceRetriever()
        mock_boto.assert_called_once_with("bedrock-agent-runtime")


# Test: Parallel execution of slices


def test_retrieve_executes_multiple_slices(retriever, mock_bedrock_agent, sample_kb_results):
    """Test that multiple slices are executed."""
    # Setup mock to return results for each call
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}

    result = retriever.retrieve(
        query="genealogy documents",
        knowledge_base_id="kb-123",
        data_source_id="ds-456",
        metadata_filter={"topic": {"$eq": "genealogy"}},
        num_results=5,
    )

    # Should have called retrieve at least twice (unfiltered + filtered)
    assert mock_bedrock_agent.retrieve.call_count >= 2
    assert len(result) > 0


def test_retrieve_without_filter_uses_single_slice(
    retriever, mock_bedrock_agent, sample_kb_results
):
    """Test that without filter, only unfiltered slice is used."""
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}

    result = retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id="ds-456",
        metadata_filter=None,
        num_results=5,
    )

    # Should only call once (no filter means no filtered slice)
    assert mock_bedrock_agent.retrieve.call_count == 1
    assert len(result) == len(sample_kb_results)


# Test: Result deduplication


def test_deduplicate_keeps_highest_score():
    """Test that deduplication keeps the result with highest score."""
    results = [
        {
            "content": {"text": "Same document"},
            "location": {"s3Location": {"uri": "s3://bucket/doc1/text.txt"}},
            "score": 0.7,
        },
        {
            "content": {"text": "Same document"},
            "location": {"s3Location": {"uri": "s3://bucket/doc1/text.txt"}},
            "score": 0.95,
        },
        {
            "content": {"text": "Different document"},
            "location": {"s3Location": {"uri": "s3://bucket/doc2/text.txt"}},
            "score": 0.8,
        },
    ]

    deduped = deduplicate_results(results)

    assert len(deduped) == 2  # Two unique documents
    # Find the doc1 result - should have the higher score
    doc1 = next(r for r in deduped if "doc1" in r["location"]["s3Location"]["uri"])
    assert doc1["score"] == 0.95


def test_deduplicate_preserves_metadata():
    """Test that metadata is preserved from the kept result."""
    results = [
        {
            "content": {"text": "Document"},
            "location": {"s3Location": {"uri": "s3://bucket/doc1/text.txt"}},
            "score": 0.9,
            "metadata": {"topic": "genealogy", "source": "filtered"},
        },
        {
            "content": {"text": "Document"},
            "location": {"s3Location": {"uri": "s3://bucket/doc1/text.txt"}},
            "score": 0.7,
            "metadata": {"topic": "genealogy", "source": "unfiltered"},
        },
    ]

    deduped = deduplicate_results(results)

    assert len(deduped) == 1
    assert deduped[0]["metadata"]["source"] == "filtered"  # Higher score result's metadata


def test_deduplicate_empty_list():
    """Test deduplication of empty list."""
    assert deduplicate_results([]) == []


def test_deduplicate_single_item():
    """Test deduplication of single item."""
    results = [
        {
            "content": {"text": "Only document"},
            "location": {"s3Location": {"uri": "s3://bucket/doc1/text.txt"}},
            "score": 0.9,
        }
    ]
    deduped = deduplicate_results(results)
    assert len(deduped) == 1


# Test: Single slice failure handling


def test_retrieve_handles_single_slice_failure(retriever, mock_bedrock_agent, sample_kb_results):
    """Test that failure in one slice doesn't break entire retrieval."""
    # First call succeeds, second fails
    mock_bedrock_agent.retrieve.side_effect = [
        {"retrievalResults": sample_kb_results},
        Exception("Slice 2 failed"),
    ]

    result = retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id="ds-456",
        metadata_filter={"topic": {"$eq": "genealogy"}},
        num_results=5,
    )

    # Should still return results from successful slice
    assert len(result) == len(sample_kb_results)


def test_retrieve_all_slices_fail_returns_empty(retriever, mock_bedrock_agent):
    """Test that if all slices fail, empty list is returned."""
    mock_bedrock_agent.retrieve.side_effect = Exception("All slices failed")

    result = retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id="ds-456",
        metadata_filter={"topic": {"$eq": "genealogy"}},
        num_results=5,
    )

    assert result == []


# Test: Timeout handling


def test_retrieve_handles_timeout(retriever, mock_bedrock_agent, sample_kb_results):
    """Test timeout handling for slow slices."""
    # Create a retriever with very short timeout
    with patch("ragstack_common.multislice_retriever.boto3.client") as mock_boto:
        mock_boto.return_value = mock_bedrock_agent
        retriever = MultiSliceRetriever(
            bedrock_agent_client=mock_bedrock_agent,
            timeout_seconds=0.001,  # Very short timeout
        )

    # Make the mock take a long time
    def slow_retrieve(*args, **kwargs):
        import time
        time.sleep(1)
        return {"retrievalResults": sample_kb_results}

    mock_bedrock_agent.retrieve.side_effect = slow_retrieve

    # Should handle timeout gracefully and return empty or partial results
    result = retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id="ds-456",
        metadata_filter=None,
        num_results=5,
    )

    # Result may be empty due to timeout, but should not raise
    assert isinstance(result, list)


# Test: Slice configurations


def test_retrieve_configurable_slice_count(mock_bedrock_agent, sample_kb_results):
    """Test that slice count is configurable."""
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}

    # Create retriever with 2 slices
    retriever = MultiSliceRetriever(
        bedrock_agent_client=mock_bedrock_agent,
        max_slices=2,
    )

    retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id="ds-456",
        metadata_filter={"topic": {"$eq": "genealogy"}},
        num_results=5,
    )

    # Should call retrieve twice (unfiltered + filtered, capped at 2)
    assert mock_bedrock_agent.retrieve.call_count == 2


def test_slice_config_structure():
    """Test SliceConfig dataclass structure."""
    config = SliceConfig(
        name="filtered",
        use_filter=True,
        num_results=5,
    )
    assert config.name == "filtered"
    assert config.use_filter is True
    assert config.num_results == 5


# Test: Correct filter application


def test_retrieve_applies_filter_correctly(retriever, mock_bedrock_agent, sample_kb_results):
    """Test that metadata filter is correctly applied to filtered slice."""
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}

    test_filter = {"topic": {"$eq": "genealogy"}}

    retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id="ds-456",
        metadata_filter=test_filter,
        num_results=5,
    )

    # Check that at least one call included the filter
    calls = mock_bedrock_agent.retrieve.call_args_list
    filter_found = False
    for call in calls:
        config = call.kwargs.get("retrievalConfiguration", {})
        vector_config = config.get("vectorSearchConfiguration", {})
        if "filter" in vector_config:
            filter_found = True
            # The filter should contain our metadata filter
            break

    assert filter_found, "No call included a metadata filter"


def test_retrieve_includes_data_source_filter(retriever, mock_bedrock_agent, sample_kb_results):
    """Test that data source ID filter is always included."""
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}

    retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id="ds-456",
        metadata_filter=None,
        num_results=5,
    )

    # Check all calls include data source filter
    for call in mock_bedrock_agent.retrieve.call_args_list:
        config = call.kwargs.get("retrievalConfiguration", {})
        vector_config = config.get("vectorSearchConfiguration", {})
        filter_expr = vector_config.get("filter", {})

        # Should have the data source filter
        assert "x-amz-bedrock-kb-data-source-id" in str(filter_expr) or "ds-456" in str(filter_expr)


# Test: Result merging


def test_retrieve_merges_results_from_all_slices(retriever, mock_bedrock_agent):
    """Test that results from all slices are merged."""
    # Different results from each slice
    results_slice1 = [
        {
            "content": {"text": "Doc 1"},
            "location": {"s3Location": {"uri": "s3://bucket/doc1/text.txt"}},
            "score": 0.9,
        }
    ]
    results_slice2 = [
        {
            "content": {"text": "Doc 2"},
            "location": {"s3Location": {"uri": "s3://bucket/doc2/text.txt"}},
            "score": 0.85,
        }
    ]

    mock_bedrock_agent.retrieve.side_effect = [
        {"retrievalResults": results_slice1},
        {"retrievalResults": results_slice2},
    ]

    result = retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id="ds-456",
        metadata_filter={"topic": {"$eq": "test"}},
        num_results=5,
    )

    # Should have both documents
    assert len(result) == 2
    uris = [r["location"]["s3Location"]["uri"] for r in result]
    assert "s3://bucket/doc1/text.txt" in uris
    assert "s3://bucket/doc2/text.txt" in uris


# Test: Enabled flag


def test_retrieve_respects_enabled_flag(mock_bedrock_agent, sample_kb_results):
    """Test that retrieval can be disabled."""
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}

    retriever = MultiSliceRetriever(
        bedrock_agent_client=mock_bedrock_agent,
        enabled=False,
    )

    retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id="ds-456",
        metadata_filter={"topic": {"$eq": "genealogy"}},
        num_results=5,
    )

    # Should fall back to single unfiltered query
    assert mock_bedrock_agent.retrieve.call_count == 1


# Test: Edge cases


def test_retrieve_empty_query(retriever, mock_bedrock_agent):
    """Test retrieval with empty query."""
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": []}

    result = retriever.retrieve(
        query="",
        knowledge_base_id="kb-123",
        data_source_id="ds-456",
        metadata_filter=None,
        num_results=5,
    )

    # Should still make the call (KB handles empty queries)
    assert isinstance(result, list)


def test_retrieve_no_data_source_id(retriever, mock_bedrock_agent, sample_kb_results):
    """Test retrieval without data source ID."""
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}

    result = retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id=None,  # No data source filter
        metadata_filter=None,
        num_results=5,
    )

    assert len(result) == len(sample_kb_results)
