# Phase 1: Backend Implementation

## Phase Goal

Implement backend infrastructure to support collapsible sources with document access control. This includes adding the new `chat_allow_document_access` configuration option, implementing document URL mapping from Bedrock citations to original S3 files, generating secure presigned URLs, and updating IAM permissions.

**Success Criteria:**
- ✅ New configuration option `chat_allow_document_access` exists in DynamoDB
- ✅ Conversation Lambda can map citations to original documents via TrackingTable
- ✅ Presigned URLs are generated when access is enabled
- ✅ All existing chat functionality continues to work
- ✅ Unit tests cover all new backend logic

**Estimated tokens:** ~75,000

---

## Prerequisites

**Completed:**
- Phase 0 read and understood
- Development environment verified

**External Dependencies:**
- AWS SDK v3 packages installed in `amplify/data/functions/`
- Access to deploy SAM stack to test environment
- DynamoDB ConfigurationTable exists and is seeded

**Environment Requirements:**
- `TRACKING_TABLE_NAME` environment variable will be added to conversation Lambda
- Conversation Lambda role will need additional IAM permissions (added in this phase)

---

## Tasks

### Task 1: Add Configuration Schema and Seed Data

**Goal:** Add `chat_allow_document_access` to DynamoDB configuration schema and seed default values

**Files to Modify:**
- `publish.py` (lines ~1740-1830) - Update `seed_configuration_table()` function
- `tests/unit/test_seed_configuration.py` - Add test assertions for new config key

**Prerequisites:**
- Read existing `seed_configuration_table()` function
- Understand Schema vs Default configuration pattern

**Implementation Steps:**

1. **Add to Schema Configuration**
   - Locate `schema_config` dictionary in `seed_configuration_table()`
   - Add new entry for `chat_allow_document_access` with:
     - Type: `BOOL`
     - Description: Clear explanation of feature
     - Category: `'chat'` (groups with other chat settings)
   - Follow the exact pattern used by existing `chat_require_auth` entry

2. **Add to Default Configuration**
   - Locate `default_config` dictionary in same function
   - Set default value to `False` (secure by default, like `chat_require_auth`)
   - Ensure Boolean type matches schema

3. **Update Unit Tests**
   - Add assertion to verify `chat_allow_document_access` exists in schema
   - Add assertion to verify default value is `False`
   - Run tests to confirm: `uv run pytest tests/unit/test_seed_configuration.py -v`

**Verification Checklist:**
- [ ] `chat_allow_document_access` appears in Schema config with correct type
- [ ] Default value is `False` (secure by default)
- [ ] Description clearly explains the feature
- [ ] Category is `'chat'` (matches other chat settings)
- [ ] Unit tests pass and cover new configuration

**Testing Instructions:**

Run unit tests to verify configuration schema:
```bash
uv run pytest tests/unit/test_seed_configuration.py::test_seed_configuration -v
```

Expected output should include assertions passing for `chat_allow_document_access`.

**Commit Message Template:**
```
feat(config): add chat_allow_document_access configuration option

- Add to Schema configuration with BOOL type and description
- Set default value to False (secure by default)
- Update unit tests to verify new config exists
- Follows pattern established by chat_require_auth
```

**Estimated tokens:** ~15,000

---

### Task 2: Update TypeScript ChatConfig Interface

**Goal:** Extend the `ChatConfig` TypeScript interface to include the new configuration option

**Files to Modify:**
- `amplify/data/functions/conversation.ts` (lines ~24-34) - Update `ChatConfig` interface
- `amplify/data/functions/conversation.ts` (lines ~116-160) - Update `getChatConfig()` function

**Prerequisites:**
- Task 1 complete (configuration exists in DynamoDB)
- Read existing `ChatConfig` interface and `getChatConfig()` implementation

**Implementation Steps:**

1. **Update Interface**
   - Add `allowDocumentAccess: boolean` to `ChatConfig` interface
   - Place after existing fields, maintain alphabetical-ish order
   - Add JSDoc comment explaining purpose

2. **Update getChatConfig() Parser**
   - Locate where DynamoDB item is parsed into `ChatConfig`
   - Add line to parse `chat_allow_document_access` from `result.Item`
   - Use nullish coalescing (`??`) with `false` default
   - Match the pattern used by `requireAuth` parsing

