"""
Tests for media source extraction in query_kb Lambda.

Tests the extraction of media sources with timestamps, speaker labels,
and content_type metadata from Bedrock KB citations.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add Lambda source directory to path
sys.path.insert(0, str(Path(__file__).parents[3] / "src" / "lambda" / "query_kb"))


class TestMediaSourceExtraction:
    """Test cases for media source extraction from KB citations."""

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb_client = MagicMock()
        mock_conditions = MagicMock()
        mock_s3 = MagicMock()
        mock_bedrock_agent = MagicMock()
        mock_bedrock_runtime = MagicMock()

        # Setup mock clients
        mock_boto3.client.side_effect = lambda service, **kwargs: {
            "s3": mock_s3,
            "dynamodb": mock_dynamodb_client,
            "bedrock-agent-runtime": mock_bedrock_agent,
            "bedrock-runtime": mock_bedrock_runtime,
        }.get(service, MagicMock())

        mock_boto3.resource.return_value = mock_dynamodb
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
            mock_config.get_parameter.side_effect = lambda key, default=None: {
                "chat_allow_document_access": True,
            }.get(key, default)
            with patch("ragstack_common.config.ConfigurationManager", return_value=mock_config):
                # Store mocks for test access
                self.mock_boto3 = mock_boto3
                self.mock_s3 = mock_s3
                self.mock_dynamodb = mock_dynamodb
                yield

    def test_extract_media_source_with_transcript_content_type(self):
        """Test extraction of media source with transcript content_type."""
        import importlib
        import index

        importlib.reload(index)

        # Setup mock for tracking table lookup
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "media123",
                "filename": "interview.mp4",
                "input_s3_uri": "s3://test-bucket/input/media123/interview.mp4",
                "type": "media",
            }
        }
        index.dynamodb.Table.return_value = mock_table

        # Setup mock for presigned URL generation
        index.s3_client.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/test-bucket/input/media123/interview.mp4?sig=xyz"
        )

        citations = [
            {
                "retrievedReferences": [
                    {
                        "content": {"text": "The speaker mentioned the project deadline."},
                        "location": {
                            "s3Location": {"uri": "s3://test-bucket/content/media123/transcript.txt"}
                        },
                        "metadata": {
                            "content_type": "transcript",
                            "media_type": "video",
                            "timestamp_start": 90,
                            "timestamp_end": 120,
                            "speaker": "speaker_0",
                            "segment_index": 3,
                            "document_id": "media123",
                        },
                    }
                ]
            }
        ]

        sources = index.extract_sources(citations)

        assert len(sources) == 1
        source = sources[0]
        assert source["isMedia"] is True
        assert source["mediaType"] == "video"
        assert source["contentType"] == "transcript"
        assert source["timestampStart"] == 90
        assert source["timestampEnd"] == 120
        assert source["timestampDisplay"] == "1:30-2:00"
        assert source["speaker"] == "speaker_0"
        assert source["segmentIndex"] == 3

    def test_extract_media_source_with_visual_content_type(self):
        """Test extraction of media source with visual content_type."""
        import importlib
        import index

        importlib.reload(index)

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "media456",
                "filename": "lecture.mp4",
                "input_s3_uri": "s3://test-bucket/input/media456/lecture.mp4",
                "type": "media",
            }
        }
        index.dynamodb.Table.return_value = mock_table
        index.s3_client.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/test-bucket/input/media456/lecture.mp4?sig=xyz"
        )

        citations = [
            {
                "retrievedReferences": [
                    {
                        "content": {"text": "[Visual segment]"},
                        "location": {
                            "s3Location": {"uri": "s3://test-bucket/content/media456/segment_0.txt"}
                        },
                        "metadata": {
                            "content_type": "visual",
                            "media_type": "video",
                            "timestamp_start": 0,
                            "timestamp_end": 30,
                            "segment_index": 0,
                            "document_id": "media456",
                        },
                    }
                ]
            }
        ]

        sources = index.extract_sources(citations)

        assert len(sources) == 1
        source = sources[0]
        assert source["isMedia"] is True
        assert source["mediaType"] == "video"
        assert source["contentType"] == "visual"
        assert source["timestampStart"] == 0
        assert source["timestampEnd"] == 30
        assert source["timestampDisplay"] == "0:00-0:30"
        assert source.get("speaker") is None

    def test_extract_audio_source_with_transcript(self):
        """Test extraction of audio source with transcript."""
        import importlib
        import index

        importlib.reload(index)

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "audio789",
                "filename": "podcast.mp3",
                "input_s3_uri": "s3://test-bucket/input/audio789/podcast.mp3",
                "type": "media",
            }
        }
        index.dynamodb.Table.return_value = mock_table
        index.s3_client.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/test-bucket/input/audio789/podcast.mp3?sig=xyz"
        )

        citations = [
            {
                "retrievedReferences": [
                    {
                        "content": {"text": "Today we discuss machine learning trends."},
                        "location": {
                            "s3Location": {"uri": "s3://test-bucket/content/audio789/transcript.txt"}
                        },
                        "metadata": {
                            "content_type": "transcript",
                            "media_type": "audio",
                            "timestamp_start": 300,
                            "timestamp_end": 330,
                            "speaker": "speaker_1",
                            "segment_index": 10,
                            "document_id": "audio789",
                        },
                    }
                ]
            }
        ]

        sources = index.extract_sources(citations)

        assert len(sources) == 1
        source = sources[0]
        assert source["isMedia"] is True
        assert source["mediaType"] == "audio"
        assert source["contentType"] == "transcript"
        assert source["timestampStart"] == 300
        assert source["timestampEnd"] == 330
        assert source["timestampDisplay"] == "5:00-5:30"
        assert source["speaker"] == "speaker_1"

    def test_presigned_url_includes_timestamp_fragment(self):
        """Test that presigned URLs include #t= fragment for media sources."""
        import importlib
        import index

        importlib.reload(index)

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "media123",
                "filename": "video.mp4",
                "input_s3_uri": "s3://test-bucket/input/media123/video.mp4",
                "type": "media",
            }
        }
        index.dynamodb.Table.return_value = mock_table
        index.s3_client.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/test-bucket/input/media123/video.mp4?sig=xyz"
        )

        citations = [
            {
                "retrievedReferences": [
                    {
                        "content": {"text": "Test content"},
                        "location": {
                            "s3Location": {"uri": "s3://test-bucket/content/media123/transcript.txt"}
                        },
                        "metadata": {
                            "content_type": "transcript",
                            "media_type": "video",
                            "timestamp_start": 60,
                            "timestamp_end": 90,
                            "document_id": "media123",
                        },
                    }
                ]
            }
        ]

        sources = index.extract_sources(citations)

        assert len(sources) == 1
        source = sources[0]
        # Presigned URL should include #t=start,end fragment
        assert source["documentUrl"] is not None
        assert "#t=60,90" in source["documentUrl"]

    def test_document_source_not_marked_as_media(self):
        """Test that regular document sources are not marked as media."""
        import importlib
        import index

        importlib.reload(index)

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "doc123",
                "filename": "report.pdf",
                "input_s3_uri": "s3://test-bucket/input/doc123/report.pdf",
                "type": "document",
            }
        }
        index.dynamodb.Table.return_value = mock_table
        index.s3_client.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/test-bucket/input/doc123/report.pdf?sig=xyz"
        )

        citations = [
            {
                "retrievedReferences": [
                    {
                        "content": {"text": "Regular document content."},
                        "location": {
                            "s3Location": {
                                "uri": "s3://test-bucket/content/doc123/extracted_text.txt"
                            }
                        },
                        "metadata": {
                            "document_id": "doc123",
                        },
                    }
                ]
            }
        ]

        sources = index.extract_sources(citations)

        assert len(sources) == 1
        source = sources[0]
        # Regular documents should not have media fields set to True
        assert source.get("isMedia") is not True
        assert source.get("mediaType") is None
        assert source.get("timestampStart") is None

    def test_backward_compatibility_with_existing_image_sources(self):
        """Test that existing image sources still work correctly."""
        import importlib
        import index

        importlib.reload(index)

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "document_id": "img123",
                "filename": "photo.jpg",
                "input_s3_uri": "s3://test-bucket/content/img123/photo.jpg",
                "type": "image",
            }
        }
        index.dynamodb.Table.return_value = mock_table
        index.s3_client.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/test-bucket/content/img123/photo.jpg?sig=xyz"
        )

        citations = [
            {
                "retrievedReferences": [
                    {
                        "content": {"text": "---\nfilename: photo.jpg\n---\nA beautiful sunset."},
                        "location": {
                            "s3Location": {"uri": "s3://test-bucket/content/img123/caption.txt"}
                        },
                        "metadata": {},
                    }
                ]
            }
        ]

        sources = index.extract_sources(citations)

        assert len(sources) == 1
        source = sources[0]
        assert source["isImage"] is True
        # Image sources should not be marked as media
        assert source.get("isMedia") is not True


