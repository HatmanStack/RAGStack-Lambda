# Text Extractors Module

Text extraction for non-OCR document types. Auto-detects format and extracts to markdown.

## text_extractors/

```python
from ragstack_common.text_extractors import extract_text, ExtractionResult

def extract_text(content: bytes, filename: str) -> ExtractionResult
```

**ExtractionResult fields:**
- `markdown`: Extracted text as markdown
- `file_type`: Detected file type (html, csv, json, etc.)
- `title`: Document title if found
- `metadata`: Extracted metadata dict

**Supported formats:**
| Format | Extractor | Dependencies |
|--------|-----------|--------------|
| HTML | HtmlExtractor | - |
| TXT | TextExtractor | - |
| CSV | CsvExtractor | - |
| JSON | JsonExtractor | - |
| XML | XmlExtractor | - |
| EML | EmailExtractor | - |
| EPUB | EpubExtractor | ebooklib |
| DOCX | DocxExtractor | python-docx |
| XLSX | XlsxExtractor | openpyxl |

## Overview

The text extractors module provides format-specific extraction for structured documents. Unlike OCR (for images/PDFs), these extractors parse native file formats and convert to clean markdown for embedding and search.

## Usage

### Basic Extraction

```python
from ragstack_common.text_extractors import extract_text

# Read file
with open("document.html", "rb") as f:
    content = f.read()

# Extract text
result = extract_text(content, filename="document.html")

# Access extracted data
print(result.markdown)     # Markdown text
print(result.file_type)    # "html"
print(result.title)        # "Document Title"
print(result.metadata)     # {"author": "...", ...}
```

### S3 Integration

```python
from ragstack_common.storage import read_s3_binary
from ragstack_common.text_extractors import extract_text

# Read from S3
content = read_s3_binary("s3://bucket/document.docx")

# Extract text
result = extract_text(content, filename="document.docx")
```

### Format Detection

```python
# Auto-detects from filename extension
result = extract_text(content, filename="data.csv")
# Uses CsvExtractor

result = extract_text(content, filename="email.eml")
# Uses EmailExtractor

result = extract_text(content, filename="book.epub")
# Uses EpubExtractor
```

## Format-Specific Examples

### HTML Extraction

```python
html_content = b"""
<html>
<head><title>Sample Document</title></head>
<body>
    <h1>Heading</h1>
    <p>Paragraph text.</p>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
    </ul>
</body>
</html>
"""

result = extract_text(html_content, filename="sample.html")

# result.markdown:
# # Heading
#
# Paragraph text.
#
# - Item 1
# - Item 2

# result.title: "Sample Document"
# result.file_type: "html"
```

**Features:**
- Converts HTML tags to markdown
- Extracts title from `<title>` tag
- Preserves lists, tables, headings
- Strips scripts, styles, navigation

### CSV Extraction

```python
csv_content = b"""
Name,Email,Department
John Doe,john@example.com,Engineering
Jane Smith,jane@example.com,Sales
"""

result = extract_text(csv_content, filename="employees.csv")

# result.markdown:
# | Name | Email | Department |
# |------|-------|------------|
# | John Doe | john@example.com | Engineering |
# | Jane Smith | jane@example.com | Sales |

# result.file_type: "csv"
# result.metadata: {"rows": 2, "columns": 3}
```

**Features:**
- Auto-detects delimiter (`,`, `\t`, `;`)
- Converts to markdown table
- Handles quoted values
- Preserves header row

### JSON Extraction

```python
json_content = b"""
{
    "title": "Configuration",
    "settings": {
        "theme": "dark",
        "notifications": true
    },
    "users": ["alice", "bob"]
}
"""

result = extract_text(json_content, filename="config.json")

# result.markdown:
# # Configuration
#
# ## settings
# - **theme**: dark
# - **notifications**: true
#
# ## users
# - alice
# - bob

# result.title: "Configuration"
# result.file_type: "json"
```

**Features:**
- Converts to hierarchical markdown
- Detects title from "title" or "name" fields
- Formats arrays as bullet lists
- Formats objects as key-value pairs

### XML Extraction

```python
xml_content = b"""
<document>
    <title>Sample XML</title>
    <section name="Introduction">
        <paragraph>Text content</paragraph>
    </section>
</document>
"""

result = extract_text(xml_content, filename="doc.xml")

# result.markdown:
# # Sample XML
#
# ## Introduction
# Text content

# result.title: "Sample XML"
# result.file_type: "xml"
```

**Features:**
- Converts to hierarchical markdown
- Preserves structure via headings
- Extracts attributes as metadata
- Handles nested elements

### Email Extraction (EML)

```python
eml_content = b"""
From: sender@example.com
To: recipient@example.com
Subject: Meeting Notes
Date: Mon, 1 Jan 2024 10:00:00 -0500

Meeting notes:
- Discuss Q1 goals
- Review budget
"""

result = extract_text(eml_content, filename="meeting.eml")

# result.markdown:
# From: sender@example.com
# To: recipient@example.com
# Date: Mon, 1 Jan 2024 10:00:00 -0500
#
# Meeting notes:
# - Discuss Q1 goals
# - Review budget

# result.title: "Meeting Notes"
# result.file_type: "eml"
# result.metadata: {
#     "from": "sender@example.com",
#     "to": "recipient@example.com",
#     "date": "Mon, 1 Jan 2024 10:00:00 -0500"
# }
```

**Features:**
- Extracts headers (From, To, Subject, Date)
- Handles multipart messages
- Extracts plaintext parts only
- Preserves email thread structure

### EPUB Extraction

