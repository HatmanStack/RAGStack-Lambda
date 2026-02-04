# Storage Module

S3 utilities and file operations for document management.

## storage.py

```python
def parse_s3_uri(s3_uri: str) -> tuple[str, str]  # (bucket, key)
def read_s3_text(s3_uri: str, encoding: str = "utf-8") -> str
def read_s3_binary(s3_uri: str) -> bytes
def write_s3_text(s3_uri: str, content: str, content_type: str = "text/plain") -> None
def delete_s3_object(s3_uri: str) -> None
def generate_presigned_url(s3_uri: str, expiration: int = 3600) -> str
def write_metadata_to_s3(s3_uri: str, metadata: dict) -> None
def extract_filename_from_s3_uri(s3_uri: str) -> str
def get_file_type_from_filename(filename: str) -> str
def is_valid_uuid(value: str) -> bool
```

## Overview

Utility functions for S3 operations with consistent error handling and URI parsing.

## Usage

### Parse S3 URI

```python
from ragstack_common.storage import parse_s3_uri

bucket, key = parse_s3_uri("s3://my-bucket/path/to/file.txt")
# bucket: "my-bucket"
# key: "path/to/file.txt"
```

### Read Text Files

```python
from ragstack_common.storage import read_s3_text

# UTF-8 (default)
content = read_s3_text("s3://bucket/file.txt")

# Custom encoding
content = read_s3_text("s3://bucket/file.txt", encoding="latin-1")
```

### Read Binary Files

```python
from ragstack_common.storage import read_s3_binary

image_bytes = read_s3_binary("s3://bucket/image.png")
pdf_bytes = read_s3_binary("s3://bucket/document.pdf")
```

### Write Text Files

```python
from ragstack_common.storage import write_s3_text

write_s3_text(
    "s3://bucket/output.txt",
    "Hello, world!",
    content_type="text/plain"
)

# Markdown
write_s3_text(
    "s3://bucket/output.md",
    "# Heading\n\nContent",
    content_type="text/markdown"
)
```

### Delete Objects

```python
from ragstack_common.storage import delete_s3_object

delete_s3_object("s3://bucket/file-to-remove.txt")
```

### Generate Presigned URLs

```python
from ragstack_common.storage import generate_presigned_url

# Default 1-hour expiry
url = generate_presigned_url("s3://bucket/private-file.pdf")

# Custom expiry (5 minutes)
url = generate_presigned_url("s3://bucket/temporary.txt", expiration=300)
```

**Returns:** HTTPS URL for temporary public access

### Write Metadata

```python
from ragstack_common.storage import write_metadata_to_s3

metadata = {
    "topic": "genealogy",
    "date_range": "1900-1950",
    "location": "chicago"
}
write_metadata_to_s3("s3://bucket/doc/metadata.json", metadata)
```

### File Type Detection

```python
from ragstack_common.storage import get_file_type_from_filename

file_type = get_file_type_from_filename("document.pdf")  # "pdf"
file_type = get_file_type_from_filename("image.jpg")     # "image"
file_type = get_file_type_from_filename("video.mp4")     # "video"
```

**Returns:** `pdf`, `image`, `video`, `audio`, `text`, `unknown`

### Extract Filename

```python
from ragstack_common.storage import extract_filename_from_s3_uri

filename = extract_filename_from_s3_uri("s3://bucket/path/file.pdf")
# Returns: "file.pdf"
```

### Validate UUID

```python
from ragstack_common.storage import is_valid_uuid

is_valid_uuid("550e8400-e29b-41d4-a716-446655440000")  # True
is_valid_uuid("not-a-uuid")  # False
```

## sources.py

```python
def extract_source_url_from_content(content_text: str) -> str | None
def extract_image_caption_from_content(content_text: str) -> str | None
def extract_filename_from_frontmatter(content_text: str) -> str | None
def construct_image_uri_from_content_uri(content_s3_uri: str, content_text: str | None = None) -> str | None
```

### Extract Source URL

```python
from ragstack_common.sources import extract_source_url_from_content

content = """---
source_url: https://example.com/article
---
Content here"""

url = extract_source_url_from_content(content)
# Returns: "https://example.com/article"
```

**Use case:** Extract original URL from scraped markdown content

### Extract Image Caption

```python
from ragstack_common.sources import extract_image_caption_from_content

content = """---
caption: A beautiful sunset over mountains
---"""

caption = extract_image_caption_from_content(content)
# Returns: "A beautiful sunset over mountains"
```

### Extract Filename

```python
from ragstack_common.sources import extract_filename_from_frontmatter

content = """---
filename: document.pdf
---"""

filename = extract_filename_from_frontmatter(content)
# Returns: "document.pdf"
```

### Construct Image URI

```python
from ragstack_common.sources import construct_image_uri_from_content_uri

# From caption content URI
content_uri = "s3://bucket/images/img-123/caption/content.txt"
image_uri = construct_image_uri_from_content_uri(content_uri)
# Returns: "s3://bucket/images/img-123/image.jpg"

# With content text for image_id extraction
content_text = """---
image_id: img-456
---"""
image_uri = construct_image_uri_from_content_uri(content_uri, content_text)
# Returns: "s3://bucket/images/img-456/image.jpg"
```

**Use case:** Convert Knowledge Base caption URIs to actual image file URIs for thumbnails

## Error Handling

All functions raise exceptions on errors:

```python
from ragstack_common.storage import read_s3_text
import botocore.exceptions

try:
    content = read_s3_text("s3://bucket/missing-file.txt")
except botocore.exceptions.ClientError as e:
    if e.response['Error']['Code'] == 'NoSuchKey':
        print("File not found")
    elif e.response['Error']['Code'] == 'AccessDenied':
        print("Permission denied")
    else:
        raise
```

## Best Practices

1. **URI Format**: Always use `s3://bucket/key` format, not `https://` URLs
2. **Encoding**: Specify encoding explicitly for non-UTF-8 text files
3. **Content Type**: Set correct content_type for write operations (affects browser behavior)
4. **Presigned URLs**: Use short expiry times for sensitive documents
5. **Error Handling**: Catch `ClientError` and check error codes for specific handling

## See Also

- [constants.py](./UTILITIES.md#constants) - File type constants
- [models.py](./UTILITIES.md#models) - Document data models
