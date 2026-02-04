# Metadata Filtering

This guide explains the metadata filtering feature in RAGStack-Lambda, which enables intelligent filtering of search results based on document metadata.

## Overview

Metadata filtering allows you to narrow down search results using document attributes like topic, document type, date range, and other extracted metadata. The system automatically discovers metadata patterns in your Knowledge Base and generates filter examples.

## How It Works

### 1. Metadata Extraction (During Ingestion)

When documents are ingested, an LLM analyzes the content to extract structured metadata:

- **Auto mode** (default): LLM decides which fields to extract based on content
- **Manual mode**: Only extracts keys you specify in `metadata_manual_keys`

Common extracted fields include `topic`, `document_type`, `date_range`, `location`. Metadata is stored with each document's vectors for filtered retrieval.

### 2. Metadata Analysis

The Metadata Analyzer Lambda:
- Samples vectors from your Knowledge Base (up to 1000)
- Counts occurrences of each metadata key
- Calculates occurrence rates (percentage of documents with each key)
- Collects sample values for each key
- Updates the Key Library with statistics

### 3. Filter Example Generation

After analysis, an LLM generates practical filter examples:
- Based on discovered metadata fields
- Uses S3 Vectors-compatible filter syntax
- Creates 5-8 examples with names, descriptions, and use cases

## Using the Settings Tab UI

### Metadata Analysis Panel

The Settings tab includes a **Metadata Analysis** panel with:

1. **Analyze Button** - Triggers metadata analysis
2. **Metadata Key Statistics** (expandable) - Shows discovered keys
3. **Filter Examples** (expandable) - Shows AI-generated filters

### Running Analysis

1. Navigate to the **Settings** tab
2. Scroll to the **Metadata Analysis** section
3. Click **Analyze Metadata** button
4. Wait for analysis to complete (typically 1-2 minutes)
5. View results in the expandable sections

### Understanding Key Statistics

| Column | Description |
|--------|-------------|
| Key Name | The metadata field name (e.g., `topic`) |
| Type | Data type: string, number, boolean, list |
| Occurrences | Number of documents with this key |
| Sample Values | Example values found in documents |
| Status | Active or inactive |

### Using Filter Examples

Each filter example includes:
- **Active**: Toggle to enable/disable this example
- **Name**: Short descriptive title
- **Description**: What the filter does
- **Use Case**: When to use this filter
- **Filter JSON**: The actual filter expression (click **View** to see)

### Enabling/Disabling Filter Examples

Filter examples use **few-shot learning** - enabled examples are fed to the LLM as reference patterns when generating filters from user queries.

- **Toggle Active**: Enable examples that match your use case, disable irrelevant ones
- **Improve accuracy**: Disabling poor examples helps the LLM generate better filters
- **Re-analysis**: When you run "Analyze Metadata" again, disabled examples are replaced with new ones while enabled examples are preserved

## Filter Syntax

RAGStack uses S3 Vectors filter syntax:

### Basic Operators

```json
// Equality
{"field": {"$eq": "value"}}

// Not equals
{"field": {"$ne": "value"}}

// In list
{"field": {"$in": ["value1", "value2"]}}
```

### Logical Operators

```json
// AND
{"$and": [
  {"topic": {"$eq": "genealogy"}},
  {"document_type": {"$eq": "pdf"}}
]}

// OR
{"$or": [
  {"topic": {"$eq": "genealogy"}},
  {"topic": {"$eq": "immigration"}}
]}
```

### Example Filters

**PDF Documents Only:**
```json
{"document_type": {"$eq": "pdf"}}
```

**Genealogy or Immigration Topics:**
```json
{"$or": [
  {"topic": {"$eq": "genealogy"}},
  {"topic": {"$eq": "immigration"}}
]}
```

## Configuration Options

The following configuration options control metadata filtering:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `metadata_extraction_enabled` | `true` | Enable/disable metadata extraction |
| `metadata_extraction_model` | `claude-haiku-4-5` | Model for metadata extraction |
| `metadata_extraction_mode` | `auto` | `auto`: LLM decides keys. `manual`: use specified keys |
| `metadata_manual_keys` | `[]` | Keys to extract in manual mode |
| `metadata_max_keys` | `8` | Maximum metadata keys per document |
| `filter_generation_enabled` | `true` | Enable/disable automatic filter generation |
| `filter_generation_model` | `claude-haiku-4-5` | Model for filter generation |
| `multislice_enabled` | `true` | Enable parallel filtered/unfiltered queries |
| `multislice_count` | `2` | Number of parallel retrieval slices (2-4) |
| `multislice_timeout_ms` | `5000` | Timeout per slice in milliseconds |
| `multislice_filtered_boost` | `1.25` | Score multiplier for filtered results (1.25 = 25% boost) |

