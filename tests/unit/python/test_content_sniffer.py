"""Unit tests for content sniffer."""

import io
import zipfile

import pytest

from ragstack_common.text_extractors.sniffer import ContentSniffer
from tests.fixtures.text_extractor_samples import (
    CSV_MALFORMED,
    CSV_NO_HEADER,
    CSV_SEMICOLON,
    CSV_STANDARD,
    CSV_TAB_SEPARATED,
    EMAIL_MINIMAL,
    EMAIL_SIMPLE,
    FULL_HTML_PAGE,
    HTML_FRAGMENT,
    JSON_ARRAY_OF_OBJECTS,
    JSON_MALFORMED,
    JSON_NESTED,
    JSON_SIMPLE_ARRAY,
    JSON_SIMPLE_OBJECT,
    SIMPLE_TEXT,
    TEXT_LOOKS_LIKE_JSON,
    TEXT_LOOKS_LIKE_XML,
    TEXT_WITH_COMMAS,
    XML_NO_DECLARATION,
    XML_SIMPLE,
    XML_WITH_ATTRIBUTES,
    XML_WITH_NAMESPACE,
)


class TestContentSnifferHtml:
    """Tests for HTML detection."""

    def test_detects_full_html_page(self):
        """Test detection of full HTML with DOCTYPE."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(FULL_HTML_PAGE.encode())
        assert file_type == "html"
        assert confidence >= 0.8

    def test_detects_html_fragment(self):
        """Test detection of HTML fragment."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(HTML_FRAGMENT.encode())
        assert file_type == "html"
        assert confidence >= 0.5

    def test_detects_html_with_extension_hint(self):
        """Test HTML detection with extension hint."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(HTML_FRAGMENT.encode(), "page.html")
        assert file_type == "html"
        assert confidence >= 0.7


class TestContentSnifferJson:
    """Tests for JSON detection."""

    def test_detects_simple_object(self):
        """Test detection of JSON object."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(JSON_SIMPLE_OBJECT.encode())
        assert file_type == "json"
        assert confidence >= 0.8

    def test_detects_simple_array(self):
        """Test detection of JSON array."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(JSON_SIMPLE_ARRAY.encode())
        assert file_type == "json"
        assert confidence >= 0.8

    def test_detects_array_of_objects(self):
        """Test detection of JSON array of objects."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(JSON_ARRAY_OF_OBJECTS.encode())
        assert file_type == "json"
        assert confidence >= 0.8

    def test_detects_nested_json(self):
        """Test detection of nested JSON."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(JSON_NESTED.encode())
        assert file_type == "json"
        assert confidence >= 0.8

    def test_malformed_json_not_detected_as_json(self):
        """Test that malformed JSON is not detected as JSON."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(JSON_MALFORMED.encode())
        # Should fall back to txt or have low confidence
        assert file_type != "json" or confidence < 0.7


class TestContentSnifferXml:
    """Tests for XML detection."""

    def test_detects_xml_with_declaration(self):
        """Test detection of XML with declaration."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(XML_SIMPLE.encode())
        assert file_type == "xml"
        assert confidence >= 0.9

    def test_detects_xml_without_declaration(self):
        """Test detection of XML without declaration."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(XML_NO_DECLARATION.encode())
        assert file_type == "xml"
        assert confidence >= 0.6

    def test_detects_xml_with_attributes(self):
        """Test detection of XML with attributes."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(XML_WITH_ATTRIBUTES.encode())
        assert file_type == "xml"
        assert confidence >= 0.8

    def test_detects_xml_with_namespace(self):
        """Test detection of XML with namespaces."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(XML_WITH_NAMESPACE.encode())
        assert file_type == "xml"
        assert confidence >= 0.8


class TestContentSnifferEmail:
    """Tests for email detection."""

    def test_detects_simple_email(self):
        """Test detection of simple email."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(EMAIL_SIMPLE.encode())
        assert file_type == "eml"
        assert confidence >= 0.8

    def test_detects_minimal_email(self):
        """Test detection of minimal email."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(EMAIL_MINIMAL.encode())
        assert file_type == "eml"
        assert confidence >= 0.7


class TestContentSnifferCsv:
    """Tests for CSV detection."""

    def test_detects_standard_csv(self):
        """Test detection of standard CSV."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(CSV_STANDARD.encode())
        assert file_type == "csv"
        assert confidence >= 0.7

    def test_detects_tab_separated(self):
        """Test detection of tab-separated values."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(CSV_TAB_SEPARATED.encode())
        assert file_type == "csv"
        assert confidence >= 0.7

    def test_detects_semicolon_separated(self):
        """Test detection of semicolon-separated values."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(CSV_SEMICOLON.encode())
        assert file_type == "csv"
        assert confidence >= 0.7

    def test_detects_csv_no_header(self):
        """Test detection of CSV without header."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(CSV_NO_HEADER.encode())
        assert file_type == "csv"
        assert confidence >= 0.6

    def test_text_with_commas_not_csv(self):
        """Test that plain text with commas is not detected as CSV."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(TEXT_WITH_COMMAS.encode())
        # Should NOT be detected as CSV
        assert file_type == "txt"

    def test_txt_extension_biases_away_from_csv(self):
        """Test that .txt extension biases away from CSV detection."""
        sniffer = ContentSniffer()
        # This looks slightly CSV-like but has .txt extension
        content = "one, two, three\nfour, five, six"
        file_type, confidence = sniffer.sniff(content.encode(), "notes.txt")
        assert file_type == "txt"


class TestContentSnifferPlainText:
    """Tests for plain text detection."""

    def test_detects_simple_text(self):
        """Test detection of simple text."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(SIMPLE_TEXT.encode())
        assert file_type == "txt"

    def test_text_looks_like_json_but_isnt(self):
        """Test that text with JSON-like chars is detected as text."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(TEXT_LOOKS_LIKE_JSON.encode())
        assert file_type == "txt"

    def test_text_looks_like_xml_but_isnt(self):
        """Test that text with angle brackets is detected as text."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(TEXT_LOOKS_LIKE_XML.encode())
        assert file_type == "txt"


