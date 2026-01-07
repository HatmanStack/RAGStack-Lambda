"""Unit tests for CSV extractor."""

import pytest

from ragstack_common.text_extractors.csv_extractor import CsvExtractor
from ragstack_common.text_extractors.base import ExtractionResult
from tests.fixtures.text_extractor_samples import (
    CSV_STANDARD,
    CSV_TAB_SEPARATED,
    CSV_SEMICOLON,
    CSV_NO_HEADER,
    CSV_QUOTED_FIELDS,
    CSV_NUMERIC,
    CSV_MALFORMED,
    CSV_SINGLE_COLUMN,
    CSV_EMPTY,
)


class TestCsvExtractor:
    """Tests for CsvExtractor."""

    def test_extracts_standard_csv(self):
        """Test extraction of standard comma-separated CSV."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_STANDARD.encode(), "data.csv")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "csv"
        assert "name" in result.markdown.lower()
        assert "age" in result.markdown.lower()

    def test_extracts_tab_separated(self):
        """Test extraction of tab-separated values."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_TAB_SEPARATED.encode(), "data.tsv")

        assert result.file_type == "csv"
        assert "name" in result.markdown.lower()

    def test_extracts_semicolon_separated(self):
        """Test extraction of semicolon-separated values."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_SEMICOLON.encode(), "data.csv")

        assert result.file_type == "csv"
        assert "name" in result.markdown.lower()

    def test_handles_csv_no_header(self):
        """Test handling of CSV without header row."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_NO_HEADER.encode(), "data.csv")

        assert result.file_type == "csv"
        # Should generate column names like Column1, Column2
        assert "Column" in result.markdown or "column" in result.markdown.lower()

    def test_handles_quoted_fields(self):
        """Test handling of CSV with quoted fields containing delimiters."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_QUOTED_FIELDS.encode(), "data.csv")

        assert result.file_type == "csv"
        # Should correctly parse "Smith, John" as a single field
        assert "Smith" in result.markdown

    def test_detects_numeric_columns(self):
        """Test detection of numeric column types."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_NUMERIC.encode(), "data.csv")

        # Structural metadata should indicate column types
        assert "columns" in result.structural_metadata or "column_count" in result.structural_metadata

    def test_generates_frontmatter(self):
        """Test that frontmatter is generated correctly."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_STANDARD.encode(), "sales.csv")

        assert result.markdown.startswith("---\n")
        assert "source_file: sales.csv" in result.markdown
        assert "file_type: csv" in result.markdown

    def test_structural_metadata_includes_counts(self):
        """Test that structural metadata includes row and column counts."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_STANDARD.encode(), "data.csv")

        assert "row_count" in result.structural_metadata
        assert "column_count" in result.structural_metadata
        assert result.structural_metadata["row_count"] == 5  # 5 data rows
        assert result.structural_metadata["column_count"] == 4  # name, age, city, email

    def test_generates_sample_rows_table(self):
        """Test that sample rows are included as markdown table."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_STANDARD.encode(), "data.csv")

        # Should have markdown table markers
        assert "|" in result.markdown
        assert "---" in result.markdown

    def test_malformed_csv_falls_back_to_text(self):
        """Test that malformed CSV falls back to plain text with warning."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_MALFORMED.encode(), "broken.csv")

        # Should still produce output, possibly with warning
        assert isinstance(result, ExtractionResult)
        # May have a parse warning
        # The file type might be 'csv' with a warning or 'txt'

    def test_single_column_csv(self):
        """Test handling of single-column CSV."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_SINGLE_COLUMN.encode(), "single.csv")

        # Single column is technically valid
        assert isinstance(result, ExtractionResult)

    def test_empty_csv(self):
        """Test handling of empty CSV file."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_EMPTY.encode(), "empty.csv")

        assert isinstance(result, ExtractionResult)
        # Empty file should produce minimal output

    def test_columns_listed_in_output(self):
        """Test that column names are listed in the markdown output."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_STANDARD.encode(), "data.csv")

        # Should describe columns
        assert "name" in result.markdown.lower()
        assert "email" in result.markdown.lower()

    def test_delimiter_detected_in_metadata(self):
        """Test that detected delimiter is recorded in metadata."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_TAB_SEPARATED.encode(), "data.tsv")

        assert "delimiter" in result.structural_metadata
        assert result.structural_metadata["delimiter"] == "\t"

    def test_title_extracted_from_filename(self):
        """Test title is extracted from filename."""
        extractor = CsvExtractor()
        result = extractor.extract(CSV_STANDARD.encode(), "sales_data_2024.csv")

        assert result.title == "sales_data_2024"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
