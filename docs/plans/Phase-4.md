# Phase 4: Chat Frontend - UI Components

## Overview

Create a conversational chat interface at `/chat` route with:
- Message bubbles (user vs AI)
- Session-based conversation history
- Source citations display
- "New Chat" functionality
- CloudScape Design System components

**Estimated Duration**: 1.5 days
**Estimated Token Count**: ~35,000 tokens

---

## Goals

- [ ] Chat components created (ChatPanel, MessageBubble, SourceList)
- [ ] Chat page added with `/chat` route
- [ ] Navigation updated with Chat link
- [ ] GraphQL query updated for sessionId
- [ ] Session state management working
- [ ] Source citations displayed
- [ ] Component tests passing (80%+ coverage)
- [ ] Manual UI testing complete
- [ ] Styling complete (message bubbles, loader animation)

---

## Prerequisites

- Phase 3 complete (backend returns ChatResponse with sessionId)
- Frontend environment working (`npm start`)
- Familiar with React hooks, CloudScape components
- Understand React Testing Library and Vitest

---

## Key Patterns to Reference

Throughout this phase, use these subagent queries when you need examples:

**Component Structure**:
- "Use explore-base-general to show the chat panel component structure and state management patterns"

**CloudScape Patterns**:
- "Use explore-base-general to find CloudScape Container, SpaceBetween, and FormField usage patterns"

**GraphQL Integration**:
- "Use explore-base-general to show how AWS Amplify GraphQL client is used in React components"

**Testing Patterns**:
- "Use explore-base-testing to find React component testing patterns with Vitest and Testing Library"

---

## Tasks

### Task 4.1: Update GraphQL Query

**Goal**: Modify queryKnowledgeBase query to include sessionId parameter

**Files to Modify**:
- `src/ui/src/graphql/queries/queryKnowledgeBase.js`

**Prerequisites**: None (first task)

**Instructions**:

1. **Locate existing query file**:
   - Should be in `src/ui/src/graphql/queries/`
   - May already exist from Phase 3 or earlier

2. **Update query to match Phase 3 schema**:
   ```javascript
   export const queryKnowledgeBase = /* GraphQL */ `
     query QueryKnowledgeBase($query: String!, $sessionId: String) {
       queryKnowledgeBase(query: $query, sessionId: $sessionId) {
         answer
         sessionId
         error
         sources {
           documentId
           pageNumber
           s3Uri
           snippet
         }
       }
     }
   `;
   ```

3. **Understand the change**:
   - Added `$sessionId: String` parameter (optional)
   - Added `sessionId` to response (Bedrock returns this)
   - Added `error` field for error handling
   - Added structured `sources` array (replaces generic citations)

**Verification Checklist**:

- [ ] Query file updated
- [ ] sessionId parameter is optional (no `!` required marker)
- [ ] All response fields match Phase 3 GraphQL schema
- [ ] Syntax is valid GraphQL

**Testing**: No automated tests (query definition only)

**Commit Message**:
```
feat(graphql): update queryKnowledgeBase for chat support

- Add optional sessionId parameter for conversation history
- Add sessionId to response for client-side session tracking
- Add error field for graceful error handling
- Add structured sources array with documentId and pageNumber
```

**Estimated Tokens**: ~2,000

---

### Task 4.2: Create Chat Component Structure

**Goal**: Set up component directory and create page wrapper

**Files to Create**:
- `src/ui/src/components/Chat/index.jsx` (main page)
- `src/ui/src/components/Chat/ChatPanel.jsx` (chat interface - stub)
- `src/ui/src/components/Chat/MessageBubble.jsx` (message display - stub)
- `src/ui/src/components/Chat/SourceList.jsx` (citations - stub)
- `src/ui/src/components/Chat/ChatPanel.css` (styling - empty)

**Prerequisites**: Task 4.1 complete

**Instructions**:

1. **Create directory**:
   ```bash
   mkdir -p src/ui/src/components/Chat
   ```

2. **Create main Chat page** (`index.jsx`):

   This is the route-level component that wraps the chat interface in CloudScape layout.

   **Pattern to reference**:
   - Look at existing pages (Dashboard, Upload, Search) for ContentLayout usage
   - Use CloudScape Header component with description

   **Key implementation points**:
   ```jsx
   import React from 'react';
   import { ContentLayout, Header } from '@cloudscape-design/components';
   import { ChatPanel } from './ChatPanel';

   export function Chat() {
     return (
       <ContentLayout
         header={
           <Header
             variant="h1"
             description="Ask questions about your documents using natural language"
           >
             Knowledge Base Chat
           </Header>
         }
       >
         <ChatPanel />
       </ContentLayout>
     );
   }
   ```

3. **Create component stubs**:

   Create placeholder files for the other components (will implement in later tasks):

   **ChatPanel.jsx** (stub):
   ```jsx
   import React from 'react';
   import { Container } from '@cloudscape-design/components';

   export function ChatPanel() {
     return <Container>ChatPanel - TODO</Container>;
   }
   ```

   **MessageBubble.jsx** (stub):
   ```jsx
   import React from 'react';

   export function MessageBubble({ message }) {
     return <div>MessageBubble - TODO</div>;
   }
   ```

   **SourceList.jsx** (stub):
   ```jsx
   import React from 'react';

   export function SourceList({ sources }) {
     return null; // Render nothing for now
   }
   ```

   **ChatPanel.css** (empty file for now)

4. **Understand the component hierarchy**:
   ```
   Chat (page)
   └── ChatPanel (main interface)
       ├── Container (CloudScape)
       ├── Messages list
       │   └── MessageBubble (each message)
       │       └── SourceList (for AI messages)
       └── Input section (FormField + Input + Button)
   ```

**Verification Checklist**:

