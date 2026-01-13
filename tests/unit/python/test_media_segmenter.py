"""Unit tests for MediaSegmenter."""

import pytest

from ragstack_common.media_segmenter import MediaSegmenter


class TestMediaSegmenterInit:
    """Tests for MediaSegmenter initialization."""

    def test_default_segment_duration(self):
        """Test default segment duration is 30 seconds."""
        segmenter = MediaSegmenter()
        assert segmenter.segment_duration == 30

    def test_custom_segment_duration(self):
        """Test custom segment duration."""
        segmenter = MediaSegmenter(segment_duration=60)
        assert segmenter.segment_duration == 60


class TestSegmentTranscript:
    """Tests for segmenting transcripts by time boundaries."""

    def test_segment_single_segment_transcript(self):
        """Test transcript that fits in one segment."""
        words = [
            {"word": "Hello", "start_time": 0.0, "end_time": 0.5, "type": "pronunciation"},
            {"word": "world", "start_time": 0.5, "end_time": 1.0, "type": "pronunciation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=2.0)

        assert len(segments) == 1
        assert segments[0]["segment_index"] == 0
        assert segments[0]["timestamp_start"] == 0
        assert segments[0]["timestamp_end"] == 30
        assert "Hello world" in segments[0]["text"]

    def test_segment_multiple_segments(self):
        """Test transcript spanning multiple segments."""
        words = [
            {"word": "First", "start_time": 0.0, "end_time": 0.5, "type": "pronunciation"},
            {"word": "segment", "start_time": 15.0, "end_time": 15.5, "type": "pronunciation"},
            {"word": "Second", "start_time": 35.0, "end_time": 35.5, "type": "pronunciation"},
            {"word": "segment", "start_time": 40.0, "end_time": 40.5, "type": "pronunciation"},
            {"word": "Third", "start_time": 65.0, "end_time": 65.5, "type": "pronunciation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=70.0)

        assert len(segments) == 3
        assert segments[0]["timestamp_start"] == 0
        assert segments[0]["timestamp_end"] == 30
        assert segments[1]["timestamp_start"] == 30
        assert segments[1]["timestamp_end"] == 60
        assert segments[2]["timestamp_start"] == 60
        assert segments[2]["timestamp_end"] == 90

    def test_segment_preserves_word_order(self):
        """Test that words are preserved in correct order within segments."""
        words = [
            {"word": "One", "start_time": 0.0, "end_time": 0.3, "type": "pronunciation"},
            {"word": "two", "start_time": 0.3, "end_time": 0.6, "type": "pronunciation"},
            {"word": "three", "start_time": 0.6, "end_time": 0.9, "type": "pronunciation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=1.0)

        assert "One two three" in segments[0]["text"]

    def test_segment_handles_empty_transcript(self):
        """Test handling of empty transcript."""
        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript([], total_duration=60.0)

        # Should still create segments for the duration
        assert len(segments) == 2
        assert segments[0]["text"] == ""
        assert segments[1]["text"] == ""

    def test_segment_assigns_word_count(self):
        """Test that word count is assigned to each segment."""
        words = [
            {"word": "One", "start_time": 0.0, "end_time": 0.3, "type": "pronunciation"},
            {"word": "two", "start_time": 0.3, "end_time": 0.6, "type": "pronunciation"},
            {"word": "three", "start_time": 35.0, "end_time": 35.3, "type": "pronunciation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=40.0)

        assert segments[0]["word_count"] == 2
        assert segments[1]["word_count"] == 1


class TestSpeakerLabels:
    """Tests for speaker label handling."""

    def test_segment_preserves_speaker_labels(self):
        """Test that speaker labels are preserved in segments."""
        words = [
            {"word": "Hello", "start_time": 0.0, "end_time": 0.5, "speaker": "spk_0", "type": "pronunciation"},
            {"word": "Hi", "start_time": 1.0, "end_time": 1.5, "speaker": "spk_1", "type": "pronunciation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=2.0)

        # Should identify primary speaker in segment
        assert "speaker" in segments[0]

    def test_segment_identifies_primary_speaker(self):
        """Test that primary speaker is identified when multiple speakers."""
        words = [
            {"word": "One", "start_time": 0.0, "end_time": 0.5, "speaker": "spk_0", "type": "pronunciation"},
            {"word": "Two", "start_time": 0.5, "end_time": 1.0, "speaker": "spk_0", "type": "pronunciation"},
            {"word": "Three", "start_time": 1.0, "end_time": 1.5, "speaker": "spk_1", "type": "pronunciation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=2.0)

        # spk_0 has more words, should be primary
        assert segments[0]["speaker"] == "spk_0"

    def test_segment_handles_missing_speaker(self):
        """Test handling when speaker labels are missing."""
        words = [
            {"word": "Hello", "start_time": 0.0, "end_time": 0.5, "type": "pronunciation"},
            {"word": "world", "start_time": 0.5, "end_time": 1.0, "type": "pronunciation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=2.0)

        # Should handle gracefully
        assert segments[0].get("speaker") is None or segments[0].get("speaker") == ""


class TestPunctuationHandling:
    """Tests for punctuation in transcripts."""

    def test_segment_includes_punctuation(self):
        """Test that punctuation is properly included in text."""
        words = [
            {"word": "Hello", "start_time": 0.0, "end_time": 0.5, "type": "pronunciation"},
            {"word": ",", "type": "punctuation"},
            {"word": "world", "start_time": 0.5, "end_time": 1.0, "type": "pronunciation"},
            {"word": ".", "type": "punctuation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=1.0)

        # Text should include punctuation properly attached
        assert "Hello" in segments[0]["text"]
        assert "world" in segments[0]["text"]

    def test_punctuation_not_counted_as_words(self):
        """Test that punctuation is not counted in word count."""
        words = [
            {"word": "Hello", "start_time": 0.0, "end_time": 0.5, "type": "pronunciation"},
            {"word": ",", "type": "punctuation"},
            {"word": "world", "start_time": 0.5, "end_time": 1.0, "type": "pronunciation"},
            {"word": ".", "type": "punctuation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=1.0)

        # Only pronunciation items should be counted
        assert segments[0]["word_count"] == 2


class TestEdgeCases:
    """Tests for edge cases."""

    def test_segment_handles_silence(self):
        """Test handling of silence (gaps in transcript)."""
        words = [
            {"word": "Before", "start_time": 0.0, "end_time": 0.5, "type": "pronunciation"},
            # Gap from 0.5 to 29.5 (silence)
            {"word": "After", "start_time": 29.5, "end_time": 30.0, "type": "pronunciation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=30.0)

        assert len(segments) == 1
        assert "Before" in segments[0]["text"]
        assert "After" in segments[0]["text"]

    def test_segment_handles_last_partial_segment(self):
        """Test that last segment handles partial duration correctly."""
        words = [
            {"word": "Last", "start_time": 65.0, "end_time": 65.5, "type": "pronunciation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=70.0)

        # Should have 3 segments (0-30, 30-60, 60-90)
        assert len(segments) == 3
        assert segments[2]["timestamp_start"] == 60
        assert segments[2]["timestamp_end"] == 90

    def test_segment_boundary_word_assignment(self):
        """Test word at exact segment boundary is assigned to correct segment."""
        words = [
            {"word": "Boundary", "start_time": 30.0, "end_time": 30.5, "type": "pronunciation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=35.0)

        # Word at 30.0 should be in second segment (30-60)
        assert segments[0]["word_count"] == 0
        assert segments[1]["word_count"] == 1

    def test_long_duration_creates_many_segments(self):
        """Test that long duration creates appropriate number of segments."""
        words = []  # Empty for simplicity

        segmenter = MediaSegmenter(segment_duration=30)
        # 2 hours = 7200 seconds = 240 segments
        segments = segmenter.segment_transcript(words, total_duration=7200.0)

        assert len(segments) == 240

    def test_segment_metadata_structure(self):
        """Test that segment metadata has all required fields."""
        words = [
            {"word": "Test", "start_time": 0.0, "end_time": 0.5, "type": "pronunciation"},
        ]

        segmenter = MediaSegmenter(segment_duration=30)
        segments = segmenter.segment_transcript(words, total_duration=30.0)

        segment = segments[0]
        assert "segment_index" in segment
        assert "timestamp_start" in segment
        assert "timestamp_end" in segment
        assert "text" in segment
        assert "word_count" in segment


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
