# Amplify Chat Component

A reusable React component and Web Component for AI chat with source attribution, built with AWS Amplify and Bedrock Knowledge Base.

## Quick Start

### As React Component

```bash
npm install @ragstack/amplify-chat aws-amplify @aws-amplify/ui-react-ai
```

```tsx
import { ChatWithSources } from '@ragstack/amplify-chat';
import { Amplify } from 'aws-amplify';
import amplifyConfig from './amplify_outputs.json';

// Configure Amplify once at app startup
Amplify.configure(amplifyConfig);

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

### As Web Component (Zero Config)

```html
<!DOCTYPE html>
<html>
<head>
  <title>Chat Demo</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
  <!-- Load the web component -->
  <script src="https://your-cdn.cloudfront.net/wc.js"></script>

  <!-- Use the component -->
  <amplify-chat
    conversation-id="demo-chat"
    header-text="Document Q&A"
    header-subtitle="Ask questions about your documents"
    theme-preset="light"
  ></amplify-chat>
</body>
</html>
```

**Note:** Web component includes Amplify configuration at build time (zero runtime config needed)

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

## Props Reference

### React Component Props (ChatWithSources)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `conversationId` | `string` | `"default"` | Unique ID for conversation thread |
| `headerText` | `string` | `"Document Q&A"` | Chat header title |
| `headerSubtitle` | `string` | `"Ask questions..."` | Chat header subtitle |
| `showSources` | `boolean` | `true` | Display source citations |
| `maxWidth` | `string` | `"100%"` | Max width (CSS value) |
| `userId` | `string \| null` | `null` | User ID (authenticated mode) |
| `userToken` | `string \| null` | `null` | Auth token (authenticated mode) |
| `themePreset` | `'light' \| 'dark' \| 'brand'` | `'light'` | Theme preset |
| `themeOverrides` | `object` | `undefined` | Custom theme colors/spacing |
| `onSendMessage` | `(msg: string, convId: string) => void` | `undefined` | Callback when message sent |
| `onResponseReceived` | `(response: ChatMessage) => void` | `undefined` | Callback when response received |

### Web Component Attributes

Same props as React component, but use kebab-case:

```html
<amplify-chat
  conversation-id="my-chat"
  header-text="Custom Title"
  show-sources="true"
  theme-preset="dark"
  theme-overrides='{"primaryColor":"#ff6b6b"}'
></amplify-chat>
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
}
```

## Troubleshooting

### Component doesn't render

**Problem:** Web component shows nothing

**Solutions:**
1. Check browser console for errors
2. Verify script tag loaded: `console.log(customElements.get('amplify-chat'))`
3. Ensure Amplify backend is deployed: check `amplify_outputs.json` exists
4. Try React DevTools to inspect component tree

### "Authentication required" error

**Problem:** Error when sending message in authenticated mode

**Solutions:**
1. Verify backend `requireAuth` setting in DynamoDB ConfigurationTable
2. For guest mode: don't pass `userId` or `userToken` props
3. For authenticated mode: pass both `userId` AND `userToken` (not just one)
4. Check Lambda authorizer logs in CloudWatch

### Sources not displaying

**Problem:** No citations appear even though backend returns them

**Solutions:**
1. Verify `showSources={true}` prop is set
2. Check GraphQL response includes `sources` array
3. Inspect backend Lambda logs for source extraction
4. Verify Bedrock Knowledge Base has indexed documents

### Theme not applying

**Problem:** Custom theme colors don't work

**Solutions:**
1. Check `themePreset` value is valid: 'light', 'dark', or 'brand'
2. For overrides, use valid JSON: `theme-overrides='{"primaryColor":"#ff0000"}'`
3. Verify CSS custom properties are supported by browser (IE11 not supported)
4. Use browser DevTools to inspect element styles

### Bundle size too large

**Problem:** Web component script is slow to load

**Solutions:**
1. Verify using gzipped version (most CDNs auto-gzip)
2. Expected size: ~121 KB gzipped (production build)
3. Enable CDN caching headers
4. Consider code splitting for React component usage

### TypeScript errors

**Problem:** `npm run type-check` fails

**Solutions:**
1. Verify `amplify_outputs.json` exists at project root
2. Check TypeScript version: requires 5.x+
3. If error is in `amplify/data/resource.ts`, that's parent project (outside component scope)
4. Component itself should type-check: `cd src/amplify-chat && npm run type-check`

For more issues, see: [docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md)

## Related Documentation

- [Component API](../../docs/AMPLIFY_CHAT.md) - Full API reference
- [Architecture](../../docs/ARCHITECTURE.md) - System design
- [Development](../../docs/DEVELOPMENT.md) - Development patterns

## License

MIT
