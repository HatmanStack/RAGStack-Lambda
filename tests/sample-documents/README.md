# Sample Test Documents

Sample documents for testing RAGStack-Lambda.

## Generate Test Documents

```bash
pip install pymupdf Pillow python-docx openpyxl
python3 generate_samples.py
```

Creates:
- `text-native.pdf` - PDF with embedded text
- `invoice.jpg` - Sample invoice image
- `document.docx` - Word document
- `spreadsheet.xlsx` - Excel spreadsheet
- `scanned.pdf` - OCR test document (create manually)

## Create Scanned PDF

```bash
# Using ImageMagick
convert invoice.jpg -quality 100 scanned.pdf

# Using Python
pip install img2pdf
img2pdf invoice.jpg -o scanned.pdf
```

## File Limits

- Maximum file size: 10 MB per document
- Supported formats: PDF, JPG, PNG, DOCX, XLSX, TXT

## Usage

Use these documents for:
- Manual UI upload testing
- Integration test suite
- End-to-end validation
- Performance benchmarking

## Privacy

⚠️ **Do not commit** sensitive documents. Use only public or synthetic data.

## Full Documentation

See **[docs/TESTING.md](../../docs/TESTING.md#sample-test-documents)** for details about:
- Test data generation
- File size limits
- Dependencies
- Custom documents
