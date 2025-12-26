# Library Reference

Public API for `lib/ragstack_common/`. Internal functions omitted.

## config.py

```python
class ConfigurationManager:
    def __init__(table_name: str | None = None) -> None
    def get_parameter(param_name: str, default: Any = None) -> Any
    def get_effective_config() -> dict[str, Any]
    def update_custom_config(custom_config: dict[str, Any]) -> None
    def get_schema() -> dict[str, Any]
```

**Environment:** `CONFIGURATION_TABLE_NAME`

## storage.py

```python
def parse_s3_uri(s3_uri: str) -> tuple[str, str]  # (bucket, key)
def read_s3_text(s3_uri: str, encoding: str = "utf-8") -> str
def read_s3_binary(s3_uri: str) -> bytes
def write_s3_text(s3_uri: str, content: str, content_type: str = "text/plain") -> None
def write_s3_binary(s3_uri: str, content: bytes, content_type: str = "application/octet-stream") -> None
def delete_s3_object(s3_uri: str) -> None
```

## ocr.py

```python
class OcrService:
    def __init__(region: str | None = None, backend: str = "textract", bedrock_model_id: str | None = None)
    def process_document(document: Document) -> Document
```

**Backends:** `textract`, `bedrock`

## bedrock.py

```python
class BedrockClient:
    def __init__(region: str | None = None, max_retries: int = 7, initial_backoff: float = 2)
    def invoke_model(model_id: str, system_prompt: str | list, content: list, temperature: float = 0.0) -> dict
    def generate_embeddings(text: str, model_id: str = "amazon.nova-embed-text-v1:0") -> list[float]
```

**Environment:** `AWS_REGION`

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

## image.py

```python
def validate_image_type(content_type: str | None, filename: str | None) -> tuple[bool, str]
def validate_image_size(size_bytes: int | None) -> tuple[bool, str]
def is_supported_image(filename: str) -> bool
def resize_image_for_bedrock(image_bytes: bytes, max_dimension: int = 2048) -> bytes
```

**Supported:** JPG, PNG, GIF, WEBP (max 10MB)

## appsync.py

```python
def publish_document_update(graphql_endpoint: str, document_id: str, filename: str, status: str, **kwargs) -> None
def publish_image_update(graphql_endpoint: str, image_id: str, filename: str, status: str, **kwargs) -> None
def publish_scrape_update(graphql_endpoint: str, job_id: str, base_url: str, **kwargs) -> None
```

## auth.py

```python
def check_public_access(event: dict, access_type: str, config_manager: ConfigurationManager) -> tuple[bool, str | None]
```

**Access types:** `chat`, `search`, `upload`, `image_upload`, `scrape`
