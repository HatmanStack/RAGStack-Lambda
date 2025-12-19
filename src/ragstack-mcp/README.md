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

| Tool | Description |
|------|-------------|
| `search_knowledge_base` | Search for relevant documents |
| `chat_with_knowledge_base` | Ask questions with AI-generated answers and citations |
| `start_scrape_job` | Scrape a website into the knowledge base |
| `get_scrape_job_status` | Check scrape job progress |
| `list_scrape_jobs` | List recent scrape jobs |
| `upload_document_url` | Get a presigned URL to upload documents |

## Usage Examples

Once configured, just ask your AI assistant naturally:

- "Search my knowledge base for authentication best practices"
- "What does our documentation say about API rate limits?"
- "Scrape the React docs at react.dev/reference"
- "Check the status of my scrape job"
- "Upload a new document called quarterly-report.pdf"

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
