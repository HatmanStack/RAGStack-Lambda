# Retrieval Module

Knowledge Base retrieval and ingestion functions.

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

## Overview

`MultiSliceRetriever` improves retrieval quality by running parallel queries:
1. **Unfiltered query**: Baseline vector similarity
2. **Filtered query**: Query with metadata filter applied
3. **Boost filtered results**: Apply score multiplier to filtered results
4. **Merge and deduplicate**: Combine results, keep highest score per document

## Usage

### Initialize

```python
from ragstack_common.multislice_retriever import MultiSliceRetriever

# Default config
retriever = MultiSliceRetriever()

# Custom config
retriever = MultiSliceRetriever(
    timeout_seconds=10.0,
    max_slices=2,
    enabled=True,
    filtered_score_boost=1.3  # 30% boost
)

# Disable multi-slice (fallback to single query)
retriever = MultiSliceRetriever(enabled=False)
```

### Retrieve Documents

```python
from ragstack_common.multislice_retriever import MultiSliceRetriever

retriever = MultiSliceRetriever()

# Simple query (no filter)
results = retriever.retrieve(
    query="What is RAGStack?",
    knowledge_base_id="KB123",
    data_source_id="DS456",
    num_results=5
)

# Query with metadata filter
metadata_filter = {
    "topic": {"$eq": "genealogy"}
}
results = retriever.retrieve(
    query="Pictures of Judy",
    knowledge_base_id="KB123",
    data_source_id="DS456",
    metadata_filter=metadata_filter,
    num_results=10
)

# Process results
for result in results:
    print(f"Score: {result['score']:.3f}")
    print(f"Content: {result['content'][:100]}...")
    print(f"URI: {result['location']['s3Location']['uri']}")
```

### Result Format

```python
{
    "score": 0.85,  # Relevance score (boosted if filtered)
    "content": "Extracted text content...",
    "location": {
        "type": "S3",
        "s3Location": {
            "uri": "s3://bucket/path/content.txt"
        }
    },
    "metadata": {
        "topic": "genealogy",
        "x-amz-bedrock-kb-data-source-id": "DS456"
    }
}
```

### Deduplicate Results

```python
from ragstack_common.multislice_retriever import deduplicate_results

# Manually deduplicate result list
filtered_results = [...]
unfiltered_results = [...]
all_results = filtered_results + unfiltered_results

unique_results = deduplicate_results(all_results)
# Keeps highest score for each unique S3 URI
```

## Filtered Score Boost

When multi-slice retrieval runs parallel queries, filtered results receive a score boost:

**How it works:**
1. Filtered results match explicit query intent (metadata filter)
2. Unfiltered results provide baseline vector similarity
3. Filtered scores multiplied by `filtered_score_boost` (default 1.25)
4. Results merged and deduplicated, keeping highest score

**Example:**
```python
# Unfiltered result: score 0.80
# Filtered result: score 0.75 → boosted to 0.94 (0.75 × 1.25)
# Final ranking: filtered result ranks first despite lower base score
```

**Configuration:**
- **Increase boost (1.3-1.5)**: Filtered results buried by visual similarity
- **Decrease boost (1.1-1.2)**: Text-heavy KB where precision matters
- **Disable boost (1.0)**: Testing pure vector similarity

See [METADATA_FILTERING.md](../METADATA_FILTERING.md) for technical details on S3 Vectors quantization.

## ingestion.py

```python
def start_ingestion_with_retry(kb_id: str, ds_id: str, max_retries: int = 5, base_delay: float = 5, client=None) -> dict
def ingest_documents_with_retry(kb_id: str, ds_id: str, documents: list[dict], max_retries: int = 5, base_delay: float = 2, client=None) -> dict
def check_document_status(kb_id: str, ds_id: str, s3_uri: str, sleep_first: bool = True, client=None) -> str
def batch_check_document_statuses(kb_id: str, ds_id: str, s3_uris: list[str], batch_size: int = 25, client=None) -> dict[str, str]
```

**Environment:** `AWS_REGION`

**Retry behavior:** Exponential backoff when IngestDocuments/StartIngestionJob conflict.

### Start Full Ingestion

```python
from ragstack_common.ingestion import start_ingestion_with_retry

# Trigger full KB sync
response = start_ingestion_with_retry(
    kb_id="KB123",
    ds_id="DS456",
    max_retries=5,
    base_delay=5.0
)

ingestion_job_id = response["ingestionJobId"]
print(f"Started job: {ingestion_job_id}")
```

**Returns:** `{"ingestionJobId": "...", "status": "STARTING"}`

### Ingest Specific Documents

```python
from ragstack_common.ingestion import ingest_documents_with_retry

documents = [
    {"dataSourceId": "DS456", "s3": {"uri": "s3://bucket/doc1.txt"}},
    {"dataSourceId": "DS456", "s3": {"uri": "s3://bucket/doc2.txt"}},
]

response = ingest_documents_with_retry(
    kb_id="KB123",
    ds_id="DS456",
    documents=documents
)

print(f"Ingestion job: {response['ingestionJobId']}")
```

### Check Document Status

```python
from ragstack_common.ingestion import check_document_status

status = check_document_status(
    kb_id="KB123",
    ds_id="DS456",
    s3_uri="s3://bucket/document.txt"
)

print(f"Status: {status}")  # INDEXED, PARTIALLY_INDEXED, FAILED, etc.
```

### Batch Check Document Statuses

```python
from ragstack_common.ingestion import batch_check_document_statuses

s3_uris = [
    "s3://bucket/doc1.txt",
    "s3://bucket/doc2.txt",
    "s3://bucket/doc3.txt"
]

statuses = batch_check_document_statuses(
    kb_id="KB123",
    ds_id="DS456",
    s3_uris=s3_uris,
    batch_size=25
)

for uri, status in statuses.items():
    print(f"{uri}: {status}")
```

**Returns:** `{s3_uri: status}` dict

## Error Handling

### Retrieval Errors

```python
from ragstack_common.multislice_retriever import MultiSliceRetriever

retriever = MultiSliceRetriever(timeout_seconds=10.0)

try:
    results = retriever.retrieve(...)
except Exception as e:
    # Timeout, KB not found, permission denied, etc.
    logger.error(f"Retrieval failed: {e}")
    results = []
```

### Ingestion Conflicts

```python
from ragstack_common.ingestion import start_ingestion_with_retry
import botocore.exceptions

try:
    response = start_ingestion_with_retry(kb_id, ds_id)
except botocore.exceptions.ClientError as e:
    if e.response['Error']['Code'] == 'ConflictException':
        # Retries exhausted, still conflicting job
        logger.error("Ingestion already in progress")
    else:
        raise
```

## Best Practices

1. **Enable multi-slice by default** - Better results with minimal latency cost
2. **Tune boost value per use case** - Image-heavy KBs may need higher boost
3. **Handle timeouts gracefully** - Network issues can cause retrieval failures
4. **Wait for ingestion completion** - Don't query immediately after ingestion
5. **Batch status checks** - More efficient than individual checks

## Performance

### Retrieval
- **Single query**: ~200-500ms
- **Multi-slice (2 parallel)**: ~300-700ms (not 2x due to parallelism)
- **Timeout**: Configurable, default 5 seconds per slice

### Ingestion
- **StartIngestion**: ~1-2 seconds
- **IngestDocuments**: ~100-500ms per document
- **Sync completion**: Minutes to hours (depends on document count)

## See Also

- [Metadata Filtering](../METADATA_FILTERING.md) - Filter syntax and configuration
- [Configuration](../CONFIGURATION.md#query-time-filtering) - Retrieval settings
