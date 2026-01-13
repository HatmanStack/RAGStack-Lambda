"""
ProcessMedia Lambda

Handles video and audio file processing through AWS Transcribe.
Outputs timestamped transcript segments for embedding.

Input event:
{
    "document_id": "abc123",
    "input_s3_uri": "s3://input-bucket/uploads/video.mp4",
    "output_s3_prefix": "s3://output-bucket/content/abc123/",
    "fileType": "media",
    "detectedType": "video"
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
from ragstack_common.storage import parse_s3_uri
from ragstack_common.transcribe_client import TranscribeClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Module-level AWS clients (reused across warm invocations)
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")


def _extract_filename(input_s3_uri: str) -> str:
    """Extract filename from S3 URI."""
    parts = input_s3_uri.split("/")
    return parts[-1] if parts else "media"


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
    # Rough estimates based on typical bitrates
    # Video: ~1MB per second (8 Mbps), Audio: ~128KB per second (1 Mbps)
    if media_type == "video":
        bytes_per_second = 1_000_000  # ~1MB/s for typical video
    else:
        bytes_per_second = 128_000  # ~128KB/s for typical audio

    return max(30.0, content_length / bytes_per_second)


def lambda_handler(event, context):
    """
    Main Lambda handler for media file processing.

    Orchestrates transcription through AWS Transcribe and outputs
    timestamped transcript segments.
    """
    tracking_table = os.environ.get("TRACKING_TABLE")
    if not tracking_table:
        raise ValueError("TRACKING_TABLE environment variable is required")

    vector_bucket = os.environ.get("VECTOR_BUCKET")
    graphql_endpoint = os.environ.get("GRAPHQL_ENDPOINT")

    logger.info(f"ProcessMedia: Received event: {event}")

    document_id = None
    filename = None

    try:
        # Extract event data
        document_id = event["document_id"]
        input_s3_uri = event["input_s3_uri"]
        output_s3_prefix = event["output_s3_prefix"]
        detected_type = event.get("detectedType", "video")

        filename = _extract_filename(input_s3_uri)
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
            job_name, poll_interval=10, max_wait=900  # 15 minute max
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
        full_transcript = transcript_json.get("results", {}).get("transcripts", [{}])[0].get(
            "transcript", ""
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

        # Write segment files to S3
        segments_prefix = f"{output_prefix}segments/".replace("//", "/")
        for segment in segments:
            segment_key = f"{segments_prefix}segment_{segment['segment_index']:03d}.txt"
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

        # Write media metadata
        metadata = {
            "document_id": document_id,
            "media_type": detected_type,
            "duration_seconds": int(estimated_duration),
            "total_segments": len(segments),
            "language_code": language_code,
            "transcribe_job_id": job_name,
            "segments": [
                {
                    "segment_index": s["segment_index"],
                    "timestamp_start": s["timestamp_start"],
                    "timestamp_end": s["timestamp_end"],
                    "word_count": s["word_count"],
                    "speaker": s.get("speaker"),
                }
                for s in segments
            ],
        }

        metadata_key = f"{output_prefix}media_metadata.json".replace("//", "/")
        s3_client.put_object(
            Bucket=output_bucket,
            Key=metadata_key,
            Body=json.dumps(metadata, indent=2).encode("utf-8"),
            ContentType="application/json",
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

        # Return result for Step Functions
        return {
            "document_id": document_id,
            "status": "transcribed",
            "output_s3_uri": full_transcript_uri,
            "total_segments": len(segments),
            "duration_seconds": int(estimated_duration),
            "media_type": detected_type,
        }

    except Exception as e:
        logger.error(f"Media processing failed: {e}", exc_info=True)

        # Update status to failed
        try:
            if tracking_table and document_id:
                table = dynamodb.Table(tracking_table)
                table.update_item(
                    Key={"document_id": document_id},
                    UpdateExpression=(
                        "SET #status = :status, "
                        "error_message = :error, "
                        "updated_at = :updated_at"
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
