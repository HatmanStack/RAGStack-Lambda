# Utilities Module

Shared utilities for logging, authentication, image processing, and constants.

## logging_utils.py

```python
def safe_log_event(event: dict[str, Any], sensitive_keys: frozenset[str] | None = None, max_depth: int = 5) -> dict[str, Any]
def log_summary(operation: str, *, success: bool = True, duration_ms: float | None = None, item_count: int | None = None, error: str | None = None, **kwargs) -> dict[str, Any]
```

**Purpose:** Mask sensitive data (tokens, credentials, user queries) before CloudWatch logging.

### safe_log_event

Recursively redacts sensitive fields from event dictionaries for safe logging.

```python
from ragstack_common.logging_utils import safe_log_event
import json

# Lambda event with sensitive data
event = {
    "headers": {
        "Authorization": "Bearer secret-token-12345",
        "Cookie": "session=abc123"
    },
    "body": json.dumps({
        "query": "confidential search query",
        "api_key": "sk-1234567890"
    }),
    "requestContext": {
        "identity": {
            "userArn": "arn:aws:iam::123456789012:user/alice"
        }
    }
}

# Safe logging
safe_event = safe_log_event(event)

# Result:
# {
#     "headers": {
#         "Authorization": "[REDACTED]",
#         "Cookie": "[REDACTED]"
#     },
#     "body": {
#         "query": "[REDACTED]",
#         "api_key": "[REDACTED]"
#     },
#     "requestContext": {
#         "identity": {
#             "userArn": "arn:aws:iam::123456789012:user/alice"
#         }
#     }
# }

logger.info("Event received", extra={"event": safe_event})
```

**Default sensitive keys:**
- `authorization`, `token`, `password`, `secret`, `api_key`
- `query`, `message`, `content`, `text`
- `cookie`, `session`, `credentials`

**Custom sensitive keys:**

```python
# Add custom keys to redact
custom_sensitive = frozenset(["email", "phone", "ssn"])
safe_event = safe_log_event(event, sensitive_keys=custom_sensitive)
```

**Max depth protection:**

```python
# Prevent deep recursion on complex structures
safe_event = safe_log_event(deeply_nested_event, max_depth=3)
# Stops redacting after 3 levels of nesting
```

### log_summary

Creates structured log messages for operation summaries.

```python
from ragstack_common.logging_utils import log_summary
import logging

logger = logging.getLogger(__name__)

# Success case
summary = log_summary(
    operation="document_ingestion",
    success=True,
    duration_ms=1234.5,
    item_count=10,
    document_id="doc-123"
)

logger.info(summary)

# Result:
# {
#     "operation": "document_ingestion",
#     "success": true,
#     "duration_ms": 1234.5,
#     "item_count": 10,
#     "document_id": "doc-123"
# }

# Error case
summary = log_summary(
    operation="knowledge_base_query",
    success=False,
    duration_ms=567.8,
    error="ThrottlingException: Rate exceeded",
    query_length=150
)

logger.error(summary)

# Result:
# {
#     "operation": "knowledge_base_query",
#     "success": false,
#     "duration_ms": 567.8,
#     "error": "ThrottlingException: Rate exceeded",
#     "query_length": 150
# }
```

**Use case:** Consistent structured logging for CloudWatch Insights queries

**Example query:**

```
fields @timestamp, operation, success, duration_ms, item_count
| filter operation = "document_ingestion"
| stats avg(duration_ms), sum(item_count) by success
```

## auth.py

```python
def check_public_access(event: dict, access_type: str, config_manager: ConfigurationManager) -> tuple[bool, str | None]
```

**Access types:** `chat`, `search`, `upload`, `image_upload`, `scrape`

### check_public_access

Validates if an unauthenticated request is allowed based on configuration.

```python
from ragstack_common.auth import check_public_access
from ragstack_common.config import ConfigurationManager

config = ConfigurationManager()

# Check if public chat is allowed
allowed, error_message = check_public_access(
    event={"requestContext": {"authorizer": None}},
    access_type="chat",
    config_manager=config
)

if not allowed:
    return {
        "statusCode": 403,
        "body": json.dumps({"error": error_message})
    }
```

**Access types and config keys:**

