"""Visual Segmenter for extracting media segments for Nova embedding.

This module provides a segmenter that extracts 30-second segments from
video and audio files for use with Nova Multimodal Embeddings.

The segmenter:
- Uses FFmpeg for media manipulation
- Extracts segments at configurable duration (default 30s for Nova limits)
- Outputs segments to local filesystem or S3
- Preserves quality for accurate visual/audio embedding
"""

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import boto3

from ragstack_common.exceptions import MediaProcessingError
from ragstack_common.storage import parse_s3_uri

logger = logging.getLogger(__name__)

# Default segment duration (Nova Multimodal Embeddings max: 30 seconds)
DEFAULT_SEGMENT_DURATION = 30

# FFmpeg binary path (set by Lambda layer or environment)
FFMPEG_PATH = os.environ.get("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.environ.get("FFPROBE_PATH", "ffprobe")


class VisualSegmenter:
    """
    Extracts video/audio segments for Nova Multimodal Embeddings.

    Splits media files into 30-second segments aligned with Nova's
    input requirements. Handles both video and audio files.

    Usage:
        segmenter = VisualSegmenter()
        segments = segmenter.extract_segments(
            input_path="/tmp/video.mp4",
            output_dir="/tmp/segments",
            media_type="video"
        )
    """

    def __init__(
        self,
        segment_duration: int = DEFAULT_SEGMENT_DURATION,
        ffmpeg_path: str | None = None,
        ffprobe_path: str | None = None,
    ):
        """
        Initialize the visual segmenter.

        Args:
            segment_duration: Duration of each segment in seconds (default: 30).
            ffmpeg_path: Path to ffmpeg binary (default: from environment or 'ffmpeg').
            ffprobe_path: Path to ffprobe binary (default: from environment or 'ffprobe').
        """
        self.segment_duration = segment_duration
        self.ffmpeg_path = ffmpeg_path or FFMPEG_PATH
        self.ffprobe_path = ffprobe_path or FFPROBE_PATH
        self._s3_client = None

        logger.info(
            f"Initialized VisualSegmenter: segment_duration={segment_duration}s, "
            f"ffmpeg={self.ffmpeg_path}"
        )

    @property
    def s3_client(self):
        """Lazy-load S3 client."""
        if self._s3_client is None:
            self._s3_client = boto3.client("s3")
        return self._s3_client

    def get_duration(self, input_path: str) -> float:
        """
        Get media duration using ffprobe.

        Args:
            input_path: Path to media file.

        Returns:
            Duration in seconds.

        Raises:
            MediaProcessingError: If ffprobe fails.
        """
        try:
            cmd = [
                self.ffprobe_path,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                input_path,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                raise MediaProcessingError(f"ffprobe failed: {result.stderr}")

            data = json.loads(result.stdout)
            duration = float(data.get("format", {}).get("duration", 0))

            if duration <= 0:
                raise MediaProcessingError(f"Invalid duration: {duration}")

            logger.info(f"Media duration: {duration}s")
            return duration

        except subprocess.TimeoutExpired as e:
            raise MediaProcessingError(f"ffprobe timed out: {e}") from e
        except json.JSONDecodeError as e:
            raise MediaProcessingError(f"Invalid ffprobe output: {e}") from e

    def calculate_segments(self, total_duration: float) -> list[dict[str, Any]]:
        """
        Calculate segment boundaries for a given duration.

        Args:
            total_duration: Total media duration in seconds.

        Returns:
            List of segment dictionaries with:
            - segment_index: 0-based index
            - timestamp_start: Start time in seconds
            - timestamp_end: End time in seconds
        """
        segments = []
        current_time = 0
        index = 0

        while current_time < total_duration:
            end_time = min(current_time + self.segment_duration, total_duration)

            segments.append(
                {
                    "segment_index": index,
                    "timestamp_start": int(current_time),
                    "timestamp_end": int(end_time) if end_time == total_duration else int(end_time),
                }
            )

            current_time += self.segment_duration
            index += 1

        logger.info(f"Calculated {len(segments)} segments for {total_duration}s duration")
        return segments

    def extract_segment(
        self,
        input_path: str,
        output_path: str,
        start_time: int,
        duration: int,
        media_type: str = "video",
    ) -> str:
        """
        Extract a single segment from media file.

        Args:
            input_path: Path to input media file.
            output_path: Path for output segment file.
            start_time: Start time in seconds.
            duration: Duration in seconds.
            media_type: "video" or "audio".

        Returns:
            Path to extracted segment file.

        Raises:
            MediaProcessingError: If extraction fails.
        """
        try:
            # Build ffmpeg command
            cmd = [
                self.ffmpeg_path,
                "-y",  # Overwrite output
                "-ss",
                str(start_time),  # Seek to start time
                "-i",
                input_path,  # Input file
                "-t",
                str(duration),  # Duration
            ]

            # Add format-specific options
            if media_type == "video":
                cmd.extend(
                    [
                        "-c:v",
                        "libx264",  # Video codec
                        "-c:a",
                        "aac",  # Audio codec
                        "-preset",
                        "fast",
                        "-crf",
                        "23",  # Quality setting
                    ]
                )
            else:
                cmd.extend(
                    [
                        "-c:a",
                        "aac",  # Audio codec
                        "-b:a",
                        "128k",
                    ]
                )

            cmd.append(output_path)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout per segment
            )

            if result.returncode != 0:
                raise MediaProcessingError(f"ffmpeg extraction failed: {result.stderr}")

            logger.debug(f"Extracted segment: {output_path}")
            return output_path

        except subprocess.TimeoutExpired as e:
            raise MediaProcessingError(f"ffmpeg timed out: {e}") from e

    def extract_segments(
        self,
        input_path: str,
        output_dir: str,
        media_type: str = "video",
    ) -> list[dict[str, Any]]:
        """
        Extract all segments from a media file.

        Args:
            input_path: Path to input media file.
            output_dir: Directory for output segment files.
            media_type: "video" or "audio".

        Returns:
            List of segment dictionaries with output paths added.

        Raises:
            MediaProcessingError: If extraction fails.
        """
        # Create output directory if needed
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Get duration and calculate segments
        duration = self.get_duration(input_path)
        segments = self.calculate_segments(duration)

        # Determine output extension
        ext = ".mp4" if media_type == "video" else ".m4a"

        # Extract each segment
        for segment in segments:
            output_path = str(Path(output_dir) / f"segment_{segment['segment_index']:03d}{ext}")

            # Calculate actual duration for this segment
            seg_duration = segment["timestamp_end"] - segment["timestamp_start"]

            self.extract_segment(
                input_path=input_path,
                output_path=output_path,
                start_time=segment["timestamp_start"],
                duration=seg_duration,
                media_type=media_type,
            )

            segment["output_path"] = output_path

        logger.info(f"Extracted {len(segments)} segments to {output_dir}")
        return segments

    def extract_segments_to_s3(
        self,
        input_s3_uri: str,
        output_s3_prefix: str,
        document_id: str,
        media_type: str = "video",
    ) -> list[dict[str, Any]]:
        """
        Download media from S3, extract segments, and upload to S3.

        Args:
            input_s3_uri: S3 URI of input media file.
            output_s3_prefix: S3 prefix for output segments.
            document_id: Document ID for naming.
            media_type: "video" or "audio".

        Returns:
            List of segment dictionaries with S3 URIs.

        Raises:
            MediaProcessingError: If processing fails.
        """
        input_bucket, input_key = parse_s3_uri(input_s3_uri)

        # Determine extension from input (use .m4a for audio to match extract_segments output)
        ext = Path(input_key).suffix or (".mp4" if media_type == "video" else ".m4a")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Download input file
            local_input = str(Path(tmpdir) / f"input{ext}")
            logger.info(f"Downloading {input_s3_uri} to {local_input}")
            self.s3_client.download_file(input_bucket, input_key, local_input)

            # Extract segments locally
            segments_dir = str(Path(tmpdir) / "segments")
            segments = self.extract_segments(
                input_path=local_input,
                output_dir=segments_dir,
                media_type=media_type,
            )

            # Upload segments to S3
            output_bucket, output_prefix = parse_s3_uri(output_s3_prefix)

            for segment in segments:
                local_path = segment["output_path"]
                filename = Path(local_path).name
                s3_key = f"{output_prefix}{document_id}/visual_segments/{filename}".replace(
                    "//", "/"
                )

                logger.debug(f"Uploading segment to s3://{output_bucket}/{s3_key}")
                self.s3_client.upload_file(local_path, output_bucket, s3_key)

                segment["s3_uri"] = f"s3://{output_bucket}/{s3_key}"
                # Remove local path from output
                del segment["output_path"]

        logger.info(f"Uploaded {len(segments)} segments to S3")
        return segments
