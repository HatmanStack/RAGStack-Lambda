# RagStack Chat Component

AI chat with source attribution for **any web framework**. Integrates with AWS Bedrock Knowledge Base.

## Quick Start - Web Component (Any Framework)

Use the chat in Vue, Angular, Svelte, or vanilla JavaScript:

```html
<!-- Include the web component (from CDN after deployment) -->
<script src="https://your-cdn-url/ragstack-chat.js"></script>

<!-- Add chat to your page -->
<ragstack-chat
  conversation-id="my-app"
  header-text="Ask About Documents"
  show-sources="true"
></ragstack-chat>

<script>
  // Listen for events
  document.querySelector('ragstack-chat')
    .addEventListener('ragstack-chat:send-message', (e) => {
      console.log('User asked:', e.detail.message);
    });
</script>
```

**Get CDN URL:** Deployment outputs this URL after running `publish.py`

## Quick Start - React Component

For React applications:

```bash
npm install @ragstack/ragstack-chat
```

```tsx
import { ChatWithSources } from '@ragstack/ragstack-chat';

export function App() {
  return (
    <ChatWithSources
      conversationId="main"
      headerText="Document Q&A"
    />
  );
}
```

## Features

- Web component embeddable in any framework
- AI-Powered - Integrates with Bedrock and Claude
- Source Attribution - Shows document sources with collapsible UI
- Document Access - Download original source documents (admin-configurable)
- Styled - Compatible with Cloudscape
- Accessible - WCAG 2.1 AA compliant (keyboard nav, screen readers)
- Responsive - Desktop, tablet, mobile
- Dark Mode - System preference support
- Tested - Comprehensive test suite

## Prerequisites

- React 18+ (for React component)
- RAGStack-Lambda SAM deployment
- Bedrock Knowledge Base

## Configuration

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `conversationId` | string | `"default"` | Unique conversation ID |
| `headerText` | string | `"Document Q&A"` | Header title |
| `headerSubtitle` | string | `""` | Header subtitle |
| `showSources` | boolean | `true` | Show/hide sources |
| `maxWidth` | string | `"100%"` | Component width |
| `onSendMessage` | function | - | Callback when user sends message |
| `onResponseReceived` | function | - | Callback when AI responds |

### Callbacks

```tsx
// When user sends a message
onSendMessage={(message: string, conversationId: string) => {
  console.log(`${conversationId}: ${message}`);
}}

// When AI responds
onResponseReceived={(response: ChatMessage) => {
  console.log('Response:', response.content);
  console.log('Sources:', response.sources);
}}
```

## Source Citations

### Collapsible Sources

Source citations appear below each AI response in a collapsible UI:

- **Default state:** Collapsed (clean UI)
- **Expand/collapse:** Click "Show/Hide" button
- **Persistence:** State saved in sessionStorage (persists on page refresh)
- **Accessibility:** Keyboard navigable (Tab + Enter), screen reader support

```tsx
// Example source structure
{
  title: "financial-report-2024.pdf",
  location: "chunk-005",
  snippet: "Q4 revenue was $2.3M...",
  documentUrl: "https://s3.amazonaws.com/...",  // Optional
  documentAccessAllowed: true  // Configuration flag
}
```

### Document Downloads

When `chat_allow_document_access` is enabled (admin UI -> Configuration):

- **"View Document" links** appear in source citations
- **Presigned S3 URLs** for original uploaded files (not vector chunks)
- **1-hour expiry** for security
- **Read-only access** (no modification)

**User experience:**
1. User sends query -> AI responds with sources
2. User expands sources -> sees snippets + "View Document" links
3. User clicks link -> original PDF/image/doc downloads
4. URL expires after 1 hour

**Admin controls:**
- Toggle on/off in real-time (no redeployment)
- Changes apply within 60 seconds (DynamoDB config cache)

### Accessibility Features

- **Keyboard navigation:** Tab to navigate, Enter/Space to activate
- **Screen reader support:** ARIA labels, state announcements
- **Focus indicators:** Visible focus outlines on all interactive elements
- **Semantic HTML:** `<button>` elements (not `<div onClick>`)

