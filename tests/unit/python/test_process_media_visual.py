"""Unit tests for ProcessMedia visual segment extraction.

Tests the visual segment preparation functionality in ProcessMedia Lambda.

Note: Since 'lambda' is a Python keyword, we use importlib to load the module.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_process_media_module():
    """Load the process_media index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src"
        / "lambda"
        / "process_media"
        / "index.py"
    ).resolve()

    spec = importlib.util.spec_from_file_location("process_media_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["process_media_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    """Set required environment variables for all tests."""
    env_vars = {
        "TRACKING_TABLE": "test-tracking-table",
        "VECTOR_BUCKET": "test-vector-bucket",
        "GRAPHQL_ENDPOINT": "https://test-api.appsync.amazonaws.com/graphql",
        "AWS_REGION": "us-east-1",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    }
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def sample_media_event():
    """Sample media processing event."""
    return {
        "document_id": "media-123",
        "input_s3_uri": "s3://test-bucket/uploads/video.mp4",
        "output_s3_prefix": "s3://test-bucket/content/media-123/",
        "fileType": "media",
        "detectedType": "video",
    }


class TestProcessMediaVisualExtraction:
    """Tests for visual segment extraction in ProcessMedia."""

    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.visual_segmenter.VisualSegmenter")
    @patch("ragstack_common.transcribe_client.TranscribeClient")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("boto3.resource")
    @patch("boto3.client")
    def test_extracts_visual_segments_after_transcription(
        self,
        mock_boto_client,
        mock_boto_resource,
        mock_config_manager,
        mock_transcribe_class,
        mock_segmenter_class,
        mock_publish,
        sample_media_event,
    ):
        """Test that visual segments are extracted after transcription."""
        # Mock ConfigurationManager
        mock_config = MagicMock()
        mock_config.get_parameter.return_value = 30
        mock_config_manager.return_value = mock_config

        # Mock S3 client
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": 1000000}
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=lambda: b'{"results": {"transcripts": [{"transcript": "test"}], "items": []}}'
            )
        }

        # Mock DynamoDB
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table

        # Mock Transcribe
        mock_transcribe = MagicMock()
        mock_transcribe.start_transcription_job.return_value = "test-job"
        mock_transcribe.wait_for_completion.return_value = {
            "status": "COMPLETED",
            "transcript_uri": "s3://bucket/transcripts/test.json",
        }
        mock_transcribe.parse_transcript_with_timestamps.return_value = []
        mock_transcribe_class.return_value = mock_transcribe

        # Mock VisualSegmenter
        mock_segmenter = MagicMock()
        mock_segmenter.extract_segments_to_s3.return_value = [
            {
                "segment_index": 0,
                "timestamp_start": 0,
                "timestamp_end": 30,
                "s3_uri": "s3://bucket/segments/segment_000.mp4",
            },
        ]
        mock_segmenter_class.return_value = mock_segmenter

        mock_boto_client.return_value = mock_s3

        module = load_process_media_module()
        result = module.lambda_handler(sample_media_event, None)

        # Visual segments should be in output
        assert "visual_segments" in result
        assert len(result["visual_segments"]) > 0

    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.visual_segmenter.VisualSegmenter")
    @patch("ragstack_common.transcribe_client.TranscribeClient")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("boto3.resource")
    @patch("boto3.client")
    def test_continues_if_visual_extraction_fails(
        self,
        mock_boto_client,
        mock_boto_resource,
        mock_config_manager,
        mock_transcribe_class,
        mock_segmenter_class,
        mock_publish,
        sample_media_event,
    ):
        """Test that processing continues if visual extraction fails."""
        mock_config = MagicMock()
        mock_config.get_parameter.return_value = 30
        mock_config_manager.return_value = mock_config

        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": 1000000}
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=lambda: b'{"results": {"transcripts": [{"transcript": "test"}], "items": []}}'
            )
        }

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table

        mock_transcribe = MagicMock()
        mock_transcribe.start_transcription_job.return_value = "test-job"
        mock_transcribe.wait_for_completion.return_value = {
            "status": "COMPLETED",
            "transcript_uri": "s3://bucket/transcripts/test.json",
        }
        mock_transcribe.parse_transcript_with_timestamps.return_value = []
        mock_transcribe_class.return_value = mock_transcribe

        # Visual segmenter fails
        mock_segmenter = MagicMock()
        mock_segmenter.extract_segments_to_s3.side_effect = Exception("FFmpeg failed")
        mock_segmenter_class.return_value = mock_segmenter

        mock_boto_client.return_value = mock_s3

        module = load_process_media_module()
        result = module.lambda_handler(sample_media_event, None)

        # Should still succeed with empty visual segments
        assert result["status"] == "transcribed"
        assert result.get("visual_segments", []) == []

    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.visual_segmenter.VisualSegmenter")
    @patch("ragstack_common.transcribe_client.TranscribeClient")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("boto3.resource")
    @patch("boto3.client")
    def test_audio_only_skips_visual_extraction(
        self,
        mock_boto_client,
        mock_boto_resource,
        mock_config_manager,
        mock_transcribe_class,
        mock_segmenter_class,
        mock_publish,
    ):
        """Test that audio-only files skip visual extraction."""
        mock_config = MagicMock()
        mock_config.get_parameter.return_value = 30
        mock_config_manager.return_value = mock_config

        event = {
            "document_id": "audio-123",
            "input_s3_uri": "s3://test-bucket/uploads/audio.mp3",
            "output_s3_prefix": "s3://test-bucket/content/audio-123/",
            "fileType": "media",
            "detectedType": "audio",
        }

        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": 500000}
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=lambda: b'{"results": {"transcripts": [{"transcript": "test"}], "items": []}}'
            )
        }

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table

        mock_transcribe = MagicMock()
        mock_transcribe.start_transcription_job.return_value = "test-job"
        mock_transcribe.wait_for_completion.return_value = {
            "status": "COMPLETED",
            "transcript_uri": "s3://bucket/transcripts/test.json",
        }
        mock_transcribe.parse_transcript_with_timestamps.return_value = []
        mock_transcribe_class.return_value = mock_transcribe

        mock_segmenter = MagicMock()
        mock_segmenter_class.return_value = mock_segmenter

        mock_boto_client.return_value = mock_s3

        module = load_process_media_module()
        result = module.lambda_handler(event, None)

        # Audio should not extract visual segments
        assert result["media_type"] == "audio"
        # VisualSegmenter should not be called for audio
        mock_segmenter.extract_segments_to_s3.assert_not_called()


