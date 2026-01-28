"""Unit tests for reindex_kb Lambda

Tests the reindex Lambda handler with mocked AWS services.
Verifies KB creation, document processing, and KB deletion.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


def load_reindex_module():
    """Load the reindex_kb index module dynamically."""
    lambda_dir = (
        Path(__file__).parent.parent.parent.parent / "src" / "lambda" / "reindex_kb"
    ).resolve()
    module_path = lambda_dir / "index.py"

    # Add lambda dir to path so kb_migrator can be imported
    if str(lambda_dir) not in sys.path:
        sys.path.insert(0, str(lambda_dir))

    spec = importlib.util.spec_from_file_location("reindex_kb_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["reindex_kb_index"] = module
    spec.loader.exec_module(module)
    return module


def load_kb_migrator_module():
    """Load the kb_migrator module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src"
        / "lambda"
        / "reindex_kb"
        / "kb_migrator.py"
    ).resolve()

    spec = importlib.util.spec_from_file_location("kb_migrator", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["kb_migrator"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    """Set required environment variables for all tests."""
    env_vars = {
        "TRACKING_TABLE": "test-tracking-table",
        "DATA_BUCKET": "test-data-bucket",
        "STACK_NAME": "test-stack",
        "KB_ROLE_ARN": "arn:aws:iam::123456789:role/test-kb-role",
        "EMBEDDING_MODEL_ARN": "arn:aws:bedrock:us-east-1::foundation-model/test-embed",
        "KNOWLEDGE_BASE_ID": "test-old-kb-id",
        "GRAPHQL_ENDPOINT": "https://test-appsync.amazonaws.com/graphql",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
        "METADATA_KEY_LIBRARY_TABLE": "test-key-library-table",
        "AWS_REGION": "us-east-1",
    }
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.function_name = "test-reindex"
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"
    return context


class TestKBMigrator:
    """Tests for KBMigrator class."""

    def test_init_sets_attributes(self, set_env_vars):
        """Test KBMigrator initializes with correct attributes."""
        with patch("boto3.Session"), patch("boto3.client"):
            module = load_kb_migrator_module()
            migrator = module.KBMigrator(
                data_bucket="test-bucket",
                vector_bucket="test-vector-bucket",
                stack_name="test-stack",
                kb_role_arn="arn:aws:iam::123:role/test",
                embedding_model_arn="arn:aws:bedrock:us-east-1::model/test",
            )
            assert migrator.data_bucket == "test-bucket"
            assert migrator.vector_bucket == "test-vector-bucket"
            assert migrator.stack_name == "test-stack"

    def test_delete_knowledge_base_not_found(self, set_env_vars):
        """Test deleting a KB that doesn't exist."""
        with patch("boto3.Session"), patch("boto3.client"):
            module = load_kb_migrator_module()

            migrator = module.KBMigrator(
                data_bucket="test-bucket",
                vector_bucket="test-vector-bucket",
                stack_name="test-stack",
                kb_role_arn="arn:aws:iam::123:role/test",
                embedding_model_arn="arn:aws:bedrock:us-east-1::model/test",
            )

            # Mock bedrock-agent client to return not found
            migrator.bedrock_agent = MagicMock()
            migrator.bedrock_agent.get_knowledge_base.side_effect = ClientError(
                {"Error": {"Code": "ResourceNotFoundException"}}, "get_knowledge_base"
            )

            # Should not raise - KB already deleted
            migrator.delete_knowledge_base("nonexistent-kb-id")


class TestLambdaHandler:
    """Tests for Lambda handler functions."""

    def test_handler_routes_init(self, set_env_vars, lambda_context):
        """Test handler routes to init action."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
            patch("boto3.Session"),
        ):
            module = load_reindex_module()

            with patch.object(module, "handle_init") as mock_init:
                mock_init.return_value = {"action": "process_batch"}
                result = module.lambda_handler({"action": "init"}, lambda_context)
                mock_init.assert_called_once()
                assert result["action"] == "process_batch"

    def test_handler_routes_process_batch(self, set_env_vars, lambda_context):
        """Test handler routes to process_batch action."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
            patch("boto3.Session"),
        ):
            module = load_reindex_module()

            with patch.object(module, "handle_process_batch") as mock_process:
                mock_process.return_value = {"action": "finalize"}
                result = module.lambda_handler({"action": "process_batch"}, lambda_context)
                mock_process.assert_called_once()
                assert result["action"] == "finalize"

    def test_handler_routes_finalize(self, set_env_vars, lambda_context):
        """Test handler routes to finalize action."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
            patch("boto3.Session"),
        ):
            module = load_reindex_module()

            with patch.object(module, "handle_finalize") as mock_finalize:
                mock_finalize.return_value = {"status": "COMPLETED"}
                result = module.lambda_handler({"action": "finalize"}, lambda_context)
                mock_finalize.assert_called_once()
                assert result["status"] == "COMPLETED"

    def test_handler_routes_cleanup_failed(self, set_env_vars, lambda_context):
        """Test handler routes to cleanup_failed action."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
            patch("boto3.Session"),
        ):
            module = load_reindex_module()

            with patch.object(module, "handle_cleanup_failed") as mock_cleanup:
                mock_cleanup.return_value = {"status": "FAILED"}
                result = module.lambda_handler({"action": "cleanup_failed"}, lambda_context)
                mock_cleanup.assert_called_once()
                assert result["status"] == "FAILED"

    def test_handler_unknown_action_raises(self, set_env_vars, lambda_context):
        """Test handler raises on unknown action."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
            patch("boto3.Session"),
            patch("ragstack_common.appsync.publish_reindex_update"),
        ):
            module = load_reindex_module()

            with pytest.raises(ValueError, match="Unknown action"):
                module.lambda_handler({"action": "invalid"}, lambda_context)


class TestListAllContent:
    """Tests for list_all_content function."""

    def test_returns_all_content_types(self, set_env_vars):
        """Test listing all content types from DynamoDB."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
            patch("boto3.Session"),
        ):
            module = load_reindex_module()

            mock_table = MagicMock()
            mock_table.scan.return_value = {
                "Items": [
                    {"document_id": "doc1", "filename": "test.pdf"},  # document (no type)
                    {"document_id": "img1", "filename": "photo.jpg", "type": "image"},
                    {"document_id": "scrape1", "filename": "page.md", "type": "scraped"},
                ]
            }

            result = module.list_all_content(mock_table)
            assert len(result) == 3
            # Documents first, then images, then scraped (sorted order)
            assert result[0]["document_id"] == "doc1"
            assert result[1]["document_id"] == "img1"
            assert result[2]["document_id"] == "scrape1"

    def test_handles_pagination(self, set_env_vars):
        """Test handling paginated DynamoDB results."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
            patch("boto3.Session"),
        ):
            module = load_reindex_module()

            mock_table = MagicMock()
            mock_table.scan.side_effect = [
                {
                    "Items": [{"document_id": "doc1"}],
                    "LastEvaluatedKey": {"document_id": "doc1"},
                },
                {"Items": [{"document_id": "doc2"}]},
            ]

            result = module.list_all_content(mock_table)
            assert len(result) == 2

    def test_sorts_by_type(self, set_env_vars):
        """Test content is sorted by type: documents, images, scraped."""
        with (
            patch("boto3.client"),
            patch("boto3.resource"),
            patch("boto3.Session"),
        ):
            module = load_reindex_module()

            mock_table = MagicMock()
            # Items returned in random order
            mock_table.scan.return_value = {
                "Items": [
                    {"document_id": "scrape1", "type": "scraped"},
                    {"document_id": "img1", "type": "image"},
                    {"document_id": "doc1"},  # no type = document
                    {"document_id": "img2", "type": "image"},
                ]
            }

            result = module.list_all_content(mock_table)
            assert len(result) == 4
            # Sorted: documents first, then images, then scraped
            assert result[0]["document_id"] == "doc1"
            assert result[1]["document_id"] == "img1"
            assert result[2]["document_id"] == "img2"
            assert result[3]["document_id"] == "scrape1"
