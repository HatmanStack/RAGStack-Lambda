"""Metadata Extractor for document pipeline

This module provides LLM-based metadata extraction from document text.
It uses Claude Haiku to analyze document content and extract structured
metadata fields like topic, document_type, date_range, location, etc.

The extractor:
- Maintains consistency by presenting existing keys for reuse
- Enforces naming conventions (snake_case, lowercase)
- Keeps values concise (<100 characters)
- Updates the key library with discovered fields
"""

import json
import logging
from typing import Any

from ragstack_common.bedrock import BedrockClient
from ragstack_common.key_library import KeyLibrary

logger = logging.getLogger(__name__)

# Default model for metadata extraction (cost-efficient)
DEFAULT_EXTRACTION_MODEL = "us.amazon.nova-lite-v1:0"

# Reserved keys that should not be extracted by LLM
RESERVED_KEYS = frozenset(
    {
        "text_content",
        "s3_uri",
        "document_id",
        "embedding",
        "vector_id",
        "chunk_id",
        "chunk_index",
    }
)

# Maximum number of metadata fields to extract (8 is sweet spot for S3 Vectors 2KB limit)
DEFAULT_MAX_KEYS = 8

# Maximum length for metadata values
MAX_VALUE_LENGTH = 100

# System prompt for metadata extraction (auto mode)
EXTRACTION_SYSTEM_PROMPT = """You are a metadata extraction assistant. Analyze document content \
and extract structured metadata useful for searching and filtering.

IMPORTANT RULES:
1. Return ONLY valid JSON - no explanations or markdown
2. Use snake_case for all key names (lowercase with underscores)
3. ALL VALUES MUST BE LOWERCASE - this is critical for filtering
4. Reuse existing keys when the content clearly matches them
5. Keep values concise (under 100 characters per value)
6. Extract 5-15 metadata fields per document
7. Focus on factual, objective metadata (not subjective interpretations)
8. Extract ACTUAL content (names, places, dates) not abstract descriptions
9. For ARRAY FIELDS: output as JSON arrays with max 10 items

SUGGESTED METADATA TYPES:
- topic: Main subject/theme (e.g., "genealogy", "immigration", "military_service")
- document_type: Type of document (e.g., "certificate", "letter", "census_record")
- year: Primary year referenced as 4-digit number (e.g., "1892", "1945")
- decade: Decade of document (e.g., "1890s", "1920s")
- country: Country mentioned (e.g., "united_states", "ireland", "germany")
- state_province: State or province (e.g., "new_york", "california", "bavaria")
- city: City mentioned (e.g., "chicago", "dublin", "hamburg")
- source_category: Origin category (e.g., "government_record", "personal_document")
- language: Document language (e.g., "english", "german")
- people_mentioned: ARRAY of full names (e.g., ["john smith"] or ["john smith", "mary jones"])
- surnames: ARRAY of family names (e.g., ["smith"] or ["smith", "jones"])
- author: Document author if known (e.g., "john smith", "us census bureau")

EXAMPLES:

Input: "Letter from James Wilson to his daughter Sarah Wilson, dated March 15, 1892, \
discussing the family farm in County Cork, Ireland."
Output: {"document_type": "letter", "year": "1892", \
"people_mentioned": ["james wilson", "sarah wilson"], "surnames": ["wilson"], \
"country": "ireland", "topic": "family_correspondence"}

Input: "1920 US Census record for the O'Brien household in Chicago, Illinois showing \
Patrick O'Brien (head), Margaret O'Brien (wife), and three children."
Output: {"document_type": "census_record", "year": "1920", "country": "united_states", \
"state_province": "illinois", "city": "chicago", \
"people_mentioned": ["patrick o'brien", "margaret o'brien"], \
"surnames": ["o'brien"], "source_category": "government_record"}

OUTPUT FORMAT:
Return a JSON object with key-value pairs. Use arrays for multi-value fields. All values lowercase.

DO NOT include any text outside the JSON object."""

