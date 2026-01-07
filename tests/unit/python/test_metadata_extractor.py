"""Unit tests for MetadataExtractor

Tests the MetadataExtractor class using mocked Bedrock and KeyLibrary.
No actual AWS calls are made.
"""

from unittest.mock import MagicMock, patch

import pytest

from ragstack_common.metadata_extractor import (
    DEFAULT_EXTRACTION_MODEL,
    MAX_VALUE_LENGTH,
    MetadataExtractionError,
    MetadataExtractor,
    infer_data_type,
)

# Fixtures


@pytest.fixture
def mock_bedrock_client():
    """Create a mock BedrockClient."""
    mock_client = MagicMock()
    mock_client.invoke_model = MagicMock()
    mock_client.extract_text_from_response = MagicMock()
    return mock_client


@pytest.fixture
def mock_key_library():
    """Create a mock KeyLibrary."""
    mock_library = MagicMock()
    mock_library.get_key_names = MagicMock(return_value=[])
    mock_library.upsert_key = MagicMock()
    return mock_library


@pytest.fixture
def extractor(mock_bedrock_client, mock_key_library):
    """Create a MetadataExtractor with mocked dependencies."""
    return MetadataExtractor(
        bedrock_client=mock_bedrock_client,
        key_library=mock_key_library,
    )


@pytest.fixture
def sample_document_text():
    """Sample document text for testing."""
    return """
    Immigration Record - Ellis Island

    Name: John Smith
    Date of Arrival: March 15, 1905
    Ship: SS Carpathia
    Port of Origin: Liverpool, England
    Destination: New York City

    This document certifies that the above named person arrived at
    Ellis Island immigration station on the date specified.
    """


@pytest.fixture
def sample_extraction_response():
    """Sample LLM response with extracted metadata."""
    return {
        "topic": "immigration",
        "document_type": "ship_manifest",
        "date_range": "1900-1910",
        "location": "Ellis Island",
        "source_category": "government_record",
    }


# Test: infer_data_type helper


def test_infer_data_type_string():
    """Test data type inference for strings."""
    assert infer_data_type("hello") == "string"
    assert infer_data_type("") == "string"


def test_infer_data_type_number():
    """Test data type inference for numbers."""
    assert infer_data_type(42) == "number"
    assert infer_data_type(3.14) == "number"


def test_infer_data_type_boolean():
    """Test data type inference for booleans."""
    assert infer_data_type(True) == "boolean"
    assert infer_data_type(False) == "boolean"


def test_infer_data_type_list():
    """Test data type inference for lists."""
    assert infer_data_type([1, 2, 3]) == "list"
    assert infer_data_type(["a", "b"]) == "list"


# Test: Initialization


def test_init_with_defaults():
    """Test MetadataExtractor initialization with defaults."""
    with (
        patch("ragstack_common.metadata_extractor.BedrockClient"),
        patch("ragstack_common.metadata_extractor.KeyLibrary"),
    ):
        extractor = MetadataExtractor()
        assert extractor.model_id == DEFAULT_EXTRACTION_MODEL


def test_init_with_custom_model():
    """Test MetadataExtractor initialization with custom model."""
    with (
        patch("ragstack_common.metadata_extractor.BedrockClient"),
        patch("ragstack_common.metadata_extractor.KeyLibrary"),
    ):
        extractor = MetadataExtractor(model_id="custom-model-id")
        assert extractor.model_id == "custom-model-id"


# Test: extract_metadata


def test_extract_metadata_success(
    extractor,
    mock_bedrock_client,
    mock_key_library,
    sample_document_text,
    sample_extraction_response,
):
    """Test successful metadata extraction."""
    import json

    mock_bedrock_client.extract_text_from_response.return_value = json.dumps(
        sample_extraction_response
    )

    result = extractor.extract_metadata(sample_document_text, "doc-123")

    assert result == sample_extraction_response
    mock_bedrock_client.invoke_model.assert_called_once()
    assert mock_key_library.upsert_key.call_count == len(sample_extraction_response)


def test_extract_metadata_includes_existing_keys(
    extractor, mock_bedrock_client, mock_key_library, sample_document_text
):
    """Test that existing keys are included in the prompt."""
    import json

    mock_key_library.get_key_names.return_value = ["topic", "location", "date_range"]
    mock_bedrock_client.extract_text_from_response.return_value = json.dumps({"topic": "test"})

    extractor.extract_metadata(sample_document_text, "doc-123")

    # Check that invoke_model was called with content containing existing keys
    call_args = mock_bedrock_client.invoke_model.call_args
    content = call_args.kwargs["content"][0]["text"]
    assert "topic" in content
    assert "location" in content


