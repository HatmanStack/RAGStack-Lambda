# RAGStack-Lambda

##   🚧🚧 Active Development 🚧🚧
Serverless document processing with AI chat. Upload documents, extract text with OCR, query using Amazon Bedrock.

## Features

- 📄 Document processing & vectorization (PDF, images, Office docs) → stored in managed knowledge base
- 💬 AI chat with retrieval-augmented context and source attribution
- 📎 Collapsible source citations with optional document downloads
- 🌐 Web component for any framework (React, Vue, Angular, Svelte)
- 🚀 One-click deploy
- 💰 $7-18/month (1000 docs)

## Quick Start

### Prerequisites
- AWS Account with admin access
- Python 3.13+, Node.js 24+
- AWS CLI, SAM CLI (configured and running)
- **Docker** (required for Lambda layer builds)

### Deploy

```bash
git clone https://github.com/your-org/RAGStack-Lambda.git
cd RAGStack-Lambda

# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Deploys to us-east-1 by default (Nova Multimodal Embeddings)
python publish.py \
  --project-name my-docs \
  --admin-email admin@example.com
```

**Outputs:** Web UI URL, Chat CDN URL, GraphQL API, KB ID

## Web Component Integration

Use AI chat in **any web application** (React, Vue, Angular, Svelte, etc.):

```html
<script src="https://your-cdn-url/ragstack-chat.js"></script>

<ragstack-chat
  conversation-id="my-app"
  header-text="Ask About Documents"
></ragstack-chat>
```

Load the CDN script once, then use `<ragstack-chat>` in any framework.

## API Access

**Server-side integrations** use API key authentication. Get your key from Dashboard → Settings.

```bash
curl -X POST 'YOUR_GRAPHQL_ENDPOINT' \
  -H 'x-api-key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"query": "query { searchKnowledgeBase(query: \"...\") { results { content } } }"}'
```

**Web component** uses IAM auth (no API key needed - handled automatically).

Each UI tab shows server-side API examples in an expandable section.

## MCP Server (AI Assistant Integration)

Use your knowledge base directly in Claude Desktop, Cursor, VS Code, Amazon Q CLI, and other MCP-compatible tools.

```bash
# Install (or use uvx for zero-install)
pip install ragstack-mcp
```

Add to your AI assistant's MCP config:

```json
{
  "ragstack-kb": {
    "command": "uvx",
    "args": ["ragstack-mcp"],
    "env": {
      "RAGSTACK_GRAPHQL_ENDPOINT": "YOUR_ENDPOINT",
      "RAGSTACK_API_KEY": "YOUR_API_KEY"
    }
  }
}
```

Then ask naturally: *"Search my knowledge base for authentication docs"*

See [MCP Server docs](src/ragstack-mcp/README.md) for full setup instructions.

## Architecture

```
Upload → OCR → Embeddings → Bedrock KB
                                ↓
 Web UI (Dashboard + Chat) ←→ GraphQL API
                                ↓
 Web Component ←→ AI Chat with Sources
```

## Usage

### Documents
Upload PDF, DOCX, XLSX, TXT, MD. Processing: UPLOADED → PROCESSING → INDEXED (2-15 min)

### Images
Upload JPG, PNG, GIF, WebP with captions. Both visual content and caption text are searchable.

### Web Scraping
Scrape websites into the knowledge base. See [Web Scraping](docs/WEB_SCRAPING.md).

### Chat
Ask questions about your content. Sources show where answers came from.

## Documentation

- [Configuration](docs/CONFIGURATION.md) - Settings, quotas & API keys
- [Web Scraping](docs/WEB_SCRAPING.md) - Scrape websites
- [Chat Component](docs/RAGSTACK_CHAT.md) - Embed chat anywhere
- [Architecture](docs/ARCHITECTURE.md) - System design & API reference
- [Development](docs/DEVELOPMENT.md) - Local dev
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues

## Local Development

Setup (one time):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Run tests:
```bash
python test.py
```

## Deployment Options

```bash
# Full deployment (defaults to us-east-1)
python publish.py --project-name myapp --admin-email admin@example.com

# Backend only (skip dashboard rebuild)
python publish.py --project-name myapp --admin-email admin@example.com --skip-ui

# Backend only (skip ALL UI builds - dashboard and web component)
python publish.py --project-name myapp --admin-email admin@example.com --skip-ui-all
```

> **Note:** Currently requires us-east-1 (Nova Multimodal Embeddings). When available in other regions, use `--region <region>`.

## Cost

~1000 docs/month (5 pages):
- OCR + Embeddings: $5-15
- Infrastructure: $2
- Bedrock queries: $0.50
- **Total: $7-18/month**

## License

MIT
