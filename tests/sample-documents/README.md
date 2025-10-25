# Sample Test Documents

This directory contains sample documents for testing RAGStack-Lambda.

## Files

- `text-native.pdf` - PDF with embedded text (generated)
- Add your own scanned PDFs, images, and Office docs for testing

## Adding Documents

Place test files here and reference them in `docs/TESTING.md`.

### Recommended Test Files

For comprehensive testing, add:

1. **Scanned PDF** - A scanned document image to test OCR
2. **Invoice Image** - JPG/PNG invoice to test image OCR
3. **Word Document** - .docx file to test format conversion
4. **Excel Spreadsheet** - .xlsx file to test table extraction
5. **Large PDF** - 100+ page document to test batch processing

### Creating Test Documents

You can generate test documents using:

```python
import fitz

# Create a simple text-native PDF
doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), "Your test content here")
doc.save("test-document.pdf")
doc.close()
```

### File Size Limits

- Maximum file size: 10 MB per document
- Maximum pages: No limit (batched automatically)
- Supported formats: PDF, JPG, PNG, DOCX, XLSX, TXT

## Usage

These documents are used in:
- Manual testing via UI
- Integration tests (`tests/integration/`)
- End-to-end testing guide (`docs/TESTING.md`)

## Test Data Privacy

⚠️ **Do not commit** sensitive or confidential documents to this directory.
Use only public domain or synthetic test data.
