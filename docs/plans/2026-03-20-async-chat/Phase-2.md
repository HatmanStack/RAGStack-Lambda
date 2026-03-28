# Phase 2: Frontend Implementation

## Phase Goal

Update the ragstack-chat web component to use the new async mutation + polling pattern. Replace the sync `queryKnowledgeBase` call with: (1) send mutation, (2) poll `getConversation` every 2s, (3) correlate response via `requestId`, (4) show progressive timeout states.

**Success criteria:**
- ChatInterface sends `queryKnowledgeBase` mutation and receives immediate acknowledgment
- Polls `getConversation` every 2s until response arrives or timeout
- Progressive timeout: normal (0-30s), "still working" indicator (30-60s), hard timeout (90s)
- Input disabled while a request is in-flight (no concurrent sends)
- All existing frontend tests pass, new tests cover polling flow
- Old sync query code is removed

**Estimated tokens:** ~25,000

## Prerequisites

- Phase 1 complete (backend schema and resolvers exist)
- Node.js 24+ available
- `npm install` run in `src/ragstack-chat/`

---

## Task 1: Update GraphQL Operations and API Function

**Goal:** Replace the sync query with mutation + polling functions in ChatInterface.tsx.

**Files to Modify:**
- `src/ragstack-chat/src/components/ChatInterface.tsx` - Replace sync query with async mutation + polling

**Implementation Steps:**

1. Replace the `QUERY_KB_QUERY` GraphQL string (lines 17-47) with two new operations:

   ```typescript
   // GraphQL mutation for async chat query
   const QUERY_KB_MUTATION = `
     mutation QueryKnowledgeBase($query: String!, $conversationId: ID!, $requestId: ID!) {
       queryKnowledgeBase(query: $query, conversationId: $conversationId, requestId: $requestId) {
         conversationId
         requestId
         status
       }
     }
   `;

   // GraphQL query for polling conversation results
   const GET_CONVERSATION_QUERY = `
     query GetConversation($conversationId: ID!) {
       getConversation(conversationId: $conversationId) {
         conversationId
         turns {
           turnNumber
           requestId
           status
           userMessage
           assistantResponse
           sources {
             documentId
             pageNumber
             s3Uri
             snippet
             documentUrl
             documentAccessAllowed
             score
             filename
             isMedia
             isSegment
             segmentUrl
             mediaType
             contentType
             timestampStart
             timestampEnd
             timestampDisplay
             speaker
             isImage
             isScraped
             sourceUrl
           }
           error
           createdAt
         }
       }
     }
   `;
   ```

