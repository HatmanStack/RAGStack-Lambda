# Metadata Filtering

This guide explains the metadata filtering feature in RAGStack-Lambda, which enables intelligent filtering of search results based on document metadata.

## Overview

Metadata filtering allows you to narrow down search results using document attributes like topic, document type, date range, and other extracted metadata. The system automatically discovers metadata patterns in your Knowledge Base and generates filter examples.

## How It Works

### 1. Metadata Extraction (During Ingestion)

When documents are ingested, the system:
- Extracts metadata using LLM-based classification
- Assigns values for keys like `topic`, `document_type`, `date_range`
- Stores metadata as inline attributes with each vector

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

## Using the Search Tab UI

### Metadata Analysis Panel

The Search tab includes a **Metadata Analysis** panel with:

1. **Analyze Button** - Triggers metadata analysis
2. **Metadata Key Statistics** (expandable) - Shows discovered keys
3. **Filter Examples** (expandable) - Shows AI-generated filters

### Running Analysis

1. Navigate to the **Search** tab
2. Click **Analyze Metadata** button
3. Wait for analysis to complete (typically 1-2 minutes)
4. View results in the expandable sections

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
- **Name**: Short descriptive title
- **Description**: What the filter does
- **Use Case**: When to use this filter
- **Filter JSON**: The actual filter expression

Click **View Filter** to see the full JSON, or **Apply** to use it.

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
| `filter_generation_enabled` | `true` | Enable/disable automatic filter generation |
| `filter_generation_model` | Claude Haiku | Model for filter generation |
| `filter_generation_max_keys` | `8` | Maximum keys to include in prompts |
| `metadata_extraction_enabled` | `true` | Enable/disable metadata extraction |
| `metadata_extraction_model` | Claude Haiku | Model for metadata extraction |
| `metadata_max_keys` | `8` | Maximum metadata keys per document |

See [CONFIGURATION.md](./CONFIGURATION.md) for details on updating these settings.

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
