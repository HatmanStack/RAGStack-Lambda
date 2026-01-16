# Code Consolidation Plan

## Status: COMPLETE

## Priority 0 - High Impact, Create First

### 1. Create `lib/ragstack_common/ingestion.py`

Consolidate these duplicated functions:

| Function | Source Files |
|----------|--------------|
| `start_ingestion_with_retry()` | process_image, ingest_media, ingest_visual |
| `check_document_status()` | ingest_to_kb, ingest_media |
| `batch_check_document_statuses()` | ingest_media |

**Target API:**
```python
class KnowledgeBaseIngester:
    def __init__(self, bedrock_agent_client=None):
        ...
    def start_with_retry(self, kb_id: str, ds_id: str, max_retries: int = 5) -> str
    def check_status(self, kb_id: str, ds_id: str, s3_uri: str) -> str
    def batch_check_statuses(self, kb_id: str, ds_id: str, s3_uris: list[str]) -> dict[str, str]
```

**Files to update after creation:**
- `src/lambda/process_image/index.py` - remove `start_ingestion_with_retry()`
- `src/lambda/ingest_media/index.py` - remove `start_ingestion_with_retry()`, `check_document_status()`, `batch_check_document_statuses()`
- `src/lambda/ingest_visual/index.py` - remove `start_ingestion_with_retry()`
- `src/lambda/ingest_to_kb/index.py` - remove `check_document_status()`

### 2. Add to `lib/ragstack_common/storage.py`

| Function | Source Files |
|----------|--------------|
| `generate_presigned_url()` | query_kb, search_kb |
| `write_metadata_to_s3()` | ingest_to_kb, ingest_media, process_image, reindex_kb |

### 3. Enforce existing `parse_s3_uri()` from storage.py

Remove duplicates from:
- `src/lambda/search_kb/index.py`
- `src/lambda/process_text/index.py`
- `src/lambda/detect_file_type/index.py`
- `src/lambda/move_video/index.py`

---

## Priority 1 - Medium Impact

### 4. Add utilities to `lib/ragstack_common/storage.py`

| Function | Source Files |
|----------|--------------|
| `is_valid_uuid()` | appsync_resolvers, process_image |
| `extract_filename_from_path()` | process_text, process_media, detect_file_type |
| `get_file_type_from_filename()` | ingest_to_kb, process_image |

### 5. Move `reduce_metadata()` to `lib/ragstack_common/metadata_normalizer.py`

Source files: ingest_to_kb, ingest_media

---

## Priority 2 - Architectural (Evaluated)

### 6. ~~Consider merging `search_kb` into `query_kb`~~ - NOT NEEDED

**Decision:** After extracting shared utilities (P0-P1), the remaining code in each Lambda
is genuinely different:
- `query_kb`: conversation history, LLM generation, quota tracking
- `search_kb`: stateless vector search, simpler response format

Merging would add conditional complexity without meaningful benefit. The utility
extraction was the right consolidation approach.

---

## Implementation Checklist

- [x] P0.1: Create `lib/ragstack_common/ingestion.py` (commit 89f1f1f)
- [x] P0.2: Add `generate_presigned_url()` to storage.py
- [x] P0.3: Add `write_metadata_to_s3()` to storage.py
- [x] P0.4: Enforce `parse_s3_uri()` usage (removed 2 duplicates: search_kb, move_video)
- [x] P1.1: Add `is_valid_uuid()` to storage.py
- [x] P1.2: Add `extract_filename_from_s3_uri()` and `get_file_type_from_filename()` to storage.py
- [x] P1.3: Move `reduce_metadata()` to metadata_normalizer.py
- [x] P2.1: Evaluate search_kb → query_kb merge → NOT NEEDED (utilities extracted instead)

---

## Actual Impact

- **~650 lines of duplicate code eliminated** (exceeded estimate)
- Centralized retry/backoff tuning for Bedrock APIs
- Smaller Lambda packages → faster cold starts
- Single maintenance point for S3/metadata operations
- 4 commits total (89f1f1f, 06d6f11, 9fefc0f, 7ab1dea)