# System prompt for manual mode extraction
MANUAL_MODE_SYSTEM_PROMPT = """You are a metadata extraction assistant. Extract ONLY the specified \
metadata fields from the document. Do NOT extract any other fields.

FIELDS TO EXTRACT: {manual_keys}

{key_examples}

STRICT RULES:
1. Return ONLY valid JSON - no explanations or markdown
2. ONLY include fields from the FIELDS TO EXTRACT list above - no other fields
3. If a field is not applicable to this document, omit it entirely
4. Keep values concise (under 100 characters)
5. Use snake_case for all key names (lowercase with underscores)
6. ALL VALUES MUST BE LOWERCASE - this is critical for filtering
7. Extract ACTUAL content (names, places, dates) not abstract descriptions
8. For array fields (like people_mentioned, surnames), use JSON arrays: ["value1", "value2"]

OUTPUT FORMAT:
Return a JSON object with ONLY the specified fields. Do not add any fields not in the list.

DO NOT include any text outside the JSON object."""


class MetadataExtractionError(Exception):
    """Raised when metadata extraction fails."""


def infer_data_type(value: Any) -> str:
    """
    Infer the data type of a value for the key library.

    Args:
        value: The value to analyze.

    Returns:
        One of: string, number, boolean, list
    """
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "list"
    return "string"


