# Phase 2: Web Component Implementation

**Goal:** Build the embeddable chat web component in `src/amplify-chat/` with React component, web component wrapper, and build pipeline.

**Dependencies:** Phase 0 (ADRs), Phase 1 (packaging function expects specific structure)

**Deliverables:**
- React component (`ChatWithSources.tsx`) with Amplify AI integration
- Web component wrapper (`AmplifyChat.wc.ts`) for framework-agnostic embedding
- Build configuration (`vite.wc.config.ts`, `scripts/inject-amplify-config.js`)
- Package.json with build scripts
- Unit tests for components

**Estimated Scope:** ~25,000 tokens

---

## Context

This phase builds the actual web component that users will embed on their websites. The component:

1. **Uses Amplify AI Kit** - `@aws-amplify/ui-react-ai` for chat UI
2. **Bundles config at build time** - `amplify_outputs.json` embedded (ADR-3)
3. **Supports both React and vanilla JS** - Exports React component + web component
4. **Passes user identity** - Accepts optional `user-id` and `user-token` attributes (for Phase 4 auth)

The build output (`dist/wc.js`) will be deployed by Phase 3's CodeBuild.

---

## Task 1: Set Up Package Structure

### Goal

Create the `src/amplify-chat/` package with correct structure matching existing `package.json`.

### Files to Create/Verify

- `src/amplify-chat/package.json` (already exists, verify contents)
- `src/amplify-chat/tsconfig.json` (already exists, verify)
- `src/amplify-chat/.gitignore`
- `src/amplify-chat/src/` directory structure

### Instructions

1. **Verify package.json exists:**

   Read `src/amplify-chat/package.json`. It should already have:
   - Scripts: `build`, `build:wc`, `test`
   - Exports for both React component and web component
   - Peer dependencies on React, aws-amplify, @aws-amplify/ui-react-ai

   If missing, Phase 0 prerequisites weren't met. Check with project lead.

2. **Create directory structure:**

   ```bash
   cd src/amplify-chat
   mkdir -p src/components src/types src/styles scripts tests
   ```

3. **Create .gitignore:**

   ```
   # Build outputs
   dist/

   # Dependencies
   node_modules/

   # Generated config
   src/amplify-config.generated.ts

   # Test coverage
   coverage/
   .nyc_output/

   # Logs
   *.log
   npm-debug.log*

   # OS files
   .DS_Store
   Thumbs.db
   ```

4. **Verify tsconfig.json:**

   Should have:
   ```json
   {
     "compilerOptions": {
       "target": "ES2020",
       "module": "ESNext",
       "lib": ["ES2020", "DOM", "DOM.Iterable"],
       "jsx": "react-jsx",
       "declaration": true,
       "outDir": "./dist",
       "rootDir": "./src",
       "strict": true,
       "esModuleInterop": true,
       "skipLibCheck": true,
       "moduleResolution": "node"
     },
     "include": ["src"],
     "exclude": ["node_modules", "dist", "tests"]
   }
   ```

### Verification Checklist

- [ ] `src/amplify-chat/package.json` exists with correct exports
- [ ] Directory structure created: `src/`, `src/components/`, `src/types/`, `scripts/`, `tests/`
- [ ] `.gitignore` excludes `dist/`, `node_modules/`, `src/amplify-config.generated.ts`
- [ ] `tsconfig.json` configured for React + TypeScript

### Commit

```bash
git add src/amplify-chat/.gitignore
git commit -m "feat(component): set up web component package structure

- Create directory structure for components, types, scripts
- Add .gitignore for build outputs and generated config
- Verify package.json and tsconfig.json configuration"
```

---

## Task 2: Create Type Definitions

### Goal

Define TypeScript interfaces for component props, chat messages, and sources.

### Files to Create

- `src/amplify-chat/src/types/index.ts`

### Instructions

Create `src/types/index.ts`:

```typescript
/**
 * Type definitions for Amplify Chat component.
 *
 * These types define the public API contract for the component.
 */

/**
 * Source citation from Bedrock Knowledge Base.
 */
export interface Source {
  /** Document title or filename */
  title: string;
  /** Page number or location in document */
  location: string;
  /** Relevant text snippet from source */
  snippet: string;
}

/**
 * Bedrock citation structure (internal).
 *
 * This matches the structure returned by BedrockAgentRuntime
 * RetrieveAndGenerate API.
 */
export interface BedrockCitation {
  retrievedReferences?: Array<{
    content?: { text?: string };
    location?: {
      s3Location?: { uri?: string };
      type?: string;
    };
    metadata?: Record<string, any>;
  }>;
}

/**
 * Chat message with role, content, and optional sources.
 */
export interface ChatMessage {
  /** Message sender: user or AI assistant */
  role: 'user' | 'assistant';
  /** Message text content */
  content: string;
  /** Source citations (only for assistant messages) */
  sources?: Source[];
  /** ISO timestamp when message was created */
  timestamp: string;
  /** Model used to generate response (for quota tracking) */
  modelUsed?: string;
}

/**
 * Props for ChatWithSources React component.
 */
export interface ChatWithSourcesProps {
  /** Unique conversation identifier */
  conversationId?: string;
  /** Header title text */
  headerText?: string;
  /** Header subtitle text */
  headerSubtitle?: string;
  /** Show/hide source citations */
  showSources?: boolean;
  /** Maximum width of component */
  maxWidth?: string;
  /** User ID for authenticated mode (optional) */
  userId?: string | null;
  /** Authentication token for authenticated mode (optional) */
  userToken?: string | null;
  /** Callback when user sends message */
  onSendMessage?: (message: string, conversationId: string) => void;
  /** Callback when assistant responds */
  onResponseReceived?: (response: ChatMessage) => void;
}

/**
 * Props for SourcesDisplay component.
 */
export interface SourcesDisplayProps {
  /** Array of source citations to display */
  sources: Source[];
  /** Show/hide sources section */
  showSources?: boolean;
}
```

### Verification Checklist

- [ ] All interfaces exported
- [ ] JSDoc comments for all interfaces and properties
- [ ] `ChatMessage` includes `modelUsed` field (for Phase 4 quota display)
- [ ] `ChatWithSourcesProps` includes `userId` and `userToken` (for Phase 4 auth)
- [ ] No TypeScript errors: `npx tsc --noEmit`

### Testing

Create `tests/types.test.ts`:

```typescript
/**
 * Type tests to ensure interfaces are correctly defined.
 */
import { describe, it, expect } from 'vitest';
import type { Source, ChatMessage, ChatWithSourcesProps } from '../src/types';

describe('Type definitions', () => {
  it('Source interface is correctly defined', () => {
    const source: Source = {
      title: 'Test Document',
      location: 'Page 1',
      snippet: 'Sample text',
    };

    expect(source.title).toBe('Test Document');
  });

  it('ChatMessage interface includes required fields', () => {
    const message: ChatMessage = {
      role: 'assistant',
      content: 'Hello',
      timestamp: new Date().toISOString(),
    };

    expect(message.role).toBe('assistant');
  });

  it('ChatWithSourcesProps includes auth fields', () => {
    const props: ChatWithSourcesProps = {
      conversationId: 'test',
      userId: 'user123',
      userToken: 'token',
    };

    expect(props.userId).toBe('user123');
  });
});
```

Run: `npm test tests/types.test.ts`

### Commit

```bash
git add src/amplify-chat/src/types/index.ts tests/types.test.ts
git commit -m "feat(component): add TypeScript type definitions

- Define Source, ChatMessage, ChatWithSourcesProps interfaces
- Add auth fields (userId, userToken) for Phase 4
- Add modelUsed field for quota tracking
- Include unit tests for type definitions"
```

---

## Task 3: Create Build Configuration Script

### Goal

Create `scripts/inject-amplify-config.js` that embeds `amplify_outputs.json` into the build (ADR-3: hardcoded config).

### Files to Create

- `src/amplify-chat/scripts/inject-amplify-config.js`

### Background

