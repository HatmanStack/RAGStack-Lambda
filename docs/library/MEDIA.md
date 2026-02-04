# Media Processing Module

Audio/video transcription and segmentation for media file ingestion.

## transcribe_client.py

```python
class TranscribeClient:
    def __init__(region: str | None = None, language_code: str = "en-US", enable_speaker_diarization: bool = True)
    def start_transcription_job(document_id: str, input_s3_uri: str, output_bucket: str) -> str  # Returns job_name
    def get_job_status(job_name: str) -> str  # QUEUED, IN_PROGRESS, COMPLETED, FAILED
    def get_transcript_result(job_name: str) -> dict
    def wait_for_completion(job_name: str, timeout_seconds: int = 1800, poll_interval: int = 30) -> dict
    def parse_transcript_with_timestamps(result: dict) -> list[dict]  # Returns word-level timestamps
```

**Environment:** `AWS_REGION`

**Supported formats:** MP4, WebM, MP3, WAV, M4A, OGG, FLAC

## Overview

`TranscribeClient` wraps AWS Transcribe for batch audio/video transcription. Generates word-level timestamps with optional speaker diarization, enabling time-aligned search and attribution.

## Usage

### Initialize

```python
from ragstack_common.transcribe_client import TranscribeClient

# Default: en-US with speaker diarization
transcribe = TranscribeClient()

# Custom language and settings
transcribe = TranscribeClient(
    region="us-west-2",
    language_code="es-ES",
    enable_speaker_diarization=False
)
```

**Supported languages:** en-US, es-ES, fr-FR, de-DE, it-IT, pt-BR, ja-JP, ko-KR, zh-CN, and more (see AWS docs)

### Start Transcription Job

```python
job_name = transcribe.start_transcription_job(
    document_id="video-123",
    input_s3_uri="s3://my-bucket/videos/interview.mp4",
    output_bucket="my-bucket"
)

# Returns: "transcribe-video-123-1234567890"
```

**Job naming:** `transcribe-{document_id}-{timestamp}`

**Output location:** `s3://{output_bucket}/transcribe-{job_name}.json`

### Check Job Status

```python
status = transcribe.get_job_status(job_name)
# Returns: "QUEUED" | "IN_PROGRESS" | "COMPLETED" | "FAILED"
```

### Wait for Completion

```python
# Default: 30-minute timeout, 30-second polls
result = transcribe.wait_for_completion(job_name)

# Custom timeout and poll interval
result = transcribe.wait_for_completion(
    job_name,
    timeout_seconds=3600,  # 1 hour
    poll_interval=60       # 1 minute
)

# Raises TimeoutError if exceeds timeout_seconds
```

**Returns:** Full transcription result dict

### Get Transcript Result

```python
result = transcribe.get_transcript_result(job_name)

# Result structure:
# {
#     "jobName": "transcribe-video-123-1234567890",
#     "status": "COMPLETED",
#     "results": {
#         "transcripts": [{"transcript": "Full text..."}],
#         "items": [
#             {
#                 "start_time": "0.5",
#                 "end_time": "1.2",
#                 "alternatives": [{"content": "Hello"}],
#                 "type": "pronunciation"
#             },
#             ...
#         ],
#         "speaker_labels": {
#             "segments": [
#                 {
#                     "start_time": "0.5",
#                     "end_time": "5.3",
#                     "speaker_label": "spk_0",
#                     "items": [{"start_time": "0.5", "end_time": "1.2", "speaker_label": "spk_0"}, ...]
#                 }
#             ]
#         }
#     }
# }
```

### Parse Word-Level Timestamps

```python
result = transcribe.get_transcript_result(job_name)
words = transcribe.parse_transcript_with_timestamps(result)

# Returns:
# [
#     {
#         "word": "Hello",
#         "start_time": 0.5,
#         "end_time": 1.2,
#         "speaker": "spk_0"
#     },
#     {
#         "word": "world",
#         "start_time": 1.3,
#         "end_time": 1.8,
#         "speaker": "spk_0"
#     }
# ]
```