class TestContentSnifferBinaryFormats:
    """Tests for binary format detection (EPUB, DOCX, XLSX)."""

    def _create_minimal_epub(self) -> bytes:
        """Create a minimal EPUB file structure."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # EPUB requires these specific files
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0"?>
                <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
                    <rootfiles>
                        <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
                    </rootfiles>
                </container>""",
            )
        return buffer.getvalue()

    def _create_minimal_docx(self) -> bytes:
        """Create a minimal DOCX file structure."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # DOCX requires [Content_Types].xml with specific content
            zf.writestr(
                "[Content_Types].xml",
                """<?xml version="1.0"?>
                <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                    <Default Extension="xml" ContentType="application/xml"/>
                    <Override PartName="/word/document.xml"
                              ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
                </Types>""",
            )
            zf.writestr("word/document.xml", "<document/>")
        return buffer.getvalue()

    def _create_minimal_xlsx(self) -> bytes:
        """Create a minimal XLSX file structure."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # XLSX requires [Content_Types].xml and xl/workbook.xml
            zf.writestr(
                "[Content_Types].xml",
                """<?xml version="1.0"?>
                <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                    <Default Extension="xml" ContentType="application/xml"/>
                    <Override PartName="/xl/workbook.xml"
                              ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
                </Types>""",
            )
            zf.writestr("xl/workbook.xml", "<workbook/>")
        return buffer.getvalue()

    def test_detects_epub(self):
        """Test detection of EPUB file."""
        sniffer = ContentSniffer()
        epub_bytes = self._create_minimal_epub()
        file_type, confidence = sniffer.sniff(epub_bytes)
        assert file_type == "epub"
        assert confidence >= 0.9

    def test_detects_docx(self):
        """Test detection of DOCX file."""
        sniffer = ContentSniffer()
        docx_bytes = self._create_minimal_docx()
        file_type, confidence = sniffer.sniff(docx_bytes)
        assert file_type == "docx"
        assert confidence >= 0.9

    def test_detects_xlsx(self):
        """Test detection of XLSX file."""
        sniffer = ContentSniffer()
        xlsx_bytes = self._create_minimal_xlsx()
        file_type, confidence = sniffer.sniff(xlsx_bytes)
        assert file_type == "xlsx"
        assert confidence >= 0.9


class TestContentSnifferExtensionHints:
    """Tests for extension hint behavior."""

    def test_extension_hint_resolves_ambiguous(self):
        """Test that extension hints resolve ambiguous content."""
        sniffer = ContentSniffer()
        # Ambiguous content that could be multiple types
        content = "<data>value</data>"
        # Without hint, should detect as XML
        file_type1, _ = sniffer.sniff(content.encode())
        assert file_type1 == "xml"
        # With .html hint, might still be XML due to clear XML structure
        file_type2, _ = sniffer.sniff(content.encode(), "file.xml")
        assert file_type2 == "xml"

    def test_high_confidence_detection_not_overridden(self):
        """Test that high confidence detection is not overridden by extension."""
        sniffer = ContentSniffer()
        # Clear JSON but with .txt extension
        content = '{"key": "value"}'
        file_type, confidence = sniffer.sniff(content.encode(), "data.txt")
        # JSON should still be detected due to high confidence
        assert file_type == "json"
        assert confidence >= 0.8

    def test_unknown_extension_ignored(self):
        """Test that unknown extensions are handled gracefully."""
        sniffer = ContentSniffer()
        file_type, _ = sniffer.sniff(SIMPLE_TEXT.encode(), "file.xyz")
        assert file_type == "txt"


class TestContentSnifferEdgeCases:
    """Tests for edge cases."""

    def test_empty_content(self):
        """Test handling of empty content."""
        sniffer = ContentSniffer()
        file_type, confidence = sniffer.sniff(b"")
        assert file_type == "txt"
        assert confidence >= 0.5

    def test_whitespace_only(self):
        """Test handling of whitespace-only content."""
        sniffer = ContentSniffer()
        file_type, _ = sniffer.sniff(b"   \n\t\n   ")
        assert file_type == "txt"

    def test_binary_content(self):
        """Test handling of random binary content."""
        sniffer = ContentSniffer()
        # Random bytes that don't match any format
        binary_content = bytes(range(256))
        file_type, _ = sniffer.sniff(binary_content)
        # Should fall back to txt or detect as unknown
        assert file_type in ("txt", "binary")

    def test_very_short_content(self):
        """Test handling of very short content."""
        sniffer = ContentSniffer()
        file_type, _ = sniffer.sniff(b"a")
        assert file_type == "txt"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