| Access Type | Config Key | Default | Use Case |
|-------------|------------|---------|----------|
| `chat` | `public_chat_enabled` | `true` | Web component chat |
| `search` | `public_search_enabled` | `true` | Public knowledge base search |
| `upload` | `public_upload_enabled` | `false` | Anonymous document upload |
| `image_upload` | `public_image_upload_enabled` | `false` | Anonymous image upload |
| `scrape` | `public_scrape_enabled` | `false` | Anonymous scrape jobs |

**Return values:**

```python
# Allowed
(True, None)

# Denied
(False, "Public chat is disabled. Please sign in to continue.")
```

**Complete example:**

```python
def lambda_handler(event, context):
    config = ConfigurationManager()

    # Check public access
    allowed, error = check_public_access(event, "chat", config)
    if not allowed:
        return {
            "statusCode": 403,
            "body": json.dumps({"error": error})
        }

    # Process chat request
    # ...
```

## demo_mode.py

```python
def check_demo_mode_limit(operation: str, user_id: str | None = None) -> tuple[bool, str | None]
```

Check if operation allowed under demo mode restrictions.

**Operations:** `upload`, `chat`, `reindex`, `reprocess`, `delete`

**Returns:** `(allowed: bool, error_message: str | None)`

### check_demo_mode_limit

Enforces rate limits and feature restrictions in demo mode.

```python
from ragstack_common.demo_mode import check_demo_mode_limit

# Check if upload allowed
allowed, error = check_demo_mode_limit(
    operation="upload",
    user_id="user-123"
)

if not allowed:
    return {
        "statusCode": 429,
        "body": json.dumps({"error": error})
    }
```

**Rate limits (demo mode):**

| Operation | Limit | Scope |
|-----------|-------|-------|
| `upload` | 5/day | Per user |
| `chat` | 30/day | Per user |
| `reindex` | Blocked | All users |
| `reprocess` | Blocked | All users |
| `delete` | Blocked | All users |

**Return values:**

```python
# Allowed
(True, None)

# Rate limit exceeded
(False, "Upload limit exceeded. Demo mode allows 5 uploads per day.")

# Feature blocked
(False, "Reindex is disabled in demo mode.")
```

**Complete example:**

```python
from ragstack_common.demo_mode import check_demo_mode_limit
from ragstack_common.config import ConfigurationManager

def lambda_handler(event, context):
    config = ConfigurationManager()

    # Check if demo mode enabled
    if config.get_parameter("demo_mode_enabled", False):
        # Check demo limits
        user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
        allowed, error = check_demo_mode_limit("upload", user_id)

        if not allowed:
            return {
                "statusCode": 429,
                "body": json.dumps({"error": error})
            }

    # Process upload
    # ...
```

## image.py

```python
def validate_image_type(content_type: str | None, filename: str | None) -> tuple[bool, str]
def validate_image_size(size_bytes: int | None) -> tuple[bool, str]
def is_supported_image(filename: str) -> bool
def resize_image(image_bytes: bytes, max_dimension: int = 2048) -> bytes
def prepare_bedrock_image_attachment(image_bytes: bytes, content_type: str) -> dict

class ImageStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
```

**Supported:** JPG, PNG, GIF, WebP, AVIF (max 10MB)

### validate_image_type

Validates if image format is supported.

```python
from ragstack_common.image import validate_image_type

# From content type
valid, message = validate_image_type(content_type="image/png", filename=None)
# (True, "")

# From filename
valid, message = validate_image_type(content_type=None, filename="photo.jpg")
# (True, "")

# Invalid type
valid, message = validate_image_type(content_type="image/bmp", filename=None)
# (False, "Unsupported image type: image/bmp. Supported: JPG, PNG, GIF, WebP, AVIF")
```

### validate_image_size

Validates if image size is within limits.

```python
from ragstack_common.image import validate_image_size

# Valid size
valid, message = validate_image_size(5 * 1024 * 1024)  # 5 MB
# (True, "")

# Too large
valid, message = validate_image_size(15 * 1024 * 1024)  # 15 MB
# (False, "Image size exceeds 10 MB limit")
```

### is_supported_image

Quick check if filename extension is supported.

```python
from ragstack_common.image import is_supported_image

is_supported_image("photo.jpg")     # True
is_supported_image("image.png")     # True
is_supported_image("doc.pdf")       # False
is_supported_image("video.mp4")     # False
```

### resize_image

Resizes image to fit within max dimension while preserving aspect ratio.

