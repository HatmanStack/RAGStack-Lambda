# RAGStack-Lambda

##   🚧🚧 Active Development 🚧🚧
Serverless document processing with AI chat. Upload documents, extract text with OCR, query using Amazon Bedrock.

## Features

- 📄 Document processing & vectorization (PDF, images, Office docs) → stored in managed knowledge base
- 💬 AI chat with retrieval-augmented context and source attribution
- 🌐 Web component for any framework (React, Vue, Angular, Svelte)
- 🚀 One-click deploy
- 💰 $7-18/month (1000 docs)

## Quick Start

### Prerequisites
- AWS Account with admin access
- Python 3.13+, Node.js 24+
- AWS CLI, SAM CLI (configured and running)
- **Docker** (required for Lambda layer builds)
- **For chat (optional):** Amplify CLI (auto-installed if missing)

### Deploy

```bash
git clone https://github.com/your-org/RAGStack-Lambda.git
cd RAGStack-Lambda

# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# With chat (recommended)
python publish.py \
  --project-name my-docs \
  --admin-email admin@example.com \
  --region us-east-1 \
  --deploy-chat
```

**Outputs:** Web UI URL, Chat CDN URL, GraphQL API, KB ID

## Web Component Integration

Use AI chat in **any web application** (React, Vue, Angular, Svelte, etc.):

```html
<script src="https://your-cdn-url/amplify-chat.js"></script>

<amplify-chat
  conversation-id="my-app"
  header-text="Ask About Documents"
></amplify-chat>
```

Load the CDN script once, then use `<amplify-chat>` in any framework. Styling and configuration are centrally managed through the web UI—apply changes across all deployments instantly.

## Architecture

```
Upload → OCR → Embeddings → Bedrock KB
                                ↓
 Web UI (Dashboard + Chat) ←→ GraphQL API
                                ↓
 Web Component ←→ AI Chat with Sources
```

## Documentation

- [Deployment](docs/DEPLOYMENT.md) - Deploy with chat
- [Chat Component](docs/AMPLIFY_CHAT.md) - Web component API
- [User Guide](docs/USER_GUIDE.md) - Using the UI
- [Configuration](docs/CONFIGURATION.md) - Runtime settings
- [Development](docs/DEVELOPMENT.md) - Local dev
- [Architecture](docs/ARCHITECTURE.md) - System design
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
# With chat (recommended)
python publish.py --project-name myapp --admin-email admin@example.com --region us-east-1 --deploy-chat

# Without chat
python publish.py --project-name myapp --admin-email admin@example.com --region us-east-1

# Update chat only
python publish.py --project-name myapp --admin-email admin@example.com --region us-east-1 --chat-only
```

## Cost

~1000 docs/month (5 pages):
- OCR + Embeddings: $5-15
- Infrastructure: $2
- Bedrock queries: $0.50
- **Total: $7-18/month**

## License

MIT
