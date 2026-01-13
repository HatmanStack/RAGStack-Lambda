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

**Get CDN URL:** Dashboard → Chat tab → Embed Chat Widget section

## Dashboard Chat Tab

The Chat tab in the admin dashboard provides:

### System Prompt Editor
Customize the AI assistant's behavior by editing the system prompt. Changes apply immediately to new conversations.

**Location:** Chat tab → System Prompt (expandable section)

### Embed Code Generator
Get ready-to-use embed code with your CDN URL pre-filled:

- **Basic (Public):** For unauthenticated access
- **Authenticated:** Includes user-id and user-token attributes with example JavaScript

**Location:** Chat tab → Embed Chat Widget (expandable section)

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

## Configuration

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `conversationId` | string | `"default"` | Unique conversation ID |
| `headerText` | string | `"Document Q&A"` | Header title |
| `headerSubtitle` | string | `"Ask questions about your documents"` | Header subtitle |
| `inputPlaceholder` | string | `"Ask a question..."` | Input field placeholder |
| `showSources` | boolean | `true` | Show/hide sources |
| `maxWidth` | string | `"100%"` | Component width |
| `userId` | string \| null | `null` | User ID for authenticated mode |
| `userToken` | string \| null | `null` | Auth token for authenticated mode |
| `className` | string | - | Additional CSS class |
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
// Example document source
{
  title: "financial-report-2024.pdf",
  location: "chunk-005",
  snippet: "Q4 revenue was $2.3M...",
  documentUrl: "https://s3.amazonaws.com/...",  // Optional
  documentAccessAllowed: true  // Configuration flag
}

