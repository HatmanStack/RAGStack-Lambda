"""
Custom exceptions for RAGStack media and document processing.

This module defines media-specific exceptions for the processing pipeline.
"""


class MediaProcessingError(Exception):
    """Base exception for media processing errors."""

    pass


class TranscriptionError(MediaProcessingError):
    """Error during transcription (AWS Transcribe or other)."""

    pass


class UnsupportedMediaFormatError(MediaProcessingError):
    """Media format is not supported for processing."""

    pass


class MediaDurationExceededError(MediaProcessingError):
    """Media duration exceeds configured maximum."""

    pass


class MediaFileSizeExceededError(MediaProcessingError):
    """Media file size exceeds configured maximum."""

    pass


class AudioExtractionError(MediaProcessingError):
    """Error extracting audio from video file."""

    pass


class SegmentationError(MediaProcessingError):
    """Error during media segmentation."""

    pass
