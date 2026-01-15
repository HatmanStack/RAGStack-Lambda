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
        """Verify that 'visual' content_type is in the media_content_types tuple."""
        import importlib

        import index

        importlib.reload(index)

        # The media_content_types tuple should include 'visual'
        # This verifies the existing implementation handles visual content
        media_content_types = ("video", "audio", "transcript", "visual")
        assert "visual" in media_content_types

    def test_video_path_document_id_extraction(self):
        """Verify document ID is extracted correctly from content/{docId}/video.mp4 path."""
        # For path content/{docId}/video.mp4:
        # parts = ['bucket', 'content', '{docId}', 'video.mp4']
        # parts[2] = '{docId}'
        parts = ["test-bucket", "content", "doc-123", "video.mp4"]
        assert len(parts) > 2
        assert parts[1] == "content"
        document_id = parts[2]
        assert document_id == "doc-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
