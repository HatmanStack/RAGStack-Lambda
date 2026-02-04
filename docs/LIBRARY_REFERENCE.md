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
def delete_s3_object(s3_uri: str) -> None
def generate_presigned_url(s3_uri: str, expiration: int = 3600) -> str
def write_metadata_to_s3(s3_uri: str, metadata: dict) -> None
def extract_filename_from_s3_uri(s3_uri: str) -> str
def get_file_type_from_filename(filename: str) -> str
def is_valid_uuid(value: str) -> bool
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
    def extract_text_from_response(response: dict) -> str
    def get_metering_data(response: dict) -> dict
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
def resize_image(image_bytes: bytes, max_dimension: int = 2048) -> bytes
def prepare_bedrock_image_attachment(image_bytes: bytes, content_type: str) -> dict
```

**Supported:** JPG, PNG, GIF, WebP, AVIF (max 10MB)

## appsync.py

```python
def publish_document_update(graphql_endpoint: str, document_id: str, filename: str, status: str, **kwargs) -> None
def publish_image_update(graphql_endpoint: str, image_id: str, filename: str, status: str, **kwargs) -> None
def publish_scrape_update(graphql_endpoint: str, job_id: str, base_url: str, **kwargs) -> None
def publish_reindex_update(graphql_endpoint: str, status: str, total_documents: int, processed_count: int, **kwargs) -> None
```

## auth.py

```python
def check_public_access(event: dict, access_type: str, config_manager: ConfigurationManager) -> tuple[bool, str | None]
```

**Access types:** `chat`, `search`, `upload`, `image_upload`, `scrape`

## key_library.py

```python
class KeyLibrary:
    def __init__(table_name: str | None = None, cache_ttl_seconds: int = 300) -> None
    def get_active_keys(use_cache: bool = True) -> list[dict[str, Any]]
    def get_key(key_name: str) -> dict[str, Any] | None
    def get_key_names() -> list[str]
    def upsert_key(key_name: str, data_type: str, sample_value: Any) -> None
    def deprecate_key(key_name: str) -> None
    def get_library_stats() -> dict[str, Any]
    def check_key_similarity(proposed_key: str, threshold: float = 0.8) -> list[dict]
```

**Environment:** `METADATA_KEY_LIBRARY_TABLE`

**Data types:** `string`, `number`, `boolean`, `list`

## filter_generator.py

```python
class FilterGenerator:
    def __init__(
        bedrock_client: BedrockClient | None = None,
        key_library: KeyLibrary | None = None,
        model_id: str | None = None,
        enabled: bool = True
    ) -> None
    def generate_filter(query: str, filter_examples: list[dict] | None = None) -> dict | None
```

**Returns:** S3 Vectors compatible filter dict, or `None` if no filter intent detected.

**Operators:** `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$exists`, `$and`, `$or`

## multislice_retriever.py

```python
class MultiSliceRetriever:
    def __init__(
        bedrock_agent_client=None,
        timeout_seconds: float = 5.0,
        max_slices: int = 3,
        enabled: bool = True,
        filtered_score_boost: float = 1.25
    ) -> None
    def retrieve(
        query: str,
        knowledge_base_id: str,
        data_source_id: str | None,
        metadata_filter: dict | None = None,
        num_results: int = 5
    ) -> list[dict]

def deduplicate_results(results: list[dict]) -> list[dict]
```

**Strategy:** Runs filtered + unfiltered slices in parallel, deduplicates by S3 URI keeping highest score.

## metadata_extractor.py

```python
class MetadataExtractor:
    def __init__(
        bedrock_client: BedrockClient | None = None,
        key_library: KeyLibrary | None = None,
        model_id: str | None = None,
        max_keys: int = 8,
        extraction_mode: str = "auto",
        manual_keys: list[str] | None = None
    ) -> None
    def extract_metadata(text: str, document_id: str, update_library: bool = True) -> dict[str, Any]
    def extract_from_caption(caption: str, document_id: str, filename: str | None = None, update_library: bool = True) -> dict[str, Any]

def infer_data_type(value: Any) -> str  # Returns: string | number | boolean | list
```

**Modes:** `auto` (LLM decides keys), `manual` (use only manual_keys)

## logging_utils.py

```python
def safe_log_event(event: dict[str, Any], sensitive_keys: frozenset[str] | None = None, max_depth: int = 5) -> dict[str, Any]
def log_summary(operation: str, *, success: bool = True, duration_ms: float | None = None, item_count: int | None = None, error: str | None = None, **kwargs) -> dict[str, Any]
```

**Purpose:** Mask sensitive data (tokens, credentials, user queries) before CloudWatch logging.

## image.py (ImageStatus)

```python
class ImageStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
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

## text_extractors/

Text extraction for non-OCR document types. Auto-detects format and extracts to markdown.

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

## sources.py

```python
def extract_source_url_from_content(content_text: str) -> str | None
def extract_image_caption_from_content(content_text: str) -> str | None
def extract_filename_from_frontmatter(content_text: str) -> str | None
def construct_image_uri_from_content_uri(content_s3_uri: str, content_text: str | None = None) -> str | None
```

**Purpose:** Extract metadata from vector content frontmatter for source attribution. `construct_image_uri_from_content_uri` converts caption/content.txt S3 URIs to the actual image file URI.