3. **Update Tests**
   - Locate `conversation.test.ts`
   - Add `chat_allow_document_access` to mock DynamoDB responses
   - Test both `true` and `false` values
   - Verify config parsing works correctly

**Verification Checklist:**
- [ ] `ChatConfig` interface includes `allowDocumentAccess: boolean`
- [ ] `getChatConfig()` parses `chat_allow_document_access` from DynamoDB
- [ ] Default value is `false` when key is missing
- [ ] TypeScript compilation passes (no type errors)
- [ ] Existing tests still pass

**Testing Instructions:**

Run TypeScript type checking:
```bash
cd amplify && npx tsc --noEmit
```

Run unit tests:
```bash
cd amplify && npm run test:functions
```

**Commit Message Template:**
```
feat(backend): extend ChatConfig with allowDocumentAccess field

- Add allowDocumentAccess to ChatConfig TypeScript interface
- Parse chat_allow_document_access from DynamoDB in getChatConfig()
- Default to false when key is missing (secure by default)
- Update tests to verify config parsing
```

**Estimated tokens:** ~12,000

---

### Task 3: Implement Document Mapping Function

**Goal:** Create utility function to map Bedrock citation S3 URIs to original documents in InputBucket

**Files to Create:**
- `amplify/data/functions/mapToOriginalDocument.ts` - New utility module

**Files to Modify:**
- `amplify/data/functions/conversation.ts` - Import and use new function

**Prerequisites:**
- Task 2 complete (`ChatConfig` includes `allowDocumentAccess`)
- Understand document flow: Upload → InputBucket → Processing → OutputBucket → Bedrock KB
- Review TrackingTable schema (`document_id` is partition key, contains `input_s3_uri` and `filename`)

**Implementation Steps:**

1. **Create Utility Module**
   - Create new file `mapToOriginalDocument.ts` in `amplify/data/functions/`
   - Export async function with signature:
     ```typescript
     async function mapToOriginalDocument(
       citationS3Uri: string,
       config: ChatConfig
     ): Promise<{ documentUrl: string | null; filename: string }>
     ```

2. **Implement Early Return**
   - Check if `config.allowDocumentAccess === false`
   - If disabled, return `{ documentUrl: null, filename: 'Unknown Document' }` immediately
   - Log at info level: "Document access disabled, skipping URL generation"

3. **Extract document_id from Citation URI**
   - Citation format: `s3://output-bucket/{document_id}/chunks/chunk-NNN.json`
   - Use regex: `/\/([0-9a-f-]{36})\//` to extract UUID
   - Handle case where regex doesn't match (return null values, log warning)
   - Log extracted document_id at debug level

4. **Query TrackingTable**
   - Import `DynamoDBClient` and `GetItemCommand` from `@aws-sdk/client-dynamodb`
   - Read `TRACKING_TABLE_NAME` from `process.env`
   - Execute `GetItem` with `Key: { document_id: { S: documentId } }`
   - Handle case where item not found (document deleted) - return null values
   - Extract `input_s3_uri` and `filename` from result.Item

5. **Parse Input S3 URI**
   - Format: `s3://bucket/key`
   - Use regex: `/s3:\/\/([^/]+)\/(.+)/` to extract bucket and key
   - Handle invalid format (return null values, log warning)

6. **Generate Presigned URL**
   - Import `S3Client`, `GetObjectCommand` from `@aws-sdk/client-s3`
   - Import `getSignedUrl` from `@aws-sdk/s3-request-presigner`
   - Create S3 client with region from `process.env.AWS_REGION`
   - Generate presigned URL with 3600 second (1 hour) expiry
   - Return `{ documentUrl, filename }`

7. **Add Error Handling**
   - Wrap all AWS SDK calls in try/catch
   - On error: log error details, return `{ documentUrl: null, filename: 'Unknown Document' }`
   - Never throw errors (graceful degradation)

**Verification Checklist:**
- [ ] Function returns null when `allowDocumentAccess` is false
- [ ] UUID extraction works for valid citation URIs
- [ ] TrackingTable query executes with correct key
- [ ] S3 URI parsing handles both valid and invalid formats
- [ ] Presigned URLs are generated with 1-hour expiry
- [ ] All error cases return safe fallback values
- [ ] Function is exported and importable