## Styling

### Design Tokens

Customize appearance with CSS variables:

```css
:root {
  --chat-color-user-bg: #your-color;
  --chat-color-source-accent: #your-color;
  --chat-font-family: 'Your Font', sans-serif;
  --chat-spacing-lg: 20px;
}
```

### CSS Classes

```tsx
<ChatWithSources className="branded-chat" />
```

## Advanced Usage

### Multiple Conversations

```tsx
<ChatWithSources conversationId="support" headerText="Support" />
<ChatWithSources conversationId="docs" headerText="Documentation" />
```

### With State Management (Redux)

```tsx
import { useDispatch } from 'react-redux';

export function ConnectedChat() {
  const dispatch = useDispatch();

  return (
    <ChatWithSources
      onResponseReceived={(response) => {
        dispatch(saveConversation({
          message: response.content,
          sources: response.sources,
        }));
      }}
    />
  );
}
```

### Modal or Drawer

```tsx
<Dialog open={isOpen} onOpenChange={onClose}>
  <ChatWithSources maxWidth="100%" headerText="" />
</Dialog>
```

## Web Components

Use the component in any framework via Web Components:

```html
<script src="https://your-cdn.com/ragstack-chat.js"></script>

<ragstack-chat
  conversation-id="my-chat"
  header-text="Ask a Question"
  show-sources="true"
></ragstack-chat>

<script>
  document.querySelector('ragstack-chat')
    .addEventListener('ragstack-chat:send-message', (e) => {
      console.log('Message:', e.detail.message);
    });
</script>
```

### Framework Examples

**Vue 3:**
```vue
<template>
  <ragstack-chat
    conversation-id="vue-chat"
    @ragstack-chat:send-message="handleMessage"
  />
</template>

<script setup>
import '@ragstack/ragstack-chat/wc';
</script>
```

**Angular:**
```typescript
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import '@ragstack/ragstack-chat/wc';

@NgModule({ schemas: [CUSTOM_ELEMENTS_SCHEMA] })
export class AppModule {}
```

**Svelte:**
```svelte
<script>
  import '@ragstack/ragstack-chat/wc';
</script>

<ragstack-chat on:ragstack-chat:send-message={handleMessage} />
```

## Backend Setup

The component requires:

1. **SAM deployment** - Creates Bedrock Knowledge Base, Cognito User Pool, and AppSync GraphQL API
2. **Knowledge Base ID** - From SAM outputs, configured in web component build
3. **AppSync GraphQL** - Query endpoint injected during build

## Performance Optimization

### Memoize Component

```tsx
import { useMemo } from 'react';

const chatProps = useMemo(() => ({
  conversationId: 'main',
}), []);

return <ChatWithSources {...chatProps} />;
```

### Lazy Load

```tsx
import { lazy, Suspense } from 'react';

const ChatWithSources = lazy(() =>
  import('@ragstack/ragstack-chat').then(m => ({
    default: m.ChatWithSources,
  }))
);

<Suspense fallback={<Loading />}>
  <ChatWithSources />
</Suspense>
```

## Troubleshooting

**Component doesn't render:**
- Check browser console for errors
- Verify CDN URL is correct

**"No response from API":**
- Verify SAM deployment completed successfully
- Check GraphQL endpoint is configured
- Verify Bedrock Knowledge Base has content

**Styling conflicts:**
- Check CSS specificity
- Inspect in DevTools
- Use `!important` if needed

## Build from Source

```bash
cd src/ragstack-chat
npm install
npm run build
npm test
```

## Types

### ChatMessage

```typescript
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: string;
}
```

### Source

```typescript
interface Source {
  title: string;      // Document filename
  location: string;   // Page or offset
  snippet: string;    // Quote
}
```

## Related Documentation

- [Architecture](ARCHITECTURE.md) - System architecture details
- [Deployment](DEPLOYMENT.md) - How to deploy
- [Development](DEVELOPMENT.md) - Development patterns
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
