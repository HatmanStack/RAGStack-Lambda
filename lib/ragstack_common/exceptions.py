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


class AudioExtractionError(MediaProcessingError):
    """Error extracting audio from video file."""


class SegmentationError(MediaProcessingError):
    """Error during media segmentation."""