2. Replace the `queryKnowledgeBase` function (lines 59-131) with two functions:

   ```typescript
   // Polling configuration
   const POLL_INTERVAL_MS = 2000;      // Poll every 2 seconds
   const SLOW_THRESHOLD_MS = 30000;    // "Still working" after 30s
   const HARD_TIMEOUT_MS = 90000;      // Hard timeout at 90s

   /**
    * Send async chat mutation
    */
   async function sendChatMutation(
     message: string,
     conversationId: string,
     requestId: string,
   ): Promise<{ conversationId: string; requestId: string; status: string }> {
     const config = await fetchCDNConfig();
     if (!config?.apiEndpoint || !config?.identityPoolId || !config?.region) {
       throw new Error('API endpoint not available. Please check your configuration.');
     }

     const body = JSON.stringify({
       query: QUERY_KB_MUTATION,
       variables: { query: message, conversationId, requestId },
     });

     const response = await iamFetch(config.apiEndpoint, body, config.identityPoolId, config.region);
     if (!response.ok) {
       throw new Error(`HTTP ${response.status}: ${response.statusText}`);
     }

     const result = await response.json();
     if (result.errors?.length > 0) {
       throw new Error(result.errors[0].message);
     }

     if (!result.data?.queryKnowledgeBase) {
       throw new Error('No response data received');
     }

     return result.data.queryKnowledgeBase;
   }

   /**
    * Poll getConversation for a specific requestId's result
    */
   async function pollForResult(
     conversationId: string,
     requestId: string,
     onSlowThreshold: () => void,
   ): Promise<{
     answer: string;
     sources: Array<{
       documentId: string;
       pageNumber?: number;
       s3Uri: string;
       snippet?: string;
       documentUrl?: string;
       documentAccessAllowed?: boolean;
       score?: number;
       filename?: string;
       isMedia?: boolean;
       isSegment?: boolean;
       segmentUrl?: string;
       mediaType?: string;
       contentType?: string;
       timestampStart?: number;
       timestampEnd?: number;
       timestampDisplay?: string;
       speaker?: string;
       isImage?: boolean;
       isScraped?: boolean;
       sourceUrl?: string;
     }>;
     error?: string;
   }> {
     const config = await fetchCDNConfig();
     if (!config?.apiEndpoint || !config?.identityPoolId || !config?.region) {
       throw new Error('API endpoint not available.');
     }

     const startTime = Date.now();
     let slowNotified = false;

     while (true) {
       const elapsed = Date.now() - startTime;

       // Hard timeout
       if (elapsed > HARD_TIMEOUT_MS) {
         throw new Error('Response timed out. The query may still be processing. Please try again.');
       }

       // Slow threshold notification
       if (!slowNotified && elapsed > SLOW_THRESHOLD_MS) {
         slowNotified = true;
         onSlowThreshold();
       }

       // Poll
       const body = JSON.stringify({
         query: GET_CONVERSATION_QUERY,
         variables: { conversationId },
       });

       const response = await iamFetch(config.apiEndpoint, body, config.identityPoolId, config.region);
       if (response.ok) {
         const result = await response.json();
         const conversation = result.data?.getConversation;

         if (conversation?.turns) {
           // Find the turn matching our requestId
           const matchingTurn = conversation.turns.find(
             (t: { requestId?: string }) => t.requestId === requestId
           );

           if (matchingTurn) {
             if (matchingTurn.status === 'COMPLETED') {
               return {
                 answer: matchingTurn.assistantResponse || '',
                 sources: matchingTurn.sources || [],
               };
             }

             if (matchingTurn.status === 'ERROR') {
               throw new Error(matchingTurn.error || 'An error occurred processing your query.');
             }

             // PENDING - continue polling
           }
         }
       }
       // If poll request fails, continue polling (transient error)

       // Wait before next poll
       await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
     }
   }
   ```

3. Add a UUID generation utility at the top of the file (after imports):
   ```typescript
   /** Generate a UUID v4 using crypto API */
   function generateRequestId(): string {
     return crypto.randomUUID();
   }
   ```

**Verification Checklist:**
- [x] `QUERY_KB_QUERY` is removed, replaced by `QUERY_KB_MUTATION` and `GET_CONVERSATION_QUERY`
- [x] `sendChatMutation` sends mutation with `query`, `conversationId`, `requestId`
- [x] `pollForResult` polls every 2s, checks for matching `requestId`
- [x] Hard timeout at 90s throws descriptive error
- [x] Slow threshold at 30s calls `onSlowThreshold` callback
- [x] Both functions use `iamFetch` for IAM auth (no new dependencies)
- [x] `generateRequestId` uses `crypto.randomUUID()`
- [x] `GET_CONVERSATION_QUERY` source selection set includes all fields the UI actually renders (verify against `Source` type in schema -- optional fields like `thumbnailUrl`, `caption`, `segmentIndex` can be omitted if unused by the UI)

**Testing Instructions:**
- Tests are written in Task 3. This task focuses on the implementation.

**Commit Message Template:**
```
feat(chat-ui): replace sync query with async mutation and polling

- Add sendChatMutation for queryKnowledgeBase mutation
- Add pollForResult with 2s interval and 90s timeout
- Add progressive timeout threshold at 30s
- Remove old sync queryKnowledgeBase function
```