- [ ] Chat directory created
- [ ] index.jsx renders ContentLayout with Header
- [ ] Stub components created (will implement later)
- [ ] No TypeScript errors
- [ ] Files import correctly

**Testing**:

Write a simple smoke test:

```jsx
// src/ui/src/components/Chat/Chat.test.jsx
import { render, screen } from '@testing-library/react';
import { Chat } from './index';

describe('Chat Page', () => {
  test('renders header', () => {
    render(<Chat />);
    expect(screen.getByText(/Knowledge Base Chat/i)).toBeInTheDocument();
  });

  test('renders description', () => {
    render(<Chat />);
    expect(screen.getByText(/Ask questions about your documents/i)).toBeInTheDocument();
  });
});
```

**Commit Message**:
```
feat(chat): create chat component structure

- Add Chat page wrapper with ContentLayout
- Add ChatPanel stub (will implement in next task)
- Add MessageBubble and SourceList stubs
- Add basic smoke test for Chat page
```

**Estimated Tokens**: ~3,000

---

### Task 4.3: Implement ChatPanel Component (TDD)

**Goal**: Build main chat interface with state management, message handling, and session tracking

**Files to Modify**:
- `src/ui/src/components/Chat/ChatPanel.jsx`
- `src/ui/src/components/Chat/ChatPanel.test.jsx` (create)

**Prerequisites**: Task 4.2 complete

**Important**: Follow TDD - write tests FIRST, then implement

---

#### Step 1: Write Tests First

**Test File**: `src/ui/src/components/Chat/ChatPanel.test.jsx`

**Subagent Reference** (if needed):
- "Use explore-base-testing to show React component testing patterns with mocked GraphQL"

**Test Structure**:

```jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { ChatPanel } from './ChatPanel';

// Mock AWS Amplify GraphQL client
vi.mock('aws-amplify/api', () => ({
  generateClient: () => ({
    graphql: vi.fn()
  })
}));

describe('ChatPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders empty state initially', () => {
    render(<ChatPanel />);

    // Should show empty state message
    expect(screen.getByText(/Start a conversation/i)).toBeInTheDocument();

    // Should have input and send button
    expect(screen.getByPlaceholderText(/Ask a question/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Send/i })).toBeInTheDocument();
  });

  test('sends message and displays user message immediately', async () => {
    const mockResponse = {
      data: {
        queryKnowledgeBase: {
          answer: 'Test answer from AI',
          sessionId: 'session-123',
          sources: [],
          error: null
        }
      }
    };

    const { generateClient } = require('aws-amplify/api');
    generateClient().graphql.mockResolvedValue(mockResponse);

    render(<ChatPanel />);

    const input = screen.getByPlaceholderText(/Ask a question/i);
    const sendButton = screen.getByRole('button', { name: /Send/i });

    // Type and send message
    fireEvent.change(input, { target: { value: 'What is this?' } });
    fireEvent.click(sendButton);

    // User message should appear immediately
    expect(screen.getByText('What is this?')).toBeInTheDocument();

    // Wait for AI response
    await waitFor(() => {
      expect(screen.getByText('Test answer from AI')).toBeInTheDocument();
    });

    // Input should be cleared
    expect(input).toHaveValue('');
  });

  test('maintains sessionId across multiple messages', async () => {
    const { generateClient } = require('aws-amplify/api');
    const mockGraphql = generateClient().graphql;

    // First response creates session
    mockGraphql.mockResolvedValueOnce({
      data: {
        queryKnowledgeBase: {
          answer: 'First answer',
          sessionId: 'session-abc',
          sources: [],
          error: null
        }
      }
    });

    // Second response uses same session
    mockGraphql.mockResolvedValueOnce({
      data: {
        queryKnowledgeBase: {
          answer: 'Second answer with context',
          sessionId: 'session-abc',
          sources: [],
          error: null
        }
      }
    });

    render(<ChatPanel />);

    // Send first message
    const input = screen.getByPlaceholderText(/Ask a question/i);
    fireEvent.change(input, { target: { value: 'First question' } });
    fireEvent.click(screen.getByRole('button', { name: /Send/i }));

    await waitFor(() => {
      expect(screen.getByText('First answer')).toBeInTheDocument();
    });

    // Send second message
    fireEvent.change(input, { target: { value: 'Follow-up question' } });
    fireEvent.click(screen.getByRole('button', { name: /Send/i }));

    await waitFor(() => {
      expect(screen.getByText('Second answer with context')).toBeInTheDocument();
    });

    // Verify sessionId was passed on second call
    const secondCall = mockGraphql.mock.calls[1][0];
    expect(secondCall.variables.sessionId).toBe('session-abc');
  });

  test('displays error message when backend returns error', async () => {
    const mockError = {
      data: {
        queryKnowledgeBase: {
          answer: '',
          sessionId: null,
          sources: [],
          error: 'Session expired. Please start a new conversation.'
        }
      }
    };

    const { generateClient } = require('aws-amplify/api');
    generateClient().graphql.mockResolvedValue(mockError);

    render(<ChatPanel />);

    fireEvent.change(screen.getByPlaceholderText(/Ask/i), { target: { value: 'Test' } });
    fireEvent.click(screen.getByRole('button', { name: /Send/i }));

    await waitFor(() => {
      expect(screen.getByText(/Session expired/i)).toBeInTheDocument();
    });
  });

  test('new chat button resets conversation and session', async () => {
    const mockResponse = {
      data: {
        queryKnowledgeBase: {
          answer: 'Answer',
          sessionId: 'session-1',
          sources: [],
          error: null
        }
      }
    };

    const { generateClient } = require('aws-amplify/api');
    generateClient().graphql.mockResolvedValue(mockResponse);

    render(<ChatPanel />);

    // Send a message
    fireEvent.change(screen.getByPlaceholderText(/Ask/i), { target: { value: 'Q' } });
    fireEvent.click(screen.getByRole('button', { name: /Send/i }));

    await waitFor(() => {
      expect(screen.getByText('Answer')).toBeInTheDocument();
    });

    // Click New Chat button
    const newChatButton = screen.getByRole('button', { name: /New Chat/i });
    fireEvent.click(newChatButton);

    // Empty state should return
    expect(screen.getByText(/Start a conversation/i)).toBeInTheDocument();

    // Previous messages should be gone
    expect(screen.queryByText('Answer')).not.toBeInTheDocument();
  });

  test('disables send button when input is empty', () => {
    render(<ChatPanel />);

    const sendButton = screen.getByRole('button', { name: /Send/i });
    expect(sendButton).toBeDisabled();

    const input = screen.getByPlaceholderText(/Ask/i);
    fireEvent.change(input, { target: { value: 'Some text' } });

    expect(sendButton).not.toBeDisabled();
  });

  test('supports Enter key to send message', async () => {
    const mockResponse = {
      data: {
        queryKnowledgeBase: {
          answer: 'Response',
          sessionId: 'sess-1',
          sources: [],
          error: null
        }
      }
    };

    const { generateClient } = require('aws-amplify/api');
    generateClient().graphql.mockResolvedValue(mockResponse);

    render(<ChatPanel />);

    const input = screen.getByPlaceholderText(/Ask/i);
    fireEvent.change(input, { target: { value: 'Question' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText('Response')).toBeInTheDocument();
    });
  });
});
```