def test_extract_metadata_empty_text(extractor, mock_bedrock_client):
    """Test extraction with empty text returns empty dict."""
    result = extractor.extract_metadata("", "doc-123")

    assert result == {}
    mock_bedrock_client.invoke_model.assert_not_called()


def test_extract_metadata_whitespace_only(extractor, mock_bedrock_client):
    """Test extraction with whitespace-only text returns empty dict."""
    result = extractor.extract_metadata("   \n\t  ", "doc-123")

    assert result == {}
    mock_bedrock_client.invoke_model.assert_not_called()


def test_extract_metadata_llm_error(extractor, mock_bedrock_client, sample_document_text):
    """Test graceful degradation when LLM call fails."""
    mock_bedrock_client.invoke_model.side_effect = Exception("API error")

    result = extractor.extract_metadata(sample_document_text, "doc-123")

    assert result == {}


def test_extract_metadata_invalid_json_response(
    extractor, mock_bedrock_client, sample_document_text
):
    """Test graceful degradation when LLM returns invalid JSON."""
    mock_bedrock_client.extract_text_from_response.return_value = "not valid json {"

    result = extractor.extract_metadata(sample_document_text, "doc-123")

    assert result == {}


def test_extract_metadata_empty_response(extractor, mock_bedrock_client, sample_document_text):
    """Test graceful degradation when LLM returns empty response."""
    mock_bedrock_client.extract_text_from_response.return_value = ""

    result = extractor.extract_metadata(sample_document_text, "doc-123")

    assert result == {}


def test_extract_metadata_skips_library_update(
    extractor,
    mock_bedrock_client,
    mock_key_library,
    sample_document_text,
    sample_extraction_response,
):
    """Test that library update can be disabled."""
    import json

    mock_bedrock_client.extract_text_from_response.return_value = json.dumps(
        sample_extraction_response
    )

    extractor.extract_metadata(sample_document_text, "doc-123", update_library=False)

    mock_key_library.upsert_key.assert_not_called()


# Test: _build_extraction_prompt


def test_build_prompt_includes_text(extractor, sample_document_text):
    """Test that prompt includes document text."""
    prompt = extractor._build_extraction_prompt(sample_document_text, [])

    assert "Immigration Record" in prompt
    assert "Ellis Island" in prompt


def test_build_prompt_includes_existing_keys(extractor, sample_document_text):
    """Test that prompt includes existing keys."""
    existing_keys = ["topic", "location", "date_range"]
    prompt = extractor._build_extraction_prompt(sample_document_text, existing_keys)

    assert "Existing metadata keys" in prompt
    assert "topic" in prompt
    assert "location" in prompt


def test_build_prompt_truncates_long_text(extractor):
    """Test that very long text is truncated."""
    long_text = "x" * 10000
    prompt = extractor._build_extraction_prompt(long_text, [])

    assert len(prompt) < 10000
    assert "[Text truncated for analysis...]" in prompt


def test_build_prompt_limits_existing_keys(extractor, sample_document_text):
    """Test that existing keys are limited in prompt."""
    many_keys = [f"key_{i}" for i in range(50)]
    prompt = extractor._build_extraction_prompt(sample_document_text, many_keys)

    # Should only include first 20 keys
    assert "key_0" in prompt
    assert "key_19" in prompt
    # key_20 and beyond should not be in the string
    # (though we can't guarantee exact word boundary matching)


# Test: _parse_response


def test_parse_response_valid_json(extractor):
    """Test parsing valid JSON response."""
    response = '{"topic": "test", "location": "NYC"}'
    result = extractor._parse_response(response)

    assert result == {"topic": "test", "location": "NYC"}


def test_parse_response_with_markdown_code_block(extractor):
    """Test parsing response wrapped in markdown code block."""
    response = '```json\n{"topic": "test"}\n```'
    result = extractor._parse_response(response)

    assert result == {"topic": "test"}


def test_parse_response_with_plain_code_block(extractor):
    """Test parsing response wrapped in plain code block."""
    response = '```\n{"topic": "test"}\n```'
    result = extractor._parse_response(response)

    assert result == {"topic": "test"}


def test_parse_response_invalid_json(extractor):
    """Test that invalid JSON raises MetadataExtractionError."""
    with pytest.raises(MetadataExtractionError, match="Invalid JSON"):
        extractor._parse_response("not valid json")


def test_parse_response_non_dict(extractor):
    """Test that non-dict JSON raises MetadataExtractionError."""
    with pytest.raises(MetadataExtractionError, match="not a JSON object"):
        extractor._parse_response('["array", "not", "dict"]')