See [CONFIGURATION.md](./CONFIGURATION.md) for details on updating these settings.

## Filtered Results Relevancy Boost

When multi-slice retrieval runs parallel queries, filtered results receive a score boost to improve ranking.

**How it works:**
- Filtered results match explicit query intent (e.g., "Pictures of Judy" → `people_mentioned: judy`)
- Unfiltered results provide baseline vector similarity
- Filtered results multiplied by `multislice_filtered_boost` (default 1.25 = 25% higher score)
- Results merged and deduplicated by URI, keeping highest score

**Example:**
- Unfiltered result: score 0.80 (generic match)
- Filtered result: score 0.75 → boosted to 0.94 (0.75 × 1.25)
- Final ranking: filtered result ranks first despite lower base score

**Configuration:** Set `multislice_filtered_boost` in Settings → Configuration (1.0 = no boost, 2.0 = double score).

---

### Why Filtered Queries Score Lower

Filtered results consistently score ~10% lower than unfiltered queries, even for identical content. This isn't a bug — it's an expected consequence of S3 Vectors' architecture.

**The Trade-Off:**
S3 Vectors reduces vector database costs by ~90% (billion vectors: $46/month vs $660+ on alternatives) using aggressive 4-bit Product Quantization. You trade precision for price.

**Two mechanisms cause the relevancy drop:**

1. **Quantization Noise**
   - S3 Vectors compresses vectors 64x using 4-bit quantization
   - Unfiltered search: Millions of candidates drown out approximation error
   - Filtered search: Smaller candidate pool amplifies quantization noise
   - The ~10% drop corresponds to the noise floor of 4-bit quantization

2. **Graph Disconnection (HNSW)**
   - S3 Vectors uses HNSW (Hierarchical Navigable Small World) graphs
   - Search traverses graph edges to find nearest matches
   - Filtering disables nodes, creating holes in the graph
   - "Bridge" edges to better regions are filtered out
   - Algorithm settles for local minima instead of optimal matches

**Why Not Re-Ranking?**
Cross-encoder re-ranking (e.g., Bedrock Rerank API) works well for text documents but degrades results for image-heavy knowledge bases. Re-rankers evaluate synthesized metadata text (e.g., "people: judy wilson, topic: family_photos"), not visual embeddings. The raw vector similarity scores from multimodal embeddings are better relevance signals.

**The Solution:**
The 1.25x boost normalizes scores without discarding valuable visual similarity information. It's a simple multiplier that compensates for quantization noise while preserving the semantic relationships captured by embeddings.

**When to Adjust:**
- **Increase boost (1.3-1.5):** Filtered results buried by visual similarity
- **Decrease boost (1.1-1.2):** Text-heavy KB where precision matters more
- **Disable boost (1.0):** Testing pure vector similarity without correction

## API Access

### GraphQL Queries

**Get Metadata Statistics:**
```graphql
query GetMetadataStats {
  getMetadataStats {
    keys {
      keyName
      dataType
      occurrenceCount
      sampleValues
    }
    totalKeys
    lastAnalyzed
  }
}
```

**Get Filter Examples:**
```graphql
query GetFilterExamples {
  getFilterExamples {
    examples {
      name
      description
      useCase
      filter
    }
    totalExamples
    lastGenerated
  }
}
```

### GraphQL Mutations

**Trigger Analysis (Admin Only):**
```graphql
mutation AnalyzeMetadata {
  analyzeMetadata {
    success
    vectorsSampled
    keysAnalyzed
    examplesGenerated
    executionTimeMs
    error
  }
}
```

## Troubleshooting

### No Keys Found

- Ensure documents have been ingested with metadata extraction enabled
- Check that `metadata_extraction_enabled` is `true`
- Verify documents contain extractable content

### Analysis Timeout

- Large Knowledge Bases may take longer
- Default timeout is 60 seconds
- For very large bases, wait and retry

### Filter Not Applying

- Verify the filter syntax is correct
- Check that the key exists in your documents
- Ensure the value matches exactly (case-sensitive)

### Empty Filter Examples

- Run the analyzer first to populate examples
- Check that metadata keys exist
- Verify LLM access for example generation

## Best Practices

1. **Run Analysis After Bulk Ingestion**: Analyze after adding significant new content
2. **Review Generated Filters**: AI-generated examples may need adjustment
3. **Use Specific Filters**: More specific filters yield better results
4. **Monitor Key Statistics**: Track which keys are most populated
5. **Combine Filters**: Use AND/OR for complex queries

## Known Limitations

1. Analysis is synchronous (no progress tracking)
2. Admin authentication required for analysis
3. Metrics don't auto-refresh after ingestion
4. Generated examples cannot be edited in UI
5. Maximum 1000 vectors sampled per analysis