**Run tests** - they should FAIL (Red):
```bash
cd src/ui
npm test -- ChatPanel.test.jsx
```

---

#### Step 2: Implement ChatPanel

**Subagent References** (suggested):
- "Use explore-base-general to show state management patterns for chat interfaces with sessionId"
- "Use explore-base-general to find auto-scroll patterns for message lists"

**Implementation Guide**:

**State Variables Needed**:
```jsx
const [messages, setMessages] = useState([]);          // Array of message objects
const [inputValue, setInputValue] = useState('');     // Current input text
const [isLoading, setIsLoading] = useState(false);    // Loading state during API call
const [error, setError] = useState(null);             // Error message string or null
const [sessionId, setSessionId] = useState(null);     // Bedrock session ID
```

**Message Object Structure**:
```javascript
{
  type: 'user' | 'assistant',
  content: 'message text',
  sources: [],  // Only for assistant messages
  timestamp: '2024-01-01T00:00:00.000Z'
}
```

**Key Functions to Implement**:

1. **handleSend**:
   - Validate input (not empty/whitespace)
   - Create user message object and add to messages
   - Clear input field
   - Set loading state
   - Call GraphQL API with query and optional sessionId
   - Handle response:
     - If error: display error alert, clear sessionId
     - If success: add AI message to messages, update sessionId
   - Clear loading state

2. **handleKeyPress**:
   - Check if Enter key (not Shift+Enter)
   - Call handleSend if Enter pressed

3. **handleNewChat**:
   - Clear messages array
   - Clear sessionId
   - Clear error
   - Reset input field

4. **Auto-scroll Effect**:
   - Use useEffect to scroll to bottom when messages change
   - Use ref on messages container

**CloudScape Components to Use**:
- `Container` - Main wrapper with header
- `SpaceBetween` - Vertical spacing
- `FormField` - Label for input
- `Input` - Text input
- `Button` - Send and New Chat buttons
- `Alert` - Error messages
- `Box` - Empty state message

**GraphQL Integration Pattern**:
```jsx
import { generateClient } from 'aws-amplify/api';
import { queryKnowledgeBase } from '../../graphql/queries/queryKnowledgeBase';

const client = React.useMemo(() => generateClient(), []);

// In handleSend:
const response = await client.graphql({
  query: queryKnowledgeBase,
  variables: {
    query: userMessage,
    sessionId: sessionId  // null for first message
  }
});

const data = response.data.queryKnowledgeBase;
```

**Layout Structure**:
```jsx
<Container
  header={
    <Box float="right">
      <Button onClick={handleNewChat} disabled={messages.length === 0}>
        New Chat
      </Button>
    </Box>
  }
>
  <SpaceBetween size="l">
    {error && <Alert type="error" dismissible onDismiss={...}>{error}</Alert>}

    <div className="chat-messages-container">
      {messages.length === 0 && <EmptyState />}
      {messages.map((msg, idx) => <MessageBubble key={idx} message={msg} />)}
      {isLoading && <LoadingIndicator />}
      <div ref={messagesEndRef} />
    </div>

    <FormField>
      <SpaceBetween direction="horizontal" size="xs">
        <Input
          value={inputValue}
          onChange={...}
          onKeyDown={...}
          placeholder="Ask a question..."
          disabled={isLoading}
        />
        <Button
          variant="primary"
          onClick={handleSend}
          disabled={isLoading || !inputValue.trim()}
        >
          Send
        </Button>
      </SpaceBetween>
    </FormField>
  </SpaceBetween>
</Container>
```

**Error Handling**:
```jsx
try {
  const response = await client.graphql({...});
  const data = response.data.queryKnowledgeBase;

  if (data.error) {
    setError(data.error);
    setSessionId(null);  // Reset session on error
    return;
  }

  // Success path
  setSessionId(data.sessionId);
  // ... add AI message
} catch (err) {
  console.error('Chat error:', err);
  setError('Failed to get response. Please try again.');
} finally {
  setIsLoading(false);
}
```

**Auto-scroll Implementation**:
```jsx
const messagesEndRef = useRef(null);

useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
}, [messages]);
```

**Run tests** - they should PASS (Green):
```bash
npm test -- ChatPanel.test.jsx
```

**Refactor** if needed while keeping tests green.

**Verification Checklist**:

