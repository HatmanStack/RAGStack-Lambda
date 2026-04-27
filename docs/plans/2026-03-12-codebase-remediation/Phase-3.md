# Phase 3: Defensive Infrastructure

## Phase Goal

Add defensive infrastructure: a DLQ replay Lambda with CloudWatch alarms, S3 size guards on `read_s3_binary()`, React error boundaries for all routes and critical components, and replace `window.alert()` with Cloudscape Flashbar notifications.

**Success criteria:**
- DLQ replay Lambda exists with SAM template resources and CloudWatch alarms for all 5 DLQs
- `read_s3_binary()` has a `max_size_bytes` parameter with HEAD check
- 8 React error boundaries wrapping routes and critical components
- All 4 `window.alert()` calls replaced with Flashbar notifications
- All existing tests pass, new tests cover new code

**Estimated tokens:** ~40,000

## Prerequisites

- Phase 2 complete (types in place, query_kb refactored, mypy passing)
- Familiarity with SAM template syntax (AWS::Serverless::Function, AWS::CloudWatch::Alarm)
- Familiarity with React error boundaries and Cloudscape Design System

---

## Task 1: Add S3 Size Guard to read_s3_binary()

**Goal:** Add a configurable maximum file size check to `read_s3_binary()` using an S3 HEAD request before downloading.

**Files to Modify:**
- `lib/ragstack_common/storage.py` -- Add `max_size_bytes` parameter to `read_s3_binary()`
- `lib/ragstack_common/exceptions.py` -- Add `FileSizeLimitExceeded` exception (if not already present)

**Files to Read First:**
- `lib/ragstack_common/storage.py` -- Current `read_s3_binary()` implementation (line ~111)
- `lib/ragstack_common/exceptions.py` -- Existing exception hierarchy
- `lib/ragstack_common/ocr.py` (line ~85) -- Call site 1
- `src/lambda/detect_file_type/index.py` (line ~199) -- Call site 2

**Prerequisites:**
- None (can start in parallel with other Phase 3 tasks)

**Implementation Steps:**
- Read the existing exception hierarchy. There is already a `MediaFileSizeExceededError`. Decide whether to reuse it or create a more general `FileSizeLimitExceeded` exception. Since this guard protects against arbitrary large files (not just media), a general exception may be clearer.
- Modify `read_s3_binary()` to accept an optional `max_size_bytes: int | None = None` parameter.
- When `max_size_bytes` is provided:
  1. Call `s3_client.head_object(Bucket=bucket, Key=key)` to get `ContentLength`.
  2. If `ContentLength > max_size_bytes`, raise the size exception with the actual size and limit.
  3. Otherwise, proceed with the existing `get_object` call.
- When `max_size_bytes` is `None` (default), skip the HEAD check entirely. This preserves backward compatibility.
- Update the two call sites:
  - `lib/ragstack_common/ocr.py` line ~85: Pass a reasonable max (e.g., 500MB for OCR documents). The exact value should be read from the handler -- check what limits already exist.
  - `src/lambda/detect_file_type/index.py` line ~199: Pass a reasonable max for file type detection (same or smaller).
- Add type annotations to the modified function (consistent with Phase 2).

**Verification Checklist:**
- [ ] `read_s3_binary()` accepts optional `max_size_bytes` parameter
- [ ] HEAD check only runs when `max_size_bytes` is provided
- [ ] Exception raised includes actual size and limit in message
- [ ] Both call sites updated with appropriate limits
- [ ] Default behavior (no max) unchanged
- [ ] `uv run mypy --strict lib/ragstack_common/storage.py` passes
- [ ] Existing storage tests pass