```python
from ragstack_common.image import resize_image

# Read image
with open("large-image.jpg", "rb") as f:
    image_bytes = f.read()

# Resize to 2048x2048 max (default)
resized_bytes = resize_image(image_bytes)

# Custom max dimension
resized_bytes = resize_image(image_bytes, max_dimension=1024)
```

**Behavior:**
- If image ≤ max_dimension: returns original bytes
- If image > max_dimension: resizes maintaining aspect ratio
- Preserves format and quality

**Example:**
- Input: 4000x3000 JPG
- `resize_image(bytes, max_dimension=2048)`
- Output: 2048x1536 JPG

### prepare_bedrock_image_attachment

Formats image bytes for Bedrock API requests.

```python
from ragstack_common.image import prepare_bedrock_image_attachment
import base64

# Read and resize image
with open("photo.jpg", "rb") as f:
    image_bytes = f.read()

# Prepare for Bedrock
attachment = prepare_bedrock_image_attachment(
    image_bytes=image_bytes,
    content_type="image/jpeg"
)

# Use in Bedrock request
content = [
    {
        "type": "image",
        "source": attachment
    },
    {
        "type": "text",
        "text": "Describe this image"
    }
]
```

**Returns:**

```python
{
    "type": "base64",
    "media_type": "image/jpeg",
    "data": "base64-encoded-string"
}
```

### ImageStatus

Enum for image processing status tracking.

```python
from ragstack_common.image import ImageStatus

# Track image processing
status = ImageStatus.PENDING
# ... upload to S3 ...
status = ImageStatus.PROCESSING
# ... extract caption ...
status = ImageStatus.INDEXED
# ... or on error ...
status = ImageStatus.FAILED
```

## appsync.py

```python
def publish_document_update(graphql_endpoint: str, document_id: str, filename: str, status: str, **kwargs) -> None
def publish_image_update(graphql_endpoint: str, image_id: str, filename: str, status: str, **kwargs) -> None
def publish_scrape_update(graphql_endpoint: str, job_id: str, base_url: str, **kwargs) -> None
def publish_reindex_update(graphql_endpoint: str, status: str, total_documents: int, processed_count: int, **kwargs) -> None
```

### publish_document_update

Publishes document processing updates to AppSync for real-time UI updates.

```python
from ragstack_common.appsync import publish_document_update
import os

graphql_endpoint = os.environ["APPSYNC_ENDPOINT"]

# Publish status update
publish_document_update(
    graphql_endpoint=graphql_endpoint,
    document_id="doc-123",
    filename="report.pdf",
    status="PROCESSING",
    total_pages=10,
    pages_processed=5
)
```

**Required fields:** `document_id`, `filename`, `status`

**Optional kwargs:** `total_pages`, `pages_processed`, `pages_failed`, `error_message`

### publish_image_update

Publishes image processing updates to AppSync.

```python
from ragstack_common.appsync import publish_image_update

publish_image_update(
    graphql_endpoint=graphql_endpoint,
    image_id="img-456",
    filename="photo.jpg",
    status="INDEXED",
    caption="Sunset over mountains"
)
```

### publish_scrape_update

Publishes scrape job progress to AppSync.

```python
from ragstack_common.appsync import publish_scrape_update

publish_scrape_update(
    graphql_endpoint=graphql_endpoint,
    job_id="scrape-789",
    base_url="https://docs.example.com",
    status="PROCESSING",
    total_urls=100,
    processed_count=45,
    failed_count=2
)
```

### publish_reindex_update

Publishes reindex operation progress to AppSync.

```python
from ragstack_common.appsync import publish_reindex_update

publish_reindex_update(
    graphql_endpoint=graphql_endpoint,
    status="IN_PROGRESS",
    total_documents=500,
    processed_count=250,
    estimated_time_remaining_seconds=300
)
```

## constants.py

```python
# Query Limits
MAX_QUERY_LENGTH = 10000
SNIPPET_LENGTH = 200
MESSAGE_LIMIT = 50
MAX_SEARCH_RESULTS = 100
DEFAULT_SEARCH_RESULTS = 5

# Timeouts (seconds)
PRESIGNED_URL_EXPIRY = 3600
LAMBDA_TIMEOUT = 900
INGEST_TIMEOUT = 300
QUERY_TIMEOUT = 60

# DynamoDB Pagination
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

# OCR Processing
MIN_EXTRACTABLE_CHARS_PER_PAGE = 50
MAX_IMAGE_DIMENSION = 2048

# Rate Limiting
DEFAULT_GLOBAL_QUOTA_DAILY = 10000
DEFAULT_PER_USER_QUOTA_DAILY = 100

# Image Upload
MAX_IMAGE_SIZE_BYTES = 10485760  # 10 MB
SUPPORTED_IMAGE_TYPES: dict[str, str]  # MIME type -> extension
SUPPORTED_IMAGE_EXTENSIONS: set[str]  # {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif"}
```

