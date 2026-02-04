# Metadata Module

Metadata extraction, normalization, and filtering for enhanced search and retrieval.

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

## Overview

`MetadataExtractor` uses LLMs to extract structured metadata from document text or image captions. Metadata enables filtered search (e.g., "financial documents from 2023"). Works with `KeyLibrary` to maintain consistent metadata keys across documents.

## Usage

### Initialize

```python
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.bedrock import BedrockClient
from ragstack_common.key_library import KeyLibrary

# Auto mode: LLM decides relevant keys
extractor = MetadataExtractor(
    bedrock_client=BedrockClient(),
    key_library=KeyLibrary(),
    model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
    max_keys=8,
    extraction_mode="auto"
)

# Manual mode: Extract only specified keys
extractor = MetadataExtractor(
    extraction_mode="manual",
    manual_keys=["topic", "date_range", "location", "document_type"]
)
```

### Extract from Document Text

```python
text = """
Quarterly earnings report for Q4 2023. Revenue increased 15% to $2.4M.
Key markets: Chicago, New York. Focus areas: SaaS products, enterprise sales.
"""

metadata = extractor.extract_metadata(
    text=text,
    document_id="doc-123",
    update_library=True  # Add new keys to KeyLibrary
)

# Example result:
# {
#     "topic": "financial",
#     "date_range": "2023-Q4",
#     "location": ["chicago", "new york"],
#     "document_type": "earnings_report"
# }
```

### Extract from Image Caption

```python
caption = "Chicago skyline at sunset, 1995. Photo by John Smith."

metadata = extractor.extract_from_caption(
    caption=caption,
    document_id="img-456",
    filename="chicago-skyline.jpg",
    update_library=True
)

# Example result:
# {
#     "location": "chicago",
#     "year": 1995,
#     "photographer": "john smith",
#     "subject": "skyline"
# }
```

### Disable Library Updates

```python
# Extract without updating KeyLibrary (read-only)
metadata = extractor.extract_metadata(
    text=text,
    document_id="doc-789",
    update_library=False
)
```

## metadata_normalizer.py

```python
def expand_to_searchable_array(value: str, min_word_length: int = 3) -> list[str]
def normalize_metadata_for_s3(metadata: dict[str, Any]) -> dict[str, Any]
def reduce_metadata(metadata: dict[str, Any], reduction_level: int = 1, core_keys: frozenset[str] | None = None) -> dict[str, Any]
```

**Expansion:** "chicago, illinois" → ["chicago, illinois", "chicago", "illinois"]

**Reduction levels:** 1 = no reduction, 2 = truncate arrays, 3 = core keys only

### Expand to Searchable Array

```python
from ragstack_common.metadata_normalizer import expand_to_searchable_array

# Expand comma-separated values
expanded = expand_to_searchable_array("chicago, illinois")
# Returns: ["chicago, illinois", "chicago", "illinois"]

# Expand space-separated values (words >= 3 chars)
expanded = expand_to_searchable_array("New York City", min_word_length=3)
# Returns: ["new york city", "new", "york", "city"]

# Skip short words
expanded = expand_to_searchable_array("to be or not to be", min_word_length=3)
# Returns: ["to be or not to be", "not"]
```

**Use case:** Enable partial matching on multi-part values (search "chicago" matches "chicago, illinois")

### Normalize Metadata for S3

```python
from ragstack_common.metadata_normalizer import normalize_metadata_for_s3

raw_metadata = {
    "topic": "financial",
    "locations": "chicago, new york",  # Will be expanded
    "year": 2023,
    "revenue": 2400000.50,
    "active": True
}

normalized = normalize_metadata_for_s3(raw_metadata)

# Result:
# {
#     "topic": "financial",
#     "locations": ["chicago, new york", "chicago", "new york"],
#     "year": 2023,
#     "revenue": 2400000.5,
#     "active": True
# }
```