**Testing Instructions:**

Create test file `mapToOriginalDocument.test.ts`:

```typescript
describe('mapToOriginalDocument', () => {
  it('returns null when access is disabled', async () => {
    const config = { allowDocumentAccess: false };
    const result = await mapToOriginalDocument('s3://...', config);
    expect(result.documentUrl).toBeNull();
  });

  it('extracts document_id from citation URI', async () => {
    // Mock DynamoDB to return test data
    // Verify GetItem called with correct document_id
  });

  it('generates presigned URL when access enabled', async () => {
    // Mock DynamoDB and S3
    // Verify presigned URL is returned
    // Verify URL format is correct
  });

  it('handles missing documents gracefully', async () => {
    // Mock DynamoDB to return no item
    // Verify null is returned, no error thrown
  });
});
```

Run tests:
```bash
cd amplify && npm test -- mapToOriginalDocument.test.ts
```

**Commit Message Template:**
```
feat(backend): implement document mapping from citations to original files

- Extract document_id from Bedrock citation S3 URIs
- Query TrackingTable for input_s3_uri and filename
- Generate presigned URLs for original documents in InputBucket
- Gracefully handle missing documents and errors
- Return null when allowDocumentAccess is disabled
```

**Estimated tokens:** ~20,000

---

### Task 4: Update extractSources to Include Document URLs

**Goal:** Modify the `extractSources` function to call document mapping and include URLs in response

**Files to Modify:**
- `amplify/data/functions/conversation.ts` (lines ~339-370) - Update `extractSources` function

**Prerequisites:**
- Task 3 complete (`mapToOriginalDocument` function exists)
- Read existing `extractSources` implementation
- Understand that this function is called synchronously in `queryKnowledgeBase`

**Implementation Steps:**

1. **Make Function Async**
   - Change function signature from `function extractSources()` to `async function extractSources()`
   - Add `config: ChatConfig` parameter (needed for `mapToOriginalDocument`)
   - Update return type to `Promise<any[]>`

2. **Import Document Mapping**
   - Add import: `import { mapToOriginalDocument } from './mapToOriginalDocument';`

3. **Update Source Loop**
   - Inside the loop over `citation.retrievedReferences`
   - After extracting `s3Uri`, `title`, `location`, `snippet`
   - Call `const { documentUrl, filename } = await mapToOriginalDocument(s3Uri, config);`
   - Use `filename` from mapping result instead of parsing from S3 URI
   - Add `documentUrl` and `documentAccessAllowed: config.allowDocumentAccess` to source object

4. **Handle Async Properly**
   - Since function is now async and called in a loop, consider using `Promise.all`
   - Map over citations to create array of promises
   - Await `Promise.all()` to execute mappings in parallel
   - This improves performance when multiple sources exist

5. **Update Caller**
   - Find where `extractSources` is called (in `queryKnowledgeBase`)
   - Add `await` since function is now async
   - Pass `config` parameter

**Verification Checklist:**
- [ ] `extractSources` is now async function
- [ ] Function accepts `config: ChatConfig` parameter
- [ ] Calls `mapToOriginalDocument` for each citation
- [ ] Source objects include `documentUrl` and `documentAccessAllowed` fields
- [ ] Uses `filename` from TrackingTable (not parsed from S3 URI)
- [ ] Function is awaited at call site
- [ ] Parallel execution used for multiple sources

**Testing Instructions:**

Update existing tests in `conversation.test.ts`:

```typescript
describe('extractSources', () => {
  it('includes documentUrl when access allowed', async () => {
    const config = { allowDocumentAccess: true };
    const citations = [/* mock citation */];
    const sources = await extractSources(citations, config);

    expect(sources[0].documentUrl).toBeTruthy();
    expect(sources[0].documentAccessAllowed).toBe(true);
  });

  it('sets documentUrl to null when access disabled', async () => {
    const config = { allowDocumentAccess: false };
    const citations = [/* mock citation */];
    const sources = await extractSources(citations, config);

    expect(sources[0].documentUrl).toBeNull();
    expect(sources[0].documentAccessAllowed).toBe(false);
  });
});
```

