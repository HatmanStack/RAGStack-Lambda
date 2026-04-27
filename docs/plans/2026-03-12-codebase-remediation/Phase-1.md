# Phase 1: Test Coverage Safety Net

## Phase Goal

Write comprehensive unit tests for all 11 untested Lambda handlers and `logging_utils.py`, creating a safety net for the refactoring and infrastructure changes in Phases 2 and 3. Also audit log statements in each handler for consistent `document_id`/`image_id`/`scrape_id` inclusion and fix any gaps found.

**Success criteria:**
- All 11 untested handlers have test files with tests covering happy path, error paths, and edge cases
- `logging_utils.py` has a dedicated test file
- All tests pass with `uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short`
- No real AWS calls in any test (all mocked)

**Estimated tokens:** ~45,000

## Prerequisites

- Phase 0 read and understood (testing patterns, commit conventions, module loading strategy)
- Python 3.13 environment with dependencies: `uv pip install -r requirements.txt`
- Familiarity with pytest, `unittest.mock`, `importlib.util`

## Important Notes

- The existing `tests/unit/conftest.py` clears `sys.modules['index']` at session start. All new test files MUST use `importlib.util.spec_from_file_location()` with unique module names to avoid collisions.
- Each Lambda handler module has module-level boto3 client initialization. These must be mocked before the module is loaded, or the module must be loaded inside a mock context.
- The `tests/conftest.py` `reset_config_singleton` fixture is `autouse=True` and runs for every test automatically.
- Run `uv run ruff check .` and `uv run ruff format .` after each task to ensure lint compliance.

---

## Task 1: Test logging_utils.py

**Goal:** Add unit tests for the `mask_value`, `safe_log_event`, and `log_summary` functions in `lib/ragstack_common/logging_utils.py`.

**Files to Create:**
- `tests/unit/python/test_logging_utils.py`

**Files to Read First:**
- `lib/ragstack_common/logging_utils.py` -- The module under test (3 functions, ~190 lines)

**Prerequisites:**
- None (no Lambda handler, no module loading complexity)

**Implementation Steps:**
- This is a straightforward library module with no boto3 dependencies, so standard imports work fine.
- Test `mask_value`:
  - Sensitive key with long string (should show partial)
  - Sensitive key with short string (should show `***`)
  - Sensitive key with list/dict (should show type indicator)
  - Non-sensitive key (should pass through unchanged)
  - Nested dict (should recurse)
  - Substring matching (e.g., `"user_query"` should match `"query"`)
  - Custom sensitive_keys parameter
- Test `safe_log_event`:
  - Normal dict event
  - Non-dict input (should return `{"_raw": ...}`)
  - Exception during masking (should return safe fallback)
- Test `log_summary`:
  - All parameters provided
  - Minimal parameters (operation only)
  - Long error string (should truncate at 500)
  - Extra kwargs with primitive types
  - Extra kwargs with list/tuple types (should log count)

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_logging_utils.py -v` passes
- [x] All three functions have at least 3 tests each
- [x] No imports of boto3 or AWS SDK in this test file

**Testing Instructions:**
```bash
uv run pytest tests/unit/python/test_logging_utils.py -v
uv run ruff check tests/unit/python/test_logging_utils.py
uv run ruff format tests/unit/python/test_logging_utils.py --check
```

**Commit Message Template:**
```
test(logging_utils): add unit tests for mask_value, safe_log_event, and log_summary
```

---

## Task 2: Test admin_user_provisioner Lambda

**Goal:** Test the CloudFormation custom resource handler that idempotently creates Cognito users.

**Files to Create:**
- `tests/unit/python/test_admin_user_provisioner.py`

**Files to Read First:**
- `src/lambda/admin_user_provisioner/index.py` (142 lines)
- `tests/unit/python/test_process_media_lambda.py` (reference for module loading pattern)

**Prerequisites:**
- Task 1 complete (to validate the test infrastructure works)

**Implementation Steps:**
- Load module via `importlib.util.spec_from_file_location("admin_user_provisioner_index", ...)`.
- The module has a module-level `cognito = boto3.client("cognito-idp")` -- mock `boto3.client` before loading.
- Key functions to test: `send_response`, `create_user`, `lambda_handler`, `_handle_event`.
- Mock `urllib.request.urlopen` for CloudFormation response sending.
- Create a mock `context` object with `log_stream_name` attribute.

**Test Cases:**
- `send_response`: Verify it sends PUT to ResponseURL with correct body structure
- `create_user`: User already exists (admin_get_user returns user) -- should return `{"created": False, ...}`
- `create_user`: User doesn't exist (UserNotFoundException raised) -- should create and return `{"created": True, ...}`
- `lambda_handler` Create: Happy path with valid UserPoolId and Email
- `lambda_handler` Create: Missing UserPoolId -- should send FAILED response
- `lambda_handler` Update: With valid properties -- should call create_user
- `lambda_handler` Update: Without properties -- should send SUCCESS
- `lambda_handler` Delete: Should send SUCCESS without deleting user
- `lambda_handler` Unknown RequestType: Should send FAILED
- `lambda_handler` Unhandled exception: Should still send FAILED response to CloudFormation
- `_handle_event` ClientError: Should send FAILED with AWS error message

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_admin_user_provisioner.py -v` passes
- [x] At least 8 test cases
- [x] `urllib.request.urlopen` is mocked (no real HTTP calls)
- [x] `boto3.client("cognito-idp")` is mocked (no real AWS calls)

