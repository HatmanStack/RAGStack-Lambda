"""Unit tests for XLSX extractor."""

import io
from datetime import datetime

import pytest

try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None

from ragstack_common.text_extractors.base import ExtractionResult
from ragstack_common.text_extractors.xlsx_extractor import XlsxExtractor


def create_minimal_xlsx(
    sheets: dict[str, list[list]] | None = None,
) -> bytes:
    """Create a minimal XLSX file for testing.

    Args:
        sheets: Dict of sheet_name -> list of rows (each row is list of cell values)
    """
    if Workbook is None:
        pytest.skip("openpyxl not installed")

    wb = Workbook()

    if sheets:
        # Remove default sheet
        default_sheet = wb.active
        wb.remove(default_sheet)

        for sheet_name, rows in sheets.items():
            ws = wb.create_sheet(title=sheet_name)
            for row in rows:
                ws.append(row)
    else:
        # Default content
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["Name", "Age", "City"])
        ws.append(["Alice", 30, "New York"])
        ws.append(["Bob", 25, "Los Angeles"])

    # Write to bytes
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def single_sheet_xlsx() -> bytes:
    """Fixture for XLSX with single sheet."""
    return create_minimal_xlsx()


@pytest.fixture
def multi_sheet_xlsx() -> bytes:
    """Fixture for XLSX with multiple sheets."""
    return create_minimal_xlsx(
        sheets={
            "Sales": [
                ["Date", "Amount", "Product"],
                ["2024-01-01", 100, "Widget A"],
                ["2024-01-02", 200, "Widget B"],
            ],
            "Inventory": [
                ["Product", "Quantity", "Price"],
                ["Widget A", 50, 9.99],
                ["Widget B", 75, 14.99],
            ],
        }
    )


@pytest.fixture
def xlsx_with_types() -> bytes:
    """Fixture for XLSX with various cell types."""
    return create_minimal_xlsx(
        sheets={
            "Data": [
                ["String", "Number", "Date", "Boolean"],
                # Excel doesn't support timezone-aware datetimes
                ["Hello", 42, datetime(2024, 1, 15), True],  # noqa: DTZ001
                ["World", 3.14, datetime(2024, 6, 30), False],  # noqa: DTZ001
            ],
        }
    )


@pytest.fixture
def corrupted_xlsx() -> bytes:
    """Fixture for corrupted XLSX."""
    return b"not a valid xlsx file"


class TestXlsxExtractor:
    """Tests for XlsxExtractor."""

    def test_extracts_single_sheet(self, single_sheet_xlsx):
        """Test extraction of XLSX with single sheet."""
        extractor = XlsxExtractor()
        result = extractor.extract(single_sheet_xlsx, "data.xlsx")

        assert isinstance(result, ExtractionResult)
        assert result.file_type == "xlsx"

    def test_extracts_multi_sheet(self, multi_sheet_xlsx):
        """Test extraction of XLSX with multiple sheets."""
        extractor = XlsxExtractor()
        result = extractor.extract(multi_sheet_xlsx, "workbook.xlsx")

        assert result.file_type == "xlsx"
        assert "Sales" in result.markdown
        assert "Inventory" in result.markdown

    def test_extracts_cell_data(self, single_sheet_xlsx):
        """Test extraction of cell data."""
        extractor = XlsxExtractor()
        result = extractor.extract(single_sheet_xlsx, "data.xlsx")

        assert "Alice" in result.markdown
        assert "Bob" in result.markdown
        assert "New York" in result.markdown

    def test_handles_various_cell_types(self, xlsx_with_types):
        """Test handling of various cell types."""
        extractor = XlsxExtractor()
        result = extractor.extract(xlsx_with_types, "types.xlsx")

        assert "Hello" in result.markdown
        assert "42" in result.markdown

    def test_generates_frontmatter(self, single_sheet_xlsx):
        """Test that frontmatter is generated correctly."""
        extractor = XlsxExtractor()
        result = extractor.extract(single_sheet_xlsx, "workbook.xlsx")

        assert result.markdown.startswith("---\n")
        assert "source_file: workbook.xlsx" in result.markdown
        assert "file_type: xlsx" in result.markdown

    def test_structural_metadata_includes_sheet_count(self, multi_sheet_xlsx):
        """Test structural metadata includes sheet count."""
        extractor = XlsxExtractor()
        result = extractor.extract(multi_sheet_xlsx, "workbook.xlsx")

        assert "sheet_count" in result.structural_metadata
        assert result.structural_metadata["sheet_count"] == 2

    def test_structural_metadata_includes_sheet_names(self, multi_sheet_xlsx):
        """Test structural metadata includes sheet names."""
        extractor = XlsxExtractor()
        result = extractor.extract(multi_sheet_xlsx, "workbook.xlsx")

        assert "sheets" in result.structural_metadata
        assert "Sales" in result.structural_metadata["sheets"]
        assert "Inventory" in result.structural_metadata["sheets"]

    def test_generates_markdown_tables(self, single_sheet_xlsx):
        """Test that sheet data is formatted as markdown tables."""
        extractor = XlsxExtractor()
        result = extractor.extract(single_sheet_xlsx, "data.xlsx")

        # Should have markdown table format
        assert "|" in result.markdown
        assert "---" in result.markdown

    def test_corrupted_xlsx_falls_back(self, corrupted_xlsx):
        """Test that corrupted XLSX falls back with warning."""
        extractor = XlsxExtractor()
        result = extractor.extract(corrupted_xlsx, "broken.xlsx")

        assert isinstance(result, ExtractionResult)
        assert result.parse_warning is not None

    def test_title_from_filename(self, single_sheet_xlsx):
        """Test title is extracted from filename."""
        extractor = XlsxExtractor()
        result = extractor.extract(single_sheet_xlsx, "sales_report_2024.xlsx")

        assert result.title == "sales_report_2024"

    def test_empty_sheet_handling(self):
        """Test handling of XLSX with empty sheet."""
        xlsx_bytes = create_minimal_xlsx(sheets={"Empty": []})
        extractor = XlsxExtractor()
        result = extractor.extract(xlsx_bytes, "empty.xlsx")

        assert isinstance(result, ExtractionResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
