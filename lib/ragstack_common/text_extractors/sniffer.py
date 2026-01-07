"""
Content-based file type detection with extension hints.

Implements file type detection based on content examination,
with file extension used as a hint for ambiguous cases.
"""

import csv
import io
import json
import re
import zipfile
from pathlib import Path


class ContentSniffer:
    """Detect file type from content with extension hints.

    Detection priority:
    1. Binary format signatures (EPUB, DOCX, XLSX are ZIP-based)
    2. Text content patterns (HTML tags, JSON structure, email headers)
    3. Extension hint for tie-breaking
    4. Fallback to plain text
    """

    # Extension to file type mapping
    EXTENSION_MAP = {
        ".html": "html",
        ".htm": "html",
        ".json": "json",
        ".xml": "xml",
        ".csv": "csv",
        ".tsv": "csv",
        ".txt": "txt",
        ".eml": "eml",
        ".epub": "epub",
        ".docx": "docx",
        ".xlsx": "xlsx",
    }

    def sniff(self, content: bytes, filename: str | None = None) -> tuple[str, float]:
        """Detect file type from content.

        Args:
            content: File content as bytes.
            filename: Optional filename for extension hint.

        Returns:
            Tuple of (file_type, confidence) where confidence is 0.0-1.0.
        """
        if not content:
            return ("txt", 0.5)

        # Get extension hint
        extension_hint = None
        if filename:
            ext = Path(filename).suffix.lower()
            extension_hint = self.EXTENSION_MAP.get(ext)

        # Check binary formats first (ZIP-based)
        if self._is_zip(content):
            zip_type = self._detect_zip_type(content)
            if zip_type:
                return zip_type

        # Try to decode as text for text-based detection
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
            except UnicodeDecodeError:
                # Can't decode as text, treat as binary
                return ("binary", 0.5)

        # Check text-based formats in priority order

        # HTML detection (high priority due to clear markers)
        html_confidence = self._check_html(text)
        if html_confidence >= 0.8:
            return ("html", html_confidence)

        # XML detection (check before JSON since XML has clearer markers)
        xml_confidence = self._check_xml(text)
        if xml_confidence >= 0.8:
            return ("xml", xml_confidence)

        # JSON detection
        json_confidence = self._check_json(text)
        if json_confidence >= 0.8:
            return ("json", json_confidence)

        # Email detection
        eml_confidence = self._check_email(text)
        if eml_confidence >= 0.7:
            return ("eml", eml_confidence)

        # CSV detection (strict to avoid false positives)
        # Skip CSV check if extension hint is .txt
        if extension_hint != "txt":
            csv_confidence = self._check_csv(text)
            if csv_confidence >= 0.7:
                return ("csv", csv_confidence)

        # Lower confidence matches with extension hints

        # HTML with medium confidence (fragments without html/head/body)
        if html_confidence >= 0.5:
            # Boost confidence if extension hint matches
            if extension_hint == "html":
                return ("html", max(html_confidence, 0.7))
            return ("html", html_confidence)
        if html_confidence >= 0.4 and extension_hint == "html":
            return ("html", max(html_confidence + 0.3, 0.7))

        # XML with medium confidence or extension hint
        if xml_confidence >= 0.6:
            return ("xml", xml_confidence)
        if xml_confidence >= 0.4 and extension_hint == "xml":
            return ("xml", max(xml_confidence + 0.3, 0.7))

        # JSON with medium confidence
        if json_confidence >= 0.5:
            return ("json", json_confidence)

        # CSV with extension hint
        if extension_hint == "csv":
            csv_confidence = self._check_csv(text)
            if csv_confidence >= 0.5:
                return ("csv", csv_confidence)

        # Use extension hint for supported types
        if extension_hint and extension_hint != "txt":
            return (extension_hint, 0.6)

        # Default to plain text
        return ("txt", 0.7)

    def _is_zip(self, content: bytes) -> bool:
        """Check if content is a ZIP file."""
        return content[:4] == b"PK\x03\x04"

    def _detect_zip_type(self, content: bytes) -> tuple[str, float] | None:
        """Detect specific ZIP-based format (EPUB, DOCX, XLSX)."""
        try:
            with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
                names = zf.namelist()

                # EPUB: has META-INF/container.xml
                if "META-INF/container.xml" in names:
                    return ("epub", 0.95)

                # Check [Content_Types].xml for Office formats
                if "[Content_Types].xml" in names:
                    try:
                        content_types = zf.read("[Content_Types].xml").decode("utf-8")

                        # XLSX: references spreadsheetml
                        if "spreadsheetml" in content_types or "xl/workbook.xml" in content_types:
                            return ("xlsx", 0.95)

                        # DOCX: references wordprocessingml
                        is_docx = "wordprocessingml" in content_types
                        is_docx = is_docx or "word/document.xml" in content_types
                        if is_docx:
                            return ("docx", 0.95)
                    except (KeyError, UnicodeDecodeError):
                        pass

                # Check for xl/ directory (XLSX)
                if any(n.startswith("xl/") for n in names):
                    return ("xlsx", 0.9)

                # Check for word/ directory (DOCX)
                if any(n.startswith("word/") for n in names):
                    return ("docx", 0.9)

        except (zipfile.BadZipFile, OSError):
            pass

        return None

    def _check_html(self, text: str) -> float:
        """Check if text is HTML and return confidence."""
        text_lower = text.strip().lower()

        # Strong indicators
        if text_lower.startswith("<!doctype html"):
            return 0.95
        if "<html" in text_lower and "</html>" in text_lower:
            return 0.9
        if "<html" in text_lower:
            return 0.85

        # Medium indicators
        has_head = "<head" in text_lower
        has_body = "<body" in text_lower
        if has_head and has_body:
            return 0.8
        if has_head or has_body:
            return 0.7

        # Check for HTML-specific elements (with closing tags for higher confidence)
        html_tags = [
            "div",
            "p",
            "span",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "table",
            "ul",
            "ol",
            "li",
            "a",
            "img",
        ]
        opening_tags = sum(1 for tag in html_tags if f"<{tag}" in text_lower)
        closing_tags = sum(1 for tag in html_tags if f"</{tag}>" in text_lower)

        if opening_tags >= 2 and closing_tags >= 2:
            return 0.6
        if opening_tags >= 2 and closing_tags >= 1:
            return 0.5
        if opening_tags >= 1:
            return 0.4

        return 0.0

    def _check_xml(self, text: str) -> float:
        """Check if text is XML and return confidence."""
        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        # Strong indicator: XML declaration
        if text_stripped.startswith("<?xml"):
            return 0.95

        # Check for namespace declarations
        if "xmlns" in text_stripped and "<" in text_stripped:
            return 0.85

        # HTML-specific tags that indicate this is HTML, not generic XML
        html_specific = ["<!doctype", "<html", "<head", "<body", "<div", "<span", "<p>", "</p>"]
        if any(tag in text_lower for tag in html_specific):
            return 0.0

        # Try to find XML-like structure
        # Look for opening tag at the start
        match = re.match(r"^\s*<([a-zA-Z][a-zA-Z0-9_:-]*)", text_stripped)
        if match:
            root_tag = match.group(1)
            # Check for matching closing tag at the end
            close_pattern = f"</{root_tag}>\\s*$"
            if re.search(close_pattern, text_stripped):
                return 0.7
            # Check for self-closing
            if re.search(r"/>\s*$", text_stripped):
                return 0.65

        # Check for multiple balanced tags (even without clear root)
        opening_tags = re.findall(r"<([a-zA-Z][a-zA-Z0-9_:-]*)[^>]*>", text_stripped)
        closing_tags = re.findall(r"</([a-zA-Z][a-zA-Z0-9_:-]*)>", text_stripped)
        if len(opening_tags) >= 2 and len(closing_tags) >= 2:
            # Make sure most tags are balanced
            opening_set = set(opening_tags)
            closing_set = set(closing_tags)
            if opening_set & closing_set:  # At least some overlap
                return 0.6

        return 0.0

    def _check_json(self, text: str) -> float:
        """Check if text is JSON and return confidence."""
        text_stripped = text.strip()

        if not text_stripped:
            return 0.0

        # Must start with { or [
        if text_stripped[0] not in "{[":
            return 0.0

        # Try to parse as JSON
        try:
            json.loads(text_stripped)
            return 0.9
        except json.JSONDecodeError:
            # Might be partial or malformed JSON
            # Check for JSON-like structure
            if text_stripped[0] == "{" and ":" in text_stripped:
                return 0.3
            if text_stripped[0] == "[":
                return 0.2
            return 0.0

    def _check_email(self, text: str) -> float:
        """Check if text is an email and return confidence."""
        lines = text.split("\n")

        # Email headers typically at the start
        header_count = 0
        required_headers = 0

        for line in lines[:20]:  # Check first 20 lines
            line_stripped = line.strip()
            if not line_stripped:
                break  # Empty line marks end of headers

            # Check for header patterns
            is_required = (
                re.match(r"^From:\s*", line_stripped, re.IGNORECASE)
                or re.match(r"^To:\s*", line_stripped, re.IGNORECASE)
                or re.match(r"^Subject:\s*", line_stripped, re.IGNORECASE)
            )
            is_other = (
                re.match(r"^Date:\s*", line_stripped, re.IGNORECASE)
                or re.match(r"^Cc:\s*", line_stripped, re.IGNORECASE)
                or re.match(r"^Bcc:\s*", line_stripped, re.IGNORECASE)
                or re.match(r"^Reply-To:\s*", line_stripped, re.IGNORECASE)
                or re.match(r"^Message-ID:\s*", line_stripped, re.IGNORECASE)
                or re.match(r"^MIME-Version:\s*", line_stripped, re.IGNORECASE)
                or re.match(r"^Content-Type:\s*", line_stripped, re.IGNORECASE)
            )
            if is_required:
                header_count += 1
                required_headers += 1
            elif is_other:
                header_count += 1

        # Need at least From + To or From + Subject
        if required_headers >= 2 and header_count >= 3:
            return 0.9
        if required_headers >= 2:
            return 0.8
        if header_count >= 2:
            return 0.6

        return 0.0

    def _check_csv(self, text: str) -> float:
        """Check if text is CSV and return confidence.

        Uses strict heuristics to avoid false positives:
        - At least 2 columns
        - Consistent column count across 3+ lines
        - Header row should have shorter, space-free values
        """
        lines = [line for line in text.strip().split("\n") if line.strip()]

        if len(lines) < 2:
            return 0.0

        # Try to detect delimiter
        delimiter = self._detect_delimiter(text)
        if not delimiter:
            return 0.0

        try:
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = list(reader)
        except csv.Error:
            return 0.0

        if len(rows) < 2:
            return 0.0

        # Check column count consistency
        col_counts = [len(row) for row in rows if row]
        if not col_counts:
            return 0.0

        first_col_count = col_counts[0]

        # Need at least 2 columns
        if first_col_count < 2:
            return 0.0

        # Check consistency (allow for minor variations)
        consistent_rows = sum(1 for c in col_counts if c == first_col_count)
        consistency_ratio = consistent_rows / len(col_counts)

        if consistency_ratio < 0.8:
            return 0.0

        # Need at least 3 lines for confident detection
        if len(rows) < 3:
            return 0.5

        # Check if first row looks like a header (shorter values, no spaces typically)
        if rows[0]:
            header_looks_good = all(
                len(cell) < 50 and not cell.startswith(" ") for cell in rows[0] if cell
            )
            if header_looks_good:
                return 0.85

        return 0.7

    def _detect_delimiter(self, text: str) -> str | None:
        """Detect CSV delimiter."""
        lines = text.strip().split("\n")[:5]  # Check first 5 lines
        if not lines:
            return None

        # Count potential delimiters
        delimiters = [",", "\t", ";", "|"]
        delimiter_counts = {}

        for delim in delimiters:
            counts = [line.count(delim) for line in lines if line.strip()]
            # All lines have at least one occurrence and consistent count
            if counts and min(counts) > 0 and max(counts) == min(counts):
                delimiter_counts[delim] = min(counts)

        if not delimiter_counts:
            return None

        # Return delimiter with highest consistent count
        return max(delimiter_counts.keys(), key=lambda d: delimiter_counts[d])