**Note:** `speaker` field only present if `enable_speaker_diarization=True`

### Full Workflow Example

```python
from ragstack_common.transcribe_client import TranscribeClient

transcribe = TranscribeClient()

# Start job
job_name = transcribe.start_transcription_job(
    document_id="video-123",
    input_s3_uri="s3://my-bucket/videos/interview.mp4",
    output_bucket="my-bucket"
)

# Wait for completion
result = transcribe.wait_for_completion(job_name)

# Parse words with timestamps
words = transcribe.parse_transcript_with_timestamps(result)

# Get full transcript text
full_text = result["results"]["transcripts"][0]["transcript"]
```

## media_segmenter.py

```python
class MediaSegmenter:
    def __init__(segment_duration: int = 30)
    def segment_transcript(words: list[dict], total_duration: float) -> list[dict]
```

**Segment fields:** `text`, `start_time`, `end_time`, `speaker` (if diarization enabled)

**Default segment:** 30 seconds (configurable via `media_segment_duration_seconds`)

### Initialize

```python
from ragstack_common.media_segmenter import MediaSegmenter

# Default 30-second segments
segmenter = MediaSegmenter()

# Custom segment duration
segmenter = MediaSegmenter(segment_duration=60)  # 1-minute segments
```

### Segment Transcript

```python
from ragstack_common.transcribe_client import TranscribeClient
from ragstack_common.media_segmenter import MediaSegmenter

# Get word-level transcript
transcribe = TranscribeClient()
result = transcribe.get_transcript_result(job_name)
words = transcribe.parse_transcript_with_timestamps(result)

# Segment into time-aligned chunks
segmenter = MediaSegmenter(segment_duration=30)
segments = segmenter.segment_transcript(words, total_duration=180.5)

# Returns:
# [
#     {
#         "text": "Hello world this is the first segment...",
#         "start_time": 0.0,
#         "end_time": 30.0,
#         "speaker": "spk_0"
#     },
#     {
#         "text": "This is the second segment...",
#         "start_time": 30.0,
#         "end_time": 60.0,
#         "speaker": "spk_1"
#     },
#     ...
# ]
```

**Behavior:**
- Segments split on duration boundaries (e.g., 0-30s, 30-60s, 60-90s)
- Words allocated to segments based on start_time
- Speaker attribution preserved within segments
- Final segment may be shorter than segment_duration

### Speaker Transitions

```python
# With speaker diarization enabled
segments = segmenter.segment_transcript(words, total_duration=180.5)

# Each segment includes predominant speaker
# Segments naturally break at speaker changes when duration allows
```

## exceptions.py

Media processing exception hierarchy.

```python
class MediaProcessingError(Exception)  # Base exception
class TranscriptionError(MediaProcessingError)  # AWS Transcribe errors
class UnsupportedMediaFormatError(MediaProcessingError)  # Invalid format
class MediaDurationExceededError(MediaProcessingError)  # Too long
class MediaFileSizeExceededError(MediaProcessingError)  # Too large
class AudioExtractionError(MediaProcessingError)  # Audio extraction failed
class SegmentationError(MediaProcessingError)  # Segmentation failed
```

### Error Handling

```python
from ragstack_common.transcribe_client import TranscribeClient
from ragstack_common.exceptions import (
    TranscriptionError,
    UnsupportedMediaFormatError,
    MediaDurationExceededError,
    MediaFileSizeExceededError
)

try:
    transcribe = TranscribeClient()
    job_name = transcribe.start_transcription_job(
        document_id="video-123",
        input_s3_uri="s3://bucket/video.mp4",
        output_bucket="bucket"
    )
    result = transcribe.wait_for_completion(job_name)

except UnsupportedMediaFormatError as e:
    logger.error(f"Unsupported format: {e}")
    # Handle format error (e.g., skip file, notify user)

except MediaDurationExceededError as e:
    logger.error(f"Media too long: {e}")
    # Handle duration error (e.g., reject, chunk into parts)

except MediaFileSizeExceededError as e:
    logger.error(f"File too large: {e}")
    # Handle size error (e.g., reject, compress)

except TranscriptionError as e:
    logger.error(f"Transcription failed: {e}")
    # Handle transcription error (e.g., retry, fallback)

except TimeoutError as e:
    logger.error(f"Transcription timeout: {e}")
    # Handle timeout (e.g., retry with longer timeout)
```