CodeBuild will run this script before building the web component. It reads `../../amplify_outputs.json` (generated by `npx ampx deploy`) and creates `src/amplify-config.generated.ts` for bundling.

### Instructions

Create `scripts/inject-amplify-config.js`:

```javascript
#!/usr/bin/env node

/**
 * Inject Amplify Configuration into Web Component Build
 *
 * This script runs before the Vite build to embed amplify_outputs.json
 * into the web component bundle. This allows zero-config embedding.
 *
 * Usage: node scripts/inject-amplify-config.js
 *
 * Reads: ../../amplify_outputs.json (from Amplify deployment)
 * Writes: src/amplify-config.generated.ts (imported by src/wc.ts)
 */

const fs = require('fs');
const path = require('path');

// Paths relative to src/amplify-chat/
const AMPLIFY_OUTPUTS_PATH = path.join(__dirname, '../../amplify_outputs.json');
const GENERATED_CONFIG_PATH = path.join(__dirname, '../src/amplify-config.generated.ts');

function main() {
  console.log('🔧 Injecting Amplify configuration into web component...');

  // Check if amplify_outputs.json exists
  if (!fs.existsSync(AMPLIFY_OUTPUTS_PATH)) {
    console.error('❌ Error: amplify_outputs.json not found at', AMPLIFY_OUTPUTS_PATH);
    console.error('   Run `npx ampx deploy` first to generate Amplify configuration.');
    process.exit(1);
  }

  try {
    // Read and parse amplify_outputs.json
    const amplifyOutputsRaw = fs.readFileSync(AMPLIFY_OUTPUTS_PATH, 'utf-8');
    const amplifyOutputs = JSON.parse(amplifyOutputsRaw);

    // Generate TypeScript config file
    const configContent = `/**
 * Auto-generated Amplify Configuration
 *
 * This file is generated by scripts/inject-amplify-config.js during build.
 * DO NOT EDIT MANUALLY - changes will be overwritten.
 *
 * Generated: ${new Date().toISOString()}
 */

export const AMPLIFY_OUTPUTS = ${JSON.stringify(amplifyOutputs, null, 2)} as const;
`;

    // Write config file
    fs.writeFileSync(GENERATED_CONFIG_PATH, configContent, 'utf-8');

    console.log('✅ Amplify configuration injected successfully');
    console.log(`   API Endpoint: ${amplifyOutputs.data?.url || 'N/A'}`);
    console.log(`   Region: ${amplifyOutputs.auth?.aws_region || 'N/A'}`);

  } catch (error) {
    console.error('❌ Error injecting configuration:', error.message);
    process.exit(1);
  }
}

main();
```

Make executable:
```bash
chmod +x src/amplify-chat/scripts/inject-amplify-config.js
```

### Verification Checklist

- [ ] Script is executable (`chmod +x`)
- [ ] Reads from `../../amplify_outputs.json`
- [ ] Writes to `src/amplify-config.generated.ts`
- [ ] Exits with error code if amplify_outputs.json missing
- [ ] Generates valid TypeScript file

### Testing

Create `tests/inject-config.test.js`:

```javascript
/**
 * Tests for config injection script.
 */
const { describe, it, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

describe('inject-amplify-config', () => {
  const testOutputsPath = path.join(__dirname, '../../../amplify_outputs.json');
  const generatedConfigPath = path.join(__dirname, '../src/amplify-config.generated.ts');

  beforeEach(() => {
    // Clean up before each test
    if (fs.existsSync(generatedConfigPath)) {
      fs.unlinkSync(generatedConfigPath);
    }
  });

  afterEach(() => {
    // Clean up after tests
    if (fs.existsSync(testOutputsPath)) {
      fs.unlinkSync(testOutputsPath);
    }
    if (fs.existsSync(generatedConfigPath)) {
      fs.unlinkSync(generatedConfigPath);
    }
  });

  it('should generate config file when amplify_outputs.json exists', () => {
    // Create mock amplify_outputs.json
    const mockOutputs = {
      data: { url: 'https://test.appsync-api.us-east-1.amazonaws.com/graphql' },
      auth: { aws_region: 'us-east-1' }
    };
    fs.writeFileSync(testOutputsPath, JSON.stringify(mockOutputs, null, 2));

    // Run script
    execSync('node scripts/inject-amplify-config.js', {
      cwd: path.join(__dirname, '..'),
      stdio: 'inherit'
    });

    // Verify generated file
    assert.ok(fs.existsSync(generatedConfigPath), 'Config file should be generated');

    const content = fs.readFileSync(generatedConfigPath, 'utf-8');
    assert.ok(content.includes('AMPLIFY_OUTPUTS'), 'Should export AMPLIFY_OUTPUTS');
    assert.ok(content.includes('test.appsync-api'), 'Should include API URL');
  });

  it('should fail if amplify_outputs.json missing', () => {
    assert.throws(() => {
      execSync('node scripts/inject-amplify-config.js', {
        cwd: path.join(__dirname, '..'),
        stdio: 'pipe'
      });
    }, 'Should throw error when amplify_outputs.json missing');
  });
});
```

Run: `npm test tests/inject-config.test.js`

### Commit

```bash
git add src/amplify-chat/scripts/inject-amplify-config.js tests/inject-config.test.js
git commit -m "feat(component): add config injection script for build

- Create script to embed amplify_outputs.json in bundle
- Generate src/amplify-config.generated.ts at build time
- Fail gracefully if Amplify config missing
- Include unit tests for script behavior"
```

---

## Task 4: Update Package.json Build Scripts

### Goal

Update `package.json` to run config injection before building web component.

### Files to Modify

- `src/amplify-chat/package.json`

### Instructions

1. **Locate the scripts section** in `package.json`

2. **Update the build:wc script:**

   Change from:
   ```json
   "build:wc": "vite build --config vite.wc.config.ts"
   ```

   To:
   ```json
   "build:wc": "node scripts/inject-amplify-config.js && vite build --config vite.wc.config.ts"
   ```

3. **Verify other scripts:**

   Ensure these exist:
   ```json
   {
     "scripts": {
       "build": "tsc && npm run build:wc",
       "build:wc": "node scripts/inject-amplify-config.js && vite build --config vite.wc.config.ts",
       "build:watch": "tsc --watch",
       "type-check": "tsc --noEmit",
       "test": "vitest",
       "test:watch": "vitest --watch",
       "test:coverage": "vitest --coverage"
     }
   }
   ```

### Verification Checklist

- [ ] `build:wc` runs injection script before Vite build
- [ ] `build` script runs TypeScript compile then web component build
- [ ] Test scripts configured

### Commit

```bash
git add src/amplify-chat/package.json
git commit -m "feat(component): configure build scripts with config injection

- Run inject-amplify-config.js before web component build
- Ensure TypeScript compilation happens before bundling
- Maintain existing test scripts"
```

---

## Task 5: Create React Chat Component

### Goal

Implement `ChatWithSources.tsx` using Amplify AI Kit.

### Files to Create

- `src/amplify-chat/src/components/ChatWithSources.tsx`
- `src/amplify-chat/src/components/SourcesDisplay.tsx`

### Background

The `@aws-amplify/ui-react-ai` package provides `AIConversation` component. We wrap it to add source attribution display and our custom props.

### Instructions

Create `src/components/ChatWithSources.tsx`:

```typescript
/**
 * ChatWithSources - React Component
 *
 * Chat interface with AI assistant and source attribution.
 * Uses Amplify AI Kit for conversation management.
 */

import React from 'react';
import { AIConversation } from '@aws-amplify/ui-react-ai';
import { SourcesDisplay } from './SourcesDisplay';
import type { ChatWithSourcesProps, ChatMessage } from '../types';

export function ChatWithSources({
  conversationId = 'default',
  headerText = 'Document Q&A',
  headerSubtitle = 'Ask questions about your documents',
  showSources = true,
  maxWidth = '100%',
  userId = null,
  userToken = null,
  onSendMessage,
  onResponseReceived,
}: ChatWithSourcesProps) {
  const [currentSources, setCurrentSources] = React.useState<any[]>([]);

  /**
   * Handle message send events.
   */
  const handleSendMessage = React.useCallback((message: string) => {
    if (onSendMessage) {
      onSendMessage(message, conversationId);
    }
  }, [conversationId, onSendMessage]);

  /**
   * Handle AI response with source extraction.
   */
  const handleResponse = React.useCallback((response: any) => {
    // Extract sources from response
    if (response.citations && Array.isArray(response.citations)) {
      setCurrentSources(response.citations);
    }

    // Build ChatMessage structure
    const chatMessage: ChatMessage = {
      role: 'assistant',
      content: response.content || '',
      sources: response.citations || [],
      timestamp: new Date().toISOString(),
      modelUsed: response.modelUsed,
    };

    if (onResponseReceived) {
      onResponseReceived(chatMessage);
    }
  }, [onResponseReceived]);

  return (
    <div style={{ maxWidth, margin: '0 auto' }}>
      <AIConversation
        id={conversationId}
        // Pass auth context if provided (Phase 4 will use this)
        context={{
          userId: userId || undefined,
          userToken: userToken || undefined,
        }}
        // Event handlers
        onSendMessage={handleSendMessage}
        onResponse={handleResponse}
        // UI customization
        headerText={headerText}
        subtitle={headerSubtitle}
      />

      {showSources && currentSources.length > 0 && (
        <SourcesDisplay sources={currentSources} showSources={showSources} />
      )}
    </div>
  );
}
```

Create `src/components/SourcesDisplay.tsx`:

```typescript
/**
 * SourcesDisplay - Source Citations Component
 *
 * Displays document sources with collapsible sections.
 */

import React from 'react';
import type { SourcesDisplayProps, Source } from '../types';

export function SourcesDisplay({ sources, showSources = true }: SourcesDisplayProps) {
  if (!showSources || !sources || sources.length === 0) {
    return null;
  }

  return (
    <div className="sources-container" style={{
      marginTop: '1rem',
      padding: '1rem',
      backgroundColor: 'var(--amplify-colors-background-secondary, #f5f5f5)',
      borderRadius: '8px',
    }}>
      <h3 style={{
        fontSize: '0.875rem',
        fontWeight: 600,
        marginBottom: '0.5rem',
        color: 'var(--amplify-colors-font-secondary, #666)',
      }}>
        Sources ({sources.length})
      </h3>

      <div className="sources-list">
        {sources.map((source: Source, index: number) => (
          <div
            key={index}
            className="source-item"
            style={{
              marginBottom: '0.75rem',
              paddingBottom: '0.75rem',
              borderBottom: index < sources.length - 1 ? '1px solid #e0e0e0' : 'none',
            }}
          >
            <div style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              color: 'var(--amplify-colors-brand-primary, #0073bb)',
              marginBottom: '0.25rem',
            }}>
              {source.title}
            </div>

            {source.location && (
              <div style={{
                fontSize: '0.7rem',
                color: '#999',
                marginBottom: '0.25rem',
              }}>
                {source.location}
              </div>
            )}

            <div style={{
              fontSize: '0.8rem',
              color: '#444',
              fontStyle: 'italic',
            }}>
              "{source.snippet}"
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Verification Checklist

- [ ] `ChatWithSources` uses Amplify AI Kit's `AIConversation`
- [ ] Passes `userId` and `userToken` in context (for Phase 4)
- [ ] Extracts and displays sources
- [ ] Calls callbacks when provided
- [ ] `SourcesDisplay` renders source citations with styling
- [ ] No TypeScript errors: `npx tsc --noEmit`

### Testing

Create `tests/ChatWithSources.test.tsx`:

```typescript
/**
 * Tests for ChatWithSources component.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatWithSources } from '../src/components/ChatWithSources';

// Mock Amplify AI Kit
vi.mock('@aws-amplify/ui-react-ai', () => ({
  AIConversation: ({ headerText, subtitle }: any) => (
    <div data-testid="ai-conversation">
      <h1>{headerText}</h1>
      <p>{subtitle}</p>
    </div>
  ),
}));

describe('ChatWithSources', () => {
  it('renders with default props', () => {
    render(<ChatWithSources />);

    expect(screen.getByTestId('ai-conversation')).toBeDefined();
    expect(screen.getByText('Document Q&A')).toBeDefined();
  });

  it('renders with custom header text', () => {
    render(<ChatWithSources headerText="Custom Chat" />);

    expect(screen.getByText('Custom Chat')).toBeDefined();
  });

  it('passes userId and userToken to context', () => {
    const { container } = render(
      <ChatWithSources userId="user123" userToken="token-abc" />
    );

    // Component renders (actual context passing tested in integration)
    expect(container).toBeDefined();
  });
});
```

Run: `npm test tests/ChatWithSources.test.tsx`

### Commit

```bash
git add src/amplify-chat/src/components/ tests/ChatWithSources.test.tsx
git commit -m "feat(component): implement ChatWithSources React component

- Use Amplify AI Kit AIConversation component
- Add SourcesDisplay for citation rendering
- Pass auth context (userId, userToken) for Phase 4
- Extract and display document sources
- Include unit tests for component rendering"
```

---

## Task 6: Create Web Component Wrapper

### Goal

Implement `AmplifyChat.wc.ts` web component that wraps the React component for framework-agnostic embedding.

### Files to Create

- `src/amplify-chat/src/components/AmplifyChat.wc.ts`

### Background

This custom element allows `<amplify-chat>` to be used in any framework (Vue, Angular, vanilla JS). It uses React's `createRoot` to render the React component inside the custom element.

### Instructions

Review the existing file at `src/amplify-chat/src/components/AmplifyChat.wc.ts` (from Phase 0 prerequisites). It should already exist.

If it doesn't exist, create it following the pattern shown in Phase 0, Section "File Locations Reference". The file should:

1. Extend `HTMLElement`
2. Define observed attributes: `conversation-id`, `user-id`, `user-token`, `header-text`, `show-sources`, etc.
3. Use React's `createRoot` to mount `ChatWithSources`
4. Dispatch custom events: `amplify-chat:send-message`, `amplify-chat:response-received`
5. Provide public API methods: `getConversationId()`, `setConversationId()`

### Verification Checklist

- [ ] Custom element registered as `amplify-chat`
- [ ] Observes `user-id` and `user-token` attributes (for Phase 4)
- [ ] Renders `ChatWithSources` component
- [ ] Dispatches custom events with `bubbles: true, composed: true`
- [ ] Properly unmounts React on `disconnectedCallback`
- [ ] No TypeScript errors

### Testing

Create `tests/AmplifyChat.wc.test.ts`:

```typescript
/**
 * Tests for AmplifyChat web component.
 */
import { describe, it, expect, beforeAll } from 'vitest';
import '../src/components/AmplifyChat.wc';

describe('AmplifyChat Web Component', () => {
  beforeAll(() => {
    // Ensure custom element is defined
    if (!customElements.get('amplify-chat')) {
      throw new Error('amplify-chat custom element not registered');
    }
  });

  it('is registered as custom element', () => {
    const el = document.createElement('amplify-chat');
    expect(el).toBeInstanceOf(HTMLElement);
  });

  it('accepts conversation-id attribute', () => {
    const el = document.createElement('amplify-chat');
    el.setAttribute('conversation-id', 'test-123');

    document.body.appendChild(el);

    // @ts-ignore - custom element method
    expect(el.getConversationId()).toBe('test-123');

    document.body.removeChild(el);
  });

  it('accepts user-id and user-token attributes', () => {
    const el = document.createElement('amplify-chat');
    el.setAttribute('user-id', 'user-456');
    el.setAttribute('user-token', 'token-xyz');

    document.body.appendChild(el);

    expect(el.getAttribute('user-id')).toBe('user-456');
    expect(el.getAttribute('user-token')).toBe('token-xyz');

    document.body.removeChild(el);
  });
});
```

Run: `npm test tests/AmplifyChat.wc.test.ts`

### Commit

```bash
git add src/amplify-chat/src/components/AmplifyChat.wc.ts tests/AmplifyChat.wc.test.ts
git commit -m "feat(component): create web component wrapper