// Example media source (video/audio)
{
  title: "team-meeting.mp4",
  location: "1:30-2:00",  // Timestamp range
  snippet: "We discussed the Q4 targets...",
  documentUrl: "https://s3.amazonaws.com/...#t=90,120",  // URL with timestamp fragment
  isMedia: true,
  mediaType: "video",  // "video" or "audio"
  timestampStart: 90,  // seconds
  timestampEnd: 120,
  speaker: "speaker_0"  // When diarization enabled
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

### Media Sources (Video/Audio)

When sources come from video or audio files:

- **Timestamp display:** Shows time range (e.g., "1:30-2:00")
- **Click to play:** Opens inline player at that timestamp
- **Speaker label:** Shows speaker ID when diarization is enabled
- **Inline player:** HTML5 video/audio player embedded in source citation

**URL format:** Presigned S3 URLs include `#t=start,end` media fragment for automatic seeking.

**Player features:**
- Play/pause controls
- Seek bar
- Volume control
- Compact inline display (max 400px width for video)

### Accessibility Features

- **Keyboard navigation:** Tab to navigate, Enter/Space to activate
- **Screen reader support:** ARIA labels, state announcements
- **Focus indicators:** Visible focus outlines on all interactive elements
- **Semantic HTML:** `<button>` elements (not `<div onClick>`)

## Styling

The widget is fully customizable via CSS variables. Override any variable on the `ragstack-chat` element or a parent container.

### Quick Example

```css
ragstack-chat {
  --chat-color-user-bg: #7c3aed;
  --chat-color-source-accent: #7c3aed;
  --chat-font-family: 'Inter', sans-serif;
}
```

### CSS Variables Reference

#### Colors

| Variable | Default (Light) | Default (Dark) | shadcn/ui Equivalent |
|----------|-----------------|----------------|----------------------|
| `--chat-color-bg` | `#ffffff` | `#1a1a1a` | `--background` |
| `--chat-color-bg-secondary` | `#f5f5f5` | `#2a2a2a` | `--secondary` |
| `--chat-color-text` | `#1a1a1a` | `#ffffff` | `--foreground` |
| `--chat-color-text-secondary` | `#666666` | `#999999` | `--muted-foreground` |
| `--chat-color-border` | `#d5d5d5` | `#333333` | `--border` |
| `--chat-color-border-light` | `#e3e3e3` | `#2a2a2a` | `--border` (lighter) |
| `--chat-color-primary` | `#0056b3` | `#0056b3` | `--primary` |
| `--chat-color-user-bg` | `#0972d3` | `#0972d3` | `--primary` |
| `--chat-color-user-text` | `#ffffff` | `#ffffff` | `--primary-foreground` |
| `--chat-color-assistant-bg` | `#f5f5f5` | `#2a2a2a` | `--muted` |
| `--chat-color-assistant-text` | `#1a1a1a` | `#ffffff` | `--muted-foreground` |
| `--chat-color-source-bg` | `#f8f9fa` | `#252525` | `--card` |
| `--chat-color-source-border` | `#d5d5d5` | `#333333` | `--border` |
| `--chat-color-source-accent` | `#0972d3` | `#539fe5` | `--accent` |

#### Spacing

| Variable | Default | Description |
|----------|---------|-------------|
| `--chat-spacing-xs` | `4px` | Extra small gaps |
| `--chat-spacing-sm` | `8px` | Small gaps, button padding |
| `--chat-spacing-md` | `12px` | Medium gaps, input padding |
| `--chat-spacing-lg` | `16px` | Large gaps, section padding |
| `--chat-spacing-xl` | `20px` | Extra large gaps |
| `--chat-spacing-xxl` | `24px` | Container padding |

#### Border Radius

| Variable | Default | shadcn/ui Equivalent |
|----------|---------|----------------------|
| `--chat-radius-sm` | `2px` | `--radius` (sm) |
| `--chat-radius-md` | `4px` | `--radius` |
| `--chat-radius-lg` | `8px` | `--radius` (lg) |

#### Typography

| Variable | Default | Description |
|----------|---------|-------------|
| `--chat-font-family` | System fonts | Font stack |
| `--chat-font-size-xs` | `12px` | Timestamps, labels |
| `--chat-font-size-sm` | `13px` | Secondary text |
| `--chat-font-size-base` | `14px` | Body text |
| `--chat-font-size-lg` | `16px` | Headers |
| `--chat-font-size-xl` | `18px` | Large headers |
| `--chat-line-height-tight` | `1.4` | Compact text |
| `--chat-line-height-normal` | `1.5` | Body text |
| `--chat-line-height-relaxed` | `1.6` | Readable paragraphs |

#### Transitions

| Variable | Default | Description |
|----------|---------|-------------|
| `--chat-transition-fast` | `100ms ease-in-out` | Hover states |
| `--chat-transition-normal` | `200ms ease-in-out` | UI changes |

### HTML Attributes

Configure the widget via HTML attributes:

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `conversation-id` | string | `"default"` | Unique conversation identifier |
| `header-text` | string | `"Document Q&A"` | Header title text |
| `header-subtitle` | string | `"Ask questions about your documents"` | Subtitle below header |
| `input-placeholder` | string | `"Ask a question..."` | Input field placeholder |
| `show-sources` | boolean | `true` | Show/hide source citations |
| `max-width` | string | `"100%"` | Component max width |
| `user-id` | string | - | User ID for authenticated mode |
| `user-token` | string | - | Auth token for authenticated mode |
| `background-color` | string | - | Background color (e.g., `"#ffffff"`) |
| `text-color` | string | - | Text color (e.g., `"#1a1a1a"`) |

### Full Customization Example

```html
<style>
  .my-chat {
    /* Map to your design system */
    --chat-color-bg: var(--background);
    --chat-color-text: var(--foreground);
    --chat-color-border: var(--border);
    --chat-color-user-bg: var(--primary);
    --chat-color-user-text: var(--primary-foreground);
    --chat-color-assistant-bg: var(--muted);
    --chat-color-source-accent: var(--accent);

    /* Custom typography */
    --chat-font-family: 'Inter', sans-serif;
    --chat-font-size-base: 15px;

    /* Rounder corners */
    --chat-radius-md: 8px;
    --chat-radius-lg: 12px;
  }
</style>

<ragstack-chat
  class="my-chat"
  header-text="Support Chat"
  header-subtitle="How can we help?"
></ragstack-chat>
```

### CSS Classes

```tsx
<ChatWithSources className="branded-chat" />
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
  location: string;   // Page, offset, or timestamp range (e.g., "1:30-2:00")
  snippet: string;    // Quote
  // Media-specific fields (optional)
  isMedia?: boolean;           // true for video/audio sources
  mediaType?: 'video' | 'audio';
  timestampStart?: number;     // seconds
  timestampEnd?: number;       // seconds
  speaker?: string;            // speaker ID when diarization enabled
}
```

## Related Documentation

- [Architecture](ARCHITECTURE.md) - System design
- [Development](DEVELOPMENT.md) - Local dev
- [Configuration](CONFIGURATION.md) - Runtime settings
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
