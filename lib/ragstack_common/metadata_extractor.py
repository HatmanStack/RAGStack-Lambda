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
DEFAULT_EXTRACTION_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

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

# Maximum number of metadata fields to extract
DEFAULT_MAX_KEYS = 8

# Maximum length for metadata values
MAX_VALUE_LENGTH = 100

# System prompt for metadata extraction (auto mode)
EXTRACTION_SYSTEM_PROMPT = """You are a metadata extraction assistant. Analyze document content \
and extract structured metadata useful for searching and filtering.

IMPORTANT RULES:
1. Return ONLY valid JSON - no explanations or markdown
2. Use snake_case for all key names (lowercase with underscores)
3. Reuse existing keys when the content clearly matches them
4. Keep values concise (under 100 characters)
5. Extract 3-8 metadata fields per document
6. Focus on factual, objective metadata (not subjective interpretations)

SUGGESTED METADATA TYPES:
- topic: Main subject/theme (e.g., "genealogy", "immigration", "military_service")
- document_type: Type of document (e.g., "certificate", "letter", "census_record")
- date_range: Time period covered (e.g., "1900-1920", "19th_century")
- location: Geographic location mentioned (e.g., "New York", "Ireland")
- source_category: Origin category (e.g., "government_record", "personal_document")
- language: Document language (e.g., "english", "german")
- people_mentioned: Number of people referenced (e.g., "single", "multiple", "family")

OUTPUT FORMAT:
Return a JSON object with key-value pairs. Example:
{"topic": "immigration", "document_type": "ship_manifest", "date_range": "1890-1910"}

DO NOT include any text outside the JSON object."""

# System prompt for manual mode extraction
MANUAL_MODE_SYSTEM_PROMPT = """You are a metadata extraction assistant. Extract ONLY the specified \
metadata fields from the document.

FIELDS TO EXTRACT: {manual_keys}

RULES:
1. Return ONLY valid JSON - no explanations or markdown
2. Only include fields from the list above
3. If a field is not applicable to this document, omit it
4. Keep values concise (under 100 characters)
5. Use snake_case for all key names (lowercase with underscores)

OUTPUT FORMAT:
Return a JSON object with only the specified fields that are present in the document.
Example: {{"topic": "immigration", "document_type": "letter"}}

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
                system_prompt = MANUAL_MODE_SYSTEM_PROMPT.format(
                    manual_keys=", ".join(self.manual_keys)
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

        prompt_parts.append(f"\n\nExtract up to {self.max_keys} relevant metadata fields.")

        return "\n".join(prompt_parts)

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
        - Enforces max_keys limit
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
            # Stop at max_keys
            if count >= self.max_keys:
                break

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

            # Truncate long values
            if isinstance(value, str) and len(value) > MAX_VALUE_LENGTH:
                value = value[:MAX_VALUE_LENGTH]
                logger.debug(f"Truncated value for key '{normalized_key}'")

            # Convert lists to strings for filtering
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value[:5])  # Limit list items

            # Skip empty values
            if value is None or (isinstance(value, str) and not value.strip()):
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
