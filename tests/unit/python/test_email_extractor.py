"""Unit tests for email extractor."""

import pytest

from ragstack_common.text_extractors.email_extractor import EmailExtractor
from ragstack_common.text_extractors.base import ExtractionResult
from tests.fixtures.text_extractor_samples import (
    EMAIL_SIMPLE,
    EMAIL_WITH_CC,
    EMAIL_MULTIPART,
    EMAIL_HTML_ONLY,
    EMAIL_WITH_ATTACHMENT,
    EMAIL_MINIMAL,
    EMAIL_MALFORMED,
)


class TestEmailExtractor:
    """Tests for EmailExtractor."""

    def test_extracts_simple_email(self):
        """Test extraction of simple plain text email."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_SIMPLE.encode(), "message.eml")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "eml"
        assert "sender@example.com" in result.markdown
        assert "recipient@example.com" in result.markdown

    def test_extracts_subject(self):
        """Test extraction of email subject."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_SIMPLE.encode(), "message.eml")

        assert "Test Email" in result.markdown
        assert result.structural_metadata.get("subject") == "Test Email"

    def test_extracts_from_to_headers(self):
        """Test extraction of From and To headers."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_SIMPLE.encode(), "message.eml")

        assert result.structural_metadata.get("from") == "sender@example.com"
        assert result.structural_metadata.get("to") == "recipient@example.com"

    def test_extracts_email_with_cc(self):
        """Test extraction of email with CC header."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_WITH_CC.encode(), "meeting.eml")

        assert result.file_type == "eml"
        assert "cc1@example.com" in result.markdown or "cc" in result.structural_metadata

    def test_extracts_multipart_email(self):
        """Test extraction of multipart email prefers plain text."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_MULTIPART.encode(), "multipart.eml")

        assert result.file_type == "eml"
        # Should contain the plain text part
        assert "plain text version" in result.markdown.lower()

    def test_extracts_html_only_email(self):
        """Test extraction of HTML-only email."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_HTML_ONLY.encode(), "html.eml")

        assert result.file_type == "eml"
        # Should extract content from HTML
        assert "Welcome" in result.markdown

    def test_handles_email_with_attachment(self):
        """Test handling of email with attachment."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_WITH_ATTACHMENT.encode(), "attachment.eml")

        assert result.file_type == "eml"
        assert result.structural_metadata.get("has_attachments") is True

    def test_extracts_minimal_email(self):
        """Test extraction of minimal email."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_MINIMAL.encode(), "minimal.eml")

        assert result.file_type == "eml"
        assert result.structural_metadata.get("subject") == "Min"

    def test_malformed_email_falls_back(self):
        """Test that malformed email falls back with warning."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_MALFORMED.encode(), "broken.eml")

        assert isinstance(result, ExtractionResult)
        # Should still produce output, possibly as plain text

    def test_generates_frontmatter(self):
        """Test that frontmatter is generated correctly."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_SIMPLE.encode(), "message.eml")

        assert result.markdown.startswith("---\n")
        assert "source_file: message.eml" in result.markdown
        assert "file_type: eml" in result.markdown

    def test_structural_metadata_includes_headers(self):
        """Test structural metadata includes email headers."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_SIMPLE.encode(), "message.eml")

        assert "from" in result.structural_metadata
        assert "to" in result.structural_metadata
        assert "subject" in result.structural_metadata

    def test_body_content_preserved(self):
        """Test that email body content is preserved."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_SIMPLE.encode(), "message.eml")

        assert "plain text body" in result.markdown.lower()

    def test_title_is_subject(self):
        """Test that title is set to email subject."""
        extractor = EmailExtractor()
        result = extractor.extract(EMAIL_SIMPLE.encode(), "message.eml")

        assert result.title == "Test Email"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