class TestTimestampFormatting:
    """Test cases for timestamp display formatting."""

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()
        mock_dynamodb = MagicMock()
        mock_conditions = MagicMock()

        mock_boto3.resource.return_value = mock_dynamodb
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

    def test_format_timestamp_seconds_only(self):
        """Test formatting timestamps under 1 minute."""
        import importlib
        import index

        importlib.reload(index)

        assert index.format_timestamp(0) == "0:00"
        assert index.format_timestamp(30) == "0:30"
        assert index.format_timestamp(59) == "0:59"

    def test_format_timestamp_minutes_and_seconds(self):
        """Test formatting timestamps over 1 minute."""
        import importlib
        import index

        importlib.reload(index)

        assert index.format_timestamp(60) == "1:00"
        assert index.format_timestamp(90) == "1:30"
        assert index.format_timestamp(125) == "2:05"
        assert index.format_timestamp(600) == "10:00"

    def test_format_timestamp_hours(self):
        """Test formatting timestamps over 1 hour."""
        import importlib
        import index

        importlib.reload(index)

        assert index.format_timestamp(3600) == "60:00"  # 1 hour = 60 minutes
        assert index.format_timestamp(3661) == "61:01"  # 1h 1m 1s
        assert index.format_timestamp(7200) == "120:00"  # 2 hours


