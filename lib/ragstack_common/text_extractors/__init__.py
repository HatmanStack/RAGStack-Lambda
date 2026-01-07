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

# Public API will be populated as extractors are implemented
__all__: list[str] = []
