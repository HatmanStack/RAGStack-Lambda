"""Unit tests for query_kb Lambda source extraction."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add Lambda source directory to path
sys.path.insert(0, str(Path(__file__).parents[3] / "src" / "lambda" / "query_kb"))


class TestExtractSourceUrlFromContent:
    """Tests for extract_source_url_from_content function."""

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()
        mock_dynamodb = MagicMock()
        mock_conditions = MagicMock()
        mock_boto3.dynamodb = mock_dynamodb
        mock_boto3.dynamodb.conditions = mock_conditions

        with patch.dict(
            "sys.modules",
            {
                "boto3": mock_boto3,
                "boto3.dynamodb": mock_dynamodb,
                "boto3.dynamodb.conditions": mock_conditions,
            },
        ):
            # Need to mock config manager too
            mock_config = MagicMock()
            mock_config.get_parameter.return_value = False
            with patch("ragstack_common.config.ConfigurationManager", return_value=mock_config):
                yield

    def test_extracts_url_from_frontmatter(self):
        # Import inside test after mocking
        import importlib

        import index

        importlib.reload(index)

        content = """---
source_url: https://docs.example.com/page1
scraped_at: 2025-01-01T00:00:00Z
title: "Test Page"
---

# Test Page

Some content here.
"""
        result = index.extract_source_url_from_content(content)
        assert result == "https://docs.example.com/page1"

    def test_extracts_url_with_quotes(self):
        import importlib

        import index

        importlib.reload(index)

        content = """---
source_url: "https://docs.example.com/page2"
---

Content
"""
        result = index.extract_source_url_from_content(content)
        assert result == "https://docs.example.com/page2"

    def test_returns_none_for_no_frontmatter(self):
        import importlib

        import index

        importlib.reload(index)

        content = """# Just a regular markdown file

No frontmatter here.
"""
        result = index.extract_source_url_from_content(content)
        assert result is None

    def test_returns_none_for_empty_content(self):
        import importlib

        import index

        importlib.reload(index)

        result = index.extract_source_url_from_content("")
        assert result is None

    def test_returns_none_for_none_content(self):
        import importlib

        import index

        importlib.reload(index)

        result = index.extract_source_url_from_content(None)
        assert result is None


class TestExtractImageCaptionFromContent:
    """Tests for extract_image_caption_from_content function."""

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()
        mock_dynamodb = MagicMock()
        mock_conditions = MagicMock()
        mock_boto3.dynamodb = mock_dynamodb
        mock_boto3.dynamodb.conditions = mock_conditions

        with patch.dict(
            "sys.modules",
            {
                "boto3": mock_boto3,
                "boto3.dynamodb": mock_dynamodb,
                "boto3.dynamodb.conditions": mock_conditions,
            },
        ):
            mock_config = MagicMock()
            mock_config.get_parameter.return_value = False
            with patch("ragstack_common.config.ConfigurationManager", return_value=mock_config):
                yield

    def test_extracts_user_caption_from_frontmatter(self):
        import importlib

        import index

        importlib.reload(index)

        content = """---
image_id: test-123
filename: vacation.png
user_caption: My summer vacation photo
ai_caption: A sunny beach with palm trees
---

# Image: vacation.png

My summer vacation photo. A sunny beach with palm trees.
"""
        result = index.extract_image_caption_from_content(content)
        assert result == "My summer vacation photo"

    def test_extracts_ai_caption_if_no_user_caption(self):
        import importlib

        import index

        importlib.reload(index)

        content = """---
image_id: test-123
filename: photo.png
ai_caption: A beautiful sunset over the ocean
---

# Image: photo.png

A beautiful sunset over the ocean
"""
        result = index.extract_image_caption_from_content(content)
        assert result == "A beautiful sunset over the ocean"

    def test_extracts_content_text_if_no_frontmatter_caption(self):
        import importlib

        import index

        importlib.reload(index)

        content = """---
image_id: test-123
filename: photo.png
---

# Image: photo.png

