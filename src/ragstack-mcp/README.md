# RAGStack MCP Server

MCP (Model Context Protocol) server for RAGStack knowledge bases. Enables AI assistants to search, chat, upload, and scrape your knowledge base.

## Installation

```bash
# Using uvx (recommended - no install needed)
uvx ragstack-mcp

# Or install globally
pip install ragstack-mcp
```

## Configuration

Get your GraphQL endpoint and API key from the RAGStack dashboard:
**Settings → API Key**

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "ragstack-kb": {
      "command": "uvx",
      "args": ["ragstack-mcp"],
      "env": {
        "RAGSTACK_GRAPHQL_ENDPOINT": "https://xxx.appsync-api.us-east-1.amazonaws.com/graphql",
        "RAGSTACK_API_KEY": "da2-xxxxxxxxxxxx"
      }
    }
  }
}
```

### Amazon Q CLI

Edit `~/.aws/amazonq/mcp.json`:

```json
{
  "mcpServers": {
    "ragstack-kb": {
      "command": "uvx",
      "args": ["ragstack-mcp"],
      "env": {
        "RAGSTACK_GRAPHQL_ENDPOINT": "https://xxx.appsync-api.us-east-1.amazonaws.com/graphql",
        "RAGSTACK_API_KEY": "da2-xxxxxxxxxxxx"
      }
    }
  }
}
```

### Cursor

Open **Settings → MCP Servers → Add Server**, or edit `.cursor/mcp.json`:

```json
{
  "ragstack-kb": {
    "command": "uvx",
    "args": ["ragstack-mcp"],
    "env": {
      "RAGSTACK_GRAPHQL_ENDPOINT": "https://xxx.appsync-api.us-east-1.amazonaws.com/graphql",
      "RAGSTACK_API_KEY": "da2-xxxxxxxxxxxx"
    }
  }
}
```

### VS Code + Cline

Edit `.vscode/cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "ragstack-kb": {
      "command": "uvx",
      "args": ["ragstack-mcp"],
      "env": {
        "RAGSTACK_GRAPHQL_ENDPOINT": "https://xxx.appsync-api.us-east-1.amazonaws.com/graphql",
        "RAGSTACK_API_KEY": "da2-xxxxxxxxxxxx"
      }
    }
  }
}
```

### VS Code + Continue

Edit `~/.continue/config.json`, add to `mcpServers` array:

```json
{
  "mcpServers": [
    {
      "name": "ragstack-kb",
      "command": "uvx",
      "args": ["ragstack-mcp"],
      "env": {
        "RAGSTACK_GRAPHQL_ENDPOINT": "https://xxx.appsync-api.us-east-1.amazonaws.com/graphql",
        "RAGSTACK_API_KEY": "da2-xxxxxxxxxxxx"
      }
    }
  ]
}
```

## Available Tools

### search_knowledge_base

Search for relevant documents in the knowledge base.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | The search query |
| `max_results` | int | No | 5 | Maximum results to return |

### chat_with_knowledge_base

Ask questions and get AI-generated answers with source citations.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Your question |
| `conversation_id` | string | No | null | ID to maintain conversation context |

### start_scrape_job

Scrape a website into the knowledge base.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | Starting URL to scrape |
| `max_pages` | int | No | 50 | Maximum pages to scrape |
| `max_depth` | int | No | 3 | How deep to follow links (0 = start page only) |
| `scope` | string | No | "HOSTNAME" | `SUBPAGES`, `HOSTNAME`, or `DOMAIN` |
| `include_patterns` | list[str] | No | null | Only scrape URLs matching these glob patterns |
| `exclude_patterns` | list[str] | No | null | Skip URLs matching these glob patterns |
| `scrape_mode` | string | No | "AUTO" | `AUTO`, `FAST` (HTTP only), or `FULL` (browser) |
| `cookies` | string | No | null | Cookie string for authenticated sites |
| `force_rescrape` | bool | No | false | Re-scrape even if content unchanged |

**Scope values:**
- `SUBPAGES` - Only URLs under the starting path
- `HOSTNAME` - All pages on the same subdomain
- `DOMAIN` - All subdomains of the domain

**Scrape mode values:**
- `AUTO` - Try fast mode, fall back to full for SPAs
- `FAST` - HTTP only, faster but may miss JavaScript content
- `FULL` - Uses headless browser, handles all JavaScript

### get_scrape_job_status

Check the status of a scrape job.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | string | Yes | The scrape job ID |

### list_scrape_jobs

List recent scrape jobs.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | int | No | 10 | Maximum jobs to return |

### upload_document_url

Get a presigned URL to upload a document.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Name of the file (e.g., 'report.pdf') |

### upload_image_url

Get a presigned URL to upload an image (step 1 of image upload workflow).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Name of the image file (e.g., 'photo.jpg') |

Supported formats: JPEG, PNG, GIF, WebP, AVIF, BMP, TIFF

### generate_image_caption

Generate an AI caption for an uploaded image using a vision model (step 2, optional).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `s3_uri` | string | Yes | S3 URI returned by upload_image_url |

### submit_image

Finalize an image upload and trigger indexing (step 3).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image_id` | string | Yes | - | Image ID from upload_image_url |
| `caption` | string | No | null | Primary caption |
| `user_caption` | string | No | null | User-provided caption |
| `ai_caption` | string | No | null | AI-generated caption |

