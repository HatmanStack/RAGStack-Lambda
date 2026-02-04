# OCR Module

OCR services and Bedrock client for text extraction from images and PDFs.

## ocr.py

```python
class OcrService:
    def __init__(region: str | None = None, backend: str = "textract", bedrock_model_id: str | None = None)
    def process_document(document: Document) -> Document
```

**Backends:** `textract`, `bedrock`

## Overview

`OcrService` provides unified interface for OCR with pluggable backends:
- **Textract**: Fast, cost-effective, production-ready
- **Bedrock**: Vision models for advanced OCR (WebP/AVIF support)

## Usage

### Initialize

```python
from ragstack_common.ocr import OcrService

# Textract backend (default)
service = OcrService(backend="textract")

# Bedrock backend with specific model
service = OcrService(
    backend="bedrock",
    bedrock_model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0"
)

# Auto-detect region
service = OcrService(region="us-east-1", backend="textract")
```

### Process Document

```python
from ragstack_common.ocr import OcrService
from ragstack_common.models import Document, Status

# Create document
doc = Document(
    document_id="doc-123",
    filename="invoice.pdf",
    input_s3_uri="s3://bucket/input/invoice.pdf",
    total_pages=3
)

# Process with OCR
service = OcrService()
processed_doc = service.process_document(doc)

# Access extracted text
for page in processed_doc.pages:
    print(f"Page {page.page_number}: {page.text[:100]}...")
```

**Returns:** Document with `pages` populated and `output_s3_uri` set

## bedrock.py

```python
class BedrockClient:
    def __init__(region: str | None = None, max_retries: int = 7, initial_backoff: float = 2)
    def invoke_model(model_id: str, system_prompt: str | list, content: list, temperature: float = 0.0) -> dict
    def extract_text_from_response(response: dict) -> str
    def get_metering_data(response: dict) -> dict
```

**Environment:** `AWS_REGION`

### Initialize

```python
from ragstack_common.bedrock import BedrockClient

# Default config
client = BedrockClient()

# Custom retry behavior
client = BedrockClient(
    region="us-east-1",
    max_retries=5,
    initial_backoff=1.0
)
```

### Invoke Model

```python
from ragstack_common.bedrock import BedrockClient

client = BedrockClient()

# Simple text prompt
response = client.invoke_model(
    model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    system_prompt="You are a helpful assistant",
    content=[{"text": "What is RAGStack?"}],
    temperature=0.0
)

# Extract text from response
text = client.extract_text_from_response(response)
print(text)

# Get token usage
metering = client.get_metering_data(response)
print(f"Input tokens: {metering['inputTokens']}")
print(f"Output tokens: {metering['outputTokens']}")
```

### Vision Model (OCR)

```python
from ragstack_common.bedrock import BedrockClient
from ragstack_common.image import prepare_bedrock_image_attachment

client = BedrockClient()
image_bytes = open("image.png", "rb").read()

# Prepare image attachment
image_attachment = prepare_bedrock_image_attachment(image_bytes, "image/png")

# Invoke vision model
response = client.invoke_model(
    model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    system_prompt="Extract all visible text from this image",
    content=[
        {"text": "What text is visible in this image?"},
        {"image": image_attachment}
    ]
)

extracted_text = client.extract_text_from_response(response)
```

### Metadata Extraction

```python
from ragstack_common.bedrock import BedrockClient

client = BedrockClient()

response = client.invoke_model(
    model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    system_prompt="Extract structured metadata from documents",
    content=[{
        "text": f"Extract metadata keys: topic, date_range, location\n\nDocument:\n{text}"
    }]
)

metadata_json = client.extract_text_from_response(response)
```

## Retry Behavior

`BedrockClient` implements exponential backoff with jitter:

- **Initial backoff**: 2 seconds (configurable)
- **Max retries**: 7 attempts (configurable)
- **Backoff formula**: `base * (2 ^ attempt) * jitter`
- **Retryable errors**: ThrottlingException, ServiceUnavailableException

```python
from ragstack_common.bedrock import BedrockClient

# Aggressive retries for throttling
client = BedrockClient(max_retries=10, initial_backoff=1.0)

try:
    response = client.invoke_model(...)
except Exception as e:
    # All retries exhausted
    print(f"Failed after {client.max_retries} attempts: {e}")
```

## Error Handling

```python
from ragstack_common.ocr import OcrService
from ragstack_common.models import Document, Status

service = OcrService()
doc = Document(...)

try:
    processed = service.process_document(doc)
except Exception as e:
    # OCR failed - mark document as failed
    doc.status = Status.FAILED
    doc.error_message = str(e)
```

## Performance Considerations

### Textract Backend
- **Speed**: ~5-10 seconds per page
- **Cost**: $1.50 per 1000 pages
- **Limits**: 500 pages per document
- **Formats**: PDF, PNG, JPG, TIFF

### Bedrock Backend
- **Speed**: ~10-20 seconds per page (vision model)
- **Cost**: ~$0.01-0.02 per page (depends on model)
- **Limits**: Model context window
- **Formats**: PDF, PNG, JPG, WebP, AVIF, GIF

## Best Practices

1. **Use Textract for production** - Faster, cheaper, more reliable
2. **Use Bedrock for special formats** - WebP, AVIF, or complex layouts
3. **Batch processing** - Process multiple pages concurrently
4. **Error handling** - Always catch exceptions and mark failures
5. **Retry logic** - Let BedrockClient handle retries automatically

## See Also

- [Configuration](../CONFIGURATION.md#document-processing) - OCR backend configuration
- [models.py](./UTILITIES.md#models) - Document and Page data models
- [image.py](./UTILITIES.md#image) - Image utilities
