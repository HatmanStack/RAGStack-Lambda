# Library Reference

> **Note:** Library documentation has been reorganized into category-based modules for better navigation.
>
> See **[docs/library/README.md](./library/README.md)** for the complete API reference.

## Quick Links

### Core Modules
- **[Configuration](./library/CONFIGURATION.md)** - Runtime configuration management
- **[Storage](./library/STORAGE.md)** - S3 utilities and file operations
- **[Utilities](./library/UTILITIES.md)** - Helper functions, logging, auth, constants, models

### Document Processing
- **[OCR](./library/OCR.md)** - OCR services and Bedrock client
- **[Text Extractors](./library/TEXT_EXTRACTORS.md)** - HTML, CSV, JSON, XML, EML, EPUB, DOCX, XLSX extraction
- **[Media](./library/MEDIA.md)** - Audio/video transcription and segmentation

### Metadata & Retrieval
- **[Metadata](./library/METADATA.md)** - Metadata extraction, normalization, key library, filtering
- **[Retrieval](./library/RETRIEVAL.md)** - Knowledge Base retrieval and ingestion

### Web Scraping
- **[Scraper](./library/SCRAPER.md)** - Web scraping jobs and configuration

## Overview

The `lib/ragstack_common/` library provides reusable utilities for document processing, metadata extraction, and Knowledge Base operations. All Lambda functions import from this shared library to eliminate code duplication.

### Quick Examples

#### Configuration
```python
from ragstack_common.config import ConfigurationManager
config = ConfigurationManager()
ocr_backend = config.get_parameter("ocr_backend", default="textract")
```

#### S3 Operations
```python
from ragstack_common.storage import read_s3_text, write_s3_text
content = read_s3_text("s3://bucket/file.txt")
write_s3_text("s3://bucket/output.txt", content)
```

#### OCR Processing
```python
from ragstack_common.ocr import OcrService
service = OcrService(backend="textract")
processed = service.process_document(document)
```

#### Metadata Extraction
```python
from ragstack_common.metadata_extractor import MetadataExtractor
extractor = MetadataExtractor()
metadata = extractor.extract_metadata(text, document_id)
```

#### Knowledge Base Retrieval
```python
from ragstack_common.multislice_retriever import MultiSliceRetriever
retriever = MultiSliceRetriever()
results = retriever.retrieve(query, kb_id, ds_id)
```

## Environment Variables

| Variable | Modules | Purpose |
|----------|---------|---------|
| `AWS_REGION` | Most modules | AWS region for services |
| `CONFIGURATION_TABLE_NAME` | config.py | DynamoDB config table |
| `METADATA_KEY_LIBRARY_TABLE` | key_library.py, filter_examples.py | Metadata key storage |
| `GRAPHQL_ENDPOINT` | appsync.py | AppSync API for subscriptions |

## See Also

- **[API Reference](./API_REFERENCE.md)** - GraphQL API documentation
- **[Configuration Guide](./CONFIGURATION.md)** - User-facing configuration options
- **[Architecture](./ARCHITECTURE.md)** - System design and data flow