---

## Task 2: Update ChatInterface Component handleSend

**Goal:** Modify the `handleSend` callback to use the new mutation + polling flow with progressive timeout states.

**Files to Modify:**
- `src/ragstack-chat/src/components/ChatInterface.tsx` - Update handleSend logic
- `src/ragstack-chat/src/types/index.ts` - Add `isSlowResponse` to ErrorState (optional UX indicator)

**Prerequisites:**
- Task 1 (mutation and polling functions exist)

**Implementation Steps:**

1. In `types/index.ts`, add an optional field to `ChatMessage` for slow response indicator:
   ```typescript
   // In ChatMessage interface:
   /** Whether this response took longer than the slow threshold */
   isSlowResponse?: boolean;
   ```

2. In `ChatInterface.tsx`, add a `isSlowResponse` state:
   ```typescript
   const [isSlowResponse, setIsSlowResponse] = useState(false);
   ```

3. Replace the `handleSend` function body. The new flow:

   a. Add user message to state (same as current, lines 201-210)
   b. Call `onSendMessage` callback (same as current, lines 213-215)
   c. Set loading and clear error (same as current, lines 218-219)
   d. Reset slow response state: `setIsSlowResponse(false)`
   e. Generate a `requestId`:
      ```typescript
      const requestId = generateRequestId();
      ```
   f. Send the mutation:
      ```typescript
      await sendChatMutation(messageText, conversationId, requestId);
      ```
   g. Poll for result:
      ```typescript
      const response = await pollForResult(
        conversationId,
        requestId,
        () => setIsSlowResponse(true),  // onSlowThreshold callback
      );
      ```
   h. Process the response (same mapping logic as current, lines 226-266)
   i. Error handling stays the same structure but add `'timeout'` error type:
      ```typescript
      } else if (errorMessage.toLowerCase().includes('timed out')) {
        errorType = 'network';  // Timeout is a network-category error
        retryable = true;
      }
      ```

4. Pass `isSlowResponse` state to `MessageList` so it can show a "still working" indicator:
   ```typescript
   <MessageList
     messages={messages}
     isLoading={isLoading}
     isSlowResponse={isSlowResponse}
     error={error}
     showSources={showSources}
   />
   ```

5. Update `MessageListProps` in `types/index.ts` to accept `isSlowResponse`:
   ```typescript
   /** Whether the current request is taking longer than usual */
   isSlowResponse?: boolean;
   ```

**Verification Checklist:**
- [x] `handleSend` generates a `requestId` per message
- [x] Mutation is sent with `sendChatMutation`
- [x] Polling is done with `pollForResult`
- [x] `isSlowResponse` state is set via the `onSlowThreshold` callback
- [x] `isSlowResponse` is passed to `MessageList`
- [x] Error handling includes timeout classification
- [x] Input remains disabled during the entire mutation + polling flow (existing `isLoading` state handles this)

**Testing Instructions:**
- Tests are written in Task 3.

**Commit Message Template:**
```
feat(chat-ui): update handleSend for async mutation + polling flow

- Generate requestId per message
- Send mutation then poll for result
- Add isSlowResponse state for progressive timeout UX
- Pass slow response indicator to MessageList
```

---

## Task 3: Update MessageList for Slow Response Indicator

> **Scope note:** This task covers only the MessageList component and its tests (slow response indicator). The broader async flow tests (mutation, polling, timeout, error handling) are covered in Task 4 (ChatInterface tests).

**Goal:** Show a "taking longer than usual" message in MessageList when `isSlowResponse` is true and `isLoading` is true.

**Files to Modify:**
- `src/ragstack-chat/src/components/MessageList.tsx` - Accept and display isSlowResponse prop

**Prerequisites:**
- Task 2 (isSlowResponse prop is passed)

**Implementation Steps:**

1. Read `src/ragstack-chat/src/components/MessageList.tsx` to understand the current loading indicator.

2. Add `isSlowResponse` to the destructured props.