**Commit Message Template:**
```
test(admin_user_provisioner): add unit tests for Cognito user provisioning custom resource
```

---

## Task 3: Test api_key_resolver Lambda

**Goal:** Test the AppSync resolver that manages API keys.

**Files to Create:**
- `tests/unit/python/test_api_key_resolver.py`

**Files to Read First:**
- `src/lambda/api_key_resolver/index.py` (147 lines)

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**
- Load module via `importlib.util.spec_from_file_location("api_key_resolver_index", ...)`.
- Read the handler to understand what environment variables it needs (likely `CONFIGURATION_TABLE_NAME` or similar).
- Mock any module-level boto3 clients before loading.
- Test each resolver field/operation that the handler supports.
- Check what AppSync event structure the handler expects (field name in `event["info"]["fieldName"]` is the typical AppSync pattern).

**Test Cases:**
- Determine test cases by reading the handler. Cover:
  - Each field/operation the resolver handles
  - Missing or invalid input
  - DynamoDB error handling
  - Authentication/authorization checks if present

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_api_key_resolver.py -v` passes
- [x] All resolver operations tested
- [x] No real AWS calls

**Commit Message Template:**
```
test(api_key_resolver): add unit tests for API key management resolver
```

---

## Task 4: Test queue_processor Lambda

**Goal:** Test the SQS message processor that starts Step Functions executions.

**Files to Create:**
- `tests/unit/python/test_queue_processor.py`

**Files to Read First:**
- `src/lambda/queue_processor/index.py` (102 lines)

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**
- Load module via `importlib.util.spec_from_file_location("queue_processor_index", ...)`.
- Environment variables needed: `STATE_MACHINE_ARN`, `CONFIGURATION_TABLE_NAME`.
- Mock `boto3.client("stepfunctions")` and `boto3.resource("dynamodb")`.
- The handler calls `check_reindex_lock()` before processing -- test both locked and unlocked states.

**Test Cases:**
- `check_reindex_lock`: No config table name set -- should return without error
- `check_reindex_lock`: Lock not present -- should return without error
- `check_reindex_lock`: Lock present and `is_locked=True` -- should raise RuntimeError
- `check_reindex_lock`: DynamoDB ClientError -- should log warning and not raise
- `lambda_handler`: Single SQS record -- starts one Step Functions execution
- `lambda_handler`: Multiple SQS records -- starts execution for each
- `lambda_handler`: Execution name sanitization (special characters in document_id)
- `lambda_handler`: Reindex lock active -- should raise RuntimeError (message goes back to SQS)

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_queue_processor.py -v` passes
- [x] At least 6 test cases
- [x] Step Functions `start_execution` call verified with correct arguments
- [x] Reindex lock behavior tested both ways

