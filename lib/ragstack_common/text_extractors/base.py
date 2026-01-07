"""
Base extractor class and common utilities.

All extractors inherit from BaseExtractor and return ExtractionResult.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ExtractionResult:
    """Result of text extraction.

    Attributes:
        markdown: Full markdown content with YAML frontmatter.
        file_type: Detected or confirmed file type (e.g., 'txt', 'html', 'csv').
        title: Document title extracted or generated from filename.
        word_count: Number of words in the extracted content.
        structural_metadata: Type-specific metadata (columns, keys, etc.).
        parse_warning: Warning message if parsing failed and fell back to text.
    """

    markdown: str
    file_type: str
    title: str
    word_count: int
    structural_metadata: dict
    parse_warning: str | None


class BaseExtractor(ABC):
    """Abstract base class for all text extractors.

    Subclasses must implement the extract() method. Helper methods are
    provided for common operations like frontmatter generation and
    content decoding.
    """

    @abstractmethod
    def extract(self, content: bytes, filename: str) -> ExtractionResult:
        """Extract text content from file bytes.

        Args:
            content: Raw file content as bytes.
            filename: Original filename (used for title extraction and type hints).

        Returns:
            ExtractionResult with markdown content and metadata.
        """

    @staticmethod
    def _generate_frontmatter(metadata: dict) -> str:
        """Generate YAML frontmatter from metadata dictionary.

        Args:
            metadata: Dictionary of metadata key-value pairs.

        Returns:
            YAML frontmatter string with --- delimiters.
        """
        # Use yaml.dump for proper escaping of special characters
        yaml_content = yaml.dump(
            metadata,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        return f"---\n{yaml_content}---\n"

    @staticmethod
    def _count_words(text: str) -> int:
        """Count words in text.

        Args:
            text: Text content to count words in.

        Returns:
            Number of words (split on whitespace).
        """
        if not text or not text.strip():
            return 0
        return len(text.split())

    @staticmethod
    def _decode_content(content: bytes) -> str:
        """Decode bytes to string with UTF-8, falling back to latin-1.

        Args:
            content: Raw bytes to decode.

        Returns:
            Decoded string content.
        """
        if not content:
            return ""
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            # Fall back to latin-1 which can decode any byte sequence
            return content.decode("latin-1")

    @staticmethod
    def _extract_title_from_filename(filename: str) -> str:
        """Extract a title from the filename by removing extension.

        Args:
            filename: Filename possibly with path and extension.

        Returns:
            Title string derived from filename.
        """
        # Get just the filename without path
        path = Path(filename)
        name = path.stem  # Filename without extension
        return name