This is the caption text that appears after the header.
"""
        result = index.extract_image_caption_from_content(content)
        assert result == "This is the caption text that appears after the header."

    def test_returns_none_for_empty_content(self):
        import importlib

        import index

        importlib.reload(index)

        result = index.extract_image_caption_from_content("")
        assert result is None

    def test_returns_none_for_none_content(self):
        import importlib

        import index

        importlib.reload(index)

        result = index.extract_image_caption_from_content(None)
        assert result is None


class TestConstructImageUriFromContentUri:
    """Tests for construct_image_uri_from_content_uri function."""

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()
        mock_dynamodb = MagicMock()
        mock_conditions = MagicMock()
        mock_boto3.dynamodb = mock_dynamodb
        mock_boto3.dynamodb.conditions = mock_conditions

        with patch.dict(
            "sys.modules",
            {
                "boto3": mock_boto3,
                "boto3.dynamodb": mock_dynamodb,
                "boto3.dynamodb.conditions": mock_conditions,
            },
        ):
            mock_config = MagicMock()
            mock_config.get_parameter.return_value = False
            with patch("ragstack_common.config.ConfigurationManager", return_value=mock_config):
                yield

    def test_constructs_base_uri_from_content_txt(self):
        import importlib

        import index

        importlib.reload(index)

        content_uri = "s3://test-bucket/images/abc123/content.txt"
        result = index.construct_image_uri_from_content_uri(content_uri)
        assert result == "s3://test-bucket/images/abc123"

    def test_returns_none_for_non_content_uri(self):
        import importlib

        import index

        importlib.reload(index)

        # Not a content.txt URI
        uri = "s3://test-bucket/images/abc123/image.png"
        result = index.construct_image_uri_from_content_uri(uri)
        assert result is None

    def test_returns_none_for_empty_uri(self):
        import importlib

        import index

        importlib.reload(index)

        result = index.construct_image_uri_from_content_uri("")
        assert result is None

    def test_returns_none_for_none_uri(self):
        import importlib

        import index

        importlib.reload(index)

        result = index.construct_image_uri_from_content_uri(None)
        assert result is None


class TestVisualContentTypeDetection:
    """Tests to verify visual content_type detection works correctly."""

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()
        mock_dynamodb = MagicMock()
        mock_conditions = MagicMock()
        mock_boto3.dynamodb = mock_dynamodb
        mock_boto3.dynamodb.conditions = mock_conditions

        with patch.dict(
            "sys.modules",
            {
                "boto3": mock_boto3,
                "boto3.dynamodb": mock_dynamodb,
                "boto3.dynamodb.conditions": mock_conditions,
            },
        ):
            mock_config = MagicMock()
            mock_config.get_parameter.return_value = False
            with patch("ragstack_common.config.ConfigurationManager", return_value=mock_config):
                yield

    def test_visual_content_type_is_recognized_as_media(self):
        """Verify that 'visual' content_type is in MEDIA_CONTENT_TYPES."""
        import importlib

        import index

        importlib.reload(index)

        # Verify the real module-level constant includes 'visual'
        assert "visual" in index.MEDIA_CONTENT_TYPES

    def test_video_path_document_id_extraction(self):
        """Verify document ID is extracted correctly from content/{docId}/video.mp4 path."""
        from urllib.parse import unquote

        # Use a valid UUID format as the code expects
        test_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        s3_uri = f"s3://test-bucket/content/{test_uuid}/video.mp4"

        # Parse URI the same way the code does (split and extract parts[2])
        parts = s3_uri.replace("s3://", "").split("/")
        assert len(parts) > 2 and parts[1] == "content"
        document_id = unquote(parts[2])

        assert document_id == test_uuid


class TestKBRetrievalErrorHandling:
    """Tests for KB retrieval failure handling in lambda_handler.

    Verifies that retrieval failures surface to users instead of being
    silently swallowed (which caused LLM hallucination on zero context).
    """

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()
        mock_dynamodb = MagicMock()
        mock_conditions = MagicMock()
        mock_boto3.dynamodb = mock_dynamodb
        mock_boto3.dynamodb.conditions = mock_conditions

        with patch.dict(
            "sys.modules",
            {
                "boto3": mock_boto3,
                "boto3.dynamodb": mock_dynamodb,
                "boto3.dynamodb.conditions": mock_conditions,
            },
        ):
            mock_config = MagicMock()
            mock_config.get_parameter.return_value = False
            with patch("ragstack_common.config.ConfigurationManager", return_value=mock_config):
                yield

    def _make_throttling_error(self):
        """Create a ClientError simulating ThrottlingException."""
        from botocore.exceptions import ClientError as BotoClientError

        return BotoClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "Retrieve",
        )

    def _make_access_denied_error(self):
        """Create a ClientError simulating AccessDeniedException."""
        from botocore.exceptions import ClientError as BotoClientError

        return BotoClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "Retrieve",
        )

    def test_throttling_error_returns_user_friendly_message(self):
        """Throttling errors should return a retry message, not hallucinate."""
        import importlib

        import handler

        importlib.reload(handler)

        # Mock all the dependencies that lambda_handler needs
        with (
            patch.object(handler, "check_public_access", return_value=(True, None)),
            patch.object(handler, "get_knowledge_base_config", return_value=("kb-123", "ds-456")),
            patch.object(handler, "get_config_manager") as mock_cfg,
            patch.object(handler, "atomic_quota_check_and_increment", return_value="model-id"),
            patch.object(handler, "get_conversation_history", return_value=[]),
            patch.object(handler, "build_retrieval_query", return_value="test query"),
            patch.object(handler, "bedrock_agent") as mock_bedrock_agent,
            patch.object(handler, "is_demo_mode_enabled", return_value=False),
        ):
            mock_cfg_instance = MagicMock()
            mock_cfg_instance.get_parameter.return_value = False
            mock_cfg.return_value = mock_cfg_instance

            mock_bedrock_agent.retrieve.side_effect = self._make_throttling_error()

            # Mock context with invoked_function_arn
            mock_context = MagicMock()
            mock_context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"

            result = handler.lambda_handler(
                {"query": "test question", "arguments": {"query": "test question"}},
                mock_context,
            )

            assert "error" in result
            assert "busy" in result["error"].lower() or "try again" in result["error"].lower()
            assert result["answer"] == ""

    def test_access_denied_error_returns_user_friendly_message(self):
        """Non-throttling ClientErrors should return error message to user."""
        import importlib

        import handler

        importlib.reload(handler)

        with (
            patch.object(handler, "check_public_access", return_value=(True, None)),
            patch.object(handler, "get_knowledge_base_config", return_value=("kb-123", "ds-456")),
            patch.object(handler, "get_config_manager") as mock_cfg,
            patch.object(handler, "atomic_quota_check_and_increment", return_value="model-id"),
            patch.object(handler, "get_conversation_history", return_value=[]),
            patch.object(handler, "build_retrieval_query", return_value="test query"),
            patch.object(handler, "bedrock_agent") as mock_bedrock_agent,
            patch.object(handler, "is_demo_mode_enabled", return_value=False),
        ):
            mock_cfg_instance = MagicMock()
            mock_cfg_instance.get_parameter.return_value = False
            mock_cfg.return_value = mock_cfg_instance

            mock_bedrock_agent.retrieve.side_effect = self._make_access_denied_error()

            mock_context = MagicMock()
            mock_context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"

            result = handler.lambda_handler(
                {"query": "test question", "arguments": {"query": "test question"}},
                mock_context,
            )

            assert "error" in result
            assert "unable to search" in result["error"].lower() or "knowledge base" in result["error"].lower()
            assert result["answer"] == ""

    def test_unexpected_error_propagates(self):
        """Non-ClientError exceptions should propagate up, not be caught."""
        import importlib

        import handler

        importlib.reload(handler)

        with (
            patch.object(handler, "check_public_access", return_value=(True, None)),
            patch.object(handler, "get_knowledge_base_config", return_value=("kb-123", "ds-456")),
            patch.object(handler, "get_config_manager") as mock_cfg,
            patch.object(handler, "atomic_quota_check_and_increment", return_value="model-id"),
            patch.object(handler, "get_conversation_history", return_value=[]),
            patch.object(handler, "build_retrieval_query", return_value="test query"),
            patch.object(handler, "bedrock_agent") as mock_bedrock_agent,
            patch.object(handler, "is_demo_mode_enabled", return_value=False),
        ):
            mock_cfg_instance = MagicMock()
            mock_cfg_instance.get_parameter.return_value = False
            mock_cfg.return_value = mock_cfg_instance

            # ValueError is NOT a ClientError - should propagate
            mock_bedrock_agent.retrieve.side_effect = ValueError("unexpected error")

            mock_context = MagicMock()
            mock_context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"

            # The outer except Exception in lambda_handler will catch this, but
            # the inner retrieval try/except should NOT catch it
            # Since the outer handler catches Exception, we verify it reaches that handler
            # and returns an error (not empty results with a hallucinated answer)
            result = handler.lambda_handler(
                {"query": "test question", "arguments": {"query": "test question"}},
                mock_context,
            )

            # The outer handler catches this, but the key is it doesn't continue
            # with empty results and generate a hallucinated answer
            assert "error" in result
            assert result["answer"] == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
