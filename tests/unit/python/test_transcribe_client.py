"""Unit tests for TranscribeClient wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from ragstack_common.transcribe_client import TranscribeClient


class TestTranscribeClientInit:
    """Tests for TranscribeClient initialization."""

    @patch("boto3.client")
    def test_creates_boto3_client(self, mock_boto3_client):
        """Test that TranscribeClient creates boto3 client."""
        mock_boto3_client.return_value = MagicMock()
        client = TranscribeClient()
        mock_boto3_client.assert_called_with("transcribe")
        assert client._client is not None

    @patch("boto3.client")
    def test_accepts_custom_region(self, mock_boto3_client):
        """Test that custom region is passed to boto3."""
        mock_boto3_client.return_value = MagicMock()
        _client = TranscribeClient(region="us-west-2")
        mock_boto3_client.assert_called_with("transcribe", region_name="us-west-2")


class TestStartTranscriptionJob:
    """Tests for starting transcription jobs."""

    @patch("boto3.client")
    def test_start_transcription_job_creates_job(self, mock_boto3_client):
        """Test that start_transcription_job creates a Transcribe job."""
        mock_client = MagicMock()
        mock_client.start_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job-123",
                "TranscriptionJobStatus": "IN_PROGRESS",
            }
        }
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()
        job_name = client.start_transcription_job(
            document_id="doc-123",
            input_s3_uri="s3://bucket/audio.mp3",
            output_bucket="output-bucket",
        )

        assert job_name == "test-job-123"
        mock_client.start_transcription_job.assert_called_once()

    @patch("boto3.client")
    def test_start_transcription_job_with_language_code(self, mock_boto3_client):
        """Test that language code is passed to Transcribe."""
        mock_client = MagicMock()
        mock_client.start_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "IN_PROGRESS",
            }
        }
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()
        client.start_transcription_job(
            document_id="doc-123",
            input_s3_uri="s3://bucket/audio.mp3",
            output_bucket="output-bucket",
            language_code="es-ES",
        )

        call_args = mock_client.start_transcription_job.call_args
        assert call_args.kwargs["LanguageCode"] == "es-ES"

    @patch("boto3.client")
    def test_start_transcription_job_with_speaker_diarization(self, mock_boto3_client):
        """Test that speaker diarization settings are passed."""
        mock_client = MagicMock()
        mock_client.start_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "IN_PROGRESS",
            }
        }
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()
        client.start_transcription_job(
            document_id="doc-123",
            input_s3_uri="s3://bucket/audio.mp3",
            output_bucket="output-bucket",
            enable_speaker_diarization=True,
            max_speakers=4,
        )

        call_args = mock_client.start_transcription_job.call_args
        settings = call_args.kwargs.get("Settings", {})
        assert settings.get("ShowSpeakerLabels") is True
        assert settings.get("MaxSpeakerLabels") == 4

    @patch("boto3.client")
    def test_start_transcription_job_generates_unique_name(self, mock_boto3_client):
        """Test that job name is generated from document_id."""
        mock_client = MagicMock()
        mock_client.start_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobName": "ragstack-doc-123-abc",
                "TranscriptionJobStatus": "IN_PROGRESS",
            }
        }
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()
        client.start_transcription_job(
            document_id="doc-123",
            input_s3_uri="s3://bucket/audio.mp3",
            output_bucket="output-bucket",
        )

        call_args = mock_client.start_transcription_job.call_args
        job_name = call_args.kwargs["TranscriptionJobName"]
        assert "doc-123" in job_name or job_name.startswith("ragstack-")


class TestGetJobStatus:
    """Tests for getting job status."""

    @patch("boto3.client")
    def test_get_job_status_returns_status(self, mock_boto3_client):
        """Test that get_job_status returns the job status."""
        mock_client = MagicMock()
        mock_client.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "COMPLETED",
            }
        }
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()
        status = client.get_job_status("test-job")

        assert status == "COMPLETED"

    @patch("boto3.client")
    def test_get_job_status_in_progress(self, mock_boto3_client):
        """Test status for in-progress job."""
        mock_client = MagicMock()
        mock_client.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "IN_PROGRESS",
            }
        }
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()
        status = client.get_job_status("test-job")

        assert status == "IN_PROGRESS"

    @patch("boto3.client")
    def test_get_job_status_failed(self, mock_boto3_client):
        """Test status for failed job."""
        mock_client = MagicMock()
        mock_client.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "FAILED",
                "FailureReason": "Invalid audio format",
            }
        }
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()
        status = client.get_job_status("test-job")

        assert status == "FAILED"


class TestGetTranscriptResult:
    """Tests for retrieving transcript results."""

    @patch("boto3.client")
    def test_get_transcript_result_returns_transcript_uri(self, mock_boto3_client):
        """Test that get_transcript_result returns transcript URI."""
        mock_client = MagicMock()
        mock_client.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "COMPLETED",
                "Transcript": {"TranscriptFileUri": "s3://bucket/transcripts/test-job.json"},
            }
        }
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()
        uri = client.get_transcript_result("test-job")

        assert uri == "s3://bucket/transcripts/test-job.json"

    @patch("boto3.client")
    def test_get_transcript_result_returns_none_if_incomplete(self, mock_boto3_client):
        """Test that None is returned if job is not complete."""
        mock_client = MagicMock()
        mock_client.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "IN_PROGRESS",
            }
        }
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()
        uri = client.get_transcript_result("test-job")

        assert uri is None


class TestParseTranscriptWithTimestamps:
    """Tests for parsing transcript JSON with timestamps."""

    def test_parse_simple_transcript(self):
        """Test parsing simple transcript without speaker labels."""
        transcript_json = {
            "results": {
                "transcripts": [{"transcript": "Hello world"}],
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
                ],
            }
        }

        with patch("boto3.client"):
            client = TranscribeClient()
            words = client.parse_transcript_with_timestamps(transcript_json)

        assert len(words) == 2
        assert words[0]["word"] == "Hello"
        assert words[0]["start_time"] == 0.0
        assert words[0]["end_time"] == 0.5
        assert words[1]["word"] == "world"
        assert words[1]["start_time"] == 0.5
        assert words[1]["end_time"] == 1.0

    def test_parse_transcript_with_speaker_labels(self):
        """Test parsing transcript with speaker diarization."""
        transcript_json = {
            "results": {
                "transcripts": [{"transcript": "Hello there"}],
                "speaker_labels": {
                    "speakers": 2,
                    "segments": [
                        {
                            "speaker_label": "spk_0",
                            "start_time": "0.0",
                            "end_time": "1.0",
                            "items": [
                                {"speaker_label": "spk_0", "start_time": "0.0", "end_time": "0.5"},
                                {"speaker_label": "spk_0", "start_time": "0.5", "end_time": "1.0"},
                            ],
                        }
                    ],
                },
                "items": [
                    {
                        "type": "pronunciation",
                        "alternatives": [{"content": "Hello", "confidence": "0.99"}],
                        "start_time": "0.0",
                        "end_time": "0.5",
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [{"content": "there", "confidence": "0.98"}],
                        "start_time": "0.5",
                        "end_time": "1.0",
                    },
                ],
            }
        }

        with patch("boto3.client"):
            client = TranscribeClient()
            words = client.parse_transcript_with_timestamps(transcript_json)

        assert len(words) == 2
        assert words[0]["speaker"] == "spk_0"
        assert words[1]["speaker"] == "spk_0"

    def test_parse_transcript_handles_punctuation(self):
        """Test that punctuation items are handled correctly."""
        transcript_json = {
            "results": {
                "transcripts": [{"transcript": "Hello, world."}],
                "items": [
                    {
                        "type": "pronunciation",
                        "alternatives": [{"content": "Hello", "confidence": "0.99"}],
                        "start_time": "0.0",
                        "end_time": "0.5",
                    },
                    {
                        "type": "punctuation",
                        "alternatives": [{"content": ",", "confidence": "0.0"}],
                    },
                    {
                        "type": "pronunciation",
                        "alternatives": [{"content": "world", "confidence": "0.98"}],
                        "start_time": "0.5",
                        "end_time": "1.0",
                    },
                    {
                        "type": "punctuation",
                        "alternatives": [{"content": ".", "confidence": "0.0"}],
                    },
                ],
            }
        }

        with patch("boto3.client"):
            client = TranscribeClient()
            words = client.parse_transcript_with_timestamps(transcript_json)

        # Should only return pronunciation items, not punctuation
        pronunciation_words = [w for w in words if w.get("type") == "pronunciation"]
        assert len(pronunciation_words) == 2

    def test_parse_empty_transcript(self):
        """Test parsing empty transcript."""
        transcript_json = {
            "results": {
                "transcripts": [{"transcript": ""}],
                "items": [],
            }
        }

        with patch("boto3.client"):
            client = TranscribeClient()
            words = client.parse_transcript_with_timestamps(transcript_json)

        assert words == []


class TestWaitForCompletion:
    """Tests for polling job completion."""

    @patch("time.sleep")
    @patch("boto3.client")
    def test_wait_for_completion_returns_on_complete(self, mock_boto3_client, mock_sleep):
        """Test that wait_for_completion returns when job completes."""
        mock_client = MagicMock()
        mock_client.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "COMPLETED",
                "Transcript": {"TranscriptFileUri": "s3://bucket/transcripts/test-job.json"},
            }
        }
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()
        result = client.wait_for_completion("test-job", poll_interval=1, max_wait=60)

        assert result["status"] == "COMPLETED"
        assert result["transcript_uri"] == "s3://bucket/transcripts/test-job.json"

    @patch("time.sleep")
    @patch("boto3.client")
    def test_wait_for_completion_polls_until_complete(self, mock_boto3_client, mock_sleep):
        """Test that wait_for_completion polls until job completes."""
        mock_client = MagicMock()
        mock_client.get_transcription_job.side_effect = [
            {
                "TranscriptionJob": {
                    "TranscriptionJobName": "test-job",
                    "TranscriptionJobStatus": "IN_PROGRESS",
                }
            },
            {
                "TranscriptionJob": {
                    "TranscriptionJobName": "test-job",
                    "TranscriptionJobStatus": "IN_PROGRESS",
                }
            },
            {
                "TranscriptionJob": {
                    "TranscriptionJobName": "test-job",
                    "TranscriptionJobStatus": "COMPLETED",
                    "Transcript": {"TranscriptFileUri": "s3://bucket/transcripts/test-job.json"},
                }
            },
        ]
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()
        result = client.wait_for_completion("test-job", poll_interval=1, max_wait=60)

        assert result["status"] == "COMPLETED"
        assert mock_client.get_transcription_job.call_count == 3

    @patch("time.sleep")
    @patch("boto3.client")
    def test_wait_for_completion_raises_on_failure(self, mock_boto3_client, mock_sleep):
        """Test that wait_for_completion raises on job failure."""
        mock_client = MagicMock()
        mock_client.get_transcription_job.return_value = {
            "TranscriptionJob": {
                "TranscriptionJobName": "test-job",
                "TranscriptionJobStatus": "FAILED",
                "FailureReason": "Invalid audio format",
            }
        }
        mock_boto3_client.return_value = mock_client

        client = TranscribeClient()

        from ragstack_common.exceptions import TranscriptionError

        with pytest.raises(TranscriptionError) as exc_info:
            client.wait_for_completion("test-job", poll_interval=1, max_wait=60)

        assert "Invalid audio format" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