**Commit Message Template:**
```
test(queue_processor): add unit tests for SQS-to-Step-Functions processor
```

---

## Task 5: Test enqueue_batches Lambda

**Goal:** Test the Lambda that sends batch processing jobs to SQS and initializes DynamoDB tracking.

**Files to Create:**
- `tests/unit/python/test_enqueue_batches.py`

**Files to Read First:**
- `src/lambda/enqueue_batches/index.py` (148 lines)

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**
- Load module via `importlib.util.spec_from_file_location("enqueue_batches_index", ...)`.
- Environment variables: `TRACKING_TABLE`, `BATCH_QUEUE_URL`, `GRAPHQL_ENDPOINT` (optional).
- Mock `boto3.resource("dynamodb")` and `boto3.client("sqs")`.
- The handler sends messages in batches of 10 (SQS limit) -- test boundary conditions.

**Test Cases:**
- Happy path: 3 batches -- all enqueued in single send_message_batch call
- Batch of exactly 10 -- verify single send_message_batch call
- Batch of 11 -- verify two send_message_batch calls (10 + 1)
- Batch of 20 -- verify two send_message_batch calls (10 + 10)
- Missing TRACKING_TABLE -- should raise ValueError
- Missing BATCH_QUEUE_URL -- should raise ValueError
- DynamoDB tracking item initialized correctly (batches_total, batches_remaining, etc.)
- GraphQL endpoint present -- should attempt to publish update
- GraphQL endpoint absent -- should skip publish without error
- GraphQL publish failure -- should log warning, not raise

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_enqueue_batches.py -v` passes
- [x] SQS batching logic tested at boundaries (9, 10, 11, 20 batches)
- [x] DynamoDB update_item called with correct expression

**Commit Message Template:**
```
test(enqueue_batches): add unit tests for SQS batch enqueue and DynamoDB tracking
```

---

## Task 6: Test initial_sync Lambda

**Goal:** Test the CloudFormation custom resource that triggers the initial KB ingestion job.

**Files to Create:**
- `tests/unit/python/test_initial_sync.py`

**Files to Read First:**
- `src/lambda/initial_sync/index.py` (107 lines)

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**
- Load module via `importlib.util.spec_from_file_location("initial_sync_index", ...)`.
- Module-level: `bedrock_agent = boto3.client("bedrock-agent")` -- mock before loading.
- Mock `urllib.request.urlopen` for CloudFormation responses.
- Pattern is similar to `admin_user_provisioner` (CloudFormation custom resource).

**Test Cases:**
- Create: Happy path -- starts ingestion job, sends SUCCESS with job ID
- Create: Missing KnowledgeBaseId -- sends FAILED
- Create: Missing DataSourceId -- sends FAILED
- Create: ClientError from bedrock-agent -- sends SUCCESS anyway (don't fail deployment)
- Update: Sends SUCCESS with no action
- Delete: Sends SUCCESS with no action
- Unknown RequestType: Sends FAILED
- Unexpected exception: Sends FAILED

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_initial_sync.py -v` passes
- [x] At least 7 test cases
- [x] CloudFormation response always sent (even on error)

**Commit Message Template:**
```
test(initial_sync): add unit tests for initial KB sync custom resource
```

---

## Task 7: Test start_codebuild Lambda

**Goal:** Test the Lambda that triggers CodeBuild projects.

**Files to Create:**
- `tests/unit/python/test_start_codebuild.py`

**Files to Read First:**
- `src/lambda/start_codebuild/index.py` (158 lines)

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**
- Load module via `importlib.util.spec_from_file_location("start_codebuild_index", ...)`.
- Read the handler to identify environment variables and boto3 clients used.
- Mock all AWS clients before module loading.

