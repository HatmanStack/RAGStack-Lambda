# Phase 3: Testing & Integration

## Phase Goal

Comprehensive testing of the collapsible sources feature across all layers (unit, integration, E2E), performance validation, and production deployment with monitoring. This phase ensures the feature works reliably in production, handles edge cases gracefully, and maintains the quality standards of the codebase.

**Success Criteria:**
- ✅ Unit test coverage > 80% for all new code
- ✅ Integration tests verify complete user flows
- ✅ E2E tests pass in staging environment
- ✅ Performance metrics meet requirements (< 100ms latency)
- ✅ Feature deployed to production without issues
- ✅ Documentation updated with new feature

**Estimated tokens:** ~45,000

---

## Prerequisites

**Completed:**
- Phase 0 (Foundation) - Architecture understood
- Phase 1 (Backend) - Backend deployed and functional
- Phase 2 (Frontend) - UI components complete

**Testing Environment:**
- Staging environment with backend deployed
- Test documents uploaded to staging InputBucket
- GraphQL endpoint accessible for integration tests
- Browser automation tools installed (Playwright)

**Verification:**
- Backend returns sources with `documentUrl` field
- Admin UI shows configuration toggle
- Frontend renders collapsible sources

---

## Tasks

### Task 1: Complete Unit Test Coverage

**Goal:** Achieve > 80% unit test coverage for all new frontend and backend code

**Files to Create/Verify:**
- `amplify/data/functions/mapToOriginalDocument.test.ts` - Backend unit tests
- `amplify/data/functions/conversation.test.ts` - Update existing tests
- `src/amplify-chat/src/components/SourcesToggle.test.tsx` - Frontend tests
- `src/amplify-chat/src/components/SourcesDisplay.test.tsx` - Update existing tests

**Prerequisites:**
- All code from Phase 1 and Phase 2 complete
- Understanding of Jest/Vitest testing patterns
- Mocking patterns for AWS SDK established

**Implementation Steps:**

1. **Backend Unit Tests - Document Mapping**
   - Test `mapToOriginalDocument` function with various inputs
   - Test cases:
     - ✓ Returns null when `allowDocumentAccess` is false
     - ✓ Extracts document_id from valid citation URI
     - ✓ Handles invalid citation URI format gracefully
     - ✓ Queries TrackingTable with correct key
     - ✓ Handles missing document in TrackingTable
     - ✓ Generates presigned URL with correct parameters
     - ✓ Handles S3 errors gracefully
     - ✓ Handles DynamoDB errors gracefully

2. **Backend Unit Tests - Configuration**
   - Test `getChatConfig` function
   - Test cases:
     - ✓ Parses `chat_allow_document_access` from DynamoDB
     - ✓ Defaults to `false` when key missing
     - ✓ Caches configuration for 60 seconds
     - ✓ Handles DynamoDB errors

3. **Backend Unit Tests - extractSources**
   - Test updated `extractSources` function
   - Test cases:
     - ✓ Calls `mapToOriginalDocument` for each citation
     - ✓ Includes `documentUrl` in source objects
     - ✓ Includes `documentAccessAllowed` flag
     - ✓ Uses filename from TrackingTable (not S3 URI)
     - ✓ Handles empty citations array
     - ✓ Executes mappings in parallel (Promise.all)

4. **Frontend Unit Tests - SourcesToggle**
   - Test component behavior thoroughly
   - Test cases:
     - ✓ Renders collapsed by default
     - ✓ Expands when button clicked
     - ✓ Collapses when button clicked again
     - ✓ Persists state to sessionStorage
     - ✓ Restores state from sessionStorage on mount
     - ✓ Handles sessionStorage errors (quota exceeded)
     - ✓ Returns null when sources array is empty
     - ✓ Calls onToggle callback when provided
     - ✓ Button has correct ARIA attributes

5. **Frontend Unit Tests - SourcesDisplay**
   - Test updated source item rendering
   - Test cases:
     - ✓ Renders document link when `documentUrl` present
     - ✓ Link has correct href attribute
     - ✓ Link opens in new tab (target="_blank")
     - ✓ Link has security attributes (rel="noopener noreferrer")
     - ✓ Shows disabled state when `documentAccessAllowed` is false
     - ✓ Handles missing `documentUrl` gracefully
     - ✓ Handles missing `documentAccessAllowed` gracefully