### Usage

```python
from ragstack_common.constants import (
    MAX_QUERY_LENGTH,
    DEFAULT_SEARCH_RESULTS,
    MAX_IMAGE_SIZE_BYTES,
    SUPPORTED_IMAGE_EXTENSIONS
)

# Validate query length
if len(query) > MAX_QUERY_LENGTH:
    raise ValueError(f"Query exceeds {MAX_QUERY_LENGTH} characters")

# Use default search results
num_results = request.get("num_results", DEFAULT_SEARCH_RESULTS)

# Check image size
if file_size > MAX_IMAGE_SIZE_BYTES:
    raise ValueError("Image exceeds 10 MB limit")

# Check file extension
if file_ext not in SUPPORTED_IMAGE_EXTENSIONS:
    raise ValueError(f"Unsupported extension: {file_ext}")
```

## models.py

```python
class Status(str, Enum):
    UPLOADED, PROCESSING, OCR_COMPLETE, EMBEDDING_COMPLETE, INDEXED, FAILED

class OcrBackend(str, Enum):
    TEXTRACT, BEDROCK, TEXT_EXTRACTION

@dataclass
class Document:
    document_id: str
    filename: str
    input_s3_uri: str
    status: Status = Status.UPLOADED
    output_s3_uri: str | None = None
    total_pages: int = 0
    pages: list[Page] = field(default_factory=list)
    pages_succeeded: int = 0
    pages_failed: int = 0

@dataclass
class Page:
    page_number: int
    text: str = ""
    image_s3_uri: str | None = None
    ocr_backend: str | None = None
```

### Status

Document processing status enum.

```python
from ragstack_common.models import Status

status = Status.UPLOADED           # Initial upload
status = Status.PROCESSING         # OCR in progress
status = Status.OCR_COMPLETE       # OCR done, embedding pending
status = Status.EMBEDDING_COMPLETE # Embedding done, ingestion pending
status = Status.INDEXED            # Fully indexed in KB
status = Status.FAILED             # Processing failed
```

### OcrBackend

OCR backend selection enum.

```python
from ragstack_common.models import OcrBackend

backend = OcrBackend.TEXTRACT        # AWS Textract
backend = OcrBackend.BEDROCK         # Bedrock vision models
backend = OcrBackend.TEXT_EXTRACTION # Text extractors (DOCX, HTML, etc.)
```

### Document

Document data model.

```python
from ragstack_common.models import Document, Status

doc = Document(
    document_id="doc-123",
    filename="report.pdf",
    input_s3_uri="s3://bucket/input/report.pdf",
    status=Status.UPLOADED,
    output_s3_uri=None,
    total_pages=10,
    pages=[],
    pages_succeeded=0,
    pages_failed=0
)
```

### Page

Page-level data model.

```python
from ragstack_common.models import Page

page = Page(
    page_number=1,
    text="Extracted text content...",
    image_s3_uri="s3://bucket/pages/page-1.png",
    ocr_backend="textract"
)

doc.pages.append(page)
```

## Best Practices

1. **Logging**: Always use `safe_log_event` before logging user input or credentials
2. **Log Summaries**: Use `log_summary` for consistent structured logging
3. **Authentication**: Check public access before processing unauthenticated requests
4. **Demo Mode**: Enforce limits early in request processing to save resources
5. **Image Validation**: Validate type and size before uploading to S3
6. **Image Resize**: Resize large images before OCR to reduce costs
7. **AppSync Updates**: Publish progress updates for long-running operations
8. **Constants**: Use constants instead of magic numbers for maintainability

## See Also

- [CONFIGURATION.md](./CONFIGURATION.md) - Configuration management
- [STORAGE.md](./STORAGE.md) - S3 storage utilities
- [OCR.md](./OCR.md) - OCR processing
- [METADATA.md](./METADATA.md) - Metadata extraction