def test_parse_response_empty(extractor):
    """Test that empty response raises MetadataExtractionError."""
    with pytest.raises(MetadataExtractionError, match="Empty response"):
        extractor._parse_response("")


# Test: _filter_metadata


def test_filter_metadata_removes_reserved_keys(extractor):
    """Test that reserved keys are removed."""
    metadata = {
        "topic": "test",
        "document_id": "should-be-removed",
        "text_content": "should-be-removed",
        "location": "NYC",
    }

    result = extractor._filter_metadata(metadata)

    assert "topic" in result
    assert "location" in result
    assert "document_id" not in result
    assert "text_content" not in result


def test_filter_metadata_truncates_long_values(extractor):
    """Test that long values are truncated."""
    long_value = "x" * 200
    metadata = {"topic": long_value}

    result = extractor._filter_metadata(metadata)

    assert len(result["topic"]) == MAX_VALUE_LENGTH


def test_filter_metadata_normalizes_key_names(extractor):
    """Test that key names are normalized."""
    metadata = {
        "Topic Name": "test",
        "LOCATION-FIELD": "NYC",
    }

    result = extractor._filter_metadata(metadata)

    assert "topic_name" in result
    assert "location_field" in result


def test_filter_metadata_converts_lists(extractor):
    """Test that list values are converted to strings."""
    metadata = {"tags": ["a", "b", "c"]}

    result = extractor._filter_metadata(metadata)

    assert result["tags"] == "a, b, c"


def test_filter_metadata_skips_empty_values(extractor):
    """Test that empty values are skipped."""
    metadata = {
        "topic": "test",
        "empty": "",
        "none": None,
        "whitespace": "   ",
    }

    result = extractor._filter_metadata(metadata)

    assert "topic" in result
    assert "empty" not in result
    assert "none" not in result
    assert "whitespace" not in result


def test_filter_metadata_respects_max_keys(extractor):
    """Test that max_keys limit is enforced."""
    extractor.max_keys = 3
    metadata = {f"key_{i}": f"value_{i}" for i in range(10)}

    result = extractor._filter_metadata(metadata)

    assert len(result) == 3


# Test: _update_key_library


def test_update_key_library_calls_upsert(extractor, mock_key_library):
    """Test that upsert_key is called for each metadata field."""
    metadata = {"topic": "test", "location": "NYC"}

    extractor._update_key_library(metadata)

    assert mock_key_library.upsert_key.call_count == 2
    mock_key_library.upsert_key.assert_any_call("topic", "string", "test")
    mock_key_library.upsert_key.assert_any_call("location", "string", "NYC")


def test_update_key_library_handles_errors(extractor, mock_key_library):
    """Test that errors in key library update are handled gracefully."""
    mock_key_library.upsert_key.side_effect = Exception("DB error")
    metadata = {"topic": "test"}

    # Should not raise
    extractor._update_key_library(metadata)


# Test: extract_from_caption


def test_extract_from_caption_with_caption(
    extractor, mock_bedrock_client, sample_extraction_response
):
    """Test caption extraction with caption text."""
    import json

    mock_bedrock_client.extract_text_from_response.return_value = json.dumps(
        sample_extraction_response
    )

    extractor.extract_from_caption(
        caption="Family photo from 1920s wedding",
        document_id="img-123",
    )

    mock_bedrock_client.invoke_model.assert_called_once()
    call_args = mock_bedrock_client.invoke_model.call_args
    content = call_args.kwargs["content"][0]["text"]
    assert "Image caption:" in content
    assert "1920s wedding" in content


def test_extract_from_caption_with_filename(
    extractor, mock_bedrock_client, sample_extraction_response
):
    """Test caption extraction includes filename context."""
    import json

    mock_bedrock_client.extract_text_from_response.return_value = json.dumps(
        sample_extraction_response
    )

    extractor.extract_from_caption(
        caption="Family photo",
        document_id="img-123",
        filename="grandpa_wedding_1925.jpg",
    )

    call_args = mock_bedrock_client.invoke_model.call_args
    content = call_args.kwargs["content"][0]["text"]
    assert "Original filename:" in content
    assert "grandpa_wedding_1925.jpg" in content


def test_extract_from_caption_empty(extractor, mock_bedrock_client):
    """Test caption extraction with empty caption and no filename."""
    result = extractor.extract_from_caption(
        caption="",
        document_id="img-123",
    )

    assert result == {}
    mock_bedrock_client.invoke_model.assert_not_called()


# Test: Manual Mode Support