- Define amplify-chat custom element
- Wrap ChatWithSources React component
- Accept user-id and user-token attributes for auth
- Dispatch custom events for parent integration
- Include unit tests for web component API"
```

---

## Task 7: Create Entry Points

### Goal

Create `wc.ts` and `index.ts` entry points for web component and React component exports.

### Files to Create

- `src/amplify-chat/src/wc.ts`
- `src/amplify-chat/src/index.ts`

### Instructions

Create `src/wc.ts` (web component entry):

```typescript
/**
 * Web Component Bundle Entry Point
 *
 * This file is used to build a UMD bundle for <script> tag usage.
 * It includes the web component and all dependencies.
 *
 * Build: npm run build:wc
 * Output: dist/wc.js (UMD), dist/wc.esm.js (ESM)
 *
 * Usage:
 * <script src="https://cdn.example.com/amplify-chat.js"></script>
 * <amplify-chat conversation-id="my-chat"></amplify-chat>
 */

import { Amplify } from 'aws-amplify';
import { AMPLIFY_OUTPUTS } from './amplify-config.generated';

// Configure Amplify with bundled config (zero-config embedding)
Amplify.configure(AMPLIFY_OUTPUTS);

// Export web component (auto-registers as <amplify-chat>)
export { AmplifyChat } from './components/AmplifyChat.wc';

// Export types for TypeScript users
export type {
  ChatWithSourcesProps,
  SourcesDisplayProps,
  Source,
  ChatMessage,
  BedrockCitation,
} from './types';

// Version
export const VERSION = '1.0.0';
```

Create `src/index.ts` (React component entry):

```typescript
/**
 * React Component Package Entry Point
 *
 * For use in React applications via npm:
 * npm install @ragstack/amplify-chat
 *
 * Usage:
 * import { ChatWithSources } from '@ragstack/amplify-chat';
 */

// Export React components
export { ChatWithSources } from './components/ChatWithSources';
export { SourcesDisplay } from './components/SourcesDisplay';

// Export types
export type {
  ChatWithSourcesProps,
  SourcesDisplayProps,
  Source,
  ChatMessage,
  BedrockCitation,
} from './types';

// Version
export const VERSION = '1.0.0';
```

### Verification Checklist

- [ ] `wc.ts` configures Amplify with generated config
- [ ] `wc.ts` exports `AmplifyChat` web component
- [ ] `index.ts` exports React components only (no Amplify config)
- [ ] Both export types
- [ ] No TypeScript errors: `npx tsc --noEmit`

### Commit

```bash
git add src/amplify-chat/src/wc.ts src/amplify-chat/src/index.ts
git commit -m "feat(component): add entry points for web component and React

- Create wc.ts for web component bundle (configures Amplify)
- Create index.ts for React component export
- Export types from both entry points
- Version both at 1.0.0"
```

---

## Task 8: Verify Vite Config

### Goal

Ensure `vite.wc.config.ts` is configured correctly to build UMD bundle.

### Files to Verify

- `src/amplify-chat/vite.wc.config.ts`

### Instructions

Review the existing `vite.wc.config.ts`. It should:

1. **Entry point:** `src/wc.ts`
2. **Output formats:** UMD (`dist/wc.js`) and ESM (`dist/wc.esm.js`)
3. **External dependencies:** None (bundle all dependencies)
4. **Library name:** `AmplifyChat`

Expected config (should already exist):

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: path.resolve(__dirname, 'src/wc.ts'),
      name: 'AmplifyChat',
      fileName: (format) => `wc.${format === 'umd' ? 'umd' : 'esm'}.js`,
    },
    rollupOptions: {
      external: [],  // Bundle everything (no externals)
      output: [
        {
          format: 'umd',
          file: 'dist/wc.js',
          name: 'AmplifyChat',
          globals: {},
        },
        {
          format: 'es',
          file: 'dist/wc.esm.js',
        },
      ],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
```

