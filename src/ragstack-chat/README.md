# RagStack Chat Component

React component and Web Component for AI chat with source attribution.

## Installation

```bash
npm install @ragstack/ragstack-chat
```

## React Component

```tsx
import { ChatWithSources } from '@ragstack/ragstack-chat';

export function App() {
  return (
    <ChatWithSources
      conversationId="my-chat-1"
      headerText="Ask me anything"
      showSources={true}
    />
  );
}
```

## Web Component

```html
<script src="https://your-cdn.cloudfront.net/ragstack-chat.js"></script>

<ragstack-chat
  conversation-id="demo-chat"
  header-text="Document Q&A"
  show-sources="true"
></ragstack-chat>
```

Web component includes configuration at build time (zero runtime config).

## Props / Attributes

| Prop | Attribute | Type | Default |
|------|-----------|------|---------|
| `conversationId` | `conversation-id` | `string` | `"default"` |
| `headerText` | `header-text` | `string` | `"Document Q&A"` |
| `headerSubtitle` | `header-subtitle` | `string` | `""` |
| `showSources` | `show-sources` | `boolean` | `true` |
| `maxWidth` | `max-width` | `string` | `"100%"` |
| `userId` | `user-id` | `string \| null` | `null` |
| `userToken` | `user-token` | `string \| null` | `null` |
| `themePreset` | `theme-preset` | `'light' \| 'dark' \| 'brand'` | `'light'` |
| `onSendMessage` | - | `(msg, convId) => void` | - |
| `onResponseReceived` | - | `(response) => void` | - |

## Events (Web Component)

```javascript
const chat = document.querySelector('ragstack-chat');
chat.addEventListener('ragstack-chat:send-message', (e) => {
  console.log('Sent:', e.detail.message);
});
chat.addEventListener('ragstack-chat:response-received', (e) => {
  console.log('Response:', e.detail.response);
});
```

## Types

```typescript
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: string;
  modelUsed?: string;
}

interface Source {
  title: string;
  location: string;
  snippet: string;
  documentUrl?: string | null;
  documentAccessAllowed?: boolean;
}
```

## Build from Source

```bash
npm install
npm run build
npm test
```

## Documentation

- [docs/RAGSTACK_CHAT.md](../../docs/RAGSTACK_CHAT.md) - Full API reference
- [docs/CONFIGURATION.md](../../docs/CONFIGURATION.md) - Backend configuration
- [docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md) - Common issues
