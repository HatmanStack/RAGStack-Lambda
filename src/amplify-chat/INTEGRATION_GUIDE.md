# Amplify Chat Component - Integration Guide

A comprehensive guide for integrating the `ChatWithSources` component into your React applications.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Basic Setup](#basic-setup)
4. [Configuration](#configuration)
5. [Authentication](#authentication)
6. [Styling](#styling)
7. [Advanced Usage](#advanced-usage)
8. [Performance](#performance)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

Before integrating the component, ensure you have:

- **React 18+** - Component uses React 18 features
- **Amplify Backend** - Phase-1 implementation with chat route configured
- **Bedrock Knowledge Base** - Created and configured via SAM deployment
- **AWS Credentials** - Configured in your local environment or CI/CD
- **Amplify Project** - `amplify init` already run in the repository

### Verify Prerequisites

```bash
# Check React version
npm list react

# Verify Amplify CLI
amplify status

# Verify AWS credentials
aws sts get-caller-identity

# Check Bedrock KB exists
aws bedrock-agent list-knowledge-bases --region us-east-1
```

## Installation

### Step 1: Install Dependencies

```bash
npm install @ragstack/amplify-chat aws-amplify @aws-amplify/ui-react-ai
```

### Step 2: Configure Amplify (if not already done)

```bash
# Run from project root
amplify init

# Or if already initialized
amplify status
```

### Step 3: Set Environment Variables

Create `.env` (or `.env.local` for local development):

```bash
VITE_AWS_REGION=us-east-1
VITE_KNOWLEDGE_BASE_ID=your-kb-id-here
```

Or for Next.js:

```bash
NEXT_PUBLIC_AWS_REGION=us-east-1
NEXT_PUBLIC_KNOWLEDGE_BASE_ID=your-kb-id-here
```

## Basic Setup

### Step 1: Configure Amplify Client

In your main application entry point (`main.tsx`, `index.tsx`, or `_app.tsx`):

```tsx
import React from 'react';
import { Amplify } from 'aws-amplify';
import outputs from './amplify_outputs.json';

// Configure Amplify with generated backend outputs
Amplify.configure(outputs);

// Rest of your app initialization
```

The `amplify_outputs.json` is auto-generated when you run:

```bash
amplify sandbox
# or
amplify publish
```

### Step 2: Import Component

```tsx
import { ChatWithSources } from '@ragstack/amplify-chat';
import '@aws-amplify/ui-react/styles.css'; // Amplify styles
```

### Step 3: Add to App

```tsx
import React from 'react';
import { Authenticator } from '@aws-amplify/ui-react';
import { ChatWithSources } from '@ragstack/amplify-chat';

export function App() {
  return (
    <Authenticator>
      <ChatWithSources />
    </Authenticator>
  );
}
```

## Configuration

### Per-Instance Configuration

Each `<ChatWithSources />` instance can be configured independently:

```tsx
<ChatWithSources
  // Unique conversation ID (maintain conversation history)
  conversationId="dashboard-chat"

  // UI Text
  headerText="Ask About Your Documents"
  headerSubtitle="Powered by AI"

  // Behavior
  showSources={true}
  maxWidth="600px"

  // Callbacks
  onSendMessage={(message, convId) => {
    // Track analytics
    analytics.track('chat_message_sent', {
      conversationId: convId,
      messageLength: message.length,
    });
  }}

  onResponseReceived={(response) => {
    // Save to database
    saveConversation({
      message: response.content,
      sources: response.sources,
    });
  }}
/>
```

### Global Configuration

For application-wide settings, create a config wrapper:

```tsx
// config/chatConfig.ts
export const CHAT_CONFIG = {
  defaultConversationId: 'app-main',
  headerText: 'Help & Support',
  headerSubtitle: 'Ask questions about our services',
  showSources: true,
  maxWidth: '100%',
};

// components/ChatWithConfig.tsx
import { ChatWithSources } from '@ragstack/amplify-chat';
import { CHAT_CONFIG } from '../config/chatConfig';

export function ChatWithConfig() {
  return <ChatWithSources {...CHAT_CONFIG} />;
}
```

## Authentication

### Option 1: Using Amplify Authenticator (Recommended)

Wrap your app with the Authenticator component:

```tsx
import { Authenticator } from '@aws-amplify/ui-react';
import { ChatWithSources } from '@ragstack/amplify-chat';
import '@aws-amplify/ui-react/styles.css';

export function App() {
  return (
    <Authenticator>
      <ChatWithSources />
    </Authenticator>
  );
}
```

The Authenticator:
- Provides login/signup UI
- Manages user sessions
- Handles Cognito integration automatically
- Is optional for the ChatWithSources component

### Option 2: Custom Authentication

If you have your own auth system:

```tsx
import { ChatWithSources } from '@ragstack/amplify-chat';
import { useAuth } from './hooks/useAuth';

export function ChatPage() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginForm />;
  }

  return <ChatWithSources />;
}
```

The component will still work because:
- Amplify handles auth internally
- Bedrock KB enforces permissions
- User identity is from Cognito

### Option 3: No Authentication (Not Recommended for Production)

For development or public endpoints:

```tsx
// ⚠️ Only use in development or with other security measures
<ChatWithSources conversationId="public-demo" />
```

Be aware:
- API calls are still authenticated via Cognito (if configured)
- Bedrock KB access depends on IAM policies
- Consider implementing rate limiting

## Styling

### Option 1: Use Default Styling

No additional CSS needed - component comes styled:

```tsx
<ChatWithSources />
```

### Option 2: Override Design Tokens

Create a CSS file with custom design tokens:

```css
/* styles/chat-theme.css */

:root {
  /* Colors */
  --chat-color-user-bg: #your-primary-color;
  --chat-color-source-accent: #your-accent-color;

  /* Spacing */
  --chat-spacing-lg: 20px;

  /* Typography */
  --chat-font-size-base: 16px;
}

/* Custom component styling */
.customChat {
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}
```

Then use:

```tsx
import './styles/chat-theme.css';

<ChatWithSources className="customChat" />
```

### Option 3: CSS-in-JS Integration

For apps using styled-components or Emotion:

```tsx
import styled from 'styled-components';
import { ChatWithSources } from '@ragstack/amplify-chat';

const StyledChat = styled.div`
  .chatContainer {
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  }

  --chat-color-user-bg: ${props => props.theme.primary};
  --chat-color-source-accent: ${props => props.theme.accent};
`;

export function ThemedChat() {
  return (
    <StyledChat>
      <ChatWithSources />
    </StyledChat>
  );
}
```

### Option 4: Tailwind CSS

For Tailwind-based apps:

```tsx
import { ChatWithSources } from '@ragstack/amplify-chat';

export function TailwindChat() {
  return (
    <div className="rounded-lg shadow-lg">
      <ChatWithSources
        maxWidth="100%"
        className="chat-container"
      />
    </div>
  );
}
```

And in your CSS:

```css
@layer components {
  .chat-container {
    @apply rounded-lg border border-gray-200 bg-white;
  }

  .chat-container :root {
    --chat-color-user-bg: theme('colors.primary');
  }
}
```

## Advanced Usage

### Multiple Chat Instances

Run separate conversations:

```tsx
export function MultiChatApp() {
  return (
    <div className="chat-grid">
      <ChatWithSources
        conversationId="support"
        headerText="Support Chat"
      />
      <ChatWithSources
        conversationId="documentation"
        headerText="Documentation Chat"
      />
    </div>
  );
}
```

Each conversation:
- Maintains separate history
- Stores separately in DynamoDB
- Can be retrieved independently

### Track User Interactions

```tsx
export function AnalyticsChat() {
  const handleSendMessage = (message: string, convId: string) => {
    // Send to analytics service
    mixpanel.track('Chat Message', {
      conversationId: convId,
      messageLength: message.length,
      timestamp: new Date().toISOString(),
    });
  };

  const handleResponseReceived = (response: ChatMessage) => {
    // Log response metrics
    if (response.sources && response.sources.length > 0) {
      mixpanel.track('Chat Response with Sources', {
        sourceCount: response.sources.length,
        responseLength: response.content.length,
      });
    }
  };

  return (
    <ChatWithSources
      onSendMessage={handleSendMessage}
      onResponseReceived={handleResponseReceived}
    />
  );
}
```

### Integrate with State Management

For apps using Redux, Zustand, or other state management:

```tsx
// Redux example
import { useDispatch } from 'react-redux';
import { ChatWithSources } from '@ragstack/amplify-chat';
import { saveConversation } from './store/conversationSlice';

export function ConnectedChat() {
  const dispatch = useDispatch();

  return (
    <ChatWithSources
      onResponseReceived={(response) => {
        dispatch(saveConversation({
          message: response.content,
          sources: response.sources,
          timestamp: response.timestamp,
        }));
      }}
    />
  );
}
```

### Modal or Drawer Integration

```tsx
import { ChatWithSources } from '@ragstack/amplify-chat';

export function ChatModal({ isOpen, onClose }: ModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Chat with AI</DialogTitle>
        </DialogHeader>
        <ChatWithSources
          maxWidth="100%"
          headerText=""
          headerSubtitle=""
        />
      </DialogContent>
    </Dialog>
  );
}
```

## Performance

### Optimization Tips

#### 1. Memoize Component

```tsx
import { useMemo } from 'react';
import { ChatWithSources } from '@ragstack/amplify-chat';

export function OptimizedChat() {
  const chatProps = useMemo(
    () => ({
      conversationId: 'main',
      headerText: 'Ask Questions',
    }),
    []
  );

  return <ChatWithSources {...chatProps} />;
}
```

#### 2. Lazy Load Component

```tsx
import { lazy, Suspense } from 'react';

const ChatWithSources = lazy(() =>
  import('@ragstack/amplify-chat').then(m => ({
    default: m.ChatWithSources,
  }))
);

export function App() {
  return (
    <Suspense fallback={<Loading />}>
      <ChatWithSources />
    </Suspense>
  );
}
```

#### 3. Debounce Callbacks

```tsx
import { useCallback, useRef } from 'react';

export function DebouncedChat() {
  const debounceTimerRef = useRef<NodeJS.Timeout>();

  const handleSendMessage = useCallback((message: string) => {
    clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => {
      // Save to database
      api.saveMessage(message);
    }, 1000);
  }, []);

  return (
    <ChatWithSources onSendMessage={handleSendMessage} />
  );
}
```

## Troubleshooting

### Component Doesn't Render

**Problem:** Component appears blank or doesn't show

**Solution:**
1. Check Amplify is configured: `amplify status`
2. Verify `amplify_outputs.json` exists in project root
3. Ensure `<Authenticator>` wraps the component
4. Check browser console for errors

### "Knowledge Base not found" Error

**Problem:** Getting error about missing Knowledge Base

**Solution:**
1. Verify SAM deployment created KB: `aws bedrock-agent list-knowledge-bases`
2. Check `KNOWLEDGE_BASE_ID` environment variable is set
3. Ensure Amplify backend has access to KB (check IAM roles)
4. Verify KB is in same region as Amplify deployment

### Styling Issues

**Problem:** Styles aren't applying or are overridden

**Solution:**
1. Check CSS modules are loading: `npm run build`
2. Verify no global CSS is overriding component styles
3. Use DevTools to inspect applied styles
4. Check CSS specificity of custom styles
5. Add `!important` if needed for overrides

### Authentication Errors

**Problem:** Getting auth-related errors

**Solution:**
1. Verify Cognito user pool is created: `amplify status`
2. Check user credentials are correct
3. Verify AWS region matches: `echo $AWS_REGION`
4. Check IAM policies allow Bedrock KB access
5. Review CloudWatch logs: `aws logs tail /aws/lambda/chat-lambda --follow`

### Performance Issues

**Problem:** Component is slow or laggy

**Solution:**
1. Check network latency: Open DevTools Network tab
2. Monitor message streaming: Should see chunks arriving
3. Check component re-renders: Use React DevTools Profiler
4. Verify Bedrock model is responsive: Test via AWS Console
5. Check DynamoDB throughput: May need to increase capacity

### Dark Mode Not Working

**Problem:** Dark mode styles not applying

**Solution:**
1. Verify system dark mode is enabled
2. Check browser supports `prefers-color-scheme`
3. Set preference in browser DevTools
4. Override with CSS if system preference not working:

```css
@media (prefers-color-scheme: dark) {
  :root {
    --chat-color-bg: #1a1a1a;
    /* etc */
  }
}
```

## Getting Help

- **Issues**: Open GitHub issue in main repo
- **Docs**: See `/docs` folder in RAGStack-Lambda
- **Slack/Discord**: Check project community channels
- **AWS Support**: For infrastructure issues

## Next Steps

1. ✅ Install and configure component
2. ✅ Test with Amplify sandbox: `npx ampx sandbox`
3. ✅ Deploy backend: `amplify publish`
4. ✅ Build your app: `npm run build`
5. ✅ Deploy frontend: Follow your deployment process
6. ✅ Monitor in AWS Console for issues

For more details, see the main project documentation in `/docs`.
