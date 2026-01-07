"""
Email extractor for EML files.

Parses email content using Python's email module and extracts
headers, body content, and attachment information.
"""

import email
from email.message import Message
from email.utils import parsedate_to_datetime
from typing import Any

from .base import BaseExtractor, ExtractionResult


class EmailExtractor(BaseExtractor):
    """Extract content from email (.eml) files.

    Features:
    - Extract From, To, Cc, Subject, Date headers
    - Handle plain text and HTML bodies
    - List attachments in metadata (no content extraction)
    """

    def extract(self, content: bytes, filename: str) -> ExtractionResult:
        """Extract text content from email file bytes.

        Args:
            content: Raw email content as bytes.
            filename: Original filename.

        Returns:
            ExtractionResult with markdown content and metadata.
        """
        # Parse email
        try:
            msg = email.message_from_bytes(content)
        except Exception as e:
            # Fall back to plain text
            text = self._decode_content(content)
            return self._create_fallback_result(text, filename, str(e))

        # Extract headers
        from_addr = self._decode_header(msg.get("From", ""))
        to_addr = self._decode_header(msg.get("To", ""))
        cc_addr = self._decode_header(msg.get("Cc", ""))
        subject = self._decode_header(msg.get("Subject", ""))
        date_str = msg.get("Date", "")

        # Parse date
        date_formatted = self._format_date(date_str)

        # Extract body
        body = self._extract_body(msg)

        # Check for attachments
        attachments = self._get_attachments(msg)
        has_attachments = len(attachments) > 0

        # Build structural metadata
        structural_metadata: dict[str, Any] = {
            "from": from_addr,
            "to": to_addr,
            "subject": subject,
            "date": date_formatted,
            "has_attachments": has_attachments,
        }
        if cc_addr:
            structural_metadata["cc"] = cc_addr
        if attachments:
            structural_metadata["attachments"] = attachments

        # Use subject as title
        title = subject if subject else self._extract_title_from_filename(filename)

        # Generate markdown
        markdown_body = self._generate_markdown(
            subject, from_addr, to_addr, cc_addr, date_formatted, body, attachments
        )
        word_count = self._count_words(markdown_body)

        # Build frontmatter metadata
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "eml",
            "from": from_addr,
            "to": to_addr,
            "subject": subject,
            "date": date_formatted,
            "has_attachments": has_attachments,
        }
        frontmatter = self._generate_frontmatter(frontmatter_metadata)

        # Combine frontmatter and content
        markdown = f"{frontmatter}\n{markdown_body}"

        return ExtractionResult(
            markdown=markdown,
            file_type="eml",
            title=title,
            word_count=word_count,
            structural_metadata=structural_metadata,
            parse_warning=None,
        )

    def _decode_header(self, header: str) -> str:
        """Decode email header value."""
        if not header:
            return ""

        try:
            # Handle encoded headers like =?utf-8?q?...?=
            decoded_parts = email.header.decode_header(header)
            parts = []
            for content, charset in decoded_parts:
                if isinstance(content, bytes):
                    charset = charset or "utf-8"
                    try:
                        parts.append(content.decode(charset))
                    except (UnicodeDecodeError, LookupError):
                        parts.append(content.decode("utf-8", errors="replace"))
                else:
                    parts.append(content)
            return " ".join(parts)
        except Exception:
            return str(header)

    def _format_date(self, date_str: str) -> str:
        """Format email date to ISO format."""
        if not date_str:
            return ""

        try:
            dt = parsedate_to_datetime(date_str)
            return dt.isoformat()
        except Exception:
            return date_str

    def _extract_body(self, msg: Message) -> str:
        """Extract email body, preferring plain text over HTML."""
        if msg.is_multipart():
            # Look for plain text part first
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            return payload.decode(charset)
                        except (UnicodeDecodeError, LookupError):
                            return payload.decode("utf-8", errors="replace")

            # Fall back to HTML
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    continue

                if content_type == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            html = payload.decode(charset)
                        except (UnicodeDecodeError, LookupError):
                            html = payload.decode("utf-8", errors="replace")
                        return self._html_to_text(html)

            return ""
        else:
            # Single part message
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                content_type = msg.get_content_type()

                try:
                    text = payload.decode(charset)
                except (UnicodeDecodeError, LookupError):
                    text = payload.decode("utf-8", errors="replace")

                if content_type == "text/html":
                    return self._html_to_text(text)
                return text

            # If payload is not bytes (already decoded)
            payload = msg.get_payload()
            if isinstance(payload, str):
                return payload

            return ""

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text (simple extraction)."""
        # Simple HTML to text conversion
        import re

        # Remove script and style elements
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

        # Replace common tags
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "", text, flags=re.IGNORECASE)

        # Remove remaining tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities
        import html as html_module

        text = html_module.unescape(text)

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(line for line in lines if line)

        return text

    def _get_attachments(self, msg: Message) -> list[str]:
        """Get list of attachment filenames."""
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        attachments.append(self._decode_header(filename))

        return attachments

    def _generate_markdown(
        self,
        subject: str,
        from_addr: str,
        to_addr: str,
        cc_addr: str,
        date_formatted: str,
        body: str,
        attachments: list[str],
    ) -> str:
        """Generate markdown from email content."""
        lines = []

        # Title (subject)
        lines.append(f"# {subject or 'No Subject'}")
        lines.append("")

        # Headers
        lines.append(f"**From:** {from_addr}")
        lines.append(f"**To:** {to_addr}")
        if cc_addr:
            lines.append(f"**Cc:** {cc_addr}")
        if date_formatted:
            lines.append(f"**Date:** {date_formatted}")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Body
        lines.append(body)

        # Attachments
        if attachments:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("**Attachments:**")
            for att in attachments:
                lines.append(f"- {att}")

        return "\n".join(lines)

    def _create_fallback_result(self, text: str, filename: str, error: str) -> ExtractionResult:
        """Create fallback result when email parsing fails."""
        title = self._extract_title_from_filename(filename)
        word_count = self._count_words(text)
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "eml",
            "parse_warning": f"Email parsing failed: {error}",
        }
        frontmatter = self._generate_frontmatter(frontmatter_metadata)
        markdown = f"{frontmatter}\n{text}"

        return ExtractionResult(
            markdown=markdown,
            file_type="eml",
            title=title,
            word_count=word_count,
            structural_metadata={},
            parse_warning=f"Email parsing failed: {error}",
        )