class TestProcessMediaOutputFormat:
    """Tests for ProcessMedia output format."""

    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.visual_segmenter.VisualSegmenter")
    @patch("ragstack_common.transcribe_client.TranscribeClient")
    @patch("ragstack_common.config.ConfigurationManager")
    @patch("boto3.resource")
    @patch("boto3.client")
    def test_output_contains_both_segment_types(
        self,
        mock_boto_client,
        mock_boto_resource,
        mock_config_manager,
        mock_transcribe_class,
        mock_segmenter_class,
        mock_publish,
        sample_media_event,
    ):
        """Test that output contains both transcript and visual segments."""
        mock_config = MagicMock()
        mock_config.get_parameter.return_value = 30
        mock_config_manager.return_value = mock_config

        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": 1000000}
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=lambda: b'{"results": {"transcripts": [{"transcript": "test"}], "items": []}}'
            )
        }

        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table

        mock_transcribe = MagicMock()
        mock_transcribe.start_transcription_job.return_value = "test-job"
        mock_transcribe.wait_for_completion.return_value = {
            "status": "COMPLETED",
            "transcript_uri": "s3://bucket/transcripts/test.json",
        }
        mock_transcribe.parse_transcript_with_timestamps.return_value = [
            {"word": "test", "start_time": 0, "end_time": 0.5}
        ]
        mock_transcribe_class.return_value = mock_transcribe

        mock_segmenter = MagicMock()
        mock_segmenter.extract_segments_to_s3.return_value = [
            {
                "segment_index": 0,
                "timestamp_start": 0,
                "timestamp_end": 30,
                "s3_uri": "s3://bucket/segments/segment_000.mp4",
            },
        ]
        mock_segmenter_class.return_value = mock_segmenter

        mock_boto_client.return_value = mock_s3

        module = load_process_media_module()
        result = module.lambda_handler(sample_media_event, None)

        # Check output format
        assert "document_id" in result
        assert "output_s3_uri" in result
        assert "total_segments" in result
        assert "visual_segments" in result
        assert "transcript_segments" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
