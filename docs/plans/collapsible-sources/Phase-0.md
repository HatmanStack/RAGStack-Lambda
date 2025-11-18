# Phase 0: Foundation & Architecture

## Overview

This phase establishes the architectural foundation, design decisions, and shared patterns that will guide implementation across all subsequent phases. Read this document thoroughly before proceeding to implementation phases.

**Estimated tokens:** ~15,000

---

## Architecture Decision Records (ADRs)

### ADR-001: Configuration Storage Pattern

**Decision:** Use existing DynamoDB ConfigurationTable with new `chat_allow_document_access` key

**Rationale:**
- Follows established pattern (`chat_require_auth`, `chat_primary_model`)
- Enables runtime configuration changes without redeployment
- Leverages existing 60-second cache in conversation Lambda
- Admin UI already has configuration management infrastructure

**Alternatives Considered:**
- Environment variables → Rejected (requires redeployment)
- SSM Parameter Store → Rejected (adds complexity, DynamoDB already in use)
- Hardcoded → Rejected (no flexibility)

**Consequences:**
- Must seed new config key in `publish.py`
- Must update TypeScript `ChatConfig` interface
- Must update admin UI configuration panel

---

### ADR-002: Document URL Mapping Strategy

**Decision:** Map citations to original documents via TrackingTable lookup

**Rationale:**
- Bedrock citations reference OutputBucket (vectors/chunks)
- Original files live in InputBucket
- TrackingTable contains `input_s3_uri` for each `document_id`
- UUID extraction from S3 URI is reliable pattern

**Data Flow:**
```
Citation: s3://output-bucket/abc-123-def/chunks/chunk-005.json
         ↓ Extract UUID
TrackingTable.getItem({ document_id: "abc-123-def" })
         ↓ Returns { input_s3_uri, filename }
Generate Presigned URL: s3://input-bucket/abc-123-def/report.pdf
```