**Commit Message Template:**
```
feat(backend): add document URLs to source citations

- Make extractSources async to support presigned URL generation
- Call mapToOriginalDocument for each citation
- Include documentUrl and documentAccessAllowed in source objects
- Use actual filename from TrackingTable (not parsed from URI)
- Execute mappings in parallel for performance
```

**Estimated tokens:** ~18,000

---

### Task 5: Update IAM Permissions

**Goal:** Grant conversation Lambda permissions to read TrackingTable and generate presigned URLs for InputBucket

**Files to Modify:**
- `amplify/lib/backend-stack.ts` - Update conversation Lambda IAM role

**Prerequisites:**
- Understand current IAM role structure for conversation Lambda
- Know ARNs of TrackingTable and InputBucket (passed as parameters to Amplify stack)

**Implementation Steps:**

1. **Locate Conversation Lambda Role**
   - Find where conversation Lambda's execution role is defined
   - Should be using CDK's `PolicyStatement` class

2. **Add DynamoDB Permission**
   - Create new `PolicyStatement` for TrackingTable
   - Actions: `['dynamodb:GetItem']` (read-only)
   - Resource: ARN of TrackingTable (from SAM stack parameter)
   - Add policy to conversation Lambda role

3. **Add S3 Permission**
   - Create new `PolicyStatement` for InputBucket
   - Actions: `['s3:GetObject']` (read-only, needed for presigned URLs)
   - Resource: `${InputBucketArn}/*` (all objects in bucket)
   - Add policy to conversation Lambda role

4. **Add Environment Variable**
   - Locate environment variables section for conversation Lambda
   - Add `TRACKING_TABLE_NAME` with value from stack parameter
   - This allows runtime lookup without hardcoding

**Verification Checklist:**
- [ ] Conversation Lambda can read from TrackingTable (GetItem)
- [ ] Conversation Lambda can generate presigned URLs for InputBucket (GetObject)
- [ ] Environment variable `TRACKING_TABLE_NAME` is set
- [ ] Permissions are read-only (no Put, Delete, etc.)
- [ ] Resource ARNs are correctly referenced from parameters

**Testing Instructions:**

After deploying the updated stack:

1. **Test DynamoDB access:**
   ```bash
   # Invoke conversation Lambda with test event
   # Check CloudWatch logs for successful TrackingTable query
   ```

2. **Test S3 presigned URL:**
   ```bash
   # Invoke Lambda, verify presigned URL is generated
   # Test URL in browser (should download file)
   ```

3. **Verify permissions are minimal:**
   ```bash
   # Check IAM role in AWS console
   # Verify only GetItem (DynamoDB) and GetObject (S3) granted
   ```

**Commit Message Template:**
```
feat(backend): grant conversation Lambda permissions for document access

- Add DynamoDB GetItem permission for TrackingTable
- Add S3 GetObject permission for InputBucket (presigned URLs)
- Set TRACKING_TABLE_NAME environment variable
- Maintain least-privilege principle (read-only access)
```

**Estimated tokens:** ~12,000

---

### Task 6: Integration Testing

**Goal:** Write integration tests to verify end-to-end document URL generation flow

**Files to Create:**
- `amplify/data/functions/conversation.integration.test.ts` - Integration test suite

**Prerequisites:**
- All previous tasks complete
- Understanding of integration test patterns (mock AWS SDK, test real code paths)

**Implementation Steps:**

1. **Set Up Test Infrastructure**
   - Create integration test file
   - Mock AWS SDK clients (DynamoDB, S3, Bedrock)
   - Create realistic test fixtures (citations, tracking records)

2. **Test Document URL Generation Flow**
   - Test: Query with `allowDocumentAccess: true` returns document URLs
   - Test: Query with `allowDocumentAccess: false` returns null URLs
   - Test: Missing document in TrackingTable handled gracefully
   - Test: Invalid citation URI format handled gracefully