**Test Cases:**
- Determine test cases by reading the handler. Cover:
  - Happy path: successful CodeBuild start
  - Error handling: ClientError from CodeBuild
  - Input validation
  - Environment variable requirements

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_start_codebuild.py -v` passes
- [x] No real AWS calls

**Commit Message Template:**
```
test(start_codebuild): add unit tests for CodeBuild trigger Lambda
```

---

## Task 8: Test combine_pages Lambda

**Goal:** Test the Lambda that combines processed page outputs into a single document.

**Files to Create:**
- `tests/unit/python/test_combine_pages.py`

**Files to Read First:**
- `src/lambda/combine_pages/index.py` (247 lines)

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**
- Load module via `importlib.util.spec_from_file_location("combine_pages_index", ...)`.
- Read the handler to understand its event structure (likely receives batch completion info from DynamoDB/SQS).
- Mock S3 operations (reading page outputs, writing combined output).
- Mock DynamoDB operations (tracking table updates).

**Test Cases:**
- Determine test cases by reading the handler. Cover:
  - Happy path: combine multiple page outputs
  - Single page document (no combination needed)
  - Missing page outputs (some batches failed)
  - S3 read/write errors
  - DynamoDB tracking updates

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_combine_pages.py -v` passes
- [x] Page ordering logic tested
- [x] Error paths tested

**Commit Message Template:**
```
test(combine_pages): add unit tests for page combination logic
```

---

## Task 9: Test configuration_resolver Lambda

**Goal:** Test the AppSync resolver that manages DynamoDB configuration.

**Files to Create:**
- `tests/unit/python/test_configuration_resolver.py`

**Files to Read First:**
- `src/lambda/configuration_resolver/index.py` (302 lines)

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**
- Load module via `importlib.util.spec_from_file_location("configuration_resolver_index", ...)`.
- This is an AppSync resolver, so the event follows the AppSync format with `event["info"]["fieldName"]`.
- Mock DynamoDB table operations.
- Test each resolver field/mutation.

**Test Cases:**
- Determine test cases by reading the handler. Cover:
  - Each query field the resolver handles
  - Each mutation the resolver handles
  - Input validation for mutations
  - DynamoDB error handling
  - Unknown field name handling

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_configuration_resolver.py -v` passes
- [x] All resolver fields tested
- [x] Error handling tested

**Commit Message Template:**
```
test(configuration_resolver): add unit tests for config management resolver
```

---

## Task 10: Test budget_sync Lambda

**Goal:** Test the Lambda that synchronizes budget data.

**Files to Create:**
- `tests/unit/python/test_budget_sync.py`

**Files to Read First:**
- `src/lambda/budget_sync/index.py` (319 lines)

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**
- Load module via `importlib.util.spec_from_file_location("budget_sync_index", ...)`.
- Read the handler to understand what AWS services it interacts with (likely Cost Explorer, DynamoDB, possibly Budgets API).
- Mock all AWS clients.

**Test Cases:**
- Determine test cases by reading the handler. Cover:
  - Happy path: successful budget sync
  - AWS service errors
  - Missing/invalid budget data
  - DynamoDB updates

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_budget_sync.py -v` passes
- [x] All AWS service interactions mocked

**Commit Message Template:**
```
test(budget_sync): add unit tests for budget synchronization Lambda
```

---

## Task 11: Test kb_custom_resource Lambda

**Goal:** Test the CloudFormation custom resource for Knowledge Base management.

**Files to Create:**
- `tests/unit/python/test_kb_custom_resource.py`

**Files to Read First:**
- `src/lambda/kb_custom_resource/index.py` (339 lines)

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**
- Load module via `importlib.util.spec_from_file_location("kb_custom_resource_index", ...)`.
- This is a CloudFormation custom resource handler (similar pattern to admin_user_provisioner and initial_sync).
- Mock Bedrock KB API calls and `urllib.request.urlopen`.
- This handler likely creates/updates/deletes Bedrock Knowledge Base resources.

