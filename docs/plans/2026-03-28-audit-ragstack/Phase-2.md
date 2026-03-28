# Phase 2 -- [IMPLEMENTER] Critical Fixes and Performance

## Phase Goal

Fix the critical silent-failure bug in query_kb, add request-scoped caching to
ConfigurationManager, harden environment variable access, add size guards to S3 reads,
and consolidate duplicated S3 URI parsing. These are targeted code fixes that do not
require large structural refactors.

**Success criteria:** KB retrieval failures surface to users instead of hallucinating,
DynamoDB reads per chat request drop from ~16 to ~2, all env var access is safe from
opaque KeyError, S3 reads are guarded against unbounded memory consumption.

**Estimated tokens:** ~18k

## Prerequisites

- Phase 1 complete (quick wins and cleanup done)
- `npm run check` passes

## Tasks

### Task 1: Surface KB Retrieval Failures Instead of Swallowing (CRITICAL)

**Goal:** Replace the bare `except Exception` in query_kb that silently swallows Bedrock
retrieval failures and causes the LLM to hallucinate on zero context. (Health audit
finding 3)

**Files to Modify:**

- `src/lambda/query_kb/handler.py` -- Narrow the exception handler around KB retrieval

**Prerequisites:** None

**Implementation Steps:**

1. Open `src/lambda/query_kb/handler.py` and find the retrieval try/except block (around
   line 420-427)
1. The current code catches `Exception`, logs a warning, and continues with empty results.
   This causes the LLM to generate an answer with "No relevant information found" context.
1. Change the behavior to:
   - Catch `ClientError` specifically (from botocore.exceptions)
   - For throttling errors (`ThrottlingException`, error code check), log a warning and
     return a user-friendly error message like "The system is currently busy. Please try
     again in a moment."
   - For all other `ClientError` exceptions, log the error at ERROR level and return a
     user-friendly error message like "Unable to search the knowledge base. Please try
     again."
   - Do NOT catch generic `Exception` -- let unexpected errors propagate to the caller
     which already has error handling
1. The error response should use the same response format as successful responses so the
   frontend can display it. Look at how other error responses are structured in the handler
   (search for "error" in the response dict).

**Verification Checklist:**

- [ ] No bare `except Exception` remains around the KB retrieval call
- [ ] Throttling errors return a user-friendly message (not a stack trace)
- [ ] Other ClientErrors return a user-friendly message
- [ ] Unexpected errors propagate up (not caught)
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Add a test in `tests/unit/python/test_query_kb.py` that mocks the Bedrock
  `retrieve_and_generate` or `retrieve` call to raise a `ClientError` with error code
  `ThrottlingException`. Verify the handler returns a user-friendly error message.
- Add a test that mocks the call to raise a `ClientError` with a different error code
  (e.g., `AccessDeniedException`). Verify the handler returns an error message.
- Add a test that mocks the call to raise a non-ClientError exception (e.g., `ValueError`).
  Verify the exception propagates (is NOT caught).

**Commit Message Template:**

```text
fix(query-kb): surface KB retrieval failures instead of swallowing

- Replace bare except Exception with specific ClientError handling
- Throttling returns user-friendly retry message
- Other errors return user-friendly error message
- Unexpected errors propagate for proper error handling
```

### Task 2: Add Request-Scoped Caching to ConfigurationManager

**Goal:** Eliminate ~14 redundant DynamoDB reads per chat request by caching the effective
config for the duration of a single Lambda invocation. (Eval performance finding,
health audit finding 8 related)

**Files to Modify:**

- `lib/ragstack_common/config.py` -- Add caching to `get_effective_config()`
- `tests/unit/python/test_config.py` -- Add tests for caching behavior

**Prerequisites:** None

**Implementation Steps:**

1. Open `lib/ragstack_common/config.py` and find the `ConfigurationManager` class
1. Add a `_cache: dict[str, Any] | None = None` instance attribute in `__init__`
1. In `get_effective_config()`, check if `_cache` is not None and return it immediately
   if so. Otherwise, compute the effective config as before and store it in `_cache`
   before returning.
