# Amplify Chat Component

A reusable, embeddable React component for AI chat with source attribution. Built with AWS Amplify AI Kit and Bedrock Knowledge Base.

## Features

✨ **Embeddable** - Use in any React application
🤖 **AI-Powered** - Integrates with AWS Bedrock and Claude
📚 **Source Attribution** - Displays document sources for every response
🎨 **Styled** - Professional styling compatible with Cloudscape Design System
♿ **Accessible** - WCAG 2.1 AA compliant
📱 **Responsive** - Works on desktop, tablet, and mobile
🌙 **Dark Mode** - Supports system dark mode preferences
✅ **Tested** - Comprehensive component tests included

## Installation

### Prerequisites

- React 18+
- AWS Amplify (`@aws-amplify/ui-react-ai`)
- Amplify backend configured with chat route (see Phase-1 setup)
- Bedrock Knowledge Base created

### Package Installation

```bash
npm install @ragstack/amplify-chat aws-amplify @aws-amplify/ui-react-ai
```

Or with yarn:

```bash
yarn add @ragstack/amplify-chat aws-amplify @aws-amplify/ui-react-ai
```

## Quick Start

### Basic Usage

```tsx
import React from 'react';
import { ChatWithSources } from '@ragstack/amplify-chat';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';

export function App() {
  return (
    <Authenticator>
      <ChatWithSources />
    </Authenticator>
  );
}
```

### With Custom Props

```tsx
<ChatWithSources
  conversationId="my-chat-session"
  headerText="Ask a Question"
  headerSubtitle="About your documents"
  showSources={true}
  onSendMessage={(message, conversationId) => {
    console.log('User sent:', message);
  }}
  onResponseReceived={(response) => {
    console.log('Got response:', response);
  }}
/>
```

### Without Authentication Wrapper

```tsx
// If your app already has authentication,
// use the component directly without Authenticator

export function ChatPage() {
  return (
    <div className="chat-container">
      <ChatWithSources conversationId="app-chat" />
    </div>
  );
}
```

## Props

### `ChatWithSourcesProps`

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `conversationId` | string | `"default"` | Unique ID for the conversation thread |
| `headerText` | string | `"Document Q&A"` | Title shown in the chat header |
| `headerSubtitle` | string | `"Ask questions about your documents"` | Subtitle text |
| `inputPlaceholder` | string | `"Ask a question..."` | Placeholder for input field |
| `showSources` | boolean | `true` | Show/hide sources section |
| `maxWidth` | string | `"100%"` | CSS max-width for the component |
| `className` | string | - | Custom CSS class for the container |
| `onSendMessage` | function | - | Callback when user sends a message |
| `onResponseReceived` | function | - | Callback when AI responds |

### Callback Functions

#### `onSendMessage`

Called when the user sends a message.

```tsx
onSendMessage={(message: string, conversationId: string) => {
  console.log(`[${conversationId}] User: ${message}`);
}}
```

#### `onResponseReceived`

Called when the AI responds.

```tsx
onResponseReceived={(response: ChatMessage) => {
  console.log('AI Response:', response);
  // response.content - the AI's answer
  // response.sources - array of cited sources
}}
```

## Types

### `Source`

Represents a document source cited by the AI.

```tsx
interface Source {
  title: string;      // Document filename
  location: string;   // Page number or character offset
  snippet: string;    // Quote from the document
}
```

### `ChatMessage`

Represents a message in the conversation.

```tsx
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: string;
}
```

## Styling

### CSS Customization

The component uses CSS modules with design tokens for easy customization.

#### Change Primary Color

```css
:root {
  --chat-color-source-accent: #your-color;
  --chat-color-user-bg: #your-color;
}
```

#### Change Font

```css
:root {
  --chat-font-family: 'Your Font Family', sans-serif;
  --chat-font-size-base: 16px;
}
```

#### Change Spacing

```css
:root {
  --chat-spacing-lg: 20px;
  --chat-spacing-md: 12px;
}
```

See `src/styles/ChatWithSources.module.css` for all available design tokens.

### Styling Without CSS Modules

If your app doesn't use CSS modules, import the component and override styles:

```tsx
import ChatWithSources from '@ragstack/amplify-chat';
import styles from '@ragstack/amplify-chat/dist/styles/ChatWithSources.module.css';
import './overrides.css'; // Your custom styles

// In overrides.css:
.chatContainer {
  background: #fff;
  border-radius: 12px;
}
```

## Integration Examples

### In a Multi-Page App

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ChatWithSources } from '@ragstack/amplify-chat';
import { Authenticator } from '@aws-amplify/ui-react';

export function App() {
  return (
    <Authenticator>
      <BrowserRouter>
        <Routes>
          <Route path="/chat" element={<ChatWithSources />} />
          <Route path="/docs" element={<DocumentPage />} />
        </Routes>
      </BrowserRouter>
    </Authenticator>
  );
}
```

### Embedded in a Sidebar

```tsx
import { ChatWithSources } from '@ragstack/amplify-chat';

export function Dashboard() {
  return (
    <div className="dashboard-layout">
      <main className="dashboard-content">
        {/* Main content */}
      </main>
      <aside className="sidebar">
        <ChatWithSources maxWidth="400px" />
      </aside>
    </div>
  );
}
```

### With Custom Styling

```tsx
import { ChatWithSources } from '@ragstack/amplify-chat';
import './custom-chat.css';

export function CustomChat() {
  return (
    <ChatWithSources
      className="branded-chat"
      headerText="Ask Our AI"
      headerSubtitle="Powered by your docs"
    />
  );
}
```

In `custom-chat.css`:

```css
.branded-chat :root {
  --chat-color-source-accent: #ff6b35;
  --chat-font-family: 'Inter', sans-serif;
}

.branded-chat {
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}
```

## Backend Setup (Phase-1)

This component requires a backend configured with Amplify AI Kit. See the main project docs for Phase-1 setup:

1. **Backend Configuration** (`amplify/data/resource.ts`)
   - Defines conversation route with Claude model
   - Sets up Bedrock Knowledge Base integration
   - Configures source extraction

2. **Knowledge Base**
   - Created by SAM deployment
   - Contains documents and embeddings
   - Referenced by Amplify backend via environment variable

3. **Authentication**
   - Amplify sets up Cognito user pool
   - Component assumes parent app provides authentication
   - Authenticator wrapper handles user login

## Testing

### Run Component Tests

```bash
npm test
```

### Run Tests in Watch Mode

```bash
npm test -- --watch
```

### Generate Coverage Report

```bash
npm test -- --coverage
```

## Troubleshooting

### "AIConversation component not found"

Install Amplify UI:

```bash
npm install @aws-amplify/ui-react-ai
```

### "Bedrock Knowledge Base not found"

Ensure:
1. SAM deployment created the Knowledge Base
2. Amplify backend has `KNOWLEDGE_BASE_ID` environment variable set
3. Region matches where KB was created

### "User not authenticated"

The component doesn't handle auth. Wrap it in Authenticator:

```tsx
<Authenticator>
  <ChatWithSources />
</Authenticator>
```

### Dark mode not working

System must have dark mode preference set. Test with:

```bash
# On macOS
defaults write -g AppleInterfaceStyle Dark

# On Windows/Linux
# Use system settings for dark mode
```

### Styling conflicts

If styles are overridden, check:
1. CSS specificity - add `!important` if needed
2. CSS module conflicts - rename classes
3. Global styles - ensure no conflicting selectors

## Development

### Build from Source

```bash
cd src/amplify-chat
npm install
npm run build
```

### Run Tests

```bash
npm test
```

### Watch Mode (Development)

```bash
npm run build:watch
```

## Contributing

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes and add tests
3. Run tests: `npm test`
4. Build: `npm run build`
5. Commit: `git commit -m "feat: describe your change"`
6. Push: `git push origin feature/my-feature`
7. Create Pull Request

## License

MIT

## Support

For issues and questions:
- Check [GitHub Issues](https://github.com/your-org/RAGStack-Lambda/issues)
- See main project documentation: [RAGStack-Lambda](https://github.com/your-org/RAGStack-Lambda)
- Review [TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md)

## Changelog

### v1.0.0 (2024-11-03)

- Initial release
- Embeddable ChatWithSources component
- Source display with citations
- Cloudscape-compatible styling
- Full TypeScript support
- Comprehensive tests
- Dark mode support