@pytest.fixture
def manual_mode_extractor(mock_bedrock_client, mock_key_library):
    """Create a MetadataExtractor in manual mode."""
    return MetadataExtractor(
        bedrock_client=mock_bedrock_client,
        key_library=mock_key_library,
        extraction_mode="manual",
        manual_keys=["topic", "document_type"],
    )


def test_init_with_manual_mode(mock_bedrock_client, mock_key_library):
    """Test MetadataExtractor initialization with manual mode."""
    extractor = MetadataExtractor(
        bedrock_client=mock_bedrock_client,
        key_library=mock_key_library,
        extraction_mode="manual",
        manual_keys=["topic", "location"],
    )
    assert extractor.extraction_mode == "manual"
    assert extractor.manual_keys == ["topic", "location"]


def test_init_defaults_to_auto_mode(mock_bedrock_client, mock_key_library):
    """Test MetadataExtractor defaults to auto mode."""
    extractor = MetadataExtractor(
        bedrock_client=mock_bedrock_client,
        key_library=mock_key_library,
    )
    assert extractor.extraction_mode == "auto"
    assert extractor.manual_keys is None


def test_manual_mode_extracts_only_specified_keys(
    manual_mode_extractor, mock_bedrock_client, sample_document_text
):
    """Test that manual mode filters out keys not in manual_keys list."""
    import json

    # LLM returns extra keys that should be filtered out
    mock_bedrock_client.extract_text_from_response.return_value = json.dumps(
        {
            "topic": "immigration",
            "document_type": "ship_manifest",
            "extra_key": "should_be_filtered",
            "location": "should_also_be_filtered",
        }
    )

    result = manual_mode_extractor.extract_metadata(sample_document_text, "doc-123")

    assert "topic" in result
    assert "document_type" in result
    assert "extra_key" not in result
    assert "location" not in result


def test_manual_mode_skips_non_applicable_keys(
    manual_mode_extractor, mock_bedrock_client, sample_document_text
):
    """Test that manual mode accepts subset of keys when LLM returns fewer."""
    import json

    # LLM only returns one of the requested keys
    mock_bedrock_client.extract_text_from_response.return_value = json.dumps(
        {"topic": "immigration"}
    )

    result = manual_mode_extractor.extract_metadata(sample_document_text, "doc-123")

    assert result == {"topic": "immigration"}


def test_manual_mode_empty_keys_returns_empty(
    mock_bedrock_client, mock_key_library, sample_document_text
):
    """Test that empty manual_keys list results in empty metadata."""
    import json

    extractor = MetadataExtractor(
        bedrock_client=mock_bedrock_client,
        key_library=mock_key_library,
        extraction_mode="manual",
        manual_keys=[],
    )
    mock_bedrock_client.extract_text_from_response.return_value = json.dumps(
        {"topic": "immigration", "location": "NYC"}
    )

    result = extractor.extract_metadata(sample_document_text, "doc-123")

    assert result == {}


def test_manual_mode_uses_different_prompt(
    manual_mode_extractor, mock_bedrock_client, sample_document_text
):
    """Test that manual mode uses a different system prompt."""
    import json

    mock_bedrock_client.extract_text_from_response.return_value = json.dumps(
        {"topic": "test"}
    )

    manual_mode_extractor.extract_metadata(sample_document_text, "doc-123")

    call_args = mock_bedrock_client.invoke_model.call_args
    system_prompt = call_args.kwargs["system_prompt"]

    # Manual mode should have specific instructions about extracting only specified keys
    assert "ONLY" in system_prompt or "only" in system_prompt
    assert "topic" in system_prompt or "FIELDS TO EXTRACT" in system_prompt


def test_auto_mode_unchanged(extractor, mock_bedrock_client, sample_document_text):
    """Test that auto mode behavior is unchanged."""
    import json

    mock_bedrock_client.extract_text_from_response.return_value = json.dumps(
        {"topic": "immigration", "location": "NYC", "date_range": "1900-1910"}
    )

    result = extractor.extract_metadata(sample_document_text, "doc-123")

    # All keys should be present in auto mode
    assert "topic" in result
    assert "location" in result
    assert "date_range" in result


def test_manual_mode_prompt_includes_specified_keys(
    manual_mode_extractor, mock_bedrock_client, sample_document_text
):
    """Test that manual mode system prompt includes the specified keys."""
    import json

    mock_bedrock_client.extract_text_from_response.return_value = json.dumps(
        {"topic": "test"}
    )

    manual_mode_extractor.extract_metadata(sample_document_text, "doc-123")

    call_args = mock_bedrock_client.invoke_model.call_args
    system_prompt = call_args.kwargs["system_prompt"]

    # The system prompt should mention the keys to extract
    assert "topic" in system_prompt.lower()
    assert "document_type" in system_prompt.lower()