6. **Run Coverage Reports**
   - Generate coverage for backend: `cd amplify && npm run test:coverage`
   - Generate coverage for frontend: `cd src/amplify-chat && npm run test:coverage`
   - Verify coverage > 80% for all new files
   - Identify gaps and add tests for uncovered branches

**Verification Checklist:**
- [ ] All unit tests pass
- [ ] Coverage > 80% for `mapToOriginalDocument.ts`
- [ ] Coverage > 80% for updated `conversation.ts` functions
- [ ] Coverage > 80% for `SourcesToggle.tsx`
- [ ] Coverage > 80% for updated `SourcesDisplay.tsx`
- [ ] All error paths are tested
- [ ] All edge cases are tested (nulls, empty arrays, malformed data)

**Testing Instructions:**

Run all unit tests:
```bash
# Backend tests
cd amplify && npm run test

# Frontend tests
cd src/amplify-chat && npm run test

# Coverage reports
cd amplify && npm run test:coverage
cd src/amplify-chat && npm run test:coverage
```

Review coverage reports:
- Open `amplify/coverage/index.html` in browser
- Open `src/amplify-chat/coverage/index.html` in browser
- Identify files with < 80% coverage
- Add tests for uncovered lines/branches

**Commit Message Template:**
```
test(all): achieve 80%+ coverage for collapsible sources feature

Backend tests:
- Test document mapping from citations to original files
- Test configuration parsing and caching
- Test presigned URL generation
- Test error handling and edge cases

Frontend tests:
- Test SourcesToggle expand/collapse behavior
- Test sessionStorage persistence
- Test document link rendering
- Test accessibility attributes
```

**Estimated tokens:** ~12,000

---

### Task 2: Integration Testing

**Goal:** Test complete user flows end-to-end with real AWS SDK interactions

**Files to Create:**
- `amplify/data/functions/conversation.integration.test.ts` - Backend integration tests
- `src/ui/src/integration/collapsible-sources.test.tsx` - Frontend integration tests

**Prerequisites:**
- Task 1 complete (unit tests passing)
- Staging environment deployed with test data
- Test documents in InputBucket
- GraphQL endpoint accessible

**Implementation Steps:**

1. **Backend Integration Test Setup**
   - Create integration test file (mark with `@integration` tag)
   - Set up real AWS SDK clients (DynamoDB, S3, Bedrock)
   - Use test environment credentials
   - Create test fixtures (realistic citations, tracking records)

2. **Test Complete Query Flow**
   - Test: User sends chat query → receives sources with document URLs
   - Verify:
     - ✓ Bedrock query executes
     - ✓ Citations are extracted
     - ✓ Document mapping queries TrackingTable
     - ✓ Presigned URLs are generated
     - ✓ Response includes all expected fields
   - Use real test document uploaded to staging

3. **Test Configuration Toggle**
   - Test: Admin toggles `chat_allow_document_access` via GraphQL
   - Verify:
     - ✓ Mutation succeeds
     - ✓ Configuration persists in DynamoDB
     - ✓ Subsequent queries respect new setting
     - ✓ Cache invalidates after 60 seconds

4. **Test Error Scenarios**
   - Test: Document missing from TrackingTable
     - Verify: Response includes `documentUrl: null`, no crash
   - Test: Invalid S3 URI in citation
     - Verify: Graceful fallback, no crash
   - Test: S3 presigned URL generation fails
     - Verify: Source still appears, just without link

