"""Global pytest configuration for all tests.

Provides shared fixtures for metadata extraction testing including:
- Mocked DynamoDB tables
- Mocked Bedrock client
- Sample documents and metadata
"""

import os
from unittest.mock import MagicMock, patch

import pytest


def pytest_configure(config):
    """Set environment variables before any test collection or execution."""
    os.environ.setdefault("AWS_REGION", "us-east-1")
    os.environ.setdefault("REGION", "us-east-1")


# Import sample data (available after pytest collection)


@pytest.fixture
def sample_key_library_entries():
    """Sample key library entries for testing."""
    from tests.fixtures.metadata_samples import SAMPLE_KEY_LIBRARY_ENTRIES

    return SAMPLE_KEY_LIBRARY_ENTRIES


@pytest.fixture
def sample_immigration_text():
    """Sample immigration document text."""
    from tests.fixtures.metadata_samples import SAMPLE_IMMIGRATION_TEXT

    return SAMPLE_IMMIGRATION_TEXT


@pytest.fixture
def sample_census_text():
    """Sample census document text."""
    from tests.fixtures.metadata_samples import SAMPLE_CENSUS_TEXT

    return SAMPLE_CENSUS_TEXT


@pytest.fixture
def sample_genealogy_text():
    """Sample genealogy document text."""
    from tests.fixtures.metadata_samples import SAMPLE_GENEALOGY_TEXT

    return SAMPLE_GENEALOGY_TEXT


@pytest.fixture
def sample_image_caption():
    """Sample image caption text."""
    from tests.fixtures.metadata_samples import SAMPLE_IMAGE_CAPTION

    return SAMPLE_IMAGE_CAPTION


@pytest.fixture
def immigration_metadata():
    """Expected metadata for immigration documents."""
    from tests.fixtures.metadata_samples import IMMIGRATION_RECORD_METADATA

    return IMMIGRATION_RECORD_METADATA


@pytest.fixture
def census_metadata():
    """Expected metadata for census documents."""
    from tests.fixtures.metadata_samples import CENSUS_RECORD_METADATA

    return CENSUS_RECORD_METADATA


@pytest.fixture
def genealogy_metadata():
    """Expected metadata for genealogy documents."""
    from tests.fixtures.metadata_samples import GENEALOGY_DOCUMENT_METADATA

    return GENEALOGY_DOCUMENT_METADATA


# Mocked AWS Resources


@pytest.fixture
def mock_dynamodb_key_library_table():
    """Create a mocked DynamoDB table for key library."""
    mock_table = MagicMock()
    type(mock_table).table_status = "ACTIVE"
    mock_table.scan.return_value = {"Items": []}
    mock_table.get_item.return_value = {}
    mock_table.update_item.return_value = {}
    return mock_table


@pytest.fixture
def mock_key_library(mock_dynamodb_key_library_table):
    """Create a mocked KeyLibrary instance."""
    from ragstack_common.key_library import KeyLibrary

    with patch("ragstack_common.key_library.boto3.resource") as mock_resource:
        mock_resource.return_value.Table.return_value = mock_dynamodb_key_library_table
        library = KeyLibrary(table_name="test-key-library")
        _ = library.table  # Initialize table property
        library._table_exists = True
        return library


@pytest.fixture
def mock_bedrock_client():
    """Create a mocked BedrockClient."""
    from tests.mocks.bedrock_mock import create_mock_bedrock_client

    return create_mock_bedrock_client()


@pytest.fixture
def mock_metadata_extractor(mock_bedrock_client, mock_key_library):
    """Create a MetadataExtractor with mocked dependencies."""
    from ragstack_common.metadata_extractor import MetadataExtractor

    return MetadataExtractor(
        bedrock_client=mock_bedrock_client,
        key_library=mock_key_library,
    )


# S3 Vectors mocks (for future phases)


@pytest.fixture
def mock_s3vectors_client():
    """Create a mocked S3 Vectors client."""
    mock_client = MagicMock()

    # Default responses
    mock_client.list_vectors.return_value = {
        "vectors": [
            {"key": "vec1", "metadata": {"topic": "genealogy"}},
            {"key": "vec2", "metadata": {"topic": "immigration"}},
        ]
    }

    mock_client.query_vectors.return_value = {
        "vectors": [
            {"key": "vec1", "distance": 0.1, "metadata": {"topic": "genealogy"}},
            {"key": "vec2", "distance": 0.2, "metadata": {"topic": "immigration"}},
        ]
    }

    mock_client.put_vectors.return_value = {"status": "success"}

    return mock_client


# DynamoDB Tracking Table mock


@pytest.fixture
def mock_tracking_table():
    """Create a mocked tracking DynamoDB table."""
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "document_id": "test-doc-123",
            "filename": "test_document.pdf",
            "status": "processing",
            "total_pages": 5,
        }
    }
    mock_table.update_item.return_value = {}
    return mock_table


# Event fixtures for Lambda testing


@pytest.fixture
def ingest_event():
    """Sample ingest_to_kb Lambda event."""
    return {
        "document_id": "test-doc-123",
        "output_s3_uri": "s3://test-bucket/output/test-doc-123/full_text.txt",
        "filename": "test_document.pdf",
        "document_type": "pdf",
    }


@pytest.fixture
def process_image_event():
    """Sample process_image Lambda event."""
    return {
        "document_id": "test-img-456",
        "s3_uri": "s3://test-bucket/images/test-img-456.jpg",
        "filename": "family_photo.jpg",
        "caption": "Family photo from 1925 wedding ceremony",
        "caption_source": "user",
    }
