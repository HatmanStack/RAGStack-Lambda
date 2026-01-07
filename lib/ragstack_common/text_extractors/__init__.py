"""
Text extractors for document processing.

This module provides extractors for various text-based file formats:
- HTML, TXT, CSV, JSON, XML, EML (no additional dependencies)
- EPUB, DOCX, XLSX (requires ebooklib, python-docx, openpyxl)

Usage:
    from ragstack_common.text_extractors import extract_text, ExtractionResult

    result = extract_text(content_bytes, "document.html")
    print(result.markdown)
"""

from .base import BaseExtractor, ExtractionResult
from .csv_extractor import CsvExtractor
from .docx_extractor import DocxExtractor
from .email_extractor import EmailExtractor
from .epub_extractor import EpubExtractor
from .html_extractor import HtmlExtractor
from .json_extractor import JsonExtractor
from .sniffer import ContentSniffer
from .text_extractor import TextExtractor
from .xlsx_extractor import XlsxExtractor
from .xml_extractor import XmlExtractor

# Registry mapping file types to extractors
EXTRACTORS = {
    "html": HtmlExtractor,
    "txt": TextExtractor,
    "csv": CsvExtractor,
    "json": JsonExtractor,
    "xml": XmlExtractor,
    "eml": EmailExtractor,
    "epub": EpubExtractor,
    "docx": DocxExtractor,
    "xlsx": XlsxExtractor,
}

# Cache for extractor instances
_extractor_cache: dict[str, BaseExtractor] = {}


def _get_extractor(file_type: str) -> BaseExtractor:
    """Get or create extractor instance for file type."""
    if file_type not in _extractor_cache:
        extractor_class = EXTRACTORS.get(file_type, TextExtractor)
        _extractor_cache[file_type] = extractor_class()
    return _extractor_cache[file_type]


def extract_text(content: bytes, filename: str) -> ExtractionResult:
    """
    Extract text from file content.

    Automatically detects file type and routes to appropriate extractor.

    Args:
        content: File content as bytes.
        filename: Original filename (used for type hints and title extraction).

    Returns:
        ExtractionResult with markdown content and metadata.

    Example:
        >>> result = extract_text(b"<html>...</html>", "page.html")
        >>> print(result.file_type)
        'html'
        >>> print(result.markdown)
        '---\\nsource_file: page.html\\n...'
    """
    # Detect file type
    sniffer = ContentSniffer()
    file_type, confidence = sniffer.sniff(content, filename)

    # Get appropriate extractor
    extractor = _get_extractor(file_type)

    # Extract content
    return extractor.extract(content, filename)


# Public API exports
__all__ = [
    # Main entry point
    "extract_text",
    # Result type
    "ExtractionResult",
    # Content detection
    "ContentSniffer",
    # Base class for custom extractors
    "BaseExtractor",
    # Individual extractors
    "TextExtractor",
    "HtmlExtractor",
    "CsvExtractor",
    "JsonExtractor",
    "XmlExtractor",
    "EmailExtractor",
    "EpubExtractor",
    "DocxExtractor",
    "XlsxExtractor",
    # Registry
    "EXTRACTORS",
]