- [ ] All tests passing
- [ ] State management working (messages, sessionId, loading, error)
- [ ] User messages appear immediately
- [ ] AI responses appear after API call
- [ ] SessionId maintained across messages
- [ ] New Chat resets everything
- [ ] Error handling works
- [ ] Input clears after send
- [ ] Send button disabled when empty/loading
- [ ] Enter key sends message
- [ ] Auto-scroll to bottom works

**Commit Message**:
```
feat(chat): implement ChatPanel with session management

- Add state management for messages, sessionId, loading, error
- Implement handleSend with GraphQL integration
- Add session persistence across messages
- Add New Chat functionality to reset conversation
- Implement auto-scroll to bottom on new messages
- Add Enter key support for sending
- Add comprehensive test coverage (8 test cases)
- Handle errors gracefully with user-friendly messages
```

**Estimated Tokens**: ~12,000

---

### Task 4.4: Create MessageBubble Component

**Goal**: Display individual messages with proper styling and source integration

**Files to Create**:
- `src/ui/src/components/Chat/MessageBubble.jsx`
- `src/ui/src/components/Chat/MessageBubble.test.jsx`

**Prerequisites**: Task 4.3 complete

**TDD Approach**: Write tests first

---

#### Step 1: Write Tests

```jsx
import { render, screen } from '@testing-library/react';
import { MessageBubble } from './MessageBubble';

describe('MessageBubble', () => {
  test('renders user message with correct styling', () => {
    const message = {
      type: 'user',
      content: 'What documents do we have?',
      timestamp: new Date().toISOString()
    };

    const { container } = render(<MessageBubble message={message} />);

    expect(screen.getByText('What documents do we have?')).toBeInTheDocument();

    const bubble = container.querySelector('.message-bubble');
    expect(bubble).toHaveClass('user-message');
  });

  test('renders assistant message with correct styling', () => {
    const message = {
      type: 'assistant',
      content: 'We have 5 invoices and 3 receipts.',
      timestamp: new Date().toISOString(),
      sources: []
    };

    const { container } = render(<MessageBubble message={message} />);

    expect(screen.getByText('We have 5 invoices and 3 receipts.')).toBeInTheDocument();

    const bubble = container.querySelector('.message-bubble');
    expect(bubble).toHaveClass('assistant-message');
  });

  test('displays timestamp for message', () => {
    const timestamp = new Date('2024-01-01T12:00:00.000Z');
    const message = {
      type: 'user',
      content: 'Test',
      timestamp: timestamp.toISOString()
    };

    render(<MessageBubble message={message} />);

    // Timestamp should be formatted as time only
    const timeString = timestamp.toLocaleTimeString();
    expect(screen.getByText(timeString)).toBeInTheDocument();
  });

  test('renders SourceList for assistant messages with sources', () => {
    const message = {
      type: 'assistant',
      content: 'Based on the documents...',
      timestamp: new Date().toISOString(),
      sources: [
        { documentId: 'doc1.pdf', pageNumber: 3, s3Uri: 's3://...', snippet: 'text' }
      ]
    };

    render(<MessageBubble message={message} />);

    // SourceList should be rendered (will implement in next task)
    // For now, just verify it's called
    expect(screen.getByText('Based on the documents...')).toBeInTheDocument();
  });

  test('does not render SourceList for user messages', () => {
    const message = {
      type: 'user',
      content: 'User question',
      timestamp: new Date().toISOString()
    };

    const { container } = render(<MessageBubble message={message} />);

    // Should not have sources section
    expect(container.querySelector('.sources')).not.toBeInTheDocument();
  });

  test('preserves line breaks in message content', () => {
    const message = {
      type: 'assistant',
      content: 'Line 1\nLine 2\nLine 3',
      timestamp: new Date().toISOString(),
      sources: []
    };

    render(<MessageBubble message={message} />);

    const content = screen.getByText(/Line 1/);
    expect(content).toHaveStyle({ whiteSpace: 'pre-wrap' });
  });
});
```

---

#### Step 2: Implement MessageBubble

**Implementation Guide**:

**Component Structure**:
```jsx
import React from 'react';
import { Box, SpaceBetween } from '@cloudscape-design/components';
import { SourceList } from './SourceList';

export function MessageBubble({ message }) {
  const isUser = message.type === 'user';
  const timestamp = new Date(message.timestamp).toLocaleTimeString();

  return (
    <div className={`message-bubble ${isUser ? 'user-message' : 'assistant-message'}`}>
      <SpaceBetween size="s">
        <Box>
          <div className="message-content">{message.content}</div>
          <div className="message-timestamp">{timestamp}</div>
        </Box>

        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceList sources={message.sources} />
        )}
      </SpaceBetween>
    </div>
  );
}
```

**Key Implementation Points**:

1. **Conditional Styling**: Use className to apply different styles for user vs assistant
2. **Timestamp Formatting**: Convert ISO string to readable time
3. **Conditional Sources**: Only show SourceList for assistant messages with sources
4. **Content Preservation**: CSS will handle line breaks (white-space: pre-wrap)

**Verification Checklist**:

- [ ] All tests passing
- [ ] User messages styled differently from assistant messages
- [ ] Timestamp displays correctly
- [ ] SourceList only appears for assistant messages with sources
- [ ] Line breaks preserved in content
- [ ] Component is pure (no side effects)

**Commit Message**:
```
feat(chat): add MessageBubble component with conditional styling

- Render user and assistant messages with different styles
- Display timestamp for each message
- Integrate SourceList for assistant messages
- Preserve line breaks in message content
- Add comprehensive test coverage
```

**Estimated Tokens**: ~5,000

---

### Task 4.5: Create SourceList Component

**Goal**: Display citation sources in expandable CloudScape section

**Files to Create**:
- `src/ui/src/components/Chat/SourceList.jsx`
- `src/ui/src/components/Chat/SourceList.test.jsx`