3. In the loading indicator section, conditionally show the slow response message:
   ```tsx
   {isLoading && (
     <div className={styles.loadingIndicator}>
       <div className={styles.loadingDots}>
         <span /><span /><span />
       </div>
       {isSlowResponse && (
         <div className={styles.slowResponseMessage}>
           Taking longer than usual...
         </div>
       )}
     </div>
   )}
   ```

4. Add CSS for the slow response message in the appropriate CSS module file. Keep it minimal:
   ```css
   .slowResponseMessage {
     font-size: 0.8rem;
     color: var(--text-secondary, #666);
     margin-top: 4px;
     text-align: center;
   }
   ```

   Find the CSS module file used by MessageList (likely `src/ragstack-chat/src/styles/ChatWithSources.module.css`) and add the style there.

**Verification Checklist:**
- [x] `MessageList` accepts `isSlowResponse` prop
- [x] Slow response message shown only when both `isLoading` and `isSlowResponse` are true
- [x] CSS is minimal and uses existing color variables
- [x] Message text is "Taking longer than usual..."

**Testing Instructions:**

Update `src/ragstack-chat/src/components/__tests__/MessageList.test.tsx`:

- Test 1: Slow response message is NOT shown when `isLoading=true` and `isSlowResponse=false`
- Test 2: Slow response message IS shown when `isLoading=true` and `isSlowResponse=true`
- Test 3: Slow response message is NOT shown when `isLoading=false` regardless of `isSlowResponse`

Run: `npm run test:frontend`

**Commit Message Template:**
```
feat(chat-ui): show slow response indicator during long queries

- Display "Taking longer than usual..." after 30s threshold
- Only visible during active loading state
```

---

## Task 4: Update ChatInterface Tests

**Goal:** Update existing ChatInterface tests and add new tests for the async flow.

**Files to Modify:**
- `src/ragstack-chat/src/components/__tests__/ChatInterface.test.tsx` - Update and add tests

**Prerequisites:**
- Tasks 1-3 (implementation complete)

**Implementation Steps:**

1. Read the existing `ChatInterface.test.tsx` to understand the current test structure and mocking approach.

2. Update mocks: The existing tests likely mock the old `queryKnowledgeBase` sync function or `iamFetch`. Update these to work with the new flow:

   - Mock `iamFetch` to return different responses based on the GraphQL operation in the request body
   - For mutation calls (body contains `QueryKnowledgeBase` mutation), return a `ChatRequest` response
   - For polling calls (body contains `GetConversation` query), return a `Conversation` response

3. Add new test cases:

   **Happy path:**
   - Test: Sending a message triggers mutation, then polls, then displays response
     - Mock `iamFetch` to return PENDING on first poll, COMPLETED on second poll
     - Verify user message appears immediately
     - Verify assistant message appears after polling completes
     - Verify sources are displayed

   **Timeout:**
   - Test: Hard timeout after 90s shows error
     - Use `vi.useFakeTimers()` to control time
     - Mock `iamFetch` to always return PENDING for polls
     - Advance timers past 90s
     - Verify timeout error is shown

   **Slow response:**
   - Test: Slow threshold triggers "taking longer" indicator
     - Use `vi.useFakeTimers()`
     - Mock polls to return PENDING
     - Advance timers past 30s
     - Verify slow response indicator appears

   **Error from server:**
   - Test: ERROR status in poll response shows error message
     - Mock poll to return a turn with `status: "ERROR"` and error message
     - Verify error is displayed

   **Mutation failure:**
   - Test: Mutation HTTP error shows error message
     - Mock `iamFetch` to return error for mutation call
     - Verify error is displayed

   **Input disabled during loading:**
   - Test: Input is disabled after sending until response arrives
     - Verify input disabled state during mutation + polling

4. Remove or update any tests that reference the old `QUERY_KB_QUERY` or sync `queryKnowledgeBase` function.

