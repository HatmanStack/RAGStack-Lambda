"""Unit tests for ProcessMedia Lambda."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_process_media_module():
    """Load the process_media index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent / "src" / "lambda" / "process_media" / "index.py"
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
        "GRAPHQL_ENDPOINT": "https://test.appsync.com/graphql",
        "CONFIGURATION_TABLE_NAME": "test-config-table",
    }
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def sample_event():
    """Sample input event for ProcessMedia Lambda."""
    return {
        "document_id": "doc-123",
        "input_s3_uri": "s3://input-bucket/uploads/video.mp4",
        "output_s3_prefix": "s3://output-bucket/content/doc-123/",
        "fileType": "media",
        "detectedType": "video",
    }


@pytest.fixture
def sample_transcript_json():
    """Sample Transcribe output JSON."""
    return {
        "results": {
            "transcripts": [{"transcript": "Hello world this is a test"}],
            "items": [
                {
                    "type": "pronunciation",
                    "alternatives": [{"content": "Hello", "confidence": "0.99"}],
                    "start_time": "0.0",
                    "end_time": "0.5",
                },
                {
                    "type": "pronunciation",
                    "alternatives": [{"content": "world", "confidence": "0.98"}],
                    "start_time": "0.5",
                    "end_time": "1.0",
                },
                {
                    "type": "pronunciation",
                    "alternatives": [{"content": "this", "confidence": "0.97"}],
                    "start_time": "1.0",
                    "end_time": "1.3",
                },
                {
                    "type": "pronunciation",
                    "alternatives": [{"content": "is", "confidence": "0.99"}],
                    "start_time": "1.3",
                    "end_time": "1.5",
                },
                {
                    "type": "pronunciation",
                    "alternatives": [{"content": "a", "confidence": "0.99"}],
                    "start_time": "1.5",
                    "end_time": "1.6",
                },
                {
                    "type": "pronunciation",
                    "alternatives": [{"content": "test", "confidence": "0.95"}],
                    "start_time": "1.6",
                    "end_time": "2.0",
                },
            ],
        }
    }


class TestProcessMediaValidation:
    """Tests for input validation."""

    def test_missing_tracking_table_raises_error(self, sample_event):
        """Test that missing TRACKING_TABLE raises error."""
        with (
            patch.dict(os.environ, {"TRACKING_TABLE": ""}, clear=False),
            patch.dict(os.environ, {}, clear=True),
        ):
            module = load_process_media_module()
            with pytest.raises(ValueError, match="TRACKING_TABLE"):
                module.lambda_handler(sample_event, None)


class TestProcessMediaFlow:
    """Tests for the main processing flow."""

    @patch("ragstack_common.transcribe_client.TranscribeClient")
    @patch("ragstack_common.media_segmenter.MediaSegmenter")
    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.config.ConfigurationManager")
    def test_processes_video_file(
        self,
        mock_config_manager_class,
        mock_publish,
        mock_boto3_resource,
        mock_boto3_client,
        mock_segmenter_class,
        mock_transcribe_class,
        set_env_vars,
        sample_event,
        sample_transcript_json,
    ):
        """Test processing a video file through transcription."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.get_parameter.side_effect = lambda key, default=None: {
            "transcribe_language_code": "en-US",
            "speaker_diarization_enabled": True,
            "media_segment_duration_seconds": 30,
        }.get(key, default)
        mock_config_manager_class.return_value = mock_config

        mock_transcribe = MagicMock()
        mock_transcribe.start_transcription_job.return_value = "job-123"
        mock_transcribe.wait_for_completion.return_value = {
            "status": "COMPLETED",
            "transcript_uri": "s3://bucket/transcripts/job-123.json",
        }
        mock_transcribe.parse_transcript_with_timestamps.return_value = [
            {"word": "Hello", "start_time": 0.0, "end_time": 0.5, "type": "pronunciation"},
            {"word": "world", "start_time": 0.5, "end_time": 1.0, "type": "pronunciation"},
        ]
        mock_transcribe_class.return_value = mock_transcribe

        mock_segmenter = MagicMock()
        mock_segmenter.segment_transcript.return_value = [
            {
                "segment_index": 0,
                "timestamp_start": 0,
                "timestamp_end": 30,
                "text": "Hello world",
                "word_count": 2,
            }
        ]
        mock_segmenter_class.return_value = mock_segmenter

        # Mock S3 client
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": 1000000}
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(sample_transcript_json).encode())
        }
        mock_boto3_client.return_value = mock_s3

        # Mock DynamoDB
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        # Load and call the lambda
        module = load_process_media_module()

        # Patch the module-level clients
        with (
            patch.object(module, "s3_client", mock_s3),
            patch.object(module, "dynamodb", mock_dynamodb),
            patch.object(module, "TranscribeClient", mock_transcribe_class),
            patch.object(module, "MediaSegmenter", mock_segmenter_class),
            patch.object(module, "ConfigurationManager", mock_config_manager_class),
            patch.object(module, "publish_document_update", mock_publish),
        ):
            result = module.lambda_handler(sample_event, None)

        # Verify transcription was started
        mock_transcribe.start_transcription_job.assert_called_once()

        # Verify result structure
        assert result["document_id"] == "doc-123"
        assert "output_s3_uri" in result
        assert result["total_segments"] >= 0


class TestProcessMediaErrorHandling:
    """Tests for error handling."""

    @patch("ragstack_common.transcribe_client.TranscribeClient")
    @patch("boto3.client")
    @patch("boto3.resource")
    @patch("ragstack_common.appsync.publish_document_update")
    @patch("ragstack_common.config.ConfigurationManager")
    def test_handles_transcription_failure(
        self,
        mock_config_manager_class,
        mock_publish,
        mock_boto3_resource,
        mock_boto3_client,
        mock_transcribe_class,
        set_env_vars,
        sample_event,
    ):
        """Test handling of transcription failures."""
        from ragstack_common.exceptions import TranscriptionError

        mock_config = MagicMock()
        mock_config.get_parameter.side_effect = lambda key, default=None: {
            "transcribe_language_code": "en-US",
            "speaker_diarization_enabled": True,
            "media_segment_duration_seconds": 30,
        }.get(key, default)
        mock_config_manager_class.return_value = mock_config

        mock_transcribe = MagicMock()
        mock_transcribe.start_transcription_job.return_value = "job-123"
        mock_transcribe.wait_for_completion.side_effect = TranscriptionError("Transcription failed")
        mock_transcribe_class.return_value = mock_transcribe

        # Mock S3 client
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": 1000000}
        mock_boto3_client.return_value = mock_s3

        # Mock DynamoDB
        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        # Load and call the lambda
        module = load_process_media_module()

        with (
            patch.object(module, "s3_client", mock_s3),
            patch.object(module, "dynamodb", mock_dynamodb),
            patch.object(module, "TranscribeClient", mock_transcribe_class),
            patch.object(module, "ConfigurationManager", mock_config_manager_class),
            patch.object(module, "publish_document_update", mock_publish),
            pytest.raises(TranscriptionError),
        ):
            module.lambda_handler(sample_event, None)

        # Verify status was updated to failed
        mock_table.update_item.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
