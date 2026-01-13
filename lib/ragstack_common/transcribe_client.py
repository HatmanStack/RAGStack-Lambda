"""
AWS Transcribe client wrapper for video/audio transcription.

Provides async job management and transcript parsing with timestamps.
"""

import logging
import time
import uuid
from typing import Any

import boto3

from ragstack_common.exceptions import TranscriptionError

logger = logging.getLogger(__name__)


class TranscribeClient:
    """AWS Transcribe client wrapper for batch transcription jobs.

    Provides methods for:
    - Starting transcription jobs with speaker diarization
    - Polling job status
    - Retrieving and parsing transcripts with word-level timestamps

    Example:
        client = TranscribeClient()
        job_name = client.start_transcription_job(
            document_id="doc-123",
            input_s3_uri="s3://bucket/audio.mp3",
            output_bucket="output-bucket"
        )
        result = client.wait_for_completion(job_name)
    """

    def __init__(self, region: str | None = None):
        """Initialize TranscribeClient.

        Args:
            region: AWS region for Transcribe. Uses default if not specified.
        """
        if region:
            self._client = boto3.client("transcribe", region_name=region)
        else:
            self._client = boto3.client("transcribe")

    def start_transcription_job(
        self,
        document_id: str,
        input_s3_uri: str,
        output_bucket: str,
        language_code: str = "en-US",
        enable_speaker_diarization: bool = False,
        max_speakers: int = 2,
        output_key_prefix: str = "transcripts/",
    ) -> str:
        """Start a transcription job for audio/video content.

        Args:
            document_id: Unique document identifier (used in job name).
            input_s3_uri: S3 URI of input media file.
            output_bucket: S3 bucket for transcript output.
            language_code: Language code for transcription (default: en-US).
            enable_speaker_diarization: Enable speaker labels (default: False).
            max_speakers: Maximum number of speakers to identify (default: 2).
            output_key_prefix: S3 key prefix for output (default: transcripts/).

        Returns:
            Transcription job name.

        Raises:
            TranscriptionError: If job creation fails.
        """
        # Generate unique job name
        job_id = str(uuid.uuid4())[:8]
        job_name = f"ragstack-{document_id}-{job_id}"
        # Transcribe job names must be max 200 chars, alphanumeric + hyphens
        job_name = job_name[:200].replace("_", "-")

        logger.info(f"Starting transcription job: {job_name} for {input_s3_uri}")

        # Build job parameters
        job_params: dict[str, Any] = {
            "TranscriptionJobName": job_name,
            "LanguageCode": language_code,
            "Media": {"MediaFileUri": input_s3_uri},
            "OutputBucketName": output_bucket,
            "OutputKey": f"{output_key_prefix}{job_name}.json",
        }

        # Add settings for speaker diarization
        if enable_speaker_diarization:
            job_params["Settings"] = {
                "ShowSpeakerLabels": True,
                "MaxSpeakerLabels": max_speakers,
            }

        try:
            response = self._client.start_transcription_job(**job_params)
            created_job_name = response["TranscriptionJob"]["TranscriptionJobName"]
            logger.info(f"Transcription job started: {created_job_name}")
            return created_job_name
        except Exception as e:
            logger.exception(f"Failed to start transcription job: {e}")
            raise TranscriptionError(f"Failed to start transcription: {e}") from e

    def get_job_status(self, job_name: str) -> str:
        """Get the status of a transcription job.

        Args:
            job_name: Transcription job name.

        Returns:
            Job status: QUEUED, IN_PROGRESS, COMPLETED, or FAILED.
        """
        try:
            response = self._client.get_transcription_job(TranscriptionJobName=job_name)
            status = response["TranscriptionJob"]["TranscriptionJobStatus"]
            logger.debug(f"Job {job_name} status: {status}")
            return status
        except Exception as e:
            logger.exception(f"Failed to get job status: {e}")
            raise TranscriptionError(f"Failed to get job status: {e}") from e

    def get_transcript_result(self, job_name: str) -> str | None:
        """Get the transcript result URI for a completed job.

        Args:
            job_name: Transcription job name.

        Returns:
            S3 URI of transcript JSON, or None if job not complete.
        """
        try:
            response = self._client.get_transcription_job(TranscriptionJobName=job_name)
            job = response["TranscriptionJob"]
            if job["TranscriptionJobStatus"] != "COMPLETED":
                return None
            return job.get("Transcript", {}).get("TranscriptFileUri")
        except Exception as e:
            logger.exception(f"Failed to get transcript result: {e}")
            raise TranscriptionError(f"Failed to get transcript result: {e}") from e

    def wait_for_completion(
        self,
        job_name: str,
        poll_interval: int = 10,
        max_wait: int = 900,
    ) -> dict[str, Any]:
        """Wait for a transcription job to complete.

        Args:
            job_name: Transcription job name.
            poll_interval: Seconds between status checks (default: 10).
            max_wait: Maximum seconds to wait (default: 900 = 15 minutes).

        Returns:
            Dict with status and transcript_uri if successful.

        Raises:
            TranscriptionError: If job fails or times out.
        """
        logger.info(f"Waiting for job completion: {job_name}")
        elapsed = 0

        while elapsed < max_wait:
            response = self._client.get_transcription_job(TranscriptionJobName=job_name)
            job = response["TranscriptionJob"]
            status = job["TranscriptionJobStatus"]

            if status == "COMPLETED":
                transcript_uri = job.get("Transcript", {}).get("TranscriptFileUri")
                logger.info(f"Job {job_name} completed. Transcript: {transcript_uri}")
                return {
                    "status": "COMPLETED",
                    "transcript_uri": transcript_uri,
                }

            if status == "FAILED":
                failure_reason = job.get("FailureReason", "Unknown error")
                logger.error(f"Job {job_name} failed: {failure_reason}")
                raise TranscriptionError(f"Transcription failed: {failure_reason}")

            logger.debug(f"Job {job_name} status: {status}. Waiting...")
            time.sleep(poll_interval)
            elapsed += poll_interval

        raise TranscriptionError(f"Transcription job timed out after {max_wait} seconds")

    def parse_transcript_with_timestamps(
        self, transcript_json: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Parse transcript JSON and extract words with timestamps.

        Args:
            transcript_json: Parsed JSON from Transcribe output.

        Returns:
            List of word dictionaries with:
            - word: The word text
            - start_time: Start time in seconds
            - end_time: End time in seconds
            - confidence: Confidence score
            - speaker: Speaker label (if diarization enabled)
            - type: "pronunciation" or "punctuation"
        """
        results = transcript_json.get("results", {})
        items = results.get("items", [])
        speaker_labels = results.get("speaker_labels", {})

        # Build speaker map from segments if available
        speaker_map: dict[str, str] = {}
        if speaker_labels:
            for segment in speaker_labels.get("segments", []):
                for item in segment.get("items", []):
                    start_time = item.get("start_time")
                    if start_time:
                        speaker_map[start_time] = item.get("speaker_label", "")

        words = []
        for item in items:
            item_type = item.get("type", "")
            alternatives = item.get("alternatives", [])
            if not alternatives:
                continue

            best_alt = alternatives[0]
            word_info: dict[str, Any] = {
                "word": best_alt.get("content", ""),
                "confidence": float(best_alt.get("confidence", 0)),
                "type": item_type,
            }

            # Add timing for pronunciation items
            if item_type == "pronunciation":
                start_time = item.get("start_time")
                end_time = item.get("end_time")
                if start_time is not None:
                    word_info["start_time"] = float(start_time)
                if end_time is not None:
                    word_info["end_time"] = float(end_time)

                # Add speaker label if available
                if start_time and start_time in speaker_map:
                    word_info["speaker"] = speaker_map[start_time]

            words.append(word_info)

        logger.info(f"Parsed {len(words)} items from transcript")
        return words