**Test Cases:**
- Determine test cases by reading the handler. Cover:
  - Create: Happy path KB creation
  - Create: KB already exists
  - Create: ClientError
  - Update: Property changes
  - Delete: Happy path cleanup
  - Delete: Resource not found (should succeed)
  - CloudFormation response always sent
  - Unknown RequestType

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_kb_custom_resource.py -v` passes
- [x] CloudFormation response always sent, even on error
- [x] At least 8 test cases

**Commit Message Template:**
```
test(kb_custom_resource): add unit tests for KB CloudFormation custom resource
```

---

## Task 12: Test batch_processor Lambda

**Goal:** Test the Lambda that processes individual document batches (10-page chunks).

**Files to Create:**
- `tests/unit/python/test_batch_processor.py`

**Files to Read First:**
- `src/lambda/batch_processor/index.py` (352 lines)

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**
- Load module via `importlib.util.spec_from_file_location("batch_processor_index", ...)`.
- Read the handler to understand its event structure (receives SQS messages with page range info).
- Mock S3 (reading PDF pages, writing extracted text), DynamoDB (tracking updates), and any OCR/Bedrock calls.
- This is a complex handler -- focus on the orchestration logic, not the OCR details (those are tested in lib tests).

**Test Cases:**
- Determine test cases by reading the handler. Cover:
  - Happy path: process a 10-page batch
  - SQS event parsing
  - S3 read failures
  - OCR processing errors (should mark batch as failed, not crash)
  - DynamoDB atomic counter updates (batches_remaining decrement)
  - Last batch detection (triggers combine_pages)
  - Partial success (some pages fail, some succeed)

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_batch_processor.py -v` passes
- [x] At least 6 test cases
- [x] Atomic counter logic tested

**Commit Message Template:**
```
test(batch_processor): add unit tests for batch document processing
```

---

## Task 13: Test process_document Lambda (expand existing)

**Goal:** Expand the existing minimal test file for process_document to cover the full handler.

**Files to Modify:**
- `tests/unit/python/test_process_document_passthrough.py` -- Rename to `test_process_document.py` and expand

**Files to Read First:**
- `src/lambda/process_document/index.py` (384 lines)
- `tests/unit/python/test_process_document_passthrough.py` (existing tests)

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**
- Read the existing test file. It only tests `parse_s3_uri` and markdown passthrough.
- Rename the file to `test_process_document.py` (use `git mv`).
- Add tests for the main `lambda_handler` and other functions.
- Keep existing tests intact, add new test classes.

**Test Cases:**
- Keep all existing tests
- Add: `lambda_handler` happy path (PDF document)
- Add: `lambda_handler` with markdown passthrough (scraped content)
- Add: `lambda_handler` error handling (Textract failure)
- Add: DynamoDB tracking table updates
- Add: Missing environment variables
- Add: Unsupported file type handling

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/test_process_document.py -v` passes
- [x] Existing tests still pass
- [x] Handler entry point tested
- [x] File renamed via `git mv`

**Commit Message Template:**
```
test(process_document): expand tests to cover full handler orchestration

- Rename test_process_document_passthrough.py to test_process_document.py
- Add handler, error path, and tracking tests
- Keep existing markdown passthrough tests
```

---

## Task 14: Full Test Suite Verification

**Goal:** Verify all new tests pass together and don't interfere with existing tests.

**Files to Modify:** None (verification only)

**Prerequisites:**
- Tasks 1-13 complete

**Implementation Steps:**
- Run the full backend test suite.
- Run linting on all new test files.
- Verify no test isolation issues (parallel execution).

**Verification Checklist:**
- [x] `uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short -n auto` passes (all tests, parallel)
- [x] `uv run ruff check tests/unit/python/` passes
- [x] `uv run ruff format tests/unit/python/ --check` passes
- [x] No new test file imports `index` directly (all use `importlib.util`)
- [x] Each new test file uses a unique module name in `sys.modules`

**Commit Message Template:**
```
test: verify full test suite passes with all new handler tests
```
(Only commit if any fixes were needed during verification.)

---

## Phase Verification

After completing all tasks:

1. Run `uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short -n auto` -- all tests pass
2. Run `uv run ruff check . && uv run ruff format . --check` -- all linting passes
3. Count test files: should have at least 11 new test files (one per previously untested handler plus logging_utils)
4. Verify no test file uses `import index` at module level

**Known limitations:**
- `process_document`, `process_media`, and `reindex_kb` already had partial test coverage. Phase 1 only expands `process_document`. The other two are adequate for the safety net purpose.
- Test coverage percentage is not a goal -- meaningful test cases covering handler logic, error paths, and edge cases are the goal.