**Transformations:**
- String values: Expand to arrays using `expand_to_searchable_array`
- Numbers/booleans: Preserved as-is
- Lists: Preserved as-is
- Nested dicts: Flattened or stringified

### Reduce Metadata

```python
from ragstack_common.metadata_normalizer import reduce_metadata

full_metadata = {
    "topic": "financial",
    "locations": ["chicago", "new york", "san francisco", "seattle", "boston"],
    "tags": ["q4", "earnings", "revenue", "growth", "sales"],
    "year": 2023,
    "document_type": "report"
}

# Level 1: No reduction (default)
reduced = reduce_metadata(full_metadata, reduction_level=1)
# Returns: original metadata unchanged

# Level 2: Truncate long arrays (keep first 3 items)
reduced = reduce_metadata(full_metadata, reduction_level=2)
# {
#     "topic": "financial",
#     "locations": ["chicago", "new york", "san francisco"],
#     "tags": ["q4", "earnings", "revenue"],
#     "year": 2023,
#     "document_type": "report"
# }

# Level 3: Core keys only
core_keys = frozenset(["topic", "year", "document_type"])
reduced = reduce_metadata(full_metadata, reduction_level=3, core_keys=core_keys)
# {
#     "topic": "financial",
#     "year": 2023,
#     "document_type": "report"
# }
```

**Use case:** Reduce metadata size when approaching DynamoDB or S3 limits

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

### Initialize

```python
from ragstack_common.key_library import KeyLibrary

# Auto-detect table from environment
library = KeyLibrary()

# Specify table and cache TTL
library = KeyLibrary(
    table_name="RAGStack-project-metadata-keys-abc123",
    cache_ttl_seconds=600  # 10 minute cache
)
```

### Get Active Keys

```python
# Get cached keys (fast)
keys = library.get_active_keys(use_cache=True)

# Force refresh from DynamoDB
keys = library.get_active_keys(use_cache=False)

# Example result:
# [
#     {
#         "key_name": "topic",
#         "data_type": "string",
#         "usage_count": 150,
#         "sample_value": "financial",
#         "is_active": True
#     },
#     {
#         "key_name": "year",
#         "data_type": "number",
#         "usage_count": 200,
#         "sample_value": 2023,
#         "is_active": True
#     }
# ]
```

### Get Single Key

```python
key = library.get_key("topic")

# Returns:
# {
#     "key_name": "topic",
#     "data_type": "string",
#     "usage_count": 150,
#     "sample_value": "financial",
#     "is_active": True
# }

# Returns None if not found
missing = library.get_key("nonexistent")  # None
```

### Get Key Names

```python
key_names = library.get_key_names()
# Returns: ["topic", "year", "location", "document_type", ...]
```

### Add or Update Key

```python
# Add new key
library.upsert_key(
    key_name="photographer",
    data_type="string",
    sample_value="john smith"
)

# Update existing key (increments usage_count)
library.upsert_key(
    key_name="topic",
    data_type="string",
    sample_value="medical"
)
```

**Note:** `upsert_key` increments `usage_count` on each call, enabling popularity tracking.

### Deprecate Key

```python
# Mark key as inactive (doesn't delete)
library.deprecate_key("old_field_name")
```

**Use case:** Retire keys without breaking existing filters

### Get Statistics

```python
stats = library.get_library_stats()

# Returns:
# {
#     "total_keys": 25,
#     "active_keys": 22,
#     "deprecated_keys": 3,
#     "by_data_type": {
#         "string": 15,
#         "number": 5,
#         "boolean": 2,
#         "list": 3
#     }
# }
```

### Check Key Similarity

```python
# Check for similar existing keys (prevent duplicates)
similar = library.check_key_similarity("photo_grapher", threshold=0.8)

# Returns:
# [
#     {
#         "key_name": "photographer",
#         "similarity": 0.92
#     }
# ]
```

**Use case:** Warn users before creating keys with similar names to existing ones

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

### Initialize