class MetadataExtractor:
    """
    LLM-based metadata extractor for documents.

    Uses Claude Haiku to analyze document text and extract structured
    metadata fields. Integrates with KeyLibrary to maintain consistency
    across documents.

    Usage:
        extractor = MetadataExtractor()
        metadata = extractor.extract_metadata(text, document_id)
    """

    def __init__(
        self,
        bedrock_client: BedrockClient | None = None,
        key_library: KeyLibrary | None = None,
        model_id: str | None = None,
        max_keys: int = DEFAULT_MAX_KEYS,
        extraction_mode: str = "auto",
        manual_keys: list[str] | None = None,
    ):
        """
        Initialize the metadata extractor.

        Args:
            bedrock_client: Bedrock client for LLM calls. Creates one if not provided.
            key_library: Key library for tracking discovered keys. Creates one if not provided.
            model_id: Bedrock model ID for extraction. Uses Claude Haiku by default.
            max_keys: Maximum number of metadata fields to extract.
            extraction_mode: Either "auto" (LLM decides keys) or "manual" (use manual_keys only).
            manual_keys: List of keys to extract when in manual mode.
        """
        self.bedrock_client = bedrock_client or BedrockClient()
        self.key_library = key_library or KeyLibrary()
        self.model_id = model_id or DEFAULT_EXTRACTION_MODEL
        self.max_keys = max_keys
        self.extraction_mode = extraction_mode
        self.manual_keys = manual_keys

        logger.info(
            f"Initialized MetadataExtractor with model: {self.model_id}, "
            f"mode: {self.extraction_mode}"
        )

    def extract_metadata(
        self,
        text: str,
        document_id: str,
        update_library: bool = True,
    ) -> dict[str, Any]:
        """
        Extract metadata from document text using LLM.

        Args:
            text: The document text to analyze.
            document_id: Document identifier (for logging).
            update_library: Whether to update the key library with extracted keys.

        Returns:
            Dictionary of extracted metadata key-value pairs.
            Returns empty dict on extraction failure (graceful degradation).
        """
        if not text or not text.strip():
            logger.warning(f"Empty text provided for document {document_id}")
            return {}

        # In manual mode with empty keys, return empty result
        if self.extraction_mode == "manual" and not self.manual_keys:
            logger.info(f"Manual mode with empty keys for {document_id}, returning empty metadata")
            return {}

        try:
            # Get existing keys for prompt context (only in auto mode)
            existing_keys = []
            if self.extraction_mode == "auto":
                # Get full key objects with sample values for better LLM context
                existing_keys = self.key_library.get_active_keys()

            # Build the extraction prompt
            prompt = self._build_extraction_prompt(text, existing_keys)

            # Select appropriate system prompt based on mode
            if self.extraction_mode == "manual" and self.manual_keys:
                # Build examples for manual keys from key library
                key_examples = self._build_manual_key_examples()
                system_prompt = MANUAL_MODE_SYSTEM_PROMPT.format(
                    manual_keys=", ".join(self.manual_keys),
                    key_examples=key_examples,
                )
            else:
                system_prompt = EXTRACTION_SYSTEM_PROMPT

            # Call LLM for extraction
            response = self.bedrock_client.invoke_model(
                model_id=self.model_id,
                system_prompt=system_prompt,
                content=[{"text": prompt}],
                temperature=0.1,  # Low temperature for deterministic output
                max_tokens=1024,
                context=f"metadata_extraction/{document_id}",
            )

            # Parse the response
            response_text = self.bedrock_client.extract_text_from_response(response)
            metadata = self._parse_response(response_text)

            # Filter and validate metadata
            metadata = self._filter_metadata(metadata)

            # Update key library if enabled
            if update_library and metadata:
                self._update_key_library(metadata)

            logger.info(
                f"Extracted {len(metadata)} metadata fields for document {document_id}: "
                f"{list(metadata.keys())}"
            )

            return metadata

        except MetadataExtractionError:
            # Already logged, return empty dict for graceful degradation
            return {}
        except Exception as e:
            logger.exception(f"Unexpected error extracting metadata for {document_id}: {e}")
            return {}

    def _build_extraction_prompt(self, text: str, existing_keys: list[dict]) -> str:
        """
        Build the user prompt for metadata extraction.

        Args:
            text: Document text to analyze.
            existing_keys: List of existing key dicts with key_name, sample_values, etc.

        Returns:
            Formatted prompt string.
        """
        # Truncate text if too long (to fit within token limits)
        max_text_length = 8000  # Leave room for prompt and response
        if len(text) > max_text_length:
            text = text[:max_text_length] + "\n\n[Text truncated for analysis...]"

        # Build prompt with existing keys context
        prompt_parts = [f"Analyze this document and extract metadata:\n\n{text}"]

        if existing_keys:
            # Build rich key context with sample values
            key_descriptions = []
            for key in existing_keys[:15]:  # Limit to 15 keys
                key_name = key.get("key_name", "")
                samples = key.get("sample_values", [])[:3]  # Up to 3 samples
                if samples:
                    samples_str = ", ".join(f'"{s}"' for s in samples)
                    key_descriptions.append(f"  - {key_name}: {samples_str}")
                else:
                    key_descriptions.append(f"  - {key_name}")

            keys_block = "\n".join(key_descriptions)
            prompt_parts.append(
                f"\n\nEXISTING KEYS (you MUST use these instead of creating similar "
                f"ones):\n{keys_block}\n\n"
                "IMPORTANT: If your extracted value is semantically similar to an "
                "existing key, USE THE EXISTING KEY. For example, if 'date' exists, "
                "don't create 'date_range' or 'dates'. "
                "Only create a new key if no existing key captures the same concept."
            )

        # Only add max_keys guidance in auto mode
        if self.extraction_mode != "manual":
            prompt_parts.append(
                f"\n\nAim for around {self.max_keys} metadata fields - a few more or less is fine, "
                "but focus on the most relevant and searchable attributes."
            )

        return "\n".join(prompt_parts)

    def _build_manual_key_examples(self) -> str:
        """
        Build example values for manual extraction keys from the key library.

        Returns:
            Formatted string with key examples, or empty string if no examples.
        """
        if not self.manual_keys:
            return ""

        examples = []
        try:
            # Get all active keys from library to find examples
            active_keys = self.key_library.get_active_keys()
            key_map = {k.get("key_name", "").lower(): k for k in active_keys}

            for key in self.manual_keys:
                normalized_key = key.lower().replace(" ", "_").replace("-", "_")
                key_info = key_map.get(normalized_key)

                if key_info and key_info.get("sample_values"):
                    samples = key_info["sample_values"][:3]
                    samples_str = ", ".join(f'"{s}"' for s in samples)
                    examples.append(f"  - {normalized_key}: e.g., {samples_str}")
                else:
                    # Provide generic guidance for common keys
                    examples.append(f"  - {normalized_key}")

        except Exception as e:
            logger.warning(f"Failed to get key examples from library: {e}")
            # Fall back to just listing keys
            for key in self.manual_keys:
                normalized_key = key.lower().replace(" ", "_").replace("-", "_")
                examples.append(f"  - {normalized_key}")

        if examples:
            return "EXAMPLES FOR EACH FIELD:\n" + "\n".join(examples)
        return ""

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse the LLM response into a metadata dictionary.

        Args:
            response_text: Raw text response from LLM.

        Returns:
            Parsed metadata dictionary.

        Raises:
            MetadataExtractionError: If response cannot be parsed as JSON.
        """
        if not response_text:
            logger.warning("Empty response from LLM")
            raise MetadataExtractionError("Empty response from LLM")

        # Clean up response text (remove markdown code blocks if present)
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            metadata = json.loads(cleaned)

            if not isinstance(metadata, dict):
                logger.warning(f"LLM response is not a dict: {type(metadata)}")
                raise MetadataExtractionError("Response is not a JSON object")

            return metadata

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {response_text[:500]}")
            raise MetadataExtractionError(f"Invalid JSON response: {e}") from e

    def _filter_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        Filter and validate extracted metadata.

        - Removes reserved keys
        - Truncates long values
        - Normalizes key names
        - In manual mode, only keeps keys from manual_keys list

        Args:
            metadata: Raw extracted metadata.

        Returns:
            Filtered and validated metadata.
        """
        filtered = {}
        count = 0

        # In manual mode, normalize manual_keys for comparison
        allowed_keys = None
        if self.extraction_mode == "manual" and self.manual_keys:
            allowed_keys = {k.lower().replace(" ", "_").replace("-", "_") for k in self.manual_keys}

        for key, value in metadata.items():
            # Skip reserved keys
            if key.lower() in RESERVED_KEYS:
                logger.debug(f"Skipping reserved key: {key}")
                continue

            # Normalize key name (lowercase, snake_case)
            normalized_key = key.lower().replace(" ", "_").replace("-", "_")

            # In manual mode, skip keys not in allowed_keys
            if allowed_keys is not None and normalized_key not in allowed_keys:
                logger.debug(f"Skipping key not in manual_keys: {normalized_key}")
                continue

            # Handle different value types
            if isinstance(value, list):
                # Preserve arrays - normalize elements to lowercase, limit to 10 items (AWS limit)
                normalized_list = []
                for item in value[:10]:
                    if isinstance(item, str):
                        item_str = item.lower().strip()
                        if item_str and len(item_str) <= MAX_VALUE_LENGTH:
                            normalized_list.append(item_str)
                    elif item is not None:
                        normalized_list.append(str(item).lower())
                if not normalized_list:
                    continue
                value = normalized_list
            elif isinstance(value, str):
                # Truncate and normalize string values
                if len(value) > MAX_VALUE_LENGTH:
                    value = value[:MAX_VALUE_LENGTH]
                    logger.debug(f"Truncated value for key '{normalized_key}'")
                value = value.lower().strip()
                if not value:
                    continue
            elif value is None:
                continue

            filtered[normalized_key] = value
            count += 1

        return filtered

    def _update_key_library(self, metadata: dict[str, Any]) -> None:
        """
        Update the key library with extracted metadata fields.

        Args:
            metadata: Extracted metadata to record.
        """
        for key, value in metadata.items():
            data_type = infer_data_type(value)
            try:
                self.key_library.upsert_key(key, data_type, value)
            except Exception as e:
                # Non-critical, just log and continue
                logger.warning(f"Failed to update key library for '{key}': {e}")

    def extract_from_caption(
        self,
        caption: str,
        document_id: str,
        filename: str | None = None,
        update_library: bool = True,
    ) -> dict[str, Any]:
        """
        Extract metadata from an image caption.

        This is a convenience method for image documents where the
        "text" is actually a caption describing the image.

        Args:
            caption: Image caption text.
            document_id: Document identifier.
            filename: Optional filename for additional context.
            update_library: Whether to update the key library.

        Returns:
            Extracted metadata dictionary.
        """
        # Build context from caption and filename
        context_parts = []

        if caption:
            context_parts.append(f"Image caption: {caption}")

        if filename:
            context_parts.append(f"Original filename: {filename}")

        if not context_parts:
            logger.warning(f"No caption or filename for image {document_id}")
            return {}

        text = "\n".join(context_parts)
        return self.extract_metadata(text, document_id, update_library)

    def extract_media_metadata(
        self,
        transcript: str,
        segments: list[dict[str, Any]],
        technical_metadata: dict[str, Any],
        document_id: str,
        update_library: bool = True,
    ) -> dict[str, Any]:
        """
        Extract metadata from audio/video content.

        Combines technical metadata with LLM-extracted content metadata
        from the transcript. Returns technical metadata even if LLM fails.

        Args:
            transcript: Full transcript text.
            segments: List of transcript segments with timestamps.
            technical_metadata: Dictionary of technical metadata (duration, format, etc).
            document_id: Document identifier.
            update_library: Whether to update the key library.

        Returns:
            Combined metadata dictionary.
        """
        # Start with technical metadata
        result = {**technical_metadata}

        # Skip LLM extraction if no transcript
        if not transcript or not transcript.strip():
            logger.warning(f"No transcript for media {document_id}")
            return result

        try:
            # Build media-specific prompt
            prompt = self._build_media_extraction_prompt(transcript, segments)

            # Get existing keys for context
            existing_keys = []
            if self.key_library:
                try:
                    existing_keys = self.key_library.get_active_keys()
                except Exception as e:
                    logger.warning(f"Failed to get existing keys: {e}")

            # Build full prompt with existing keys
            full_prompt = self._build_extraction_prompt(prompt, existing_keys)

            # Media-specific system prompt
            # Note: Use media_category NOT content_type - technical metadata sets content_type
            system_prompt = """You are a metadata extraction system for audio/video content.
Extract structured metadata from the transcript to enable search and filtering.

Focus on:
- main_topic: Primary subject matter
- media_category: Format of media (podcast, interview, lecture, conversation, etc.)
- speakers: List of identified speakers
- key_themes: Major themes discussed
- sentiment: Overall tone (informative, entertaining, serious, casual, etc.)

Return ONLY valid JSON with lowercase values. No explanations."""

            # Invoke model
            response = self.bedrock_client.invoke_model(
                model_id=self.model_id,
                system_prompt=system_prompt,
                content=[{"text": full_prompt}],
                temperature=0.0,
                context="media_metadata_extraction",
            )

            # Parse response
            response_text = self.bedrock_client.extract_text_from_response(response)
            extracted = self._parse_response(response_text)
            filtered = self._filter_metadata(extracted)

            # Update key library
            if update_library:
                self._update_key_library(filtered)

            # Merge extracted metadata, preserving critical technical fields
            # Technical fields like content_type and media_type must not be overwritten
            preserve_keys = (
                "content_type",
                "media_type",
                "file_type",
                "duration_seconds",
                "total_segments",
            )
            preserved_fields = {k: v for k, v in technical_metadata.items() if k in preserve_keys}
            result.update(filtered)
            result.update(preserved_fields)  # Restore technical fields
            logger.info(f"Extracted media metadata for {document_id}: {list(result.keys())}")

        except Exception as e:
            logger.warning(f"Failed to extract media metadata for {document_id}: {e}")
            # Return technical metadata even if LLM extraction fails

        return result

    def _build_media_extraction_prompt(
        self,
        transcript: str,
        segments: list[dict[str, Any]],
    ) -> str:
        """
        Build extraction prompt for media content.

        Args:
            transcript: Full transcript text.
            segments: List of transcript segments.

        Returns:
            Prompt string for extraction.
        """
        # Truncate long transcripts
        max_length = 4000
        if len(transcript) > max_length:
            transcript = transcript[:max_length] + "\n[Transcript truncated...]"

        # Build segment summary
        segment_summary = ""
        if segments:
            num_segments = len(segments)
            total_duration = max(s.get("timestamp_end", 0) for s in segments) if segments else 0
            speakers = {s.get("speaker") for s in segments if s.get("speaker")}

            segment_summary = f"""
Segment Summary:
- Total segments: {num_segments}
- Duration: {total_duration} seconds
- Speakers detected: {len(speakers)}
"""

        return f"""AUDIO/VIDEO TRANSCRIPT:
{transcript}

{segment_summary}

Extract metadata from this media content."""
