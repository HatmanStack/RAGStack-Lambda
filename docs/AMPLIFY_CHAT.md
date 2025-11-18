# Amplify Chat Component

AI chat with source attribution for **any web framework**. Integrates with AWS Bedrock Knowledge Base.

## Quick Start - Web Component (Any Framework)

Use the chat in Vue, Angular, Svelte, or vanilla JavaScript:

```html
<!-- Include the web component (from CDN after deployment) -->
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

**Get CDN URL:** Deployment outputs this URL after running `publish.py --deploy-chat`

## Quick Start - React Component

For React applications:

```bash
npm install @ragstack/amplify-chat aws-amplify @aws-amplify/ui-react-ai
```

```tsx
import { ChatWithSources } from '@ragstack/amplify-chat';
import { Authenticator } from '@aws-amplify/ui-react';

export function App() {
  return (
    <Authenticator>
      <ChatWithSources
        conversationId="main"
        headerText="Document Q&A"
      />
    </Authenticator>
  );
}
```

## Features

- ✨ **Embeddable** - Use in any React app
- 🤖 **AI-Powered** - Integrates with Bedrock and Claude
- 📚 **Source Attribution** - Shows document sources with collapsible UI
- 📎 **Document Access** - Download original source documents (admin-configurable)
- 🎨 **Styled** - Compatible with Cloudscape
- ♿ **Accessible** - WCAG 2.1 AA compliant (keyboard nav, screen readers)
- 📱 **Responsive** - Desktop, tablet, mobile
- 🌙 **Dark Mode** - System preference support
- ✅ **Tested** - Comprehensive test suite

## Prerequisites

- React 18+
- AWS Amplify backend with chat route (from SAM deployment)
- Bedrock Knowledge Base
- AWS credentials configured

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

When `chat_allow_document_access` is enabled (admin UI → Configuration):

- **"View Document" links** appear in source citations
- **Presigned S3 URLs** for original uploaded files (not vector chunks)
- **1-hour expiry** for security
- **Read-only access** (no modification)

**User experience:**
1. User sends query → AI responds with sources
2. User expands sources → sees snippets + "View Document" links
3. User clicks link → original PDF/image/doc downloads
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
<script src="https://your-cdn.com/amplify-chat@1.0.0.js"></script>

<amplify-chat
  conversation-id="my-chat"
  header-text="Ask a Question"
  show-sources="true"
></amplify-chat>

<script>
  document.querySelector('amplify-chat')
    .addEventListener('amplify-chat:send-message', (e) => {
      console.log('Message:', e.detail.message);
    });
</script>
```

### Framework Examples

**Vue 3:**
```vue
<template>
  <amplify-chat
    conversation-id="vue-chat"
    @amplify-chat:send-message="handleMessage"
  />
</template>

<script setup>
import '@ragstack/amplify-chat/wc';
</script>
```

**Angular:**
```typescript
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import '@ragstack/amplify-chat/wc';

@NgModule({ schemas: [CUSTOM_ELEMENTS_SCHEMA] })
export class AppModule {}
```

**Svelte:**
```svelte
<script>
  import '@ragstack/amplify-chat/wc';
</script>

<amplify-chat on:amplify-chat:send-message={handleMessage} />
```

## Backend Setup

The component requires:

1. **SAM deployment** - Creates Bedrock Knowledge Base and Cognito User Pool
2. **Amplify backend** - Defines chat route with Lambda Authorizer for JWT validation
3. **Knowledge Base ID** - From SAM outputs, set in environment
4. **Authentication** - Cognito user pool from SAM stack (shared with admin UI)

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
  import('@ragstack/amplify-chat').then(m => ({
    default: m.ChatWithSources,
  }))
);

<Suspense fallback={<Loading />}>
  <ChatWithSources />
</Suspense>
```

## Troubleshooting

**Component doesn't render:**
- Verify `amplify_outputs.json` exists
- Check browser console for errors
- Ensure Authenticator wraps component

**"Knowledge Base not found":**
- Verify SAM deployment created KB
- Check `KNOWLEDGE_BASE_ID` environment variable
- Verify Amplify Lambda has Bedrock permissions

**Styling conflicts:**
- Check CSS specificity
- Inspect in DevTools
- Use `!important` if needed

**Auth errors:**
- Verify Cognito is set up
- Check AWS credentials
- Review IAM policies

## Build from Source

```bash
cd src/amplify-chat
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

- [Architecture](ARCHITECTURE.md) - Optional chat stack details
- [Deployment](DEPLOYMENT.md) - How to deploy
- [Development](DEVELOPMENT.md) - Development patterns
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