**Testing Instructions:**
- Add tests to `tests/unit/python/test_storage.py`:
  - `read_s3_binary` with `max_size_bytes=None` -- no HEAD call, normal behavior
  - `read_s3_binary` with `max_size_bytes=1000`, file is 500 bytes -- succeeds
  - `read_s3_binary` with `max_size_bytes=1000`, file is 2000 bytes -- raises exception
  - `read_s3_binary` with `max_size_bytes`, HEAD call fails -- should fall through to GET (don't block on HEAD failures)

```bash
uv run pytest tests/unit/python/test_storage.py -v
uv run pytest tests/unit/python/test_ocr.py -v
uv run pytest tests/unit/python/test_detect_file_type.py -v
```

**Commit Message Template:**
```
feat(storage): add S3 size guard with HEAD check before read

- read_s3_binary() accepts optional max_size_bytes parameter
- HEAD check prevents downloading oversized objects
- Both call sites (ocr.py, detect_file_type) updated
- Backward compatible: no max = no check
```

---

## Task 2: Create DLQ Replay Lambda

**Goal:** Create a Lambda function that moves messages from a DLQ back to its source queue for reprocessing.

**Files to Create:**
- `src/lambda/dlq_replay/index.py` -- The replay Lambda handler

**Files to Read First:**
- `template.yaml` (lines ~3748-3925) -- All 5 DLQ definitions and their source queues
- `src/lambda/queue_processor/index.py` -- Reference for SQS message handling patterns

**Prerequisites:**
- None

**Implementation Steps:**
- The Lambda receives an event with the DLQ name (or ARN) to replay. It reads messages from the DLQ and sends them to the corresponding source queue.
- The 5 DLQ-to-source mappings are:
  1. `ProcessingDLQ` -> `DocumentProcessingQueue`
  2. `BatchProcessingDLQ` -> `BatchProcessingQueue`
  3. `ScrapeDiscoveryDLQ` -> `ScrapeDiscoveryQueue`
  4. `ScrapeProcessingDLQ` -> `ScrapeProcessingQueue`
  5. `SyncRequestDLQ` -> `SyncRequestQueue` (FIFO)
- Design the handler to:
  1. Accept `{"dlq_name": "processing" | "batch" | "scrape-discovery" | "scrape-processing" | "sync"}` as input.
  2. Look up the DLQ URL and source queue URL from environment variables.
  3. Receive messages from the DLQ (up to 10 at a time, loop until empty or max iterations).
  4. Send each message to the source queue.
  5. Delete the message from the DLQ after successful send.
  6. For the FIFO queue (sync), include `MessageGroupId` and `MessageDeduplicationId` from the original message attributes.
  7. Return a summary: `{"replayed": N, "failed": M}`.
- Set a configurable max iterations to prevent runaway execution (e.g., 100 iterations = 1000 messages max).
- Log each replayed message's `MessageId` at INFO level.
- Handle errors gracefully: if a send fails, log the error and continue (don't delete the DLQ message).

**Environment variables the Lambda will need:**
- `PROCESSING_DLQ_URL`, `PROCESSING_QUEUE_URL`
- `BATCH_DLQ_URL`, `BATCH_QUEUE_URL`
- `SCRAPE_DISCOVERY_DLQ_URL`, `SCRAPE_DISCOVERY_QUEUE_URL`
- `SCRAPE_PROCESSING_DLQ_URL`, `SCRAPE_PROCESSING_QUEUE_URL`
- `SYNC_DLQ_URL`, `SYNC_QUEUE_URL`

**Verification Checklist:**
- [ ] `src/lambda/dlq_replay/index.py` exists
- [ ] Handles all 5 DLQ types
- [ ] FIFO queue handling includes MessageGroupId
- [ ] Max iteration limit prevents runaway
- [ ] Graceful error handling per message
- [ ] `uv run mypy --strict src/lambda/dlq_replay/index.py` passes
- [ ] `uv run ruff check src/lambda/dlq_replay/` passes

**Testing Instructions:**
- Create `tests/unit/python/test_dlq_replay.py` with tests:
  - Happy path: replay 3 messages from standard queue
  - FIFO queue: verify MessageGroupId included
  - Empty DLQ: returns `{"replayed": 0, "failed": 0}`
  - Invalid dlq_name: raises ValueError
  - Send failure: message not deleted from DLQ, counted in failed
  - Max iterations reached: stops and returns count

```bash
uv run pytest tests/unit/python/test_dlq_replay.py -v
```

**Commit Message Template:**
```
feat(dlq-replay): add DLQ replay Lambda for all 5 queue pairs

- Supports standard and FIFO queue replay
- Max iteration limit prevents runaway execution
- Per-message error handling (failed sends don't block others)
```

---

## Task 3: Add DLQ Replay Lambda to SAM Template

**Goal:** Add the DLQ replay Lambda function, IAM permissions, and CloudWatch alarms for all 5 DLQs to the SAM template.

**Files to Modify:**
- `template.yaml` -- Add Lambda function, IAM policies, and CloudWatch alarms

**Files to Read First:**
- `template.yaml` -- Full template (read in chunks focusing on: existing Lambda definitions for patterns, existing DLQ section ~3748-3925, existing alarm ~4211-4227)

**Prerequisites:**
- Task 2 complete (Lambda code exists)

**Implementation Steps:**
- Add a new `AWS::Serverless::Function` resource for the DLQ replay Lambda:
  - `FunctionName`: `${Prefix}-dlq-replay`
  - `CodeUri`: `src/lambda/dlq_replay/`
  - `Handler`: `index.lambda_handler`
  - `Runtime`: `python3.13`
  - `Timeout`: 300 (5 minutes)
  - `MemorySize`: 128
  - No event source (manually invoked)
  - Environment variables for all 10 queue URLs (5 DLQ + 5 source)

- Add IAM policies:
  - `sqs:ReceiveMessage`, `sqs:DeleteMessage` on all 5 DLQs
  - `sqs:SendMessage` on all 5 source queues

- Expand the existing `DLQMessagesAlarm` to cover all 5 DLQs (currently only covers `ProcessingDLQ`). Add alarms for:
  - `BatchProcessingDLQ`
  - `ScrapeDiscoveryDLQ`
  - `ScrapeProcessingDLQ`
  - `SyncRequestDLQ`

- Each alarm should trigger when `ApproximateNumberOfMessagesVisible > 0` for a period of 5 minutes. Follow the pattern of the existing `DLQMessagesAlarm`.

**Verification Checklist:**
- [ ] `DLQReplayFunction` resource exists in template.yaml
- [ ] All 10 queue URL environment variables set
- [ ] IAM policies grant receive/delete on DLQs and send on source queues
- [ ] CloudWatch alarms exist for all 5 DLQs
- [ ] `sam validate` passes (run `sam validate --lint` if available)

**Testing Instructions:**
```bash
# Validate SAM template
sam validate
```

**Commit Message Template:**
```
feat(dlq-replay): add SAM template resources for DLQ replay Lambda

- Lambda function with IAM policies for all 5 queue pairs
- CloudWatch alarms for all 5 DLQs (was only ProcessingDLQ)
```

---

## Task 4: Create React ErrorBoundary Component

**Goal:** Create a reusable error boundary component using React's class component API.

**Files to Create:**
- `src/ui/src/components/common/ErrorBoundary.tsx`
- `src/ui/src/components/common/ErrorBoundary.test.tsx`

**Files to Read First:**
- `src/ui/src/App.tsx` -- Current app structure with routes
- `src/ui/src/components/common/ApiDocs.tsx` -- Existing common component pattern
- `src/ui/src/components/Dashboard/DocumentTable.tsx` -- One of the critical components to wrap

**Prerequisites:**
- None (frontend tasks are independent of backend tasks)

**Implementation Steps:**
- Create a React class component `ErrorBoundary` that:
  1. Catches JavaScript errors in its child component tree via `componentDidCatch`.
  2. Displays a Cloudscape-styled fallback UI (use `Alert` component with `type="error"`).
  3. Includes a "Try again" button that resets the error state (calls `setState({ hasError: false })`).
  4. Logs the error to `console.error` (for CloudWatch/browser dev tools).
  5. Accepts optional props:
     - `fallback?: ReactNode` -- Custom fallback UI
     - `onError?: (error: Error, errorInfo: ErrorInfo) => void` -- Error callback
- Use Cloudscape `Alert` and `Button` components for the fallback UI.
- Keep the component simple -- no global error reporting service (YAGNI).

**Example usage:**
```tsx
<ErrorBoundary>
  <Dashboard />
</ErrorBoundary>
```

**Verification Checklist:**
- [ ] `ErrorBoundary.tsx` exists as a class component with `componentDidCatch`
- [ ] Uses Cloudscape `Alert` component for fallback
- [ ] "Try again" button resets error state
- [ ] Optional `fallback` and `onError` props
- [ ] TypeScript compiles: `cd src/ui && npx tsc --noEmit`

**Testing Instructions:**
- Write `ErrorBoundary.test.tsx` with:
  - Renders children normally when no error
  - Shows fallback UI when child throws
  - "Try again" button resets to children
  - Custom fallback prop used when provided
  - `onError` callback called with error info

```bash
cd src/ui && npm test -- --run ErrorBoundary
```

**Commit Message Template:**
```
feat(ui-error-boundary): add reusable ErrorBoundary component

- Cloudscape-styled error fallback with "Try again" button
- Optional custom fallback and onError props
```

---

## Task 5: Wrap Routes and Critical Components with ErrorBoundary

**Goal:** Add error boundaries to all 6 routes and 2 critical components (ChatInterface, DocumentTable).

**Files to Modify:**
- `src/ui/src/App.tsx` -- Wrap each route with ErrorBoundary

**Files to Read First:**
- `src/ui/src/App.tsx` -- Current route structure
- `src/ui/src/components/Dashboard/index.tsx` -- Dashboard component
- `src/ui/src/components/Chat/index.tsx` -- Chat component

**Prerequisites:**
- Task 4 complete (ErrorBoundary component exists)

**Implementation Steps:**
- In `App.tsx`, wrap each `Route`'s `element` with `<ErrorBoundary>`:
  ```tsx
  <Route path="/" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
  <Route path="/upload" element={<ErrorBoundary><Upload /></ErrorBoundary>} />
  // etc. for all 6 routes
  ```
- For critical components (DocumentTable and ChatInterface), wrap them at their usage point inside their parent components. Read the parent components to find where DocumentTable and ChatInterface are rendered.
  - `DocumentTable` is used in `src/ui/src/components/Dashboard/index.tsx` (likely)
  - `ChatInterface` or `ChatPanel` is used in `src/ui/src/components/Chat/index.tsx` (likely)
- Each boundary is independent -- an error in Chat won't take down Dashboard.

**Verification Checklist:**
- [ ] All 6 routes wrapped in `App.tsx`
- [ ] DocumentTable wrapped in its parent
- [ ] ChatPanel/ChatInterface wrapped in its parent
- [ ] TypeScript compiles: `cd src/ui && npx tsc --noEmit`
- [ ] Existing frontend tests pass: `cd src/ui && npm test`

**Commit Message Template:**
```
feat(ui-error-boundary): wrap routes and critical components

- 6 route-level boundaries in App.tsx
- DocumentTable and ChatPanel wrapped independently
```

---

## Task 6: Create Notification Context for Flashbar

**Goal:** Create a React context that provides a notification system using Cloudscape Flashbar, replacing `window.alert()`.

**Files to Create:**
- `src/ui/src/components/common/NotificationContext.tsx` -- Context provider with Flashbar state management
- `src/ui/src/components/common/NotificationContext.test.tsx` -- Tests

**Files to Read First:**
- `src/ui/src/components/Layout/AppLayout.tsx` -- Where to mount the Flashbar
- `src/ui/src/components/Dashboard/DocumentTable.tsx` -- Where `window.alert()` is used (4 call sites)
- Cloudscape Flashbar API documentation (the component accepts `items` array of flash objects)

**Prerequisites:**
- None (can be done in parallel with Task 4/5)

**Implementation Steps:**
- Create a `NotificationContext` that provides:
  - `addNotification(type: 'success' | 'error' | 'warning' | 'info', content: string, options?: { dismissible?: boolean, action?: { text: string, onClick: () => void } }): void`
  - `clearNotifications(): void`
- The context provider manages an array of Flashbar items as state.
- Each notification gets a unique `id` (use a counter or `crypto.randomUUID()`).
- Dismissible by default.
- Auto-dismiss after 10 seconds for `success` and `info` types.
- Mount the `Flashbar` component in the `AppLayout` (read the layout file to find the right insertion point).

**Verification Checklist:**
- [ ] `NotificationContext.tsx` exports `NotificationProvider` and `useNotifications` hook
- [ ] Flashbar renders in AppLayout
- [ ] `addNotification` adds items to Flashbar
- [ ] Dismiss works
- [ ] Auto-dismiss for success/info types
- [ ] TypeScript compiles

**Testing Instructions:**
- Write tests:
  - `addNotification` adds a flash item
  - Dismiss removes the item
  - Multiple notifications stack
  - `clearNotifications` removes all

```bash
cd src/ui && npm test -- --run NotificationContext
```

**Commit Message Template:**
```
feat(ui-notifications): add NotificationContext with Cloudscape Flashbar

- NotificationProvider with addNotification/clearNotifications
- Auto-dismiss for success/info types
- Mounted in AppLayout
```

---

## Task 7: Replace window.alert() with Flashbar Notifications

**Goal:** Replace all 4 `window.alert()` calls in DocumentTable.tsx with Flashbar notifications.

**Files to Modify:**
- `src/ui/src/components/Dashboard/DocumentTable.tsx` -- Replace 4 `window.alert()` calls

**Files to Read First:**
- `src/ui/src/components/Dashboard/DocumentTable.tsx` -- The 4 `window.alert()` call sites (lines ~199, 220, 228, 247)

**Prerequisites:**
- Task 6 complete (NotificationContext available)

**Implementation Steps:**
- Import and use the `useNotifications` hook in DocumentTable.
- Replace each `window.alert()`:
  1. Line ~199 (unprocessed items warning): `addNotification('warning', 'Selected items have not been processed yet. Use Reprocess to run the full pipeline first.')`
  2. Line ~220 (reindex failed): `addNotification('error', \`Reindex failed: ${...}\`)`
  3. Line ~228 (scrape jobs warning): `addNotification('warning', 'Scrape jobs cannot be reprocessed. Please start a new scrape from the Scrape page.')`
  4. Line ~247 (reprocess failed): `addNotification('error', \`Reprocess failed: ${...}\`)`
- For error notifications, consider adding a retry action where applicable.

**Verification Checklist:**
- [ ] Zero `window.alert()` calls in the entire `src/ui/` codebase
- [ ] All 4 replaced with `addNotification()` calls
- [ ] Error notifications show appropriate type (error vs warning)
- [ ] TypeScript compiles: `cd src/ui && npx tsc --noEmit`
- [ ] Existing DocumentTable tests pass (update if they mock `window.alert`)

**Testing Instructions:**
```bash
# Verify no window.alert remains
grep -r "window.alert" src/ui/src/ && echo "FAIL: window.alert still exists" || echo "PASS: no window.alert"

# Run frontend tests
cd src/ui && npm test
```

**Commit Message Template:**
```
feat(ui-notifications): replace window.alert with Flashbar notifications

- 4 window.alert() calls in DocumentTable replaced
- Warning type for user guidance, error type for failures
- Non-blocking notifications with dismiss
```

---

## Task 8: Full Verification

**Goal:** Verify all Phase 3 changes work together and nothing is broken.

**Files to Modify:** None (verification only)

**Prerequisites:**
- Tasks 1-7 complete

**Implementation Steps:**
- Run all backend tests.
- Run all frontend tests.
- Run all linting.
- Run mypy.
- Verify SAM template.

**Verification Checklist:**
- [ ] `uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short -n auto` passes
- [ ] `uv run ruff check . && uv run ruff format . --check` passes
- [ ] `uv run mypy --strict lib/ragstack_common/ src/lambda/` passes
- [ ] `cd src/ui && npm test` passes
- [ ] `cd src/ui && npx tsc --noEmit` passes
- [ ] `cd src/ui && npm run lint` passes
- [ ] `cd src/ragstack-chat && npm test` passes
- [ ] `sam validate` passes
- [ ] `grep -r "window.alert" src/ui/src/` returns nothing
- [ ] `grep -r "ErrorBoundary" src/ui/src/App.tsx` shows 6+ matches

**Commit Message Template:**
(Only commit if fixes were needed during verification.)

---

## Phase Verification

After completing all tasks:

1. **Backend:** `npm run test:backend` passes, `npm run lint` passes, mypy passes
2. **Frontend:** `npm run test:frontend` passes, `npm run lint:frontend` passes
3. **Infrastructure:** `sam validate` passes
4. **No regressions:** `npm run check` passes (full lint + test)
5. **Defensive features confirmed:**
   - `read_s3_binary()` has `max_size_bytes` parameter
   - `src/lambda/dlq_replay/index.py` exists
   - `template.yaml` has DLQ replay Lambda + 5 CloudWatch alarms
   - `ErrorBoundary` wraps all routes and critical components
   - Zero `window.alert()` in codebase
   - Flashbar notifications visible in AppLayout

**Known limitations:**
- DLQ replay Lambda is manually triggered (no automated replay). This is intentional -- automated replay could cause cascading failures.
- Error boundaries only catch render errors, not event handler errors. Event handler errors in DocumentTable are caught by try/catch and shown via Flashbar.
- S3 size guard adds one extra API call (HEAD) per read when max_size_bytes is specified. This is acceptable for the 2 call sites.
