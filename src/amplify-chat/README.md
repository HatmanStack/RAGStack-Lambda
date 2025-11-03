# Amplify Chat Component

A reusable React component for AI chat with source attribution, built with AWS Amplify and Bedrock Knowledge Base.

## Quick Start

```bash
npm install @ragstack/amplify-chat aws-amplify @aws-amplify/ui-react-ai
```

```tsx
import { ChatWithSources } from '@ragstack/amplify-chat';
import { Authenticator } from '@aws-amplify/ui-react';

export function App() {
  return (
    <Authenticator>
      <ChatWithSources conversationId="main" />
    </Authenticator>
  );
}
```

## Full Documentation

See [docs/AMPLIFY_CHAT.md](../../docs/AMPLIFY_CHAT.md) for:
- Configuration and props
- Styling and customization
- Advanced usage patterns
- Web Component integration
- Framework examples (Vue, Angular, Svelte)
- Performance optimization
- Troubleshooting

## Integration Guide

For comprehensive integration instructions with code examples, see:
**[docs/AMPLIFY_CHAT.md](../../docs/AMPLIFY_CHAT.md#basic-setup)**

## Features

- ✨ Embeddable in any React app
- 🤖 AI-powered with Claude
- 📚 Source attribution
- 🎨 Cloudscape-compatible styling
- ♿ WCAG 2.1 AA compliant
- 📱 Responsive (desktop, tablet, mobile)
- 🌙 Dark mode support

## Prerequisites

- React 18+
- AWS Amplify backend with chat configured
- Bedrock Knowledge Base
- AWS credentials

## Build from Source

```bash
npm install
npm run build
npm test
npm run build:watch  # Development
```

## Types

```typescript
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: string;
}

interface Source {
  title: string;
  location: string;
  snippet: string;
}
```

## Troubleshooting

Common issues and solutions: [docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md)

## Related Documentation

- [Component API](../../docs/AMPLIFY_CHAT.md) - Full API reference
- [Architecture](../../docs/ARCHITECTURE.md) - System design
- [Development](../../docs/DEVELOPMENT.md) - Development patterns

## License

MIT