**Prerequisites**: Task 4.4 complete

---

#### Step 1: Write Tests

```jsx
import { render, screen } from '@testing-library/react';
import { SourceList } from './SourceList';

describe('SourceList', () => {
  test('renders nothing when sources array is empty', () => {
    const { container } = render(<SourceList sources={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  test('renders nothing when sources is null', () => {
    const { container } = render(<SourceList sources={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  test('renders expandable section with source count', () => {
    const sources = [
      { documentId: 'doc1.pdf', pageNumber: 1, s3Uri: 's3://...', snippet: 'Text 1' },
      { documentId: 'doc2.pdf', pageNumber: 2, s3Uri: 's3://...', snippet: 'Text 2' }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText(/Sources \(2\)/i)).toBeInTheDocument();
  });

  test('displays document names', () => {
    const sources = [
      { documentId: 'invoice-jan.pdf', pageNumber: 1, s3Uri: 's3://...', snippet: 'Invoice' },
      { documentId: 'receipt-feb.pdf', pageNumber: 3, s3Uri: 's3://...', snippet: 'Receipt' }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText('invoice-jan.pdf')).toBeInTheDocument();
    expect(screen.getByText('receipt-feb.pdf')).toBeInTheDocument();
  });

  test('displays page numbers when available', () => {
    const sources = [
      { documentId: 'doc.pdf', pageNumber: 5, s3Uri: 's3://...', snippet: 'Text' }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText(/Page 5/i)).toBeInTheDocument();
  });

  test('handles missing page numbers gracefully', () => {
    const sources = [
      { documentId: 'doc.pdf', pageNumber: null, s3Uri: 's3://...', snippet: 'Text' }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText('doc.pdf')).toBeInTheDocument();
    expect(screen.queryByText(/Page/i)).not.toBeInTheDocument();
  });

  test('displays snippets when available', () => {
    const sources = [
      { documentId: 'doc.pdf', pageNumber: 1, s3Uri: 's3://...', snippet: 'This is a snippet from the document' }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText(/"This is a snippet from the document"/i)).toBeInTheDocument();
  });
});
```

---

#### Step 2: Implement SourceList

**Subagent Reference** (if needed):
- "Use explore-base-general to find CloudScape ExpandableSection usage patterns"

**Implementation Guide**:

```jsx
import React from 'react';
import { Box, ExpandableSection } from '@cloudscape-design/components';

export function SourceList({ sources }) {
  // Early return if no sources
  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <ExpandableSection
      headerText={`Sources (${sources.length})`}
      variant="footer"
    >
      <Box variant="small">
        {sources.map((source, index) => (
          <Box key={index} padding={{ bottom: 's' }}>
            <Box variant="strong">{source.documentId}</Box>

            {source.pageNumber && (
              <Box variant="small" color="text-body-secondary">
                Page {source.pageNumber}
              </Box>
            )}

            {source.snippet && (
              <Box variant="small" color="text-body-secondary">
                "{source.snippet}..."
              </Box>
            )}
          </Box>
        ))}
      </Box>
    </ExpandableSection>
  );
}
```

**Key Implementation Points**:

1. **Early Return**: Return null if no sources (keeps component simple)
2. **ExpandableSection**: Uses CloudScape's collapsible section (collapsed by default)
3. **Source Count**: Shows count in header for user awareness
4. **Conditional Rendering**: Only show page number and snippet if they exist
5. **Styling**: Use CloudScape Box variants for consistent design

**Verification Checklist**:

- [ ] All tests passing
- [ ] Returns null when no sources
- [ ] Expandable section renders with count
- [ ] Document names displayed
- [ ] Page numbers shown when available
- [ ] Snippets shown when available
- [ ] Uses CloudScape components consistently

**Commit Message**:
```
feat(chat): add SourceList component for citation display

- Render sources in expandable CloudScape section
- Display document names, page numbers, and snippets
- Handle missing data gracefully
- Use CloudScape Box variants for styling
- Add comprehensive test coverage
```

**Estimated Tokens**: ~4,000

---

### Task 4.6: Add Chat Styling

**Goal**: Style message bubbles, loader animation, and scrollable container

**Files to Create**:
- `src/ui/src/components/Chat/ChatPanel.css`

**Prerequisites**: Tasks 4.3-4.5 complete

**Subagent Reference** (if needed):
- "Use explore-base-general to find CSS animation patterns for loading indicators"

**Instructions**:

Create comprehensive CSS file with these sections:

---

#### Messages Container

**Purpose**: Scrollable area for messages with max height

```css
.chat-messages-container {
  min-height: 400px;
  max-height: 600px;
  overflow-y: auto;
  padding: 16px;
  background-color: #f9f9f9;
  border-radius: 8px;
}
```

**Key points**:
- Fixed height range for consistent layout
- Auto-scroll (overflow-y: auto)
- Light background to distinguish from page
- Padding for visual comfort

---

#### Message Bubbles

**Base bubble style**:
```css
.message-bubble {
  padding: 12px 16px;
  margin-bottom: 12px;
  border-radius: 8px;
  max-width: 80%;
  word-wrap: break-word;
}
```

**User messages** (blue, right-aligned):
```css
.user-message {
  background-color: rgb(1, 94, 188);
  color: white;
  margin-left: auto;
}
```

**Assistant messages** (gray, left-aligned):
```css
.assistant-message {
  background-color: rgb(209, 209, 209);
  color: black;
  margin-right: auto;
}
```

**Key points**:
- Max 80% width (prevents bubbles from spanning full container)
- Word wrap for long messages
- Margin auto for alignment (left for AI, right for user)
- Border radius for friendly appearance

---

#### Message Content