```python
# Read EPUB file
with open("book.epub", "rb") as f:
    epub_content = f.read()

result = extract_text(epub_content, filename="book.epub")

# result.markdown:
# # Book Title
#
# ## Chapter 1: Introduction
# Chapter text...
#
# ## Chapter 2: Main Content
# Chapter text...

# result.title: "Book Title"
# result.file_type: "epub"
# result.metadata: {
#     "author": "Author Name",
#     "publisher": "Publisher",
#     "language": "en"
# }
```

**Features:**
- Extracts all chapters
- Preserves chapter hierarchy
- Extracts metadata (title, author, publisher)
- Handles HTML content within EPUB

**Requires:** `pip install ebooklib`

### DOCX Extraction

```python
# Read DOCX file
with open("report.docx", "rb") as f:
    docx_content = f.read()

result = extract_text(docx_content, filename="report.docx")

# result.markdown:
# # Annual Report 2023
#
# ## Executive Summary
# Text content...
#
# ## Financial Results
# - Revenue: $1.2M
# - Profit: $300K

# result.title: "Annual Report 2023"
# result.file_type: "docx"
# result.metadata: {
#     "author": "Finance Team",
#     "created": "2024-01-15"
# }
```

**Features:**
- Extracts paragraphs and headings
- Preserves text formatting structure
- Extracts document properties
- Handles tables and lists

**Requires:** `pip install python-docx`

### XLSX Extraction

```python
# Read XLSX file
with open("data.xlsx", "rb") as f:
    xlsx_content = f.read()

result = extract_text(xlsx_content, filename="data.xlsx")

# result.markdown:
# # Sheet1
#
# | Name | Value | Status |
# |------|-------|--------|
# | Item A | 100 | Active |
# | Item B | 200 | Pending |
#
# # Sheet2
#
# | Column1 | Column2 |
# |---------|---------|
# | Data1 | Data2 |

# result.file_type: "xlsx"
# result.metadata: {"sheets": 2, "rows": 4}
```

**Features:**
- Extracts all sheets
- Converts to markdown tables
- Preserves cell values (no formulas)
- Handles merged cells

**Requires:** `pip install openpyxl`

## ExtractionResult API

```python
from dataclasses import dataclass

@dataclass
class ExtractionResult:
    markdown: str           # Extracted text as markdown
    file_type: str         # Detected file type
    title: str | None      # Document title (if found)
    metadata: dict         # Format-specific metadata
```

### Attributes

**markdown**
- Type: `str`
- Contains extracted text formatted as markdown
- Always populated (empty string if extraction fails)

**file_type**
- Type: `str`
- Format identifier: `html`, `csv`, `json`, `xml`, `eml`, `epub`, `docx`, `xlsx`, `txt`
- Used for logging and analytics

**title**
- Type: `str | None`
- Document title extracted from format-specific fields
- `None` if no title found

**metadata**
- Type: `dict`
- Format-specific metadata (author, date, row count, etc.)
- Empty dict if no metadata available

## Error Handling

```python
from ragstack_common.text_extractors import extract_text

try:
    result = extract_text(content, filename="document.docx")
    if not result.markdown.strip():
        logger.warning("Extraction produced empty text")
except ImportError as e:
    # Missing optional dependency (ebooklib, python-docx, openpyxl)
    logger.error(f"Missing dependency: {e}")
except UnicodeDecodeError as e:
    # Encoding issues
    logger.error(f"Encoding error: {e}")
except Exception as e:
    # Other extraction errors
    logger.error(f"Extraction failed: {e}")
```

## Integration with Document Pipeline

```python
from ragstack_common.storage import read_s3_binary, write_s3_text
from ragstack_common.text_extractors import extract_text
from ragstack_common.models import Document, Status

def process_text_document(document: Document) -> Document:
    """
    Extract text from non-OCR document formats.
    """
    # Read input file
    content = read_s3_binary(document.input_s3_uri)

    # Extract text
    result = extract_text(content, filename=document.filename)

    # Save markdown to S3
    output_s3_uri = document.input_s3_uri.replace("/input/", "/output/")
    output_s3_uri = output_s3_uri.rsplit(".", 1)[0] + ".md"

    write_s3_text(output_s3_uri, result.markdown, content_type="text/markdown")

    # Update document
    document.output_s3_uri = output_s3_uri
    document.status = Status.OCR_COMPLETE

    return document
```

## Fallback to OCR

Some file types (DOCX, XLSX) may contain embedded images or scanned content. Consider fallback:

```python
from ragstack_common.text_extractors import extract_text
from ragstack_common.ocr import OcrService

result = extract_text(content, filename="document.docx")

# Check if extraction produced meaningful text
if len(result.markdown.strip()) < 100:
    logger.info("Text extraction insufficient, falling back to OCR")
    ocr_service = OcrService(backend="textract")
    document = ocr_service.process_document(document)
```

## Best Practices

1. **Format Detection**: Always provide accurate filename with extension
2. **Dependencies**: Install optional dependencies only when needed (`ebooklib`, `python-docx`, `openpyxl`)
3. **Validation**: Check `result.markdown.strip()` for empty/insufficient extractions
4. **Fallback**: Have OCR fallback for documents with embedded images
5. **Encoding**: UTF-8 recommended for text files; extractors handle format-specific encodings
6. **Large Files**: Consider chunking very large CSVs or spreadsheets
7. **Security**: Validate file types before extraction to prevent malicious uploads

## See Also

- [OCR.md](./OCR.md) - OCR processing for PDFs and images
- [STORAGE.md](./STORAGE.md) - S3 storage utilities
- [models.py](./UTILITIES.md#models) - Document data models