3. **Test Configuration Reading**
   - Test: `getChatConfig()` correctly reads `chat_allow_document_access`
   - Test: Default to `false` when key missing
   - Test: Cache works (second call doesn't hit DynamoDB)

4. **Test Presigned URL Format**
   - Test: Generated URL has correct format
   - Test: URL includes required AWS signature parameters
   - Test: URL does NOT expose credentials in logs

5. **Test Error Scenarios**
   - Test: DynamoDB error doesn't crash handler
   - Test: S3 error doesn't crash handler
   - Test: Malformed S3 URI doesn't crash handler
   - All errors should log and return safe fallback

**Verification Checklist:**
- [ ] All tests pass
- [ ] Coverage > 80% for new code
- [ ] Tests verify actual AWS SDK interactions (not just mocks)
- [ ] Error paths are tested
- [ ] Tests can run in CI/CD (no real AWS calls)

**Testing Instructions:**

Run integration tests:
```bash
cd amplify && npm test -- conversation.integration.test.ts
```

Generate coverage report:
```bash
cd amplify && npm run test:coverage
```

Verify coverage meets threshold:
- `mapToOriginalDocument.ts`: > 90%
- `extractSources`: > 85%
- `getChatConfig`: > 80%

**Commit Message Template:**
```
test(backend): add integration tests for document URL generation

- Test document mapping from citations to original files
- Verify presigned URL generation when access enabled
- Test graceful degradation when access disabled
- Test error handling for missing documents and malformed URIs
- Achieve 85%+ coverage on new backend code
```

**Estimated tokens:** ~15,000

---

## Phase Verification

**Before proceeding to Phase 2, verify:**

### Functional Requirements
- [ ] `chat_allow_document_access` configuration exists in DynamoDB
- [ ] Configuration can be toggled between `true` and `false`
- [ ] When `true`, conversation responses include `documentUrl` for each source
- [ ] When `false`, conversation responses include `documentUrl: null`
- [ ] Presigned URLs are generated with 1-hour expiry
- [ ] Presigned URLs can download original files from InputBucket

### Code Quality
- [ ] All new TypeScript code compiles without errors
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Code coverage > 80% for new code
- [ ] No TypeScript `any` types (use proper interfaces)
- [ ] All functions have JSDoc comments

### Security
- [ ] Presigned URLs expire after 1 hour
- [ ] Only `s3:GetObject` permission granted (read-only)
- [ ] Only `dynamodb:GetItem` permission granted (read-only)
- [ ] AWS credentials not logged
- [ ] Configuration defaults to `false` (secure by default)

### Performance
- [ ] Document mapping adds < 100ms latency per query
- [ ] Parallel execution used for multiple sources
- [ ] DynamoDB config cache working (60s TTL)
- [ ] No N+1 query problems

### Documentation
- [ ] Code comments explain complex logic
- [ ] README updated with new configuration option
- [ ] Commit messages follow conventional commits format
- [ ] Integration tests document expected behavior

---

## Integration Points for Phase 2

**Phase 2 (Frontend) will consume:**

1. **GraphQL Response Schema:**
   ```typescript
   {
     content: string;
     sources: Array<{
       title: string;
       location: string;
       snippet: string;
       documentUrl: string | null;      // NEW
       documentAccessAllowed: boolean;  // NEW
     }>;
   }
   ```

2. **Configuration State:**
   - Admin can toggle `chat_allow_document_access` in web UI
   - Changes propagate within 60 seconds (DynamoDB cache TTL)

3. **Error Handling:**
   - Missing documents → `documentUrl: null` (frontend shows disabled state)
   - Access disabled → `documentUrl: null`, `documentAccessAllowed: false`
   - No special error states needed (graceful degradation)

---

## Known Limitations & Technical Debt

**Limitations:**
- Document mapping requires TrackingTable lookup (added latency)
- Presigned URLs expire after 1 hour (user must re-query if URL expires)
- No page-level deep linking (future enhancement)
- No document preview (future enhancement)

**Technical Debt:**
- Should extract presigned URL generation to reusable utility (if used elsewhere)
- Consider adding CloudWatch metrics for presigned URL generation rate
- Could optimize with DynamoDB batch gets if multiple documents from same upload

**Future Enhancements:**
- Page number extraction from Bedrock metadata (when available)
- Deep linking to specific pages (#page=N fragment)
- Document preview modal in frontend
- Analytics on which documents users access

---

**Estimated tokens for Phase 1:** ~75,000

**Next:** [Phase 2: Frontend Implementation](./Phase-2.md)