```css
.message-content {
  margin-bottom: 4px;
  white-space: pre-wrap;
}

.message-timestamp {
  font-size: 11px;
  opacity: 0.7;
  text-align: right;
}
```

**Key points**:
- pre-wrap preserves line breaks and spaces
- Small, subtle timestamp
- Right-aligned regardless of message alignment

---

#### Loading Animation

**Three-dot bounce animation**:

```css
.loader {
  display: flex;
  gap: 8px;
  padding: 8px 0;
}

.loader-dot {
  width: 8px;
  height: 8px;
  background-color: #666;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loader-dot:nth-child(1) {
  animation-delay: -0.32s;
}

.loader-dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}
```

**Key points**:
- Three dots with staggered animation
- Bounce effect (scale 0 to 1)
- Smooth timing (ease-in-out)
- Infinite loop during loading

---

#### Responsive Considerations

Add media query for smaller screens:

```css
@media (max-width: 768px) {
  .message-bubble {
    max-width: 90%;
  }

  .chat-messages-container {
    min-height: 300px;
    max-height: 500px;
  }
}
```

---

**Verification Checklist**:

- [ ] Message bubbles styled correctly (blue/gray, left/right)
- [ ] Scrollable container works
- [ ] Messages word-wrap properly
- [ ] Loader animation smooth and visible
- [ ] Timestamps subtle and right-aligned
- [ ] Responsive on mobile (test in browser dev tools)
- [ ] No visual glitches or overlaps

**Testing**: Manual visual verification in browser

```bash
npm start
# Navigate to /chat
# Send messages and verify styling
```

**Commit Message**:
```
style(chat): add message bubbles and loading animation

- Style user messages (blue, right-aligned)
- Style assistant messages (gray, left-aligned)
- Add scrollable messages container
- Implement three-dot bounce loading animation
- Add responsive styles for mobile
- Preserve line breaks in message content
```

**Estimated Tokens**: ~4,000

---

### Task 4.7: Add Chat Route and Navigation

**Goal**: Make chat accessible via `/chat` route and add to main navigation

**Files to Modify**:
- `src/ui/src/App.jsx` (or wherever routes are defined)
- `src/ui/src/components/Layout/Navigation.jsx` (or similar)

**Prerequisites**: Tasks 4.3-4.6 complete

**Instructions**:

---

#### Step 1: Add Route

**Find route configuration**:
- Likely in `src/ui/src/App.jsx`
- Look for React Router `<Routes>` component
- Find where other routes are defined (/, /upload, /search, /settings)

**Add chat route**:

```jsx
import { Chat } from './components/Chat';

// In your Routes component:
<Routes>
  <Route path="/" element={<Dashboard />} />
  <Route path="/upload" element={<Upload />} />
  <Route path="/search" element={<Search />} />
  <Route path="/chat" element={<Chat />} />  {/* NEW */}
  <Route path="/settings" element={<Settings />} />
</Routes>
```

**Verify route works**:
- Start dev server: `npm start`
- Navigate to http://localhost:5173/chat
- Should see chat page

---

#### Step 2: Add Navigation Link

**Find navigation configuration**:
- Likely in `src/ui/src/components/Layout/Navigation.jsx`
- Look for navigation items array

**Subagent Reference** (if needed):
- "Use explore-base-general to find navigation configuration patterns"

**Add chat link**:

```jsx
export const navigationItems = [
  { type: 'link', text: 'Dashboard', href: '/' },
  { type: 'link', text: 'Upload', href: '/upload' },
  { type: 'link', text: 'Search', href: '/search' },
  { type: 'link', text: 'Chat', href: '/chat' },     // NEW
  { type: 'link', text: 'Settings', href: '/settings' }
];
```

**Navigation placement**: Chat link placed between Search and Settings (logical grouping of query interfaces)

---

#### Step 3: Test Navigation

**Manual verification**:
1. Start dev server
2. Check navigation sidebar/menu
3. Click "Chat" link
4. Verify route changes to /chat
5. Verify chat page loads
6. Navigate to other pages and back to chat
7. Verify active state highlights "Chat" when on /chat route

**Browser testing**:
- Check navigation works in Chrome, Firefox, Safari
- Verify active link styling
- Test keyboard navigation (Tab key)

---

**Verification Checklist**:

- [ ] Chat route added to router
- [ ] Chat link added to navigation
- [ ] Link appears in correct position
- [ ] Clicking link navigates to /chat
- [ ] Active state shows when on chat page
- [ ] Navigation works from all other pages
- [ ] No console errors
- [ ] Keyboard navigation works (accessibility)

**Testing**: Write basic routing test

```jsx
// App.test.jsx or Chat.test.jsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { App } from './App';

test('chat route renders Chat component', () => {
  render(
    <MemoryRouter initialEntries={['/chat']}>
      <App />
    </MemoryRouter>
  );

  expect(screen.getByText(/Knowledge Base Chat/i)).toBeInTheDocument();
});
```

**Commit Message**:
```
feat(nav): add chat route and navigation link

- Add /chat route to React Router configuration
- Add Chat link to main navigation menu
- Position chat between Search and Settings
- Add routing test for chat page
```

**Estimated Tokens**: ~3,000

---

### Task 4.8: Manual End-to-End Testing

**Goal**: Comprehensive manual verification of chat functionality

**Prerequisites**: All previous tasks complete

**Instructions**:

Start development server and perform thorough manual testing:

```bash
cd src/ui
npm start
# Open http://localhost:5173
```

---

#### Core Functionality Tests

**Test 1: Initial Load**
- [ ] Navigate to /chat via navigation link
- [ ] Page loads without errors
- [ ] Empty state message displays
- [ ] Input field is visible and focused
- [ ] Send button is disabled (empty input)
- [ ] New Chat button is disabled (no messages)