**Alternatives Considered:**
- Store mapping in separate table → Rejected (duplicates TrackingTable data)
- Include in Bedrock metadata → Rejected (can't modify KB index structure)
- Parse filename from OutputBucket → Rejected (lossy, no extension info)

**Consequences:**
- Conversation Lambda needs DynamoDB GetItem permission on TrackingTable
- Must handle cases where document_id not found (deleted documents)
- UUID regex must match appsync_resolvers document_id generation

---

### ADR-003: Presigned URL Security Model

**Decision:** Generate presigned URLs with 1-hour expiry, read-only access

**Rationale:**
- Balances security (time-limited) with usability (enough time to download)
- Read-only (GetObject) prevents accidental/malicious modifications
- No bucket listing capabilities exposed
- URLs are revocable by toggling config (60s cache delay)

**Security Properties:**
- **Time-limited:** URLs expire after 3600 seconds
- **Action-limited:** Only `s3:GetObject`, not `s3:PutObject` or `s3:DeleteObject`
- **Resource-limited:** URL works only for specific object, not entire bucket
- **Revocable:** Admin can disable via `chat_allow_document_access = false`

**Alternatives Considered:**
- Longer expiry (24 hours) → Rejected (security risk if URL leaks)
- Shorter expiry (15 min) → Rejected (poor UX for large files)
- CloudFront signed URLs → Rejected (adds complexity, S3 presigned is sufficient)

**Consequences:**
- Conversation Lambda needs S3 GetObject permission on InputBucket
- URLs may expire while user is viewing chat (acceptable trade-off)
- Must import `@aws-sdk/s3-request-presigner` package

---

### ADR-004: UI Collapse State Management

**Decision:** Default sources to collapsed, persist state in sessionStorage

**Rationale:**
- Cleaner initial UI (less visual clutter)
- User explicitly requests sources (opt-in UX)
- sessionStorage preserves state during tab session
- Doesn't pollute localStorage with ephemeral preferences

**Behavior:**
- First render: Collapsed
- User clicks expand: Opens, saves to sessionStorage
- Page refresh: Restores last state from sessionStorage
- New tab: Resets to collapsed (sessionStorage is tab-scoped)

**Alternatives Considered:**
- Default expanded → Rejected (cluttered UI)
- localStorage → Rejected (persists across sessions inappropriately)
- No persistence → Rejected (poor UX if user refreshes page)

**Consequences:**
- Must implement sessionStorage read/write with error handling
- Must handle SSR compatibility (sessionStorage is client-only)
- Must add animation for smooth expand/collapse transition

---

### ADR-005: Source Item Display Format

**Decision:** Show filename (not S3 key), chunk ID, snippet, and optional document link

**Format:**
```
📄 financial-report-2024.pdf
   📍 Chunk ID: chunk-005
   "Q4 revenue was $2.3M, up 18% from Q3..."
   [View Document →]  (if documentUrl present)
```

**Rationale:**
- Filename is user-recognizable (S3 keys are not)
- Chunk ID provides technical traceability for debugging
- Snippet shows context (200 char limit prevents overflow)
- Document link is clearly actionable

**Alternatives Considered:**
- Show S3 URI → Rejected (exposes internal structure, not user-friendly)
- Page numbers → Rejected (not always available in Bedrock metadata)
- Full snippet → Rejected (can be very long, breaks layout)

**Consequences:**
- Must fetch filename from TrackingTable (same lookup as presigned URL)
- Must truncate snippet with ellipsis if > 200 chars
- Must handle missing documentUrl gracefully (show disabled state)

---

## Design Patterns

### Pattern 1: Configuration Access

**All Lambdas reading chat config must:**

```typescript
interface ChatConfig {
  requireAuth: boolean;
  primaryModel: string;
  fallbackModel: string;
  globalQuotaDaily: number;
  perUserQuotaDaily: number;
  allowDocumentAccess: boolean;  // NEW
}

async function getChatConfig(): Promise<ChatConfig> {
  // 1. Check cache (60s TTL)
  // 2. Read from DynamoDB ConfigurationTable
  // 3. Parse with defaults
  // 4. Update cache
  // 5. Return config
}
```

**Follow existing pattern in `amplify/data/functions/conversation.ts:116-160`**

---

### Pattern 2: Error Handling for External Services

**DynamoDB, S3, and Bedrock calls must:**

```typescript
try {
  const result = await externalService.operation();
  console.log('Operation succeeded:', { summary });
  return result;
} catch (error) {
  console.error('Operation failed:', error);
  // Return safe fallback, don't throw unless critical
  return fallbackValue;
}
```

**Graceful degradation:**
- If TrackingTable lookup fails → `documentUrl: null` (sources still show, just no link)
- If presigned URL generation fails → `documentUrl: null`
- If config read fails → Default to `allowDocumentAccess: false` (secure by default)

---

### Pattern 3: React Component Memoization

**Performance-sensitive components must use React.memo:**

```tsx
const SourcesToggleComponent: React.FC<Props> = ({ sources, defaultExpanded }) => {
  // Component implementation
};

export const SourcesToggle = React.memo(SourcesToggleComponent);
```

**When to memoize:**
- Component renders frequently (e.g., on every chat message)
- Props are stable (primitives or memoized objects)
- Component is expensive to render (e.g., list mapping)

**When NOT to memoize:**
- Component rarely re-renders
- Props change on every render anyway
- Component is trivial (single div)

---

### Pattern 4: Accessibility Requirements

**All interactive elements must:**

1. **Keyboard navigation:**
   - Focusable via Tab
   - Activatable via Enter or Space
   - Visible focus indicator

2. **Screen reader support:**
   - Semantic HTML (`<button>`, not `<div onClick>`)
   - ARIA labels where needed (`aria-expanded`, `aria-label`)
   - Status announcements (`aria-live` for dynamic content)

3. **Visual affordances:**
   - Clear hover/focus states
   - Sufficient color contrast (WCAG AA)
   - Icon + text labels (not icon-only)

**Example:**
```tsx
<button
  onClick={toggle}
  aria-expanded={expanded}
  aria-label={`${expanded ? 'Hide' : 'Show'} ${sources.length} sources`}
>
  📄 Sources ({sources.length}) {expanded ? '▼ Hide' : '▶ Show'}
</button>
```

---

### Pattern 5: Testing Strategy

**Every feature must have:**

1. **Unit tests** (Jest/Vitest)
   - Test functions in isolation
   - Mock external dependencies (DynamoDB, S3)
   - Test error paths and edge cases
   - Coverage target: 80%+

2. **Integration tests** (marked with `@pytest.mark.integration` for Python)
   - Test Lambda handler end-to-end
   - Use real AWS SDK clients (mocked with aws-sdk-mock)
   - Verify data transformations
   - Test actual GraphQL responses

3. **Component tests** (React Testing Library)
   - Test user interactions (click, type)
   - Test accessibility (keyboard nav, screen readers)
   - Verify visual states (collapsed/expanded)
   - Snapshot test only when necessary

4. **E2E tests** (Playwright) - Phase 3 only
   - Test critical user journeys
   - Verify presigned URLs work in browser
   - Test configuration toggle flow

---

## Common Pitfalls

### Pitfall 1: Forgetting async/await

**❌ Wrong:**
```typescript
const url = generatePresignedUrl(bucket, key);  // Returns Promise, not string!
sources.push({ documentUrl: url });
```

**✅ Correct:**
```typescript
const url = await generatePresignedUrl(bucket, key);
sources.push({ documentUrl: url });
```

**Why:** S3 presigned URL generation is asynchronous (AWS SDK v3)

---

### Pitfall 2: Not handling missing data

**❌ Wrong:**
```typescript
const documentId = s3Uri.match(/\/([0-9a-f-]{36})\//)[1];  // Crashes if no match!
```

**✅ Correct:**
```typescript
const match = s3Uri.match(/\/([0-9a-f-]{36})\//);
if (!match) {
  console.warn('Could not extract document_id from URI:', s3Uri);
  return { documentUrl: null, filename: 'Unknown Document' };
}
const documentId = match[1];
```

**Why:** Citations may have unexpected formats (deleted documents, manual KB uploads)

---

### Pitfall 3: Blocking async operations

**❌ Wrong:**
```typescript
sources.forEach(source => {
  const url = await generatePresignedUrl(...);  // SyntaxError in forEach!
  source.documentUrl = url;
});
```

**✅ Correct:**
```typescript
const urlPromises = sources.map(source => generatePresignedUrl(...));
const urls = await Promise.all(urlPromises);
sources.forEach((source, i) => { source.documentUrl = urls[i]; });
```

**Why:** `forEach` doesn't await, use `for...of` or `Promise.all`

---

### Pitfall 4: Exposing sensitive data in logs

**❌ Wrong:**
```typescript
console.log('Presigned URL generated:', presignedUrl);  // Logs signature!
```

**✅ Correct:**
```typescript
console.log('Presigned URL generated for document:', { documentId, filename });
```

**Why:** Presigned URLs contain AWS credentials in query params (signature, access key)

---

### Pitfall 5: Not cleaning up sessionStorage

**❌ Wrong:**
```typescript
sessionStorage.setItem('sources-expanded', 'true');  // Pollutes global namespace
```

**✅ Correct:**
```typescript
const STORAGE_KEY = 'amplify-chat-sources-expanded';
try {
  sessionStorage.setItem(STORAGE_KEY, 'true');
} catch (e) {
  // Handle QuotaExceededError, SecurityError (SSR, private browsing)
  console.warn('Failed to persist sources state:', e);
}
```

**Why:** Namespace keys, handle storage errors gracefully

---

## Tech Stack & Libraries

### Backend (Node.js)

**Required:**
- `@aws-sdk/client-dynamodb`: DynamoDB operations
- `@aws-sdk/client-s3`: S3 operations
- `@aws-sdk/s3-request-presigner`: Generate presigned URLs
- `@aws-sdk/client-bedrock-agent-runtime`: Already present (Bedrock queries)

**Version constraints:**
- Must use AWS SDK v3 (current project standard)
- TypeScript 5.x (matches `amplify/tsconfig.json`)

### Frontend (React)

**Required:**
- `react@19`: Already present
- `react-dom@19`: Already present

**No new dependencies needed** - use existing patterns

**CSS:**
- CSS Modules (`.module.css` files)
- CSS custom properties for theming
- CSS transitions for animations

### Testing

**Backend:**
- `vitest`: Already configured for TypeScript tests
- `@aws-sdk/client-dynamodb`: Mock with vitest.mock()
- `@aws-sdk/s3-request-presigner`: Mock with vitest.mock()

**Frontend:**
- `@testing-library/react`: Component tests
- `@testing-library/user-event`: User interaction simulation
- `vitest`: Test runner

---

## Shared Conventions

### Commit Messages

Follow Conventional Commits format:

```
<type>(<scope>): <subject>

<body>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructure (no behavior change)
- `test`: Add/update tests
- `docs`: Documentation only
- `chore`: Maintenance (deps, config)

**Scopes:**
- `backend`: Lambda functions, DynamoDB
- `frontend`: React components, UI
- `config`: Configuration management
- `tests`: Test files

**Examples:**
```
feat(backend): add document URL mapping via TrackingTable

- Extract document_id from Bedrock citation S3 URI
- Query TrackingTable for input_s3_uri
- Generate presigned URL for original document
- Handle missing documents gracefully
```

```
feat(frontend): add collapsible sources toggle component

- Sources collapsed by default
- Expand/collapse on button click
- Persist state in sessionStorage
- Add smooth CSS transition
- Keyboard accessible (Enter/Space)
```

### File Naming

**Backend:**
- Lambda functions: `index.ts` or `handler.ts`
- Utilities: `camelCase.ts` (e.g., `generatePresignedUrl.ts`)
- Tests: `*.test.ts` (e.g., `conversation.test.ts`)

**Frontend:**
- Components: `PascalCase.tsx` (e.g., `SourcesToggle.tsx`)
- Styles: `ComponentName.module.css`
- Types: `types.ts` or inline in component file
- Tests: `*.test.tsx`

### Code Style

**TypeScript:**
- Use `interface` for object shapes, `type` for unions/intersections
- Prefer `const` over `let`, never use `var`
- Use optional chaining (`?.`) and nullish coalescing (`??`)
- Explicit return types for functions

**React:**
- Functional components only (no class components)
- Use hooks (`useState`, `useEffect`, `useMemo`)
- Extract custom hooks when logic is reused
- Props interface above component definition

**CSS:**
- BEM-like naming within modules (`.container`, `.container__item`, `.container--expanded`)
- CSS custom properties for theming (`--chat-color-*`)
- Mobile-first media queries

---

## Testing Strategy Overview

### Test Pyramid

```
        /\
       /E2E\      <- Few (critical paths only)
      /------\
     /Integr.\   <- Some (API contracts, data flow)
    /----------\
   /   Unit     \ <- Many (functions, components)
  /--------------\
```

**Distribution:**
- Unit tests: 70% (fast, focused, many)
- Integration tests: 25% (moderate, realistic, some)
- E2E tests: 5% (slow, expensive, few)

### Coverage Targets

- **Overall:** 80%+ line coverage
- **Critical paths:** 100% (presigned URL generation, config access)
- **Error handling:** All error paths tested
- **Edge cases:** Null/undefined, empty arrays, malformed input

### Test Organization

**Backend:**
```
amplify/data/functions/
├── conversation.ts
├── conversation.test.ts       # Unit tests
└── __mocks__/
    └── @aws-sdk/               # SDK mocks
```

**Frontend:**
```
src/amplify-chat/src/components/
├── SourcesToggle.tsx
├── SourcesToggle.test.tsx     # Component tests
└── SourcesToggle.module.css
```

### Mocking Strategy

**DynamoDB:**
```typescript
vi.mock('@aws-sdk/client-dynamodb', () => ({
  DynamoDBClient: vi.fn(() => ({
    send: vi.fn().mockResolvedValue({
      Item: { input_s3_uri: { S: 's3://bucket/key' } }
    })
  })),
  GetItemCommand: vi.fn()
}));
```

**S3 Presigned URLs:**
```typescript
vi.mock('@aws-sdk/s3-request-presigner', () => ({
  getSignedUrl: vi.fn().mockResolvedValue('https://s3.amazonaws.com/...')
}));
```

**SessionStorage:**
```typescript
const mockSessionStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn()
};
global.sessionStorage = mockSessionStorage as any;
```

---

## Phase Transition Criteria

Before moving to Phase 1, verify:

- [ ] This foundation document has been read and understood completely
- [ ] Development environment is set up (Node 24+, Python 3.13+, Docker)
- [ ] Codebase has been explored (read existing conversation.ts, config patterns)
- [ ] Questions about architecture decisions have been resolved
- [ ] Testing tools are verified working (`npm run test`, `uv run pytest`)

---

## Known Constraints

**Technical:**
- Presigned URLs cannot exceed 7 days expiry (AWS limit)
- DynamoDB config cache is 60 seconds (changes not instant)
- TrackingTable uses `document_id` as partition key (no secondary indexes)
- InputBucket must have versioning enabled (existing requirement)

**Business:**
- Feature must be backward compatible (no breaking changes)
- Must work with existing authentication modes (auth + no-auth)
- Performance must not degrade (< 100ms added latency per query)
- Must follow existing configuration patterns (DynamoDB, not env vars)

**UX:**
- Sources must be keyboard accessible (Tab, Enter, Space)
- Animations must respect `prefers-reduced-motion`
- Document links must open in new tab (`target="_blank"`)
- Must work in all supported browsers (Chrome, Firefox, Safari, Edge)

---

**Estimated tokens for Phase 0:** ~15,000

**Next:** [Phase 1: Backend Implementation](./Phase-1.md)
