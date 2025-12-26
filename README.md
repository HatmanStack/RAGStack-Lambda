# RAGStack-Lambda

<p align="center">
<a href="https://www.apache.org/licenses/LICENSE-2.0.html"><img src="https://img.shields.io/badge/license-Apache2.0-blue" alt="Apache 2.0 License" /></a>
<a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.13-3776AB" alt="Python 3.13" /></a>
<a href="https://react.dev"><img src="https://img.shields.io/badge/React-19-61DAFB" alt="React 19" /></a>
</p>

<p align="center">
<a href="https://aws.amazon.com/lambda/"><img src="https://img.shields.io/badge/AWS-Lambda-FF9900" alt="AWS Lambda" /></a>
<a href="https://aws.amazon.com/bedrock/"><img src="https://img.shields.io/badge/AWS-Bedrock-232F3E" alt="AWS Bedrock" /></a>
<a href="https://aws.amazon.com/s3/"><img src="https://img.shields.io/badge/AWS-S3-569A31" alt="AWS S3" /></a>
<a href="https://aws.amazon.com/dynamodb/"><img src="https://img.shields.io/badge/AWS-DynamoDB-4053D6" alt="AWS DynamoDB" /></a>
<a href="https://aws.amazon.com/cognito/"><img src="https://img.shields.io/badge/AWS-Cognito-DD344C" alt="AWS Cognito" /></a>
</p>

Serverless document processing with AI chat. Upload documents, extract text with OCR, query using Amazon Bedrock.

## Features

- ☁️ Fully serverless architecture (Lambda, Step Functions, S3, DynamoDB)
- 📄 Document processing & vectorization (PDF, images, Office docs) with Amazon Nova multimodal embeddings
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
- [Library Reference](docs/LIBRARY_REFERENCE.md) - Public API for lib/ragstack_common

## Development

```bash
npm run check  # Lint + test all (backend + frontend)
```

## Deployment Options

```bash
# Full deployment (defaults to us-east-1)
python publish.py --project-name myapp --admin-email admin@example.com

# Skip dashboard build (still builds web component)
python publish.py --project-name myapp --admin-email admin@example.com --skip-ui

# Skip ALL UI builds (dashboard and web component)
python publish.py --project-name myapp --admin-email admin@example.com --skip-ui-all
```

> **Note:** Currently requires us-east-1 (Nova Multimodal Embeddings). When available in other regions, use `--region <region>`.

## License

MIT
