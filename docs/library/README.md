# Library Reference

Public API for `lib/ragstack_common/`. Internal functions omitted.

## Documentation Structure

Library documentation is organized by functional category:

### Core

- **[CONFIGURATION.md](./CONFIGURATION.md)** - Configuration management (`config.py`)
- **[STORAGE.md](./STORAGE.md)** - S3 utilities and file operations (`storage.py`, `sources.py`)
- **[UTILITIES.md](./UTILITIES.md)** - Helper functions and data models (`logging_utils.py`, `auth.py`, `demo_mode.py`, `image.py`, `appsync.py`, `constants.py`, `models.py`)

### Document Processing

- **[OCR.md](./OCR.md)** - OCR services and Bedrock client (`ocr.py`, `bedrock.py`)
- **[TEXT_EXTRACTORS.md](./TEXT_EXTRACTORS.md)** - Text extraction for HTML, CSV, JSON, XML, EML, EPUB, DOCX, XLSX (`text_extractors/`)
- **[MEDIA.md](./MEDIA.md)** - Audio/video transcription and segmentation (`transcribe_client.py`, `media_segmenter.py`)

### Metadata & Retrieval

- **[METADATA.md](./METADATA.md)** - Metadata extraction, normalization, and filtering (`metadata_extractor.py`, `metadata_normalizer.py`, `key_library.py`, `filter_generator.py`, `filter_examples.py`)
- **[RETRIEVAL.md](./RETRIEVAL.md)** - Knowledge Base retrieval and ingestion (`multislice_retriever.py`, `ingestion.py`)

### Web Scraping

- **[SCRAPER.md](./SCRAPER.md)** - Web scraping jobs and configuration (`scraper/`)

## Quick Reference

### Configuration Management
```python
from ragstack_common.config import ConfigurationManager
config = ConfigurationManager()
value = config.get_parameter("chat_primary_model")
```

### S3 Operations
```python
from ragstack_common.storage import read_s3_text, write_s3_text, parse_s3_uri
content = read_s3_text("s3://bucket/key")
bucket, key = parse_s3_uri("s3://bucket/key")
```

### OCR Processing
```python
from ragstack_common.ocr import OcrService
service = OcrService(backend="textract")
document = service.process_document(document)
```

### Metadata Extraction
```python
from ragstack_common.metadata_extractor import MetadataExtractor
extractor = MetadataExtractor()
metadata = extractor.extract_metadata(text, document_id)
```

### Knowledge Base Retrieval
```python
from ragstack_common.multislice_retriever import MultiSliceRetriever
retriever = MultiSliceRetriever()
results = retriever.retrieve(query, kb_id, ds_id)
```

### Text Extraction
```python
from ragstack_common.text_extractors import extract_text
result = extract_text(content_bytes, filename)
markdown = result.markdown
```

### Media Processing
```python
from ragstack_common.transcribe_client import TranscribeClient
from ragstack_common.media_segmenter import MediaSegmenter

client = TranscribeClient()
job_name = client.start_transcription_job(doc_id, input_uri, output_bucket)
result = client.wait_for_completion(job_name)

segmenter = MediaSegmenter(segment_duration=30)
segments = segmenter.segment_transcript(words, total_duration)
```

### Web Scraping
```python
from ragstack_common.scraper import ScrapeJob, ScrapeConfig, ScrapeScope

config = ScrapeConfig(
    max_pages=100,
    max_depth=3,
    scope=ScrapeScope.HOSTNAME
)
```

## Environment Variables

| Variable | Module | Purpose |
|----------|--------|---------|
| `AWS_REGION` | Most modules | AWS region for services |
| `CONFIGURATION_TABLE_NAME` | config.py | DynamoDB config table |
| `METADATA_KEY_LIBRARY_TABLE` | key_library.py, filter_examples.py | Metadata key storage |
| `GRAPHQL_ENDPOINT` | appsync.py | AppSync API endpoint for subscriptions |

## Data Models

### Document
Main document entity with processing status tracking.

```python
from ragstack_common.models import Document, Status, Page

doc = Document(
    document_id="doc-123",
    filename="example.pdf",
    input_s3_uri="s3://bucket/input/example.pdf",
    status=Status.UPLOADED
)
```

### Status Enums
- `Status`: Document processing states
- `OcrBackend`: OCR backend types (TEXTRACT, BEDROCK, TEXT_EXTRACTION)
- `ImageStatus`: Image processing states
- `ScrapeStatus`: Scrape job states

## Error Handling

### Media Processing Exceptions
```python
from ragstack_common.exceptions import (
    MediaProcessingError,
    TranscriptionError,
    UnsupportedMediaFormatError
)
```

## Constants

```python
from ragstack_common.constants import (
    MAX_QUERY_LENGTH,
    PRESIGNED_URL_EXPIRY,
    DEFAULT_PAGE_SIZE,
    SUPPORTED_IMAGE_TYPES
)
```

## Best Practices

1. **Configuration**: Use `ConfigurationManager` for all settings - changes apply immediately without redeployment
2. **S3 Operations**: Always use utility functions instead of boto3 directly for consistent error handling
3. **Metadata**: Enable `update_library=False` when extracting metadata in read-only contexts
4. **Logging**: Use `safe_log_event()` to mask sensitive data before CloudWatch logging
5. **Retries**: Bedrock and ingestion functions have built-in exponential backoff
6. **Media**: Check file format support with `TranscribeClient` before processing

## See Also

- [Configuration Guide](../CONFIGURATION.md) - User-facing configuration options
- [API Reference](../API_REFERENCE.md) - GraphQL API documentation
- [Architecture](../ARCHITECTURE.md) - System design and data flow