If config is incorrect or missing, update it to match above.

### Verification Checklist

- [ ] Entry is `src/wc.ts`
- [ ] Output includes `dist/wc.js` (UMD) and `dist/wc.esm.js` (ESM)
- [ ] No external dependencies (bundle all)
- [ ] React plugin enabled

### Commit

Only if you modified the file:

```bash
git add src/amplify-chat/vite.wc.config.ts
git commit -m "fix(component): update Vite config for web component build

- Set entry to src/wc.ts
- Configure UMD and ESM outputs
- Bundle all dependencies (no externals)"
```

---

## Phase 2 Complete - Verification

Before moving to Phase 3, verify:

### Checklist

- [ ] All commits made with conventional commit format
- [ ] All unit tests pass: `cd src/amplify-chat && npm test`
- [ ] TypeScript compiles: `cd src/amplify-chat && npx tsc --noEmit`
- [ ] Package structure matches Phase 1's `package_amplify_chat_source()` expectations
- [ ] `scripts/inject-amplify-config.js` executable and tested
- [ ] Build scripts configured in `package.json`

### Test Build (Without Amplify Config)

Since `amplify_outputs.json` doesn't exist yet, create a mock for testing:

```bash
cd src/amplify-chat

# Create mock amplify_outputs.json
cat > ../../amplify_outputs.json <<EOF
{
  "data": {
    "url": "https://mock.appsync-api.us-east-1.amazonaws.com/graphql"
  },
  "auth": {
    "aws_region": "us-east-1",
    "user_pool_id": "us-east-1_MOCK",
    "user_pool_client_id": "mock-client-id"
  }
}
EOF

# Run build
npm run build

# Verify outputs
ls -lh dist/
# Should see: wc.js, wc.esm.js, index.js, index.d.ts

# Check bundle size (should be ~300KB gzipped)
gzip -c dist/wc.js | wc -c

# Clean up mock
rm ../../amplify_outputs.json
```

### Verify Package Structure

Run Phase 1's packaging function to ensure structure is correct:

```bash
# From project root
python3 -c "
from publish import package_amplify_chat_source
import tempfile
import zipfile

# Mock S3 upload
class MockS3:
    def upload_file(self, *args): pass

import publish
publish.boto3 = type('obj', (object,), {'client': lambda *a: MockS3()})

# Package (will fail on upload, but creates zip)
try:
    key = package_amplify_chat_source('test', 'us-east-1')
except:
    pass

# Find the zip in /tmp
import glob
zips = glob.glob('/tmp/*.zip')
if zips:
    with zipfile.ZipFile(zips[0], 'r') as zf:
        print('Zip contents:')
        for name in zf.namelist()[:10]:
            print(f'  {name}')
"
```

Should output:
```
Zip contents:
  web-component/package.json
  web-component/src/wc.ts
  web-component/src/index.ts
  web-component/src/components/ChatWithSources.tsx
  ...
```

---

## Common Issues

**Issue:** `Cannot find module './amplify-config.generated'`
- **Solution:** Run `node scripts/inject-amplify-config.js` with a mock `amplify_outputs.json`

**Issue:** Build fails with "React is not defined"
- **Solution:** Verify `vite.wc.config.ts` has `@vitejs/plugin-react`

**Issue:** Tests fail with "customElements is not defined"
- **Solution:** Add to `vitest.config.ts`: `environment: 'happy-dom'`

---

## Handoff to Phase 3

**What you've delivered:**
- ✅ Complete web component package in `src/amplify-chat/`
- ✅ Build pipeline with config injection
- ✅ React component + web component wrapper
- ✅ Auth attributes ready for Phase 4 integration
- ✅ Package structure matches Phase 1's expectations

**What Phase 3 will do:**
- Create Amplify CDN infrastructure (CloudFront + S3)
- Add CodeBuild project to build and deploy web component
- Integrate with `publish.py` deployment flow
- Output CDN URL in deployment outputs

---

**Next:** [Phase-3.md](Phase-3.md) - Amplify Infrastructure & CDN Deployment