**Test 2: First Message**
- [ ] Type a question in input
- [ ] Send button becomes enabled
- [ ] Click Send (or press Enter)
- [ ] User message appears in blue bubble on right
- [ ] Loading indicator (3 dots) appears
- [ ] Input field clears
- [ ] AI response appears in gray bubble on left
- [ ] Sources section appears below AI message (if sources exist)
- [ ] Timestamp shows on both messages

**Test 3: Conversation Flow**
- [ ] Send second message (follow-up question)
- [ ] User message appears immediately
- [ ] AI response references previous context (session working)
- [ ] Both messages and responses visible
- [ ] Auto-scroll keeps latest message in view
- [ ] New Chat button now enabled

**Test 4: Source Citations**
- [ ] Expand sources section below AI message
- [ ] Document names visible
- [ ] Page numbers visible (when available)
- [ ] Snippets visible (when available)
- [ ] Multiple sources display correctly
- [ ] Section collapses when clicked again

**Test 5: New Chat**
- [ ] Click "New Chat" button
- [ ] Confirmation or immediate reset (based on implementation)
- [ ] All messages cleared
- [ ] Empty state returns
- [ ] New Chat button disabled again
- [ ] Session reset (next query starts fresh conversation)

**Test 6: Error Handling**
- [ ] Trigger session expiration (wait or mock)
- [ ] Error alert displays at top
- [ ] Error message is user-friendly
- [ ] Alert can be dismissed
- [ ] Can start new conversation after error

**Test 7: Input Validation**
- [ ] Send button disabled when input empty
- [ ] Send button disabled when only whitespace
- [ ] Send button disabled during loading
- [ ] Enter key sends message
- [ ] Shift+Enter creates new line (if implemented)

---

#### UI/UX Tests

**Visual Design**
- [ ] Message bubbles properly styled (colors, alignment)
- [ ] Timestamps readable but subtle
- [ ] Loading animation smooth
- [ ] Scrollbar appears when needed
- [ ] No visual overlaps or glitches
- [ ] CloudScape theme consistent with rest of app

**Responsive Design**
- [ ] Test on wide screen (>1920px)
- [ ] Test on laptop (1366x768)
- [ ] Test on tablet (768px)
- [ ] Test on mobile (375px)
- [ ] Message bubbles adapt width
- [ ] Navigation remains usable
- [ ] Text remains readable

**Accessibility**
- [ ] Tab navigation works (input → send → new chat)
- [ ] Focus indicators visible
- [ ] Screen reader labels present (check with browser tools)
- [ ] Keyboard shortcuts work (Enter to send)
- [ ] Color contrast sufficient (WCAG AA)

---

#### Performance Tests

**Loading States**
- [ ] Loading indicator appears immediately
- [ ] UI remains responsive during loading
- [ ] Can't send multiple messages during loading
- [ ] Error doesn't leave stuck in loading state

**Scroll Behavior**
- [ ] Auto-scroll smooth, not jarring
- [ ] Scroll works with many messages (test 10+ messages)
- [ ] Manual scroll up doesn't auto-scroll down
- [ ] Latest message scrolls into view when sent

**Session Management**
- [ ] SessionId persists across messages
- [ ] Session resets on New Chat
- [ ] Session expires gracefully after timeout

---

#### Edge Cases

**Long Content**
- [ ] Very long user message wraps correctly
- [ ] Very long AI response wraps correctly
- [ ] Many sources display without breaking layout
- [ ] Long document names don't overflow

**Empty/Null Data**
- [ ] Empty AI response handled
- [ ] No sources handled (SourceList not shown)
- [ ] Missing page numbers handled
- [ ] Missing snippets handled

**Network Issues**
- [ ] Slow network shows loading state
- [ ] Network error shows error message
- [ ] Can recover from error and retry

---

#### Browser Compatibility

Test in multiple browsers:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (if on Mac)
- [ ] Edge (if on Windows)

---

#### Documentation

