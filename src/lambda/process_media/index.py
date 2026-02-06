"""
ProcessMedia Lambda

Handles video and audio file processing through AWS Transcribe.
Outputs timestamped transcript segments for embedding.

Media files are uploaded directly to content/{docId}/ folder and processed
via EventBridge trigger. No Step Functions involved for media.

Input event (EventBridge S3):
{
    "detail": {
        "bucket": {"name": "bucket"},
        "object": {"key": "content/{docId}/video.mp4"}
    }
}

Output:
{
    "document_id": "abc123",
    "status": "transcribed",
    "output_s3_uri": "s3://output-bucket/content/abc123/transcript_full.txt",
    "total_segments": 4,
    "duration_seconds": 120,
    "media_type": "video"
}
"""

import json
import logging
import os
from datetime import UTC, datetime

import boto3

from ragstack_common.appsync import publish_document_update
from ragstack_common.config import ConfigurationManager
from ragstack_common.exceptions import TranscriptionError
from ragstack_common.media_segmenter import MediaSegmenter
from ragstack_common.storage import extract_filename_from_s3_uri, parse_s3_uri
from ragstack_common.transcribe_client import TranscribeClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level AWS clients (reused across warm invocations)
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")


# Media file extensions
MEDIA_EXTENSIONS = {".mp4", ".webm", ".mp3", ".wav", ".m4a", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg"}


def _is_eventbridge_event(event: dict) -> bool:
    """Check if this is an EventBridge S3 event (vs Step Functions)."""
    detail = event.get("detail", {})
    if not detail:
        return False
    bucket_info = detail.get("bucket", {})
    object_info = detail.get("object", {})
    return bool(bucket_info.get("name") and object_info.get("key"))


def _parse_eventbridge_event(event: dict) -> dict | None:
    """
    Parse EventBridge S3 event to extract media processing parameters.

    Args:
        event: EventBridge S3 event

    Returns:
        Dict with document_id, input_s3_uri, output_s3_prefix, detectedType
        or None if not a media file (caller should skip processing)
    """
    detail = event.get("detail", {})
    bucket_info = detail.get("bucket", {})
    object_info = detail.get("object", {})

    bucket = bucket_info.get("name")
    key = object_info.get("key")

    # Expected key format: content/{docId}/{filename}
    # e.g., content/abc123/video.mp4
    if not key.startswith("content/"):
        logger.info(f"Skipping non-content path: {key}")
        return None

    # Extract document_id from path
    parts = key.split("/")
    if len(parts) < 3:
        logger.info(f"Invalid content path format: {key}")
        return None

    document_id = parts[1]
    filename = parts[-1]

    # Check if it's a media file
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in MEDIA_EXTENSIONS:
        logger.info(f"Skipping non-media file: {key}")
        return None

    # Determine media type
    detected_type = "video" if ext in VIDEO_EXTENSIONS else "audio"

    input_s3_uri = f"s3://{bucket}/{key}"
    output_s3_prefix = f"s3://{bucket}/content/{document_id}/"

    return {
        "document_id": document_id,
        "input_s3_uri": input_s3_uri,
        "output_s3_prefix": output_s3_prefix,
        "detectedType": detected_type,
        "filename": filename,
    }


def _get_media_duration_estimate(content_length: int, media_type: str) -> float:
    """Estimate media duration from file size.

    This is a rough estimate until actual duration is extracted.
    For more accurate duration, use FFprobe or mediainfo.

    Args:
        content_length: File size in bytes.
        media_type: "video" or "audio".

    Returns:
        Estimated duration in seconds.
    """
    # Rough estimates: Video ~1MB/s (8 Mbps), Audio ~128KB/s (1 Mbps)
    bytes_per_second = 1_000_000 if media_type == "video" else 128_000
    return max(30.0, content_length / bytes_per_second)


def lambda_handler(event, context):
    """
    Main Lambda handler for media file processing.

    Orchestrates transcription through AWS Transcribe and outputs
    timestamped transcript segments.

    Handles both EventBridge S3 events and Step Functions events.
    """
    tracking_table = os.environ.get("TRACKING_TABLE")
    if not tracking_table:
        raise ValueError("TRACKING_TABLE environment variable is required")

    vector_bucket = os.environ.get("VECTOR_BUCKET")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    logger.info(f"ProcessMedia: Received event: {json.dumps(event)[:500]}")

    document_id = None
    filename = None

    try:
        # Check if this is an EventBridge S3 event (vs Step Functions)
        is_eventbridge = _is_eventbridge_event(event)

        if is_eventbridge:
            # Try parsing as EventBridge S3 event (direct upload to content/)
            eb_event = _parse_eventbridge_event(event)
            if eb_event:
                document_id = eb_event["document_id"]
                input_s3_uri = eb_event["input_s3_uri"]
                output_s3_prefix = eb_event["output_s3_prefix"]
                detected_type = eb_event["detectedType"]
                logger.info(f"EventBridge trigger: {document_id}, type={detected_type}")
            else:
                # EventBridge event but not a media file - skip processing
                logger.info("EventBridge event is not a media file, skipping")
                return {"status": "skipped", "reason": "not a media file"}
        else:
            # Legacy Step Functions event format
            document_id = event["document_id"]
            input_s3_uri = event["input_s3_uri"]
            output_s3_prefix = event["output_s3_prefix"]
            detected_type = event.get("detectedType", "video")

            # Fix output_s3_prefix - EventBridge template produces wrong format
            # Received: s3://bucket/content/input/{doc_id}/{filename}/
            # Expected: s3://bucket/content/{doc_id}/
            if "/content/input/" in output_s3_prefix:
                bucket_and_prefix = output_s3_prefix.split("/content/input/")[0]
                output_s3_prefix = f"{bucket_and_prefix}/content/{document_id}/"
                logger.info(f"Fixed output_s3_prefix to: {output_s3_prefix}")

        filename = extract_filename_from_s3_uri(input_s3_uri, default="media")
        logger.info(f"Processing media file: {filename} (type: {detected_type})")

        # Get configuration
        config_manager = ConfigurationManager()
        language_code = config_manager.get_parameter("transcribe_language_code", "en-US")
        enable_diarization = config_manager.get_parameter("speaker_diarization_enabled", True)
        segment_duration = config_manager.get_parameter("media_segment_duration_seconds", 30)

        # Update status to transcribing
        table = dynamodb.Table(tracking_table)
        now = datetime.now(UTC).isoformat()

        table.update_item(
            Key={"document_id": document_id},
            UpdateExpression=(
                "SET #status = :status, "
                "#type = :type, "
                "media_type = :media_type, "
                "file_type = :file_type, "
                "updated_at = :updated_at, "
                "created_at = if_not_exists(created_at, :created_at), "
                "filename = if_not_exists(filename, :filename), "
                "input_s3_uri = if_not_exists(input_s3_uri, :input_s3_uri)"
            ),
            ExpressionAttributeNames={"#status": "status", "#type": "type"},
            ExpressionAttributeValues={
                ":status": "transcribing",
                ":type": "media",
                ":media_type": detected_type,
                ":file_type": detected_type,  # video or audio
                ":updated_at": now,
                ":created_at": now,
                ":filename": filename,
                ":input_s3_uri": input_s3_uri,
            },
        )

        # Publish real-time update
        publish_document_update(graphql_endpoint, document_id, filename, "PROCESSING")

        # Get file metadata for duration estimation
        input_bucket, input_key = parse_s3_uri(input_s3_uri)
        head_response = s3_client.head_object(Bucket=input_bucket, Key=input_key)
        content_length = head_response.get("ContentLength", 0)
        estimated_duration = _get_media_duration_estimate(content_length, detected_type)

        logger.info(
            f"Media file: {content_length} bytes, estimated duration: {estimated_duration}s"
        )

        # Start transcription job
        output_bucket, _ = parse_s3_uri(output_s3_prefix)
        transcribe_client = TranscribeClient()

        job_name = transcribe_client.start_transcription_job(
            document_id=document_id,
            input_s3_uri=input_s3_uri,
            output_bucket=vector_bucket or output_bucket,
            language_code=language_code,
            enable_speaker_diarization=enable_diarization,
            max_speakers=4,
            output_key_prefix=f"transcripts/{document_id}/",
        )

        logger.info(f"Started transcription job: {job_name}")

        # Update status with job info
        table.update_item(
            Key={"document_id": document_id},
            UpdateExpression="SET transcribe_job_id = :job_id, updated_at = :updated_at",
            ExpressionAttributeValues={
                ":job_id": job_name,
                ":updated_at": datetime.now(UTC).isoformat(),
            },
        )

        # Wait for transcription to complete
        result = transcribe_client.wait_for_completion(
            job_name,
            poll_interval=10,
            max_wait=900,  # 15 minute max
        )

        if result["status"] != "COMPLETED":
            raise TranscriptionError(f"Transcription did not complete: {result}")

        transcript_uri = result["transcript_uri"]
        logger.info(f"Transcription completed: {transcript_uri}")

        # Download and parse transcript
        transcript_bucket, transcript_key = parse_s3_uri(transcript_uri)
        transcript_response = s3_client.get_object(Bucket=transcript_bucket, Key=transcript_key)
        transcript_json = json.loads(transcript_response["Body"].read().decode("utf-8"))

        # Parse words with timestamps
        words = transcribe_client.parse_transcript_with_timestamps(transcript_json)
        logger.info(f"Parsed {len(words)} words from transcript")

        # Get actual duration from transcript if available
        if words:
            actual_duration = max(w.get("end_time", 0) for w in words if w.get("end_time"))
            if actual_duration > 0:
                estimated_duration = actual_duration

        # Segment transcript
        segmenter = MediaSegmenter(segment_duration=segment_duration)
        segments = segmenter.segment_transcript(words, total_duration=estimated_duration)
        logger.info(f"Created {len(segments)} segments")

        # Write full transcript to S3
        full_transcript = (
            transcript_json.get("results", {}).get("transcripts", [{}])[0].get("transcript", "")
        )
        output_bucket, output_prefix = parse_s3_uri(output_s3_prefix)
        transcript_key = f"{output_prefix}transcript_full.txt".replace("//", "/")

        s3_client.put_object(
            Bucket=output_bucket,
            Key=transcript_key,
            Body=full_transcript.encode("utf-8"),
            ContentType="text/plain",
        )

        full_transcript_uri = f"s3://{output_bucket}/{transcript_key}"
        logger.info(f"Wrote full transcript to: {full_transcript_uri}")

        # Video stays in content/ - uploaded directly there, KB syncs from there
        video_uri = input_s3_uri

        # Write segment files to S3 (flat structure, no /segments/ subfolder)
        for segment in segments:
            seg_name = f"segment-{segment['segment_index']:03d}.txt"
            segment_key = f"{output_prefix}{seg_name}".replace("//", "/")
            segment_content = segment["text"]

            s3_client.put_object(
                Bucket=output_bucket,
                Key=segment_key,
                Body=segment_content.encode("utf-8"),
                ContentType="text/plain",
                Metadata={
                    "timestamp_start": str(segment["timestamp_start"]),
                    "timestamp_end": str(segment["timestamp_end"]),
                    "word_count": str(segment["word_count"]),
                    "segment_index": str(segment["segment_index"]),
                },
            )

        # Update DynamoDB tracking
        table.update_item(
            Key={"document_id": document_id},
            UpdateExpression=(
                "SET #status = :status, "
                "duration_seconds = :duration, "
                "total_segments = :segments, "
                "output_s3_uri = :output_uri, "
                "language_code = :language, "
                "updated_at = :updated_at"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "transcribed",
                ":duration": int(estimated_duration),
                ":segments": len(segments),
                ":output_uri": full_transcript_uri,
                ":language": language_code,
                ":updated_at": datetime.now(UTC).isoformat(),
            },
        )

        # Publish completion update
        publish_document_update(
            graphql_endpoint,
            document_id,
            filename,
            "OCR_COMPLETE",
            total_pages=len(segments),
        )

        # Build transcript segment list for output
        transcript_segments = [
            {
                "segment_index": s["segment_index"],
                "timestamp_start": s["timestamp_start"],
                "timestamp_end": s["timestamp_end"],
                "text": s["text"],
                "word_count": s["word_count"],
                "speaker": s.get("speaker"),
            }
            for s in segments
        ]

        # Build result
        result = {
            "document_id": document_id,
            "status": "transcribed",
            "output_s3_uri": full_transcript_uri,
            "video_s3_uri": video_uri,
            "total_segments": len(segments),
            "duration_seconds": int(estimated_duration),
            "media_type": detected_type,
            "transcript_segments": transcript_segments,
        }

        # If triggered via EventBridge (not Step Functions), invoke IngestMedia directly
        ingest_media_arn = os.environ.get("INGEST_MEDIA_FUNCTION_ARN")
        if is_eventbridge and ingest_media_arn:
            logger.info(f"EventBridge trigger: invoking IngestMedia for {document_id}")
            try:
                lambda_client.invoke(
                    FunctionName=ingest_media_arn,
                    InvocationType="Event",  # Async invocation
                    Payload=json.dumps(result),
                )
            except Exception as invoke_err:
                # Log but don't fail - transcription succeeded, ingest can be retried
                logger.error(f"Failed to invoke IngestMedia for {document_id}: {invoke_err}")

        return result

    except Exception as e:
        logger.error(f"Media processing failed: {e}", exc_info=True)

        # Update status to failed
        try:
            if tracking_table and document_id:
                table = dynamodb.Table(tracking_table)
                table.update_item(
                    Key={"document_id": document_id},
                    UpdateExpression=(
                        "SET #status = :status, error_message = :error, updated_at = :updated_at"
                    ),
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": "failed",
                        ":error": str(e),
                        ":updated_at": datetime.now(UTC).isoformat(),
                    },
                )
                # Publish failure update
                publish_document_update(
                    graphql_endpoint,
                    document_id,
                    filename or "unknown",
                    "FAILED",
                    error_message=str(e),
                )
        except Exception as update_error:
            logger.error(f"Failed to update DynamoDB: {update_error}")

        raise