```python
from ragstack_common.filter_generator import FilterGenerator
from ragstack_common.bedrock import BedrockClient
from ragstack_common.key_library import KeyLibrary

generator = FilterGenerator(
    bedrock_client=BedrockClient(),
    key_library=KeyLibrary(),
    model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
    enabled=True
)
```

### Generate Filter from Query

```python
# Simple filter
query = "show me financial documents from 2023"
filter_dict = generator.generate_filter(query)

# Returns:
# {
#     "$and": [
#         {"topic": {"$eq": "financial"}},
#         {"year": {"$eq": 2023}}
#     ]
# }

# Range filter
query = "documents from 2020 to 2023"
filter_dict = generator.generate_filter(query)

# Returns:
# {
#     "$and": [
#         {"year": {"$gte": 2020}},
#         {"year": {"$lte": 2023}}
#     ]
# }

# No filter intent
query = "what is quantum computing?"
filter_dict = generator.generate_filter(query)
# Returns: None
```

### With Custom Examples

```python
from ragstack_common.filter_examples import FilterExampleManager

# Get examples from DynamoDB
example_manager = FilterExampleManager()
examples = example_manager.get_examples(active_only=True)

# Generate filter with examples for few-shot learning
filter_dict = generator.generate_filter(query, filter_examples=examples)
```

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

### Initialize

```python
from ragstack_common.filter_examples import FilterExampleManager

manager = FilterExampleManager()
```

### Get Examples

```python
# Get active examples only
examples = manager.get_examples(active_only=True)

# Get all examples (including inactive)
all_examples = manager.get_examples(active_only=False)

# Example result:
# [
#     {
#         "name": "financial-2023",
#         "description": "Financial documents from 2023",
#         "use_case": "Find quarterly reports",
#         "filter": {"$and": [{"topic": {"$eq": "financial"}}, {"year": {"$eq": 2023}}]},
#         "active": True
#     }
# ]
```

### Add or Update Example

```python
manager.upsert_example(
    name="chicago-photos",
    description="Photos taken in Chicago",
    use_case="Find Chicago images",
    filter={"location": {"$eq": "chicago"}},
    active=True
)
```

### Delete Example

```python
manager.delete_example("old-example-name")
```

## Data Type Inference

```python
from ragstack_common.metadata_extractor import infer_data_type

# String
infer_data_type("financial")  # "string"

# Number
infer_data_type(2023)  # "number"
infer_data_type(3.14)  # "number"

# Boolean
infer_data_type(True)  # "boolean"

# List
infer_data_type(["a", "b", "c"])  # "list"
```

## Error Handling

```python
from ragstack_common.metadata_extractor import MetadataExtractor
from ragstack_common.key_library import KeyLibrary

try:
    extractor = MetadataExtractor()
    metadata = extractor.extract_metadata(text, document_id)
except Exception as e:
    logger.error(f"Metadata extraction failed: {e}")
    metadata = {}  # Continue with empty metadata

try:
    library = KeyLibrary()
    keys = library.get_active_keys()
except Exception as e:
    logger.error(f"KeyLibrary error: {e}")
    keys = []  # Continue without key library
```

## Best Practices

1. **Extraction Mode**: Use `auto` for diverse document types, `manual` for standardized schemas
2. **Library Updates**: Enable `update_library=True` during ingestion, disable during queries
3. **Caching**: KeyLibrary caches for 5 minutes by default - adjust `cache_ttl_seconds` based on update frequency
4. **Key Similarity**: Check similarity before creating new keys to avoid duplicates
5. **Normalization**: Always normalize metadata before storing in S3 for consistent search
6. **Reduction**: Use reduction when metadata grows large (approaching DynamoDB 400KB limit)
7. **Filter Generation**: Provide examples for better filter accuracy in domain-specific use cases

## See Also

- [RETRIEVAL.md](./RETRIEVAL.md) - Multi-slice retrieval with metadata filters
- [CONFIGURATION.md](./CONFIGURATION.md) - Configuration for metadata extraction
- [constants.py](./UTILITIES.md#constants) - Metadata-related constants
