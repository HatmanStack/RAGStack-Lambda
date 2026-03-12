"""
Custom exceptions for RAGStack media and document processing.

This module defines media-specific exceptions for the processing pipeline.
"""


class MediaProcessingError(Exception):
    """Base exception for media processing errors."""


class TranscriptionError(MediaProcessingError):
    """Error during transcription (AWS Transcribe or other)."""


class UnsupportedMediaFormatError(MediaProcessingError):
    """Media format is not supported for processing."""


class MediaDurationExceededError(MediaProcessingError):
    """Media duration exceeds configured maximum."""


class MediaFileSizeExceededError(MediaProcessingError):
    """Media file size exceeds configured maximum."""


class FileSizeLimitExceededError(Exception):
    """File size exceeds the configured maximum for download."""

    def __init__(self, actual_size: int, max_size: int, s3_uri: str = "") -> None:
        self.actual_size = actual_size
        self.max_size = max_size
        self.s3_uri = s3_uri
        super().__init__(
            f"File size {actual_size} bytes exceeds limit of {max_size} bytes"
            + (f" for {s3_uri}" if s3_uri else "")
        )


class AudioExtractionError(MediaProcessingError):
    """Error extracting audio from video file."""


class SegmentationError(MediaProcessingError):
    """Error during media segmentation."""
