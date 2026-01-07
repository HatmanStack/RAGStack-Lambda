"""Unit tests for XML extractor."""

import pytest

from ragstack_common.text_extractors.xml_extractor import XmlExtractor
from ragstack_common.text_extractors.base import ExtractionResult
from tests.fixtures.text_extractor_samples import (
    XML_SIMPLE,
    XML_NO_DECLARATION,
    XML_WITH_ATTRIBUTES,
    XML_WITH_NAMESPACE,
    XML_COMPLEX,
    XML_EMPTY_ROOT,
    XML_MALFORMED,
)


class TestXmlExtractor:
    """Tests for XmlExtractor."""

    def test_extracts_simple_xml(self):
        """Test extraction of simple XML."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_SIMPLE.encode(), "data.xml")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "xml"
        assert "root" in result.markdown.lower()

    def test_extracts_xml_no_declaration(self):
        """Test extraction of XML without declaration."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_NO_DECLARATION.encode(), "data.xml")

        assert result.file_type == "xml"
        assert "root" in result.markdown.lower()

    def test_extracts_xml_with_attributes(self):
        """Test extraction of XML with attributes."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_WITH_ATTRIBUTES.encode(), "catalog.xml")

        assert result.file_type == "xml"
        assert "product" in result.markdown.lower()

    def test_extracts_xml_with_namespace(self):
        """Test extraction of XML with namespaces."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_WITH_NAMESPACE.encode(), "data.xml")

        assert result.file_type == "xml"
        # Should include namespace info
        assert "namespace" in result.markdown.lower() or "xmlns" in result.structural_metadata.get("namespaces", [])

    def test_extracts_complex_xml(self):
        """Test extraction of complex XML structure."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_COMPLEX.encode(), "bookstore.xml")

        assert result.file_type == "xml"
        assert "bookstore" in result.markdown.lower() or "book" in result.markdown.lower()

    def test_handles_empty_root(self):
        """Test handling of XML with empty root element."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_EMPTY_ROOT.encode(), "empty.xml")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "xml"

    def test_malformed_xml_falls_back(self):
        """Test that malformed XML falls back with warning."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_MALFORMED.encode(), "broken.xml")

        assert isinstance(result, ExtractionResult)
        assert result.parse_warning is not None

    def test_generates_frontmatter(self):
        """Test that frontmatter is generated correctly."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_SIMPLE.encode(), "config.xml")

        assert result.markdown.startswith("---\n")
        assert "source_file: config.xml" in result.markdown
        assert "file_type: xml" in result.markdown

    def test_structural_metadata_includes_root_element(self):
        """Test structural metadata includes root element name."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_SIMPLE.encode(), "data.xml")

        assert "root_element" in result.structural_metadata
        assert result.structural_metadata["root_element"] == "root"

    def test_structural_metadata_includes_element_count(self):
        """Test structural metadata includes element count."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_WITH_ATTRIBUTES.encode(), "catalog.xml")

        assert "element_count" in result.structural_metadata
        assert result.structural_metadata["element_count"] > 0

    def test_unique_elements_listed(self):
        """Test that unique element names are listed."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_COMPLEX.encode(), "bookstore.xml")

        assert "unique_elements" in result.structural_metadata
        assert len(result.structural_metadata["unique_elements"]) > 0

    def test_title_extracted_from_filename(self):
        """Test title is extracted from filename."""
        extractor = XmlExtractor()
        result = extractor.extract(XML_SIMPLE.encode(), "application_config.xml")

        assert result.title == "application_config"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