1. Add a `clear_cache(self) -> None` method that sets `_cache = None`
1. At each Lambda handler entry point that uses ConfigurationManager, call `clear_cache()`
   at the start of the handler function. Search for all `get_config_manager()` call sites
   and find the handler functions that call them. The handler entry point is the
   `lambda_handler()` or `handler()` function in each Lambda.
   Key files to update:
   - `src/lambda/appsync_resolvers/index.py` -- `lambda_handler()`
   - `src/lambda/query_kb/handler.py` -- `handler()` or `lambda_handler()`
   - `src/lambda/search_kb/index.py` -- handler function
   - Any other Lambda handlers that call `get_config_manager()`
1. The cache is cleared once per invocation, so all `get_parameter()` calls within a
   single invocation read from DynamoDB only once.

**Verification Checklist:**

- [ ] `ConfigurationManager` has a `clear_cache()` method
- [ ] `get_effective_config()` returns cached result on second call within same invocation
- [ ] Each Lambda handler that uses ConfigurationManager calls `clear_cache()` at entry
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Add a test in `tests/unit/python/test_config.py` that:
  1. Creates a ConfigurationManager with mocked DynamoDB
  1. Calls `get_effective_config()` twice
  1. Asserts DynamoDB `get_item` was called only once (cached)
  1. Calls `clear_cache()`
  1. Calls `get_effective_config()` again
  1. Asserts DynamoDB `get_item` was called again (cache cleared)

**Commit Message Template:**

```text
perf(config): add request-scoped caching to ConfigurationManager

- Cache effective config after first DynamoDB read per invocation
- Add clear_cache() method called at Lambda handler entry points
- Reduces ~16 DynamoDB reads to ~2 per chat request
```

### Task 3: Harden Environment Variable Access in appsync_resolvers

**Goal:** Replace bare `os.environ["KEY"]` access with `os.environ.get()` plus explicit
error messages to prevent opaque KeyError on cold start. (Eval defensiveness finding)

**Files to Modify:**

- `src/lambda/appsync_resolvers/index.py` -- Replace bracket access with `.get()` and
  validation

**Prerequisites:** None

**Implementation Steps:**

1. Open `src/lambda/appsync_resolvers/index.py` and find all `os.environ["..."]` calls
   (lines 146-147 and any others)
1. For REQUIRED environment variables (like `TRACKING_TABLE`, `DATA_BUCKET`), replace with
   a helper pattern:

   ```python
   TRACKING_TABLE = os.environ.get("TRACKING_TABLE")
   DATA_BUCKET = os.environ.get("DATA_BUCKET")
   ```

   Then at the top of `lambda_handler()`, add validation:

   ```python
   if not TRACKING_TABLE:
       raise ValueError("TRACKING_TABLE environment variable is required")
   if not DATA_BUCKET:
       raise ValueError("DATA_BUCKET environment variable is required")
   ```

1. This way, the module imports without crashing, and the error message is clear when
   the handler is invoked.
1. For optional environment variables (like `STATE_MACHINE_ARN`, `KNOWLEDGE_BASE_ID`),
   they already use `os.environ.get()` so no change is needed.
1. Search for `os.environ[` (with bracket) across all Lambda handlers to find any other
   instances of this pattern and fix them too.

**Verification Checklist:**

- [ ] `grep -rn 'os.environ\[' src/lambda/` returns zero results (all use `.get()`)
- [ ] Required env vars are validated at handler entry with clear ValueError messages
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Existing tests should continue to pass because they set environment variables in fixtures.
- Add a test that verifies the handler raises `ValueError` with a descriptive message when
  a required environment variable is missing. Use `unittest.mock.patch.dict(os.environ, ...)`
  to remove the variable.

**Commit Message Template:**

```text
fix(appsync-resolvers): replace bare os.environ[] with safe access

- Use os.environ.get() to prevent opaque KeyError on cold start
- Add explicit ValueError with descriptive message for required vars
- Apply pattern across all Lambda handlers
```

### Task 4: Add Size Guard to `read_s3_text()`

**Goal:** Prevent unbounded memory consumption when reading S3 objects. (Eval concern)

**Files to Modify:**

- `lib/ragstack_common/storage.py` -- Add size check before reading S3 object body
- `tests/unit/python/test_storage.py` -- Add test for size guard (create if needed)

**Prerequisites:** None

**Implementation Steps:**

1. Open `lib/ragstack_common/storage.py` and find the `read_s3_text()` function
1. Before calling `.read()` on the S3 Body, check `ContentLength` from the S3 response
1. Add a `max_size_bytes` parameter with a sensible default (e.g., 50MB = 50 * 1024 * 1024)
1. If `ContentLength` exceeds `max_size_bytes`, raise a `ValueError` with a clear message
   including the actual size and the limit
