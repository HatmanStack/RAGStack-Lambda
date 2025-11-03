# RAGStack-Lambda

Serverless document processing pipeline with AI-powered chat. Upload documents, extract text with OCR, and query using Amazon Bedrock Knowledge Base.

## Features

- 🔍 **Document Search** - Upload PDFs, images, Office docs → searchable knowledge base
- 💬 **AI Chat** - Conversational interface with source attribution (optional)
- 🌐 **Web Component** - Drop-in chat for any framework (Vue, Angular, Svelte, vanilla JS)
- 🚀 **One-Click Deploy** - Complete infrastructure via `publish.py`
- 💰 **Cost-Effective** - S3 vector storage (~$7-18/month for 1000 docs)

## Quick Start

### Prerequisites
- AWS Account with Bedrock models enabled (AWS Console → Bedrock → Model access)
- Python 3.13+, Node.js 24+, AWS CLI, SAM CLI, Docker

### Deploy with Chat (Recommended)

```bash
git clone https://github.com/your-org/RAGStack-Lambda.git
cd RAGStack-Lambda

# Deploy document search + AI chat
python publish.py \
  --project-name my-docs \
  --admin-email admin@example.com \
  --region us-east-1 \
  --deploy-chat
```

**Outputs:**
- Web UI URL (CloudFront)
- Chat Component URL (for web component integration)
- GraphQL API endpoint
- Bedrock Knowledge Base ID

### Deploy Search Only

```bash
# Just document search (no chat)
python publish.py \
  --project-name my-docs \
  --admin-email admin@example.com \
  --region us-east-1
```

## Web Component Integration

Use the AI chat in **any web application** (no React needed):

```html
<!-- Include the web component -->
<script src="https://your-cdn-url/amplify-chat.js"></script>

<!-- Add chat to your page -->
<amplify-chat
  conversation-id="my-app"
  header-text="Ask About Documents"
  show-sources="true"
></amplify-chat>

<script>
  // Listen for events
  document.querySelector('amplify-chat')
    .addEventListener('amplify-chat:send-message', (e) => {
      console.log('User asked:', e.detail.message);
    });
</script>
```

### Framework Examples

**Vue 3:**
```vue
<template>
  <amplify-chat conversation-id="vue-app" />
</template>

<script setup>
import '@ragstack/amplify-chat/wc';
</script>
```

**Angular:**
```typescript
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import '@ragstack/amplify-chat/wc';

@Component({
  template: '<amplify-chat conversation-id="angular-app"></amplify-chat>',
  schemas: [CUSTOM_ELEMENTS_SCHEMA]
})
```

**Svelte:**
```svelte
<script>
  import '@ragstack/amplify-chat/wc';
</script>

<amplify-chat conversation-id="svelte-app" />
```

**React:**
```tsx
import { ChatWithSources } from '@ragstack/amplify-chat';

<ChatWithSources conversationId="react-app" />
```

See [Chat Component Guide](docs/AMPLIFY_CHAT.md) for full API.

## Architecture

```
Document Upload → OCR (Textract/Bedrock) → Embeddings → Bedrock KB
                                                             ↓
   Web UI (React) ←─────────→ GraphQL API ←────────→ Query/Search
                                                             ↓
   Web Component (Any Framework) ←──────────────→ AI Chat with Sources
```

**Stack:**
- **Core (SAM)**: Lambda, Step Functions, S3, DynamoDB, AppSync, Bedrock
- **Chat (Amplify)**: Optional conversational interface, web component
- **Frontend**: React UI + Web Component for multi-framework support

## Cost Estimate

~1000 documents/month (5 pages each):

| Service | Cost |
|---------|------|
| OCR (Textract) + Embeddings | $5-15 |
| S3 + Lambda + DynamoDB | $2 |
| Bedrock (chat queries) | $0.50 |
| **Total** | **~$7-18/month** |

## Deployment Options

```bash
# Full stack (search + chat)
python publish.py --project-name myapp --admin-email admin@example.com --region us-east-1 --deploy-chat

# Search only
python publish.py --project-name myapp --admin-email admin@example.com --region us-east-1

# Update chat only (after SAM deployed)
python publish.py --project-name myapp --admin-email admin@example.com --region us-east-1 --chat-only

# Backend only (skip UI rebuild)
python publish.py --project-name myapp --admin-email admin@example.com --region us-east-1 --skip-ui
```

## Documentation

### Quick Start
- [Deployment Guide](docs/DEPLOYMENT.md) - Step-by-step with chat setup
- [User Guide](docs/USER_GUIDE.md) - Using the web UI

### Integration
- [Chat Component](docs/AMPLIFY_CHAT.md) - Web component API, framework examples
- [UI Component](docs/UI.md) - React web UI customization

### Development
- [Development Guide](docs/DEVELOPMENT.md) - Local setup, testing
- [Configuration](docs/CONFIGURATION.md) - Runtime settings
- [Testing](docs/TESTING.md) - Test structure

### Operations
- [Architecture](docs/ARCHITECTURE.md) - System design
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues
- [Optimization](docs/OPTIMIZATION.md) - Performance tuning

## Local Development

```bash
# Install and test locally (no AWS needed)
npm install
npm test              # All tests (~3s)
npm run lint          # Lint all code
npm run test:all      # Lint + test

# Build web component
cd src/amplify-chat
npm install
npm run build        # Builds dist/wc.js
```

## What You Get

After deployment:

1. **Search UI** - React app for document upload and search (CloudFront URL)
2. **AI Chat** - Conversational interface with source citations (web component)
3. **GraphQL API** - AppSync endpoint for custom integrations
4. **Knowledge Base** - Bedrock KB with your documents indexed

## Key Features

- **Multi-Format OCR** - PDF (text/scanned), images, Office docs, text files
- **Dual OCR Backends** - Textract (cost-effective) or Bedrock (multimodal)
- **Semantic Search** - Vector similarity search via Bedrock
- **Chat with Sources** - AI responses include document citations
- **Web Component** - Framework-agnostic integration
- **Real-Time Updates** - Dashboard shows processing status
- **Runtime Config** - Change OCR/models without redeployment

## Project Structure

```
RAGStack-Lambda/
├── src/
│   ├── lambda/          # Lambda functions (OCR, embeddings, query, config)
│   ├── statemachine/    # Step Functions workflow
│   ├── api/             # GraphQL schema
│   ├── ui/              # React web UI
│   └── amplify-chat/    # Chat component (React + Web Component)
├── lib/ragstack_common/ # Shared Python library
├── tests/               # Unit & integration tests
├── template.yaml        # CloudFormation/SAM
├── publish.py           # Deployment automation
└── docs/                # Documentation
```

## Security

- ✅ HTTPS/TLS everywhere
- ✅ S3 SSE, DynamoDB encryption
- ✅ Cognito authentication + optional MFA
- ✅ Least-privilege IAM policies
- ✅ Public S3 access blocked

## Support

- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- [GitHub Issues](https://github.com/your-org/RAGStack-Lambda/issues)
- Check CloudWatch logs for errors

## License

MIT