class TestMediaUrlGeneration:
    """Test cases for media URL generation with timestamp fragments."""

    @pytest.fixture(autouse=True)
    def _mock_boto3(self):
        """Mock boto3 clients to avoid AWS initialization."""
        mock_boto3 = MagicMock()
        mock_dynamodb = MagicMock()
        mock_conditions = MagicMock()
        mock_s3 = MagicMock()

        mock_boto3.client.side_effect = lambda service, **kwargs: {
            "s3": mock_s3,
        }.get(service, MagicMock())

        mock_boto3.resource.return_value = mock_dynamodb
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
                self.mock_s3 = mock_s3
                yield

    def test_generate_media_url_with_timestamps(self):
        """Test generating presigned URL with timestamp fragment."""
        import importlib
        import index

        importlib.reload(index)

        index.s3_client.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/bucket/key?sig=abc"
        )

        url = index.generate_media_url("test-bucket", "video.mp4", 90, 120)

        assert url is not None
        assert "#t=90,120" in url

    def test_generate_media_url_without_timestamps(self):
        """Test generating presigned URL without timestamps."""
        import importlib
        import index

        importlib.reload(index)

        index.s3_client.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/bucket/key?sig=abc"
        )

        url = index.generate_media_url("test-bucket", "video.mp4", None, None)

        assert url is not None
        assert "#t=" not in url

    def test_generate_media_url_with_start_only(self):
        """Test generating presigned URL with start timestamp only."""
        import importlib
        import index

        importlib.reload(index)

        index.s3_client.generate_presigned_url.return_value = (
            "https://s3.amazonaws.com/bucket/key?sig=abc"
        )

        url = index.generate_media_url("test-bucket", "video.mp4", 60, None)

        assert url is not None
        assert "#t=60" in url

    def test_generate_media_url_returns_none_on_error(self):
        """Test that URL generation returns None on error."""
        import importlib
        import index

        importlib.reload(index)

        index.s3_client.generate_presigned_url.side_effect = Exception("S3 error")

        url = index.generate_media_url("test-bucket", "video.mp4", 0, 30)

        assert url is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