## scraper/

Web scraping module for ingesting documentation sites.

```python
from ragstack_common.scraper import ScrapeJob, ScrapeConfig, ScrapeStatus, ScrapeScope

class ScrapeStatus(str, Enum):
    PENDING, DISCOVERING, PROCESSING, COMPLETED, COMPLETED_WITH_ERRORS, FAILED, CANCELLED

class ScrapeScope(str, Enum):
    SUBPAGES  # Only paths under starting URL
    HOSTNAME  # Same subdomain
    DOMAIN    # All subdomains

@dataclass
class ScrapeConfig:
    max_pages: int = 100
    max_depth: int = 3
    scope: ScrapeScope = ScrapeScope.SUBPAGES
    include_patterns: list[str] = None
    exclude_patterns: list[str] = None
    scrape_mode: str = "auto"  # auto, fast, full
    cookies: str | None = None
    force_rescrape: bool = False

@dataclass
class ScrapeJob:
    job_id: str
    base_url: str
    status: ScrapeStatus
    config: ScrapeConfig
    total_urls: int
    processed_count: int
    failed_count: int
```

**Architecture:** Discovery via SQS, HTTP-first fetching with Playwright fallback, SHA-256 content deduplication.

## ingestion.py

Bedrock Knowledge Base ingestion with retry logic for concurrent API conflicts.

```python
def start_ingestion_with_retry(kb_id: str, ds_id: str, max_retries: int = 5, base_delay: float = 5, client=None) -> dict
def ingest_documents_with_retry(kb_id: str, ds_id: str, documents: list[dict], max_retries: int = 5, base_delay: float = 2, client=None) -> dict
def check_document_status(kb_id: str, ds_id: str, s3_uri: str, sleep_first: bool = True, client=None) -> str
def batch_check_document_statuses(kb_id: str, ds_id: str, s3_uris: list[str], batch_size: int = 25, client=None) -> dict[str, str]
```

**Environment:** `AWS_REGION`

**Retry behavior:** Exponential backoff when IngestDocuments/StartIngestionJob conflict.

## transcribe_client.py

AWS Transcribe client wrapper for batch transcription jobs.

```python
class TranscribeClient:
    def __init__(region: str | None = None, language_code: str = "en-US", enable_speaker_diarization: bool = True)
    def start_transcription_job(document_id: str, input_s3_uri: str, output_bucket: str) -> str  # Returns job_name
    def get_job_status(job_name: str) -> str  # QUEUED, IN_PROGRESS, COMPLETED, FAILED
    def get_transcript_result(job_name: str) -> dict
    def wait_for_completion(job_name: str, timeout_seconds: int = 1800, poll_interval: int = 30) -> dict
    def parse_transcript_with_timestamps(result: dict) -> list[dict]  # Returns word-level timestamps
```

**Environment:** `AWS_REGION`

**Supported formats:** MP4, WebM, MP3, WAV, M4A, OGG, FLAC

## media_segmenter.py

Segments transcripts into time-aligned chunks for embedding and search.

```python
class MediaSegmenter:
    def __init__(segment_duration: int = 30)
    def segment_transcript(words: list[dict], total_duration: float) -> list[dict]
```

**Segment fields:** `text`, `start_time`, `end_time`, `speaker` (if diarization enabled)

**Default segment:** 30 seconds (configurable via `media_segment_duration_seconds`)

## metadata_normalizer.py

Normalizes metadata for S3 Vectors storage with smart array expansion.

```python
def expand_to_searchable_array(value: str, min_word_length: int = 3) -> list[str]
def normalize_metadata_for_s3(metadata: dict[str, Any]) -> dict[str, Any]
def reduce_metadata(metadata: dict[str, Any], reduction_level: int = 1, core_keys: frozenset[str] | None = None) -> dict[str, Any]
```

**Expansion:** "chicago, illinois" → ["chicago, illinois", "chicago", "illinois"]

**Reduction levels:** 1 = no reduction, 2 = truncate arrays, 3 = core keys only

## exceptions.py

Media processing exception hierarchy.

```python
class MediaProcessingError(Exception)  # Base exception
class TranscriptionError(MediaProcessingError)  # AWS Transcribe errors
class UnsupportedMediaFormatError(MediaProcessingError)  # Invalid format
class MediaDurationExceededError(MediaProcessingError)  # Too long
class MediaFileSizeExceededError(MediaProcessingError)  # Too large
class AudioExtractionError(MediaProcessingError)  # Audio extraction failed
class SegmentationError(MediaProcessingError)  # Segmentation failed
```

## demo_mode.py

```python
def check_demo_mode_limit(operation: str, user_id: str | None = None) -> tuple[bool, str | None]
```

Check if operation allowed under demo mode restrictions.

**Operations:** `upload`, `chat`, `reindex`, `reprocess`, `delete`

**Returns:** `(allowed: bool, error_message: str | None)`

---

## filter_examples.py

```python
class FilterExampleManager:
    def __init__(table_name: str | None = None) -> None
    def get_examples(active_only: bool = True) -> list[dict]
    def upsert_example(name: str, description: str, use_case: str, filter: dict, active: bool = True) -> None
    def delete_example(name: str) -> None
```

Manage metadata filter examples for few-shot learning.

**Environment:** `METADATA_KEY_LIBRARY_TABLE`