1. Check if there are other functions in storage.py that read S3 objects without size guards
   and apply the same pattern

**Verification Checklist:**

- [ ] `read_s3_text()` has a `max_size_bytes` parameter with a default
- [ ] Reading an object larger than the limit raises `ValueError`
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Add a test that mocks an S3 response with `ContentLength` exceeding the limit and verifies
  `ValueError` is raised
- Add a test that mocks a normal-sized S3 response and verifies it reads successfully

**Commit Message Template:**

```text
fix(storage): add size guard to read_s3_text

- Check ContentLength before reading S3 object body
- Add max_size_bytes parameter with 50MB default
- Prevents unbounded memory consumption on large objects
```

### Task 5: Consolidate Inline S3 URI Parsing

**Goal:** Replace 17 instances of inline `replace("s3://", "").split("/", 1)` with calls
to the existing `parse_s3_uri()` utility. (Health audit finding 4)

**Files to Modify:**

- `src/lambda/appsync_resolvers/index.py` -- 8 occurrences
- `src/lambda/query_kb/sources.py` -- 4 occurrences
- `src/lambda/query_kb/handler.py` -- 1 occurrence
- `src/lambda/query_kb/retrieval.py` -- 1 occurrence
- `src/lambda/process_image/index.py` -- 2 occurrences

**Prerequisites:** None

**Implementation Steps:**

1. Search for all occurrences of `replace("s3://", "")` across the codebase
1. For each occurrence, replace the inline parsing with a call to `parse_s3_uri()` from
   `ragstack_common.storage`
1. Each file may already import from `ragstack_common.storage` -- if so, add `parse_s3_uri`
   to the existing import. If not, add the import.
1. The `parse_s3_uri()` function returns a tuple `(bucket, key)`. Match the variable names
   used at each call site.
1. Be careful with the `query_kb/` files -- they use the dual import pattern. Add
   `parse_s3_uri` to the existing import block (both the try and except branches).
1. Run tests after each file to catch regressions early.

**Verification Checklist:**

- [ ] `grep -rn 'replace.*s3://' src/lambda/` returns zero results
- [ ] All replacements use `parse_s3_uri()` from `ragstack_common.storage`
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Existing tests should cover the behavior since `parse_s3_uri()` has the same semantics
  as the inline pattern. Run `npm run test:backend` to confirm.

**Commit Message Template:**

```text
refactor(storage): consolidate inline S3 URI parsing to parse_s3_uri

- Replace 17 instances of inline s3:// parsing with ragstack_common utility
- Ensures consistent error handling for malformed URIs
```

### Task 6: Move boto3 Clients to Module Level in combine_pages

**Goal:** Follow Lambda best practices by moving boto3 client creation to module level
for connection reuse across warm invocations. (Health audit finding 13)

**Files to Modify:**

- `src/lambda/combine_pages/index.py` -- Move client creation out of functions

**Prerequisites:** None

**Implementation Steps:**

1. Open `src/lambda/combine_pages/index.py` and find boto3 client creation inside helper
   functions (around lines 55 and 102)
1. Move the client creation to module level (top of file, after imports)
1. Update the functions to use the module-level clients instead of creating new ones
1. Verify no other Lambda handlers have the same issue by searching for
   `boto3.client(` and `boto3.resource(` inside function bodies (not at module level)

**Verification Checklist:**

- [ ] `src/lambda/combine_pages/index.py` creates boto3 clients at module level
- [ ] No boto3 client creation inside function bodies in this file
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Existing tests should cover this refactor. Run `npm run test:backend`.

**Commit Message Template:**

```text
perf(combine-pages): move boto3 clients to module level

- Enables connection reuse across warm Lambda invocations
- Follows Lambda best practices for client initialization
```

## Phase Verification

1. Run `npm run check` -- all lint and tests pass
1. Verify no bare `except Exception` around KB retrieval in `query_kb/handler.py`
1. Verify ConfigurationManager has `clear_cache()` and it is called at handler entry points
1. Verify `grep -rn 'os.environ\[' src/lambda/` returns zero results
1. Verify `grep -rn 'replace.*s3://' src/lambda/` returns zero results
1. Verify git log shows 6 atomic commits with conventional commit messages
