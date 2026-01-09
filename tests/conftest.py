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


