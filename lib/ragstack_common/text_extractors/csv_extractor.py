"""
CSV extractor with smart extraction.

Detects delimiters, infers column types, and generates descriptive
markdown with schema summaries and sample data.
"""

import csv
import io
import re

from .base import BaseExtractor, ExtractionResult


class CsvExtractor(BaseExtractor):
    """Extract content from CSV files with smart analysis.

    Features:
    - Automatic delimiter detection (comma, tab, semicolon, pipe)
    - Column type inference (text, numeric, date)
    - Sample value extraction
    - Markdown table generation
    """

    def extract(self, content: bytes, filename: str) -> ExtractionResult:
        """Extract text content from CSV file bytes.

        Args:
            content: Raw CSV content as bytes.
            filename: Original filename.

        Returns:
            ExtractionResult with markdown content and metadata.
        """
        # Decode content
        text = self._decode_content(content)
        title = self._extract_title_from_filename(filename)

        # Handle empty file
        if not text.strip():
            return self._create_empty_result(filename, title)

        # Detect delimiter
        delimiter = self._detect_delimiter(text)
        if not delimiter:
            delimiter = ","  # Default fallback

        # Parse CSV
        try:
            rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        except csv.Error as e:
            # Fall back to plain text with warning
            return self._create_fallback_result(text, filename, title, str(e))

        if not rows:
            return self._create_empty_result(filename, title)

        # Determine if first row is header
        has_header = self._detect_header(rows)

        if has_header:
            headers = rows[0]
            data_rows = rows[1:]
        else:
            # Generate column names
            headers = [f"Column{i + 1}" for i in range(len(rows[0]))]
            data_rows = rows

        # Infer column types
        column_types = self._infer_column_types(data_rows, headers)

        # Get sample values for each column
        sample_values = self._get_sample_values(data_rows, headers)

        # Build structural metadata
        structural_metadata = {
            "row_count": len(data_rows),
            "column_count": len(headers),
            "columns": headers,
            "delimiter": delimiter,
            "has_header": has_header,
            "column_types": column_types,
        }

        # Generate markdown
        markdown_body = self._generate_markdown(
            filename, headers, column_types, sample_values, data_rows, len(data_rows)
        )

        word_count = self._count_words(markdown_body)

        # Build frontmatter metadata
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "csv",
            "rows": len(data_rows),
            "columns": headers,
            "delimiter": repr(delimiter),
        }
        frontmatter = self._generate_frontmatter(frontmatter_metadata)

        # Combine frontmatter and content
        markdown = f"{frontmatter}\n{markdown_body}"

        return ExtractionResult(
            markdown=markdown,
            file_type="csv",
            title=title,
            word_count=word_count,
            structural_metadata=structural_metadata,
            parse_warning=None,
        )

    def _detect_delimiter(self, text: str) -> str | None:
        """Detect CSV delimiter from content."""
        lines = text.strip().split("\n")[:5]
        if not lines:
            return None

        delimiters = [",", "\t", ";", "|"]
        best_delimiter = None
        best_count = 0

        for delim in delimiters:
            counts = [line.count(delim) for line in lines if line.strip()]
            if counts and min(counts) > 0:
                # All lines have at least one occurrence
                avg_count = sum(counts) / len(counts)
                # Check consistency - allow slight variation
                is_consistent = max(counts) - min(counts) <= 1
                if is_consistent and avg_count > best_count:
                    best_count = avg_count
                    best_delimiter = delim

        return best_delimiter

    def _detect_header(self, rows: list[list[str]]) -> bool:
        """Detect if first row is a header row."""
        if len(rows) < 2:
            return True  # Assume header for single row

        first_row = rows[0]
        second_row = rows[1]

        # Header heuristics:
        # 1. Header cells are typically shorter
        # 2. Header cells don't contain numbers (usually)
        # 3. Header cells don't start with spaces

        header_score = 0

        for i, cell in enumerate(first_row):
            if not cell:
                continue
            # Shorter than data
            if i < len(second_row) and len(cell) < len(second_row[i]):
                header_score += 1
            # No leading spaces
            if not cell.startswith(" "):
                header_score += 1
            # Not a number
            if not re.match(r"^-?\d+\.?\d*$", cell.strip()):
                header_score += 1

        # If most indicators suggest header
        return header_score >= len(first_row)

    def _infer_column_types(self, data_rows: list[list[str]], headers: list[str]) -> dict[str, str]:
        """Infer column types from data."""
        types = {}
        for i, header in enumerate(headers):
            values = [row[i] for row in data_rows if i < len(row) and row[i].strip()][:20]
            types[header] = self._infer_type(values)
        return types

    def _infer_type(self, values: list[str]) -> str:
        """Infer type from a list of values."""
        if not values:
            return "text"

        numeric_count = 0
        date_count = 0

        for v in values:
            v = v.strip()
            # Check numeric
            if re.match(r"^-?\d+\.?\d*$", v):
                numeric_count += 1
            # Check date patterns
            elif re.match(r"^\d{4}-\d{2}-\d{2}", v) or re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", v):
                date_count += 1

        # If majority are numeric
        if numeric_count > len(values) * 0.7:
            return "numeric"
        if date_count > len(values) * 0.7:
            return "date"
        return "text"

    def _get_sample_values(
        self, data_rows: list[list[str]], headers: list[str]
    ) -> dict[str, list[str]]:
        """Get sample values for each column."""
        samples: dict[str, list[str]] = {}
        for i, header in enumerate(headers):
            values = []
            seen: set[str] = set()
            for row in data_rows:
                if i < len(row) and row[i].strip() and row[i] not in seen:
                    values.append(row[i])
                    seen.add(row[i])
                if len(values) >= 3:
                    break
            samples[header] = values
        return samples

    def _generate_markdown(
        self,
        filename: str,
        headers: list[str],
        column_types: dict[str, str],
        sample_values: dict[str, list[str]],
        data_rows: list[list[str]],
        row_count: int,
    ) -> str:
        """Generate descriptive markdown from CSV data."""
        lines = []

        # Title
        lines.append(f"# Data: {filename}")
        lines.append("")
        lines.append(f"This dataset contains {row_count} records with {len(headers)} columns.")
        lines.append("")

        # Column descriptions
        lines.append("## Columns")
        lines.append("")
        for header in headers:
            col_type = column_types.get(header, "text")
            samples = sample_values.get(header, [])
            sample_str = ", ".join(f'"{s}"' for s in samples[:3]) if samples else ""
            if sample_str:
                lines.append(f"- **{header}**: {col_type.capitalize()} (e.g., {sample_str})")
            else:
                lines.append(f"- **{header}**: {col_type.capitalize()} values")
        lines.append("")

        # Sample data table
        lines.append("## Sample Records")
        lines.append("")

        # Table header
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Table rows (first 5)
        for row in data_rows[:5]:
            # Pad row if needed
            padded_row = row + [""] * (len(headers) - len(row))
            cells = []
            for cell in padded_row[: len(headers)]:
                cells.append(cell[:50] + "..." if len(cell) > 50 else cell)
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    def _create_empty_result(self, filename: str, title: str) -> ExtractionResult:
        """Create result for empty CSV file."""
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "csv",
            "rows": 0,
            "columns": [],
        }
        frontmatter = self._generate_frontmatter(frontmatter_metadata)
        markdown = f"{frontmatter}\n# Empty CSV: {filename}\n\nThis CSV file is empty."

        return ExtractionResult(
            markdown=markdown,
            file_type="csv",
            title=title,
            word_count=0,
            structural_metadata={"row_count": 0, "column_count": 0},
            parse_warning="Empty file",
        )

    def _create_fallback_result(
        self, text: str, filename: str, title: str, error: str
    ) -> ExtractionResult:
        """Create fallback result when CSV parsing fails."""
        word_count = self._count_words(text)
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "csv",
            "parse_warning": f"CSV parsing failed: {error}",
        }
        frontmatter = self._generate_frontmatter(frontmatter_metadata)
        markdown = f"{frontmatter}\n{text}"

        return ExtractionResult(
            markdown=markdown,
            file_type="csv",
            title=title,
            word_count=word_count,
            structural_metadata={},
            parse_warning=f"CSV parsing failed: {error}",
        )