5. **Frontend Integration Tests**
   - Test: Render chat with sources from real GraphQL query
   - Verify:
     - ✓ Sources appear in UI
     - ✓ Expand/collapse works
     - ✓ Document links have correct URLs
     - ✓ Clicking link triggers download (verify event, don't actually download)

6. **Test Cross-Component Integration**
   - Test: Admin UI → Configuration → Chat
   - Steps:
     1. Disable document access in admin UI
     2. Send chat query
     3. Verify document links hidden
     4. Enable document access
     5. Send chat query
     6. Verify document links appear

**Verification Checklist:**
- [ ] Integration tests pass with real AWS services
- [ ] Complete user flows work end-to-end
- [ ] Configuration changes propagate correctly
- [ ] Error scenarios handled gracefully
- [ ] Tests use realistic test data
- [ ] Tests don't depend on specific timing (avoid flakiness)

**Testing Instructions:**

Run integration tests:
```bash
# Backend integration tests (require AWS credentials)
cd amplify && npm run test:integration

# Frontend integration tests
cd src/ui && npm run test:integration
```

Set up test environment:
```bash
# Upload test document to staging
aws s3 cp test-document.pdf s3://staging-input-bucket/test-id/

# Seed TrackingTable with test record
aws dynamodb put-item --table-name staging-tracking-table --item '{...}'

# Query staging chat to generate test data
```

**Commit Message Template:**
```
test(integration): add end-to-end tests for document access flow

- Test complete query flow: question → sources → document URLs
- Test configuration toggle propagation
- Test error scenarios (missing docs, invalid URIs)
- Test cross-component integration (admin UI → chat)
- Use real AWS SDK clients with test environment
```

**Estimated tokens:** ~12,000

---

### Task 3: End-to-End Testing with Playwright

**Goal:** Automate critical user journeys in browser with Playwright

**Files to Create:**
- `tests/e2e/collapsible-sources.spec.ts` - Playwright test suite
- `playwright.config.ts` - Update config if needed

**Prerequisites:**
- Playwright installed: `npm install -D @playwright/test`
- Staging environment accessible via HTTPS
- Test user credentials available
- Test documents in staging environment

**Implementation Steps:**

1. **Set Up Playwright Test Suite**
   - Create new spec file for collapsible sources tests
   - Configure base URL to staging environment
   - Set up test fixtures (page, authenticated context)

2. **Test: User Views Collapsible Sources**
   - Navigate to chat interface
   - Send test question that returns sources
   - Verify sources are collapsed by default
   - Click expand button
   - Verify sources expand with animation
   - Verify source titles, snippets appear
   - Click collapse button
   - Verify sources collapse

3. **Test: User Downloads Document**
   - Expand sources (from previous test state)
   - Verify "View Document" link appears
   - Set up download listener
   - Click document link
   - Verify download initiates (new tab/download)
   - Verify downloaded file matches expected document

4. **Test: Admin Toggles Document Access**
   - Log in as admin user
   - Navigate to Configuration page
   - Locate "Allow Document Access" toggle
   - Verify current state matches backend
   - Toggle OFF
   - Verify success notification
   - Open chat in new tab
   - Send query
   - Verify document links NOT present
   - Return to Configuration
   - Toggle ON
   - Open chat in new tab
   - Send query
   - Verify document links ARE present

5. **Test: Keyboard Navigation**
   - Navigate to chat with keyboard only
   - Tab to sources toggle button
   - Verify focus indicator visible
   - Press Enter to expand
   - Tab through sources
   - Tab to document link
   - Press Enter on document link
   - Verify download initiates

6. **Test: Screen Reader Compatibility**
   - Enable screen reader simulation (Playwright doesn't fully support this, use manual testing notes)
   - Verify ARIA attributes present in DOM
   - Verify state changes are announced (check for aria-live regions)

**Verification Checklist:**
- [ ] All E2E tests pass in staging environment
- [ ] Tests are deterministic (no flakiness)
- [ ] Tests wait for elements correctly (no arbitrary sleeps)
- [ ] Tests clean up after themselves (close tabs, reset state)
- [ ] Screenshots captured on failure
- [ ] Tests run in CI/CD pipeline

**Testing Instructions:**

Run E2E tests locally:
```bash
# Install browsers (first time only)
npx playwright install

# Run tests
npx playwright test tests/e2e/collapsible-sources.spec.ts

# Run in headed mode (see browser)
npx playwright test --headed

# Run with debugging
npx playwright test --debug
```

View test report:
```bash
npx playwright show-report
```

**Commit Message Template:**
```
test(e2e): add Playwright tests for collapsible sources

- Test sources collapse/expand in browser
- Test document download flow
- Test admin configuration toggle propagation
- Test keyboard navigation accessibility
- Run against staging environment
- Capture screenshots on failure
```

**Estimated tokens:** ~15,000

---

### Task 4: Performance Testing and Optimization

**Goal:** Verify feature meets performance requirements and identify bottlenecks

**Files to Create:**
- `tests/performance/document-mapping.bench.ts` - Performance benchmarks

**Prerequisites:**
- All functional tests passing
- Access to staging environment with realistic data
- Performance testing tools installed

**Implementation Steps:**

1. **Benchmark Document Mapping**
   - Measure time to map 1 citation to original document
   - Measure time to map 5 citations (parallel)
   - Measure time to map 10 citations (parallel)
   - Target: < 100ms per query (including all mappings)

2. **Benchmark Presigned URL Generation**
   - Measure time to generate single presigned URL
   - Should be < 50ms (S3 presigned URLs are fast)

3. **Benchmark TrackingTable Queries**
   - Measure time to query TrackingTable by document_id
   - Should be < 20ms (DynamoDB single-item query)

4. **Test Frontend Rendering Performance**
   - Measure time to render 10 sources (collapsed)
   - Measure time to expand 10 sources
   - Measure time for collapse animation
   - Target: < 16ms per frame (60 FPS)

5. **Test Memory Usage**
   - Monitor memory during expand/collapse cycles
   - Verify no memory leaks (use Chrome DevTools)
   - Test with 50 expand/collapse cycles

6. **Optimize if Needed**
   - If benchmarks fail:
     - Consider batch DynamoDB queries (GetBatchItem)
     - Consider caching presigned URLs (short TTL)
     - Consider lazy loading sources (render on expand)
   - Re-run benchmarks after optimization

**Verification Checklist:**
- [ ] Document mapping adds < 100ms latency per query
- [ ] Presigned URL generation < 50ms
- [ ] TrackingTable query < 20ms
- [ ] Frontend rendering maintains 60 FPS
- [ ] No memory leaks detected
- [ ] Performance acceptable with 10+ sources

**Testing Instructions:**

Run performance benchmarks:
```bash
# Backend benchmarks
cd amplify && npm run bench

# Frontend performance profiling
# Use Chrome DevTools:
# 1. Open chat in Chrome
# 2. Open DevTools → Performance tab
# 3. Record while expanding/collapsing sources
# 4. Analyze flame graph for bottlenecks
```

Example benchmark output:
```
Document Mapping Performance:
  1 citation:  45ms ✓ (target: <100ms)
  5 citations: 62ms ✓ (parallel execution)
  10 citations: 89ms ✓ (parallel execution)

Presigned URL Generation:
  Single URL: 32ms ✓ (target: <50ms)

TrackingTable Query:
  Single item: 12ms ✓ (target: <20ms)
```

**Commit Message Template:**
```
test(perf): add performance benchmarks for document mapping

- Benchmark document mapping latency (< 100ms target)
- Benchmark presigned URL generation (< 50ms target)
- Benchmark TrackingTable queries (< 20ms target)
- Verify frontend rendering performance (60 FPS)
- Test memory usage and detect leaks
- All benchmarks pass performance targets
```

**Estimated tokens:** ~8,000

---

### Task 5: Update Documentation

**Goal:** Document the new feature in all relevant documentation files

**Files to Modify:**
- `CLAUDE.md` - Add configuration option
- `docs/CONFIGURATION.md` - Document `chat_allow_document_access`
- `docs/AMPLIFY_CHAT.md` - Document web component behavior
- `README.md` - Mention feature in overview

**Prerequisites:**
- Feature complete and tested
- Understanding of feature capabilities and limitations

**Implementation Steps:**

1. **Update CLAUDE.md**
   - Add `chat_allow_document_access` to configuration options list
   - Document default value (false)
   - Explain purpose and behavior

2. **Update CONFIGURATION.md**
   - Add new section for document access configuration
   - Document:
     - Configuration key: `chat_allow_document_access`
     - Type: Boolean
     - Default: `false`
     - Purpose: Enable/disable source document downloads
     - Security implications: Presigned URLs expire after 1 hour
   - Include example of toggling via admin UI

3. **Update AMPLIFY_CHAT.md**
   - Document collapsible sources behavior
   - Document document link functionality
   - Add example of what users see
   - Document sessionStorage persistence
   - Note accessibility features (keyboard nav, screen reader support)

4. **Update README.md**
   - Add bullet point in features list:
     - "Collapsible source citations with optional document downloads"
   - No need for extensive detail (link to docs for more)

5. **Add Troubleshooting Section**
   - Add to `docs/TROUBLESHOOTING.md`:
     - Issue: "Document links not appearing"
       - Cause: `chat_allow_document_access` disabled
       - Solution: Enable in admin UI → Configuration
     - Issue: "Presigned URL expired"
       - Cause: URLs expire after 1 hour
       - Solution: Re-send query to generate new URL
     - Issue: "Document not found"
       - Cause: Original file deleted from InputBucket
       - Solution: Re-upload document

**Verification Checklist:**
- [ ] All documentation files updated
- [ ] Configuration option documented with examples
- [ ] Security implications clearly stated
- [ ] Troubleshooting scenarios covered
- [ ] Documentation is clear and concise

**Testing Instructions:**

Review documentation for:
- Accuracy (matches implemented behavior)
- Clarity (easy to understand)
- Completeness (covers all use cases)
- Consistency (terminology matches across docs)

**Commit Message Template:**
```
docs: document collapsible sources and document access feature

- Add chat_allow_document_access to CLAUDE.md and CONFIGURATION.md
- Document collapsible sources behavior in AMPLIFY_CHAT.md
- Update README with new feature
- Add troubleshooting entries for common issues
```

**Estimated tokens:** ~6,000

---

### Task 6: Deployment to Production

**Goal:** Deploy feature to production environment with monitoring and rollback plan

**Files to Verify:**
- All code changes committed
- All tests passing
- Documentation complete

**Prerequisites:**
- Feature approved for production deployment
- Staging environment tests all passing
- Rollback plan documented

**Implementation Steps:**

1. **Pre-Deployment Checklist**
   - [ ] All unit tests passing
   - [ ] All integration tests passing
   - [ ] E2E tests passing in staging
   - [ ] Performance benchmarks meet targets
   - [ ] Documentation updated
   - [ ] Security review complete
   - [ ] Changelog updated

2. **Deploy Backend (SAM Stack)**
   - Run deployment script:
     ```bash
     python publish.py \
       --project-name production \
       --admin-email admin@example.com \
       --region us-east-1 \
       --deploy-chat
     ```
   - Monitor CloudFormation stack update
   - Verify no rollbacks occur

3. **Verify Backend Deployment**
   - Check Lambda logs for errors:
     ```bash
     aws logs tail /aws/lambda/production-conversation --follow
     ```
   - Test GraphQL query manually:
     ```graphql
     query {
       conversation(message: "test", conversationId: "test") {
         content
         sources {
           title
           documentUrl
           documentAccessAllowed
         }
       }
     }
     ```
   - Verify `documentUrl` is `null` by default (secure default)

4. **Enable Feature for Testing**
   - Log in to admin UI
   - Navigate to Configuration
   - Enable `chat_allow_document_access`
   - Send test chat query
   - Verify document links appear
   - Click document link
   - Verify file downloads successfully

5. **Monitor Production**
   - Watch CloudWatch metrics:
     - Lambda errors (should be 0)
     - Lambda duration (should be < baseline + 100ms)
     - S3 GetObject requests (should increase when users download docs)
   - Watch CloudWatch logs for errors
   - Set up alerts for elevated error rates

6. **Gradual Rollout (Optional)**
   - If traffic is high, consider gradual rollout:
     - Day 1: Enable for admin users only (test in production)
     - Day 2: Enable for 10% of users
     - Day 3: Enable for 50% of users
     - Day 4: Enable for 100% of users
   - Monitor metrics at each stage

7. **Rollback Plan**
   - If critical issue discovered:
     1. Disable `chat_allow_document_access` in admin UI (immediate mitigation)
     2. Revert CloudFormation stack to previous version
     3. Investigate issue in staging environment
     4. Fix and re-deploy
   - Document rollback procedure:
     ```bash
     # Quick rollback (disable feature)
     aws dynamodb update-item --table-name Config \
       --key '{"Configuration": {"S": "Default"}}' \
       --update-expression "SET chat_allow_document_access = :val" \
       --expression-attribute-values '{":val": {"BOOL": false}}'

     # Full rollback (revert stack)
     aws cloudformation update-stack --stack-name production \
       --use-previous-template \
       --parameters [previous parameters]
     ```

**Verification Checklist:**
- [ ] Backend deployed successfully
- [ ] Frontend deployed successfully
- [ ] Configuration toggle works in admin UI
- [ ] Document links appear when enabled
- [ ] Document downloads work
- [ ] No errors in CloudWatch logs
- [ ] Performance metrics within acceptable range
- [ ] Rollback plan tested and documented

**Testing Instructions:**

Post-deployment testing:
1. Verify feature OFF by default:
   - Send chat query
   - Verify NO document links
2. Enable feature:
   - Log in as admin
   - Toggle ON
   - Send chat query
   - Verify document links appear
3. Download test:
   - Click document link
   - Verify file downloads
4. Disable feature:
   - Toggle OFF
   - Send chat query
   - Verify NO document links

**Commit Message Template:**
```
chore(deploy): deploy collapsible sources to production

- Deploy backend with document mapping and presigned URLs
- Deploy frontend with collapsible UI and document links
- Deploy admin UI with configuration toggle
- Verify all tests passing
- Monitor CloudWatch metrics for errors
- Document rollback procedure
```

**Estimated tokens:** ~10,000

---

## Phase Verification

**Feature is complete when:**

### Testing
- [x] Unit test coverage > 80% for all new code
- [x] Integration tests verify end-to-end flows
- [x] E2E tests pass in staging and production
- [x] Performance benchmarks meet targets
- [x] No memory leaks detected
- [x] All edge cases tested and handled

### Documentation
- [x] CLAUDE.md updated
- [x] CONFIGURATION.md updated
- [x] AMPLIFY_CHAT.md updated
- [x] README.md updated
- [x] TROUBLESHOOTING.md updated
- [x] Changelog updated

### Deployment
- [x] Deployed to production
- [x] Feature enabled and working
- [x] Monitoring in place
- [x] Rollback plan tested
- [x] No production errors
- [x] Performance acceptable

### User Acceptance
- [x] Admin can toggle document access
- [x] Users see collapsible sources
- [x] Users can download documents when enabled
- [x] Feature works across browsers
- [x] Accessibility verified

---

## Monitoring and Maintenance

**Metrics to Monitor:**

1. **CloudWatch Metrics:**
   - Lambda duration (should not significantly increase)
   - Lambda errors (should remain at 0)
   - Lambda invocations (track usage)

2. **S3 Metrics:**
   - GetObject requests on InputBucket (track downloads)
   - Presigned URL generation rate

3. **DynamoDB Metrics:**
   - TrackingTable read capacity (should not spike)
   - GetItem latency (should remain low)

4. **User Metrics (if analytics enabled):**
   - Sources expand rate (% of users who expand sources)
   - Document download rate (% of users who download docs)
   - Time to first download (user engagement)

**Alerts to Set Up:**

```yaml
Alerts:
  - Name: HighLambdaErrors
    Metric: Lambda Errors
    Threshold: > 5 in 5 minutes
    Action: Notify on-call, investigate immediately

  - Name: HighLatency
    Metric: Lambda Duration p99
    Threshold: > 5 seconds
    Action: Notify team, investigate optimization

  - Name: ConfigurationErrors
    Metric: DynamoDB GetItem errors
    Threshold: > 10 in 5 minutes
    Action: Check DynamoDB health, verify permissions
```

**Maintenance Tasks:**

1. **Weekly:**
   - Review CloudWatch logs for warnings
   - Check error rates and latency metrics
   - Verify presigned URLs are being generated

2. **Monthly:**
   - Review user analytics (if enabled)
   - Analyze document download patterns
   - Optimize if needed (caching, batch queries)

3. **Quarterly:**
   - Review security (ensure presigned URLs still secure)
   - Update dependencies (@aws-sdk packages)
   - Re-run performance benchmarks

---

## Review Feedback (Iteration 1)

### Task 1: Unit Test Coverage

> **Consider:** The coverage report at `amplify/coverage/index.html:26` shows overall coverage of 65.34%. The plan at line 8 requires ">80% for all new code". Are you measuring coverage for ALL code or just the new Phase 1-2 code?

> **Think about:** Looking at `amplify/coverage/data/functions/index.html:86-93`, the conversation.ts file shows 43.29% statement coverage. Which parts of this file contain new Phase 1-2 code versus pre-existing code? Should the Lambda handler function (lines 42-115) be covered by tests?

> **Reflect:** The extractSources and mapToOriginalDocument functions have excellent coverage (85-96%). What testing approach did you use there that could be applied to increase coverage of the conversation handler?

### Task 2: Integration Testing

> **Consider:** Looking at `src/amplify-chat/src/components/__tests__/integration/conversation.integration.test.tsx:33`, why is the integration test suite using `describe.skip`? The comment on line 32 mentions "test environment configuration complexity" - what specific configuration is missing?

> **Think about:** The plan at lines 169-245 describes creating integration tests that run against a real backend. You've written the tests (3 scenarios total), but they're not executing. What would it take to configure the test environment so these tests can run?

> **Reflect:** Integration tests are meant to verify the complete user flow with real AWS SDK interactions. If these tests remain skipped, how can you verify that document mapping, TrackingTable queries, and presigned URL generation actually work in a real environment?

### Task 3: E2E Testing

> **Consider:** Running `glob **/*.e2e.{ts,tsx,js,spec.ts}` returns no files. The plan at lines 247-314 describes creating E2E tests with Playwright. Do E2E tests exist anywhere in the codebase?

> **Think about:** The plan specifies testing user flows like "upload document → query → see sources → click document link → download file". Without E2E tests, how are these critical user journeys validated before production deployment?

> **Reflect:** Look at the success criteria on line 10: "E2E tests pass in staging environment". Can this criterion be met if no E2E tests have been created?

### Task 4: Performance Testing

> **Consider:** Running `glob **/*.bench.{ts,js}` and `glob **/performance/**` returns no files. The plan at lines 393-492 describes creating performance benchmarks. Have performance tests been implemented?

> **Think about:** The plan at line 414 specifies a target of "<100ms per query (including all mappings)". Without benchmarks, how can you verify this requirement is met? What happens if document mapping adds 500ms latency in production?

> **Reflect:** The plan at lines 411-414 describes measuring time for 1, 5, and 10 citations in parallel. Could you verify the performance impact by measuring actual execution time in your existing unit tests?

### Task 6: Deployment Readiness

> **Consider:** The pre-deployment checklist at lines 596-604 requires "All unit tests passing", "All integration tests passing", and "E2E tests passing in staging". Looking at your test output showing "Test Files 1 failed | 3 passed" and integration tests skipped, are all prerequisites met?

> **Think about:** The plan at line 11 states "Performance metrics meet requirements (<100ms latency)" as a success criterion. Without performance tests, can you confidently deploy to production claiming this criterion is met?

> **Reflect:** If a production deployment happens now and document downloads are slow or broken, what visibility would you have into the root cause? How would integration and E2E tests have caught these issues earlier?

### Overall Phase 3 Assessment

> **Consider:** The Phase goal at lines 3-5 states this is "comprehensive testing... across all layers (unit, integration, E2E), performance validation, and production deployment". Of the 6 tasks, how many are fully complete versus partially complete?

> **Think about:** The success criteria at lines 7-13 list 6 requirements. Count how many you can confidently check off with evidence from actual test execution (not test file existence). Is this phase truly complete?

> **Reflect:** Look at the excellent work in Phase 2 - all tests passing, great code quality, comprehensive documentation. What prevented the same thoroughness from being applied to integration, E2E, and performance testing in Phase 3?

---

## Post-Launch Improvements

**After feature is stable, consider:**

1. **Analytics Dashboard:**
   - Track which documents are downloaded most
   - Analyze user engagement with sources
   - A/B test collapsed vs expanded default

2. **Performance Optimizations:**
   - Cache presigned URLs (short TTL, 5 minutes)
   - Batch TrackingTable queries if multiple docs
   - Prefetch document metadata on page load

3. **UX Enhancements:**
   - Add document preview modal (iframe or PDF.js)
   - Add page number extraction from Bedrock metadata
   - Add "Copy link" button for sharing presigned URLs

4. **Admin Features:**
   - Configurable presigned URL expiry time
   - Per-user document access permissions
   - Analytics on document access patterns

---

**Estimated tokens for Phase 3:** ~45,000

---

## Implementation Complete

**Total estimated tokens across all phases:** ~205,000

When all tasks in all phases are complete and verified, the collapsible sources with document access feature is production-ready.

**Final Checklist:**
- [ ] Phase 0: Architecture understood
- [ ] Phase 1: Backend implemented and tested
- [ ] Phase 2: Frontend implemented and tested
- [ ] Phase 3: Integration tested and deployed
- [ ] Documentation complete
- [ ] Monitoring in place
- [ ] Team trained on new feature
- [ ] Rollback plan documented

**Congratulations!** The feature is complete and live in production.