**Create Test Log** (don't commit - for your records):

```
Chat Interface Manual Test Results
Date: [date]
Tester: [name]
Browser: Chrome 120

✅ Initial load
✅ First message flow
✅ Conversation continuity
✅ Source citations
✅ New chat reset
✅ Error handling
✅ Input validation
✅ Visual design
✅ Responsive (desktop/mobile)
✅ Accessibility basics
✅ Loading states
✅ Scroll behavior
✅ Edge cases
✅ Browser compatibility

Issues Found:
- [List any issues or note "None"]

Notes:
- [Any observations or suggestions]
```

---

**Verification Checklist**:

- [ ] All core functionality working
- [ ] All UI/UX tests passing
- [ ] All accessibility checks passing
- [ ] All edge cases handled
- [ ] No console errors
- [ ] Performance acceptable
- [ ] Browser compatibility confirmed

**Commit Message**: N/A (manual testing - no code changes)

**Estimated Tokens**: ~5,000

---

## Phase 4 Summary

### What You Built

**Components**:
- ✅ Chat page with ContentLayout
- ✅ ChatPanel with full session management
- ✅ MessageBubble with user/AI styling
- ✅ SourceList with expandable citations
- ✅ Complete CSS styling and animations

**Features**:
- ✅ Conversational interface at `/chat`
- ✅ Session-based history (Bedrock managed)
- ✅ Message bubbles (user right/blue, AI left/gray)
- ✅ Source citations below AI responses
- ✅ Auto-scroll to latest message
- ✅ New Chat button to reset
- ✅ Loading states and error handling
- ✅ Keyboard support (Enter to send)

**Testing**:
- ✅ Component tests (80%+ coverage)
- ✅ Integration tests for GraphQL
- ✅ Manual UI/UX verification
- ✅ Accessibility checks
- ✅ Responsive design tested

### Commits Made

Expected ~6-7 feature commits:
1. Update GraphQL query for sessionId
2. Create chat component structure
3. Implement ChatPanel with session management
4. Add MessageBubble component
5. Add SourceList component
6. Add chat styling and animations
7. Add chat route and navigation

### Final Verification

**Run all tests**:
```bash
cd src/ui

# Run all chat tests
npm test -- Chat/

# Run specific test files
npm test -- ChatPanel.test.jsx
npm test -- MessageBubble.test.jsx
npm test -- SourceList.test.jsx

# Coverage report
npm test -- Chat/ --coverage
```

**Start dev server**:
```bash
npm start
# Navigate to http://localhost:5173/chat
# Complete manual test checklist
```

**Verify integration with backend** (if backend available):
```bash
# In separate terminal, start SAM local
cd ../../  # Back to project root
sam build
sam local start-api

# Update UI to point to local API
# Test end-to-end flow
```

---

## Complete Implementation Verification

**All 4 Phases Complete** - verify entire implementation:

### Backend Tests
```bash
# Configuration tests
pytest lib/ragstack_common/test_config.py -v

# Lambda tests
pytest src/lambda/appsync_resolvers/test_configuration.py -v
pytest src/lambda/query_kb/test_handler.py -v

# Coverage
pytest src/lambda/ --cov --cov-report=term
```

### Frontend Tests
```bash
cd src/ui

# All tests
npm test

# Settings tests
npm test -- Settings.test.jsx

# Chat tests
npm test -- Chat/

# Coverage
npm test -- --coverage
```

### Local Integration
```bash
# Build backend
sam build

# Test configuration retrieval
sam local invoke AppSyncResolverFunction -e tests/events/get_configuration.json

# Test KB query
sam local invoke QueryKBFunction -e tests/events/query_kb_new_session.json

# Start UI
cd src/ui && npm start
```

### Manual Verification
1. Settings page → verify 7 fields render
2. Change OCR backend → verify Bedrock model appears
3. Change chat model → save → verify no re-embed modal
4. Change embedding model → verify re-embed modal appears
5. Chat page → send message → verify response
6. Send follow-up → verify context preserved
7. Click New Chat → verify reset

---

## Success Criteria

### Settings Feature ✅
- [x] 7 configuration fields (ocr_backend, bedrock_ocr_model_id, chat_model_id, 2 embedding fields)
- [x] Conditional field visibility (Bedrock model only when Bedrock selected)
- [x] Field ordering correct (OCR → Chat → Embeddings)
- [x] Re-embedding workflow preserved (only triggers for embedding changes)
- [x] Schema-driven rendering working
- [x] Form interactions working (save, reset)

### Chat Feature ✅
- [x] Chat page at `/chat` route
- [x] Navigation link working
- [x] Session management (Bedrock sessionId)
- [x] Message display (user vs AI styling)
- [x] Source citations with expand/collapse
- [x] New Chat button resets conversation
- [x] Error handling for session expiration
- [x] Loading states during API calls
- [x] Auto-scroll to latest message
- [x] Keyboard support (Enter to send)

### Quality ✅
- [x] 80%+ test coverage
- [x] All tests passing
- [x] No console errors
- [x] CloudScape design system consistent
- [x] Responsive design working
- [x] Accessibility basics covered
- [x] TDD followed throughout

---

## Troubleshooting

### Common Issues

**Issue**: ChatPanel doesn't receive messages from backend

**Solution**:
- Check GraphQL query matches Phase 3 schema exactly
- Verify `sessionId` parameter is optional (no `!`)
- Check browser network tab for API errors
- Verify Amplify client is configured correctly

---

**Issue**: Session not persisting across messages

**Solution**:
- Verify sessionId is stored in state after first response
- Check that sessionId is passed in GraphQL variables for subsequent calls
- Confirm backend returns same sessionId
- Check for state reset issues (unnecessary re-renders)

---

**Issue**: Sources not displaying

**Solution**:
- Verify backend returns sources array in correct format
- Check SourceList component receives sources prop
- Ensure SourceList doesn't return null when sources exist
- Check console for prop type warnings

---

**Issue**: Styling not applied

**Solution**:
- Verify ChatPanel.css is imported in ChatPanel.jsx
- Check className strings match CSS selectors
- Ensure no CSS specificity conflicts
- Clear browser cache and reload

---

**Issue**: Loading animation not showing

**Solution**:
- Check isLoading state is set to true during API call
- Verify loading indicator is rendered when isLoading is true
- Ensure loader CSS is loaded
- Check animation browser compatibility

---

**Issue**: Auto-scroll not working

**Solution**:
- Verify messagesEndRef is created and attached to bottom div
- Check useEffect dependency array includes [messages]
- Ensure scrollIntoView is called with smooth behavior
- Test with multiple messages to verify scroll trigger

---

### Performance Considerations

**Slow message rendering with many messages**:
- Implement virtualization if >100 messages (React Virtualized)
- Consider pagination or "load older messages" pattern
- Optimize MessageBubble rendering (React.memo)

**High memory usage**:
- Limit message history (keep last 50 messages)
- Clear old messages when starting new chat
- Avoid storing large data in component state

---

## Next Steps

**Implementation Complete!** 🎉

You've successfully built:
1. Enhanced Settings UI with 7 configuration fields
2. Conversational Chat interface with session management

**Ready for**:
- Code review
- User acceptance testing
- AWS deployment (when appropriate)
- Documentation updates

**Optional Enhancements** (future):
- [ ] Message history persistence (localStorage)
- [ ] Export conversation feature
- [ ] Copy message to clipboard
- [ ] Syntax highlighting for code in messages
- [ ] Typing indicator while AI generates response
- [ ] Message editing/deletion
- [ ] Share conversation via link

---

**Phase 4 Token Total**: ~35,000 tokens
**Total Implementation Plan**: ~125,000 tokens

**Congratulations on completing the implementation!** 🚀