**Verification Checklist:**
- [x] All existing tests either pass or are updated for new async flow
- [x] Happy path test covers mutation -> poll -> display
- [x] Timeout test verifies 90s hard timeout
- [x] Slow threshold test verifies 30s indicator
- [x] Server error test covers ERROR status from poll
- [x] Mutation failure test covers HTTP errors
- [x] No references to old sync query remain in tests

**Testing Instructions:**
```bash
cd src/ragstack-chat && npx vitest run src/components/__tests__/ChatInterface.test.tsx
```

Then run full frontend suite:
```bash
npm run test:frontend
```

**Commit Message Template:**
```
test(chat-ui): update ChatInterface tests for async polling flow

- Mock mutation and polling responses separately
- Add timeout, slow threshold, and error test cases
- Remove old sync query test references
```

---

## Task 5: Clean Up Old Sync Code

**Goal:** Remove any remaining references to the old sync query pattern.

**Files to Modify:**
- `src/ragstack-chat/src/components/ChatInterface.tsx` - Verify no old code remains
- `src/ragstack-chat/src/components/__tests__/integration/conversation.integration.test.tsx` - Update if it references old sync query

**Prerequisites:**
- Tasks 1-4

**Implementation Steps:**

1. Search for `QUERY_KB_QUERY` across the entire `src/ragstack-chat/` directory. Remove any remaining references.

2. Search for `queryKnowledgeBase(query:` (the old query signature) across `src/ragstack-chat/`. Update any remaining references to use the mutation signature.

3. Read `src/ragstack-chat/src/components/__tests__/integration/conversation.integration.test.tsx` and update if it references the old sync flow. This is an integration test so it may need the new mutation + polling mocks.

4. Verify the `ChatResponse` type in the GraphQL schema (`src/api/schema.graphql`) is no longer referenced by any frontend code. It may still be used by Python backend types (`ragstack_common/types.py`) which is fine.

**Verification Checklist:**
- [x] No references to `QUERY_KB_QUERY` in `src/ragstack-chat/`
- [x] No references to old sync function signature in `src/ragstack-chat/`
- [x] Integration test updated if applicable
- [x] `ChatResponse` GraphQL type not referenced by frontend

**Testing Instructions:**
```bash
npm run test:frontend
npm run lint:frontend
```

**Commit Message Template:**
```
refactor(chat-ui): remove old sync query references

- Clean up remaining references to sync queryKnowledgeBase
- Update integration test for async flow
```

---

## Task 6: Run Full Test Suite

**Goal:** Verify everything works end-to-end.

**Files to Modify:** None (verification only)

**Prerequisites:**
- Tasks 1-5

**Implementation Steps:**

1. Run full test suite:
   ```bash
   npm run test
   ```

2. Run full lint:
   ```bash
   npm run lint
   npm run lint:frontend
   ```

3. Fix any failures.

**Verification Checklist:**
- [x] `npm run test` passes (all backend + frontend tests)
- [x] `npm run lint` passes
- [x] `npm run lint:frontend` passes

**Commit Message Template:**
```
test: verify full test suite passes with async chat implementation
```

---

## Phase Verification

After completing all Phase 2 tasks:

1. **ChatInterface.tsx:** Uses `sendChatMutation` + `pollForResult` instead of sync query
2. **MessageList.tsx:** Shows "Taking longer than usual..." after 30s
3. **Types:** `ChatMessage` has optional `isSlowResponse`, `MessageListProps` has `isSlowResponse`
4. **Tests:** All frontend tests pass, covering mutation, polling, timeout, and error scenarios
5. **No old code:** No references to sync `queryKnowledgeBase` query in frontend

**Known limitations:**
- `ChatResponse` GraphQL type remains in schema (still referenced by Python types, harmless)
- `KBQueryDataSource` remains in template (used by `searchKnowledgeBase`)
- Polling interval is fixed at 2s (could be tuned later based on production metrics)
- No conversation listing/search UI (out of scope per brainstorm)
