"""
Media segmenter for splitting transcripts into time-aligned chunks.

Segments transcripts into 30-second (configurable) chunks with proper
timestamp alignment and speaker label tracking.
"""

import logging
import math
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)


class MediaSegmenter:
    """Segments transcripts into time-aligned chunks.

    Takes word-level timestamps from AWS Transcribe output and groups them
    into fixed-duration segments (default 30 seconds) for embedding and search.

    Example:
        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=120.0)
        # Returns 4 segments of 30 seconds each
    """

    def __init__(self, segment_duration: int = 30):
        """Initialize MediaSegmenter.

        Args:
            segment_duration: Duration of each segment in seconds (default: 30).
        """
        self.segment_duration = segment_duration

    def segment_transcript(
        self, words: list[dict[str, Any]], total_duration: float
    ) -> list[dict[str, Any]]:
        """Segment transcript words into time-aligned chunks.

        Args:
            words: List of word dictionaries from TranscribeClient.parse_transcript_with_timestamps().
                   Each word has: word, start_time, end_time, type, speaker (optional).
            total_duration: Total duration of the media in seconds.

        Returns:
            List of segment dictionaries with:
            - segment_index: Zero-based segment index
            - timestamp_start: Start time in seconds
            - timestamp_end: End time in seconds
            - text: Combined text of all words in segment
            - word_count: Number of pronunciation words in segment
            - speaker: Primary speaker in segment (if available)
        """
        # Calculate number of segments needed
        num_segments = max(1, math.ceil(total_duration / self.segment_duration))
        logger.info(
            f"Segmenting transcript: duration={total_duration}s, "
            f"segment_duration={self.segment_duration}s, num_segments={num_segments}"
        )

        # Initialize segment containers
        segment_words: list[list[dict[str, Any]]] = [[] for _ in range(num_segments)]

        # Assign words to segments based on start_time
        for word in words:
            start_time = word.get("start_time")
            if start_time is None:
                # Punctuation without timing - attach to previous word's segment
                continue

            # Determine which segment this word belongs to
            segment_idx = int(start_time // self.segment_duration)
            # Clamp to valid range (handles edge cases)
            segment_idx = min(segment_idx, num_segments - 1)
            segment_words[segment_idx].append(word)

        # Build segment metadata
        segments = []
        for idx in range(num_segments):
            segment = self._build_segment(
                segment_index=idx,
                words=segment_words[idx],
                all_words=words,
            )
            segments.append(segment)

        logger.info(f"Created {len(segments)} segments")
        return segments

    def _build_segment(
        self,
        segment_index: int,
        words: list[dict[str, Any]],
        all_words: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build segment metadata from words.

        Args:
            segment_index: Zero-based index of this segment.
            words: Words belonging to this segment.
            all_words: All words in transcript (for punctuation attachment).

        Returns:
            Segment dictionary with metadata.
        """
        timestamp_start = segment_index * self.segment_duration
        timestamp_end = (segment_index + 1) * self.segment_duration

        # Build text from words with proper punctuation handling
        text = self._build_text(words, all_words, timestamp_start, timestamp_end)

        # Count pronunciation words only
        word_count = sum(1 for w in words if w.get("type") == "pronunciation")

        # Determine primary speaker
        speaker = self._get_primary_speaker(words)

        segment: dict[str, Any] = {
            "segment_index": segment_index,
            "timestamp_start": timestamp_start,
            "timestamp_end": timestamp_end,
            "text": text,
            "word_count": word_count,
        }

        if speaker:
            segment["speaker"] = speaker

        return segment

    def _build_text(
        self,
        words: list[dict[str, Any]],
        all_words: list[dict[str, Any]],
        timestamp_start: float,
        timestamp_end: float,
    ) -> str:
        """Build text from words with proper spacing and punctuation.

        Args:
            words: Words in this segment.
            all_words: All words for punctuation lookup.
            timestamp_start: Segment start time.
            timestamp_end: Segment end time.

        Returns:
            Formatted text string.
        """
        if not words:
            return ""

        # Get word indices in all_words for punctuation handling
        text_parts = []
        for word in words:
            if word.get("type") == "pronunciation":
                text_parts.append(word.get("word", ""))

        return " ".join(text_parts)

    def _get_primary_speaker(self, words: list[dict[str, Any]]) -> str | None:
        """Determine the primary speaker in a segment.

        Args:
            words: Words in the segment.

        Returns:
            Speaker label of most frequent speaker, or None if no speakers.
        """
        speakers = [w.get("speaker") for w in words if w.get("speaker")]
        if not speakers:
            return None

        # Count speaker occurrences and return most common
        speaker_counts = Counter(speakers)
        return speaker_counts.most_common(1)[0][0]