---

## Configuration Tools (Read-Only)

### get_configuration

Get all current RAGStack configuration settings organized by category.

Returns settings for:
- **Chat:** Models, quotas, system prompt, document access
- **Metadata Extraction:** Enabled, model, mode (auto/manual), max keys
- **Query-Time Filtering:** Filter generation, multi-slice retrieval settings
- **Public Access:** Which endpoints allow unauthenticated access
- **Document Processing:** OCR backend, image caption prompt
- **Budget:** Alert thresholds

**Note:** Read-only. To modify settings, use the admin dashboard (Cognito auth required).

---

## Metadata Analysis Tools

These tools help understand and optimize metadata extraction and filtering.

### get_metadata_stats

Get statistics about metadata keys extracted from documents.

Returns key names, data types, occurrence counts, sample values, and status.

### get_filter_examples

Get AI-generated filter examples for metadata-based search queries.

Returns filter patterns with name, description, use case, and JSON filter syntax.

**Filter syntax reference:**
- Basic operators: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$exists`
- Logical operators: `$and`, `$or`
- Example: `{"topic": {"$eq": "genealogy"}}`

### get_key_library

Get the complete metadata key library with all discovered keys.

Returns all keys available for filtering with data types and sample values.

### check_key_similarity

Check if a proposed metadata key is similar to existing keys.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `key_name` | string | Yes | - | Proposed key name to check |
| `threshold` | float | No | 0.8 | Similarity threshold (0.0-1.0) |

Use this before adding documents with new keys to avoid duplicates.

### analyze_metadata

Trigger metadata analysis to discover keys and generate filter examples.

**Note:** This is a long-running operation (1-2 minutes). It samples up to 1000 vectors and uses LLM analysis.

Run this after ingesting new documents or when filter generation isn't working as expected.

---

## Usage Examples

Once configured, just ask your AI assistant naturally:

**Search & Chat:**
- "Search my knowledge base for authentication best practices"
- "What does our documentation say about API rate limits?"

**Web Scraping:**
- "Scrape the React docs at react.dev/reference"
- "Check the status of my scrape job"

**Document & Image Upload:**
- "Upload a new document called quarterly-report.pdf"
- "Upload this image and generate a caption for it"

**Metadata Analysis:**
- "What metadata keys are available for filtering?"
- "Analyze the metadata in my knowledge base"
- "Show me the filter examples"
- "Check if 'author' is similar to any existing keys"

**Configuration:**
- "What are my current RAGStack settings?"
- "What model is being used for chat?"
- "Is multi-slice retrieval enabled?"
- "What are my quota limits?"

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RAGSTACK_GRAPHQL_ENDPOINT` | Yes | Your RAGStack GraphQL API URL |
| `RAGSTACK_API_KEY` | Yes | Your RAGStack API key |

## Development

```bash
# Clone and install
cd src/ragstack-mcp
uv sync

# Run locally
uv run ragstack-mcp

# Build package
uv build

# Publish to PyPI
uv publish
```

## License

MIT
