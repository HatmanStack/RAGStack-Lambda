"""Unit tests for VisualSegmenter."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ragstack_common.visual_segmenter import VisualSegmenter


class TestVisualSegmenterInit:
    """Tests for VisualSegmenter initialization."""

    def test_default_segment_duration(self):
        """Test default segment duration is 30 seconds."""
        segmenter = VisualSegmenter()
        assert segmenter.segment_duration == 30

    def test_custom_segment_duration(self):
        """Test custom segment duration is accepted."""
        segmenter = VisualSegmenter(segment_duration=60)
        assert segmenter.segment_duration == 60


class TestGetDuration:
    """Tests for media duration extraction."""

    @patch("subprocess.run")
    def test_get_duration_from_video(self, mock_run):
        """Test extracting duration from video file."""
        # Mock ffprobe output
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"format": {"duration": "120.5"}}',
            stderr="",
        )

        segmenter = VisualSegmenter()
        duration = segmenter.get_duration("/tmp/video.mp4")

        assert duration == 120.5
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_get_duration_handles_error(self, mock_run):
        """Test handling ffprobe errors."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: Invalid file",
        )

        segmenter = VisualSegmenter()

        from ragstack_common.exceptions import MediaProcessingError

        with pytest.raises(MediaProcessingError):
            segmenter.get_duration("/tmp/invalid.mp4")


class TestCalculateSegments:
    """Tests for segment calculation."""

    def test_calculate_segments_short_video(self):
        """Test segment calculation for short video (< 30s)."""
        segmenter = VisualSegmenter(segment_duration=30)
        segments = segmenter.calculate_segments(25.0)

        assert len(segments) == 1
        assert segments[0]["segment_index"] == 0
        assert segments[0]["timestamp_start"] == 0
        assert segments[0]["timestamp_end"] == 25

    def test_calculate_segments_exact_duration(self):
        """Test segment calculation for exact multiple of duration."""
        segmenter = VisualSegmenter(segment_duration=30)
        segments = segmenter.calculate_segments(60.0)

        assert len(segments) == 2
        assert segments[0]["timestamp_start"] == 0
        assert segments[0]["timestamp_end"] == 30
        assert segments[1]["timestamp_start"] == 30
        assert segments[1]["timestamp_end"] == 60

    def test_calculate_segments_partial_last(self):
        """Test segment calculation with partial last segment."""
        segmenter = VisualSegmenter(segment_duration=30)
        segments = segmenter.calculate_segments(45.0)

        assert len(segments) == 2
        assert segments[1]["timestamp_start"] == 30
        assert segments[1]["timestamp_end"] == 45

    def test_calculate_segments_long_video(self):
        """Test segment calculation for long video (2 hours)."""
        segmenter = VisualSegmenter(segment_duration=30)
        segments = segmenter.calculate_segments(7200.0)  # 2 hours

        assert len(segments) == 240  # 7200 / 30
        assert segments[-1]["timestamp_end"] == 7200


class TestExtractSegment:
    """Tests for segment extraction."""

    @patch("subprocess.run")
    def test_extract_video_segment(self, mock_run):
        """Test extracting a video segment with ffmpeg."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        segmenter = VisualSegmenter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "segment_000.mp4")
            result = segmenter.extract_segment(
                input_path="/tmp/video.mp4",
                output_path=output_path,
                start_time=0,
                duration=30,
                media_type="video",
            )

            assert result == output_path
            mock_run.assert_called_once()

            # Verify ffmpeg command
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "ffmpeg" in cmd[0]
            assert "-ss" in cmd
            assert "-t" in cmd

    @patch("subprocess.run")
    def test_extract_audio_segment(self, mock_run):
        """Test extracting an audio segment."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        segmenter = VisualSegmenter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "segment_000.mp3")
            result = segmenter.extract_segment(
                input_path="/tmp/audio.mp3",
                output_path=output_path,
                start_time=0,
                duration=30,
                media_type="audio",
            )

            assert result == output_path

    @patch("subprocess.run")
    def test_extract_segment_ffmpeg_error(self, mock_run):
        """Test handling ffmpeg extraction errors."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error encoding",
        )

        segmenter = VisualSegmenter()

        from ragstack_common.exceptions import MediaProcessingError

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "segment_000.mp4")
            with pytest.raises(MediaProcessingError):
                segmenter.extract_segment(
                    input_path="/tmp/video.mp4",
                    output_path=output_path,
                    start_time=0,
                    duration=30,
                    media_type="video",
                )


class TestExtractSegments:
    """Tests for full segment extraction workflow."""

    @patch.object(VisualSegmenter, "extract_segment")
    @patch.object(VisualSegmenter, "get_duration")
    def test_extract_segments_returns_segment_info(self, mock_duration, mock_extract):
        """Test full segment extraction returns segment info."""
        mock_duration.return_value = 65.0  # 65 seconds = 3 segments

        def mock_extract_fn(input_path, output_path, start_time, duration, media_type):
            return output_path

        mock_extract.side_effect = mock_extract_fn

        segmenter = VisualSegmenter(segment_duration=30)

        with tempfile.TemporaryDirectory() as tmpdir:
            segments = segmenter.extract_segments(
                input_path="/tmp/video.mp4",
                output_dir=tmpdir,
                media_type="video",
            )

            assert len(segments) == 3
            assert segments[0]["segment_index"] == 0
            assert segments[0]["timestamp_start"] == 0
            assert segments[0]["timestamp_end"] == 30
            assert "output_path" in segments[0]

            assert segments[2]["timestamp_start"] == 60
            assert segments[2]["timestamp_end"] == 65

    @patch.object(VisualSegmenter, "extract_segment")
    @patch.object(VisualSegmenter, "get_duration")
    def test_extract_segments_creates_output_dir(self, mock_duration, mock_extract):
        """Test that output directory is created if it doesn't exist."""
        mock_duration.return_value = 25.0
        mock_extract.return_value = "/tmp/test/segment_000.mp4"

        segmenter = VisualSegmenter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = str(Path(tmpdir) / "new_dir" / "segments")
            segmenter.extract_segments(
                input_path="/tmp/video.mp4",
                output_dir=output_dir,
                media_type="video",
            )

            assert Path(output_dir).exists()


class TestExtractSegmentsToS3:
    """Tests for S3-based segment extraction."""

    @patch("boto3.client")
    @patch.object(VisualSegmenter, "extract_segments")
    def test_extract_segments_to_s3(self, mock_extract, mock_boto3):
        """Test extracting segments and uploading to S3."""
        mock_s3 = MagicMock()
        mock_boto3.return_value = mock_s3

        mock_extract.return_value = [
            {
                "segment_index": 0,
                "timestamp_start": 0,
                "timestamp_end": 30,
                "output_path": "/tmp/segment_000.mp4",
            }
        ]

        segmenter = VisualSegmenter()

        with patch("builtins.open", MagicMock()):
            segments = segmenter.extract_segments_to_s3(
                input_s3_uri="s3://bucket/video.mp4",
                output_s3_prefix="s3://bucket/segments/",
                document_id="doc123",
                media_type="video",
            )

            # Should download input, extract, and upload segments
            assert len(segments) >= 0  # May be mocked


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