### Exception Details

#### MediaProcessingError
Base exception for all media processing errors.

#### TranscriptionError
Raised when AWS Transcribe job fails or returns error status.

**Common causes:**
- Unsupported audio codec
- Corrupted media file
- AWS service errors

#### UnsupportedMediaFormatError
Raised when file format not supported by Transcribe.

**Supported:** MP4, WebM, MP3, WAV, M4A, OGG, FLAC

#### MediaDurationExceededError
Raised when media duration exceeds limits.

**AWS Transcribe limits:** Up to 4 hours per job

#### MediaFileSizeExceededError
Raised when file size exceeds limits.

**AWS Transcribe limits:** Up to 2GB per file

#### AudioExtractionError
Raised when extracting audio from video fails.

**Common causes:**
- Video has no audio track
- Unsupported audio codec
- Corrupted video file

#### SegmentationError
Raised when transcript segmentation fails.

**Common causes:**
- Invalid word timestamp format
- Empty transcript
- Negative timestamps

## Complete Example

```python
from ragstack_common.transcribe_client import TranscribeClient
from ragstack_common.media_segmenter import MediaSegmenter
from ragstack_common.exceptions import MediaProcessingError
import logging

logger = logging.getLogger(__name__)

def process_media_file(document_id: str, input_s3_uri: str, output_bucket: str) -> list[dict]:
    """
    Transcribe media file and segment into time-aligned chunks.

    Returns:
        List of segments with text, timestamps, and speaker attribution
    """
    try:
        # Initialize clients
        transcribe = TranscribeClient(
            language_code="en-US",
            enable_speaker_diarization=True
        )
        segmenter = MediaSegmenter(segment_duration=30)

        # Start transcription
        logger.info(f"Starting transcription for {document_id}")
        job_name = transcribe.start_transcription_job(
            document_id=document_id,
            input_s3_uri=input_s3_uri,
            output_bucket=output_bucket
        )

        # Wait for completion (30-minute timeout)
        logger.info(f"Waiting for transcription job {job_name}")
        result = transcribe.wait_for_completion(
            job_name,
            timeout_seconds=1800,
            poll_interval=30
        )

        # Parse word-level timestamps
        words = transcribe.parse_transcript_with_timestamps(result)
        logger.info(f"Parsed {len(words)} words from transcript")

        # Get total duration from last word
        total_duration = words[-1]["end_time"] if words else 0.0

        # Segment transcript
        segments = segmenter.segment_transcript(words, total_duration)
        logger.info(f"Created {len(segments)} segments")

        return segments

    except MediaProcessingError as e:
        logger.error(f"Media processing failed: {e}")
        raise
    except TimeoutError as e:
        logger.error(f"Transcription timeout: {e}")
        raise
```

## Best Practices

1. **Language Code**: Set correct language_code for better accuracy
2. **Speaker Diarization**: Enable for multi-speaker content (interviews, meetings)
3. **Segment Duration**: Use 30s for natural language, 60s+ for technical content
4. **Timeout**: Adjust wait_for_completion timeout based on media length (rule of thumb: 2x duration)
5. **Polling**: Use longer poll intervals (60s) for long jobs to reduce API calls
6. **Error Handling**: Catch specific exceptions for targeted error handling
7. **Cost**: AWS Transcribe charges per second of audio - consider batch processing

## See Also

- [OCR.md](./OCR.md) - Document OCR processing
- [STORAGE.md](./STORAGE.md) - S3 storage utilities
- [constants.py](./UTILITIES.md#constants) - Media-related constants
