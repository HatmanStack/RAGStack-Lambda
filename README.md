# RAGStack-Lambda

Serverless document processing with AI chat. Upload documents, extract text with OCR, query using Amazon Bedrock.

## Features

- 🔍 Document search (PDF, images, Office docs)
- 💬 AI chat with source attribution
- 🌐 Web component for any framework (Vue, Angular, Svelte)
- 🚀 One-click deploy
- 💰 $7-18/month (1000 docs)

## Quick Start

### Prerequisites
- AWS Account with admin access
- Python 3.13+, Node.js 24+, AWS CLI, SAM CLI, Docker
- **For chat (optional):** Amplify CLI

### Deploy

```bash
git clone https://github.com/your-org/RAGStack-Lambda.git
cd RAGStack-Lambda

# With chat (recommended)
python publish.py \
  --project-name my-docs \
  --admin-email admin@example.com \
  --region us-east-1 \
  --deploy-chat
```

**Outputs:** Web UI URL, Chat CDN URL, GraphQL API, KB ID

## Web Component Integration

Use AI chat in **any web application**:

```html
<script src="https://your-cdn-url/amplify-chat.js"></script>

<amplify-chat
  conversation-id="my-app"
  header-text="Ask About Documents"
></amplify-chat>
```

**Frameworks:**

```vue
<!-- Vue 3 -->
<template>
  <amplify-chat conversation-id="vue-app" />
</template>
<script setup>
import '@ragstack/amplify-chat/wc';
</script>
```

```typescript
// Angular
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import '@ragstack/amplify-chat/wc';

@Component({
  template: '<amplify-chat conversation-id="angular-app"></amplify-chat>',
  schemas: [CUSTOM_ELEMENTS_SCHEMA]
})
```

```svelte
<!-- Svelte -->
<script>
  import '@ragstack/amplify-chat/wc';
</script>
<amplify-chat conversation-id="svelte-app" />
```

```tsx
// React
import { ChatWithSources } from '@ragstack/amplify-chat';
<ChatWithSources conversationId="react-app" />
```

## Architecture

```
Upload → OCR → Embeddings → Bedrock KB
                                ↓
 Web UI ←→ GraphQL API ←→ Query/Search
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

```bash
npm install
npm test         # All tests
npm run lint     # Lint code
```

## Deployment Options

```bash
# Full (search + chat)
python publish.py --project-name myapp --admin-email admin@example.com --region us-east-1 --deploy-chat

# Search only
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
