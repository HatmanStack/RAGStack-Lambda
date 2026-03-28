# Phase 3 -- [IMPLEMENTER] Architectural Improvements

## Phase Goal

Split the 3520-line appsync_resolvers god module into domain-specific modules, abstract
the dual-import pattern in query_kb, and deduplicate filter/retrieval code shared between
search_kb and query_kb. These are the largest structural changes in the plan.

**Success criteria:** `appsync_resolvers/index.py` reduced to a thin dispatcher under
200 lines. query_kb modules import from a single `_compat.py` without `# type: ignore`
on every import. Shared filter logic lives in ragstack_common.

**Estimated tokens:** ~35k

## Prerequisites

- Phase 2 complete (all targeted fixes applied)
- `npm run check` passes
- Read ADR-002 (resolver split), ADR-004 (import compat), ADR-007 (filter dedup)

## Tasks

### Task 1: Create Resolver Domain Module Structure

**Goal:** Set up the directory structure and shared utilities for the split resolver
modules. This task creates the skeleton; subsequent tasks move functions into it.

**Files to Create:**

- `src/lambda/appsync_resolvers/resolvers/__init__.py` -- Package init, re-exports
- `src/lambda/appsync_resolvers/resolvers/shared.py` -- Shared utilities (clients, config,
  helpers used across resolver domains)

**Files to Modify:**

- `src/lambda/appsync_resolvers/index.py` -- Extract shared state into `resolvers/shared.py`

**Prerequisites:** None

**Implementation Steps:**

1. Create the `src/lambda/appsync_resolvers/resolvers/` directory with `__init__.py`
1. Identify shared state and utilities in `index.py` that are used across multiple resolver
   domains. These include:
   - boto3 clients: `s3`, `dynamodb`, `sfn`, `lambda_client`, `bedrock_agent`,
     `dynamodb_client`, `bedrock_runtime`
   - Configuration: `get_config_manager()`, `get_current_user_id()`
   - Environment variables: `TRACKING_TABLE`, `DATA_BUCKET`, `STATE_MACHINE_ARN`, etc.
   - Helper functions used by multiple domains (e.g., `check_reindex_lock()`,
     `get_document_status()` if shared)
1. Move these into `resolvers/shared.py`. Keep the module-level initialization pattern
   (boto3 clients at module level, lazy-init for config manager).
1. The `_current_event` global and its setter should stay in `index.py` since the
   dispatcher is responsible for setting it. However, `get_current_user_id()` should be
   in `shared.py` and should accept the event as a parameter instead of relying on a
   global. This removes the fragile global mutable state (health audit finding 22).
1. In `index.py`, import from `resolvers.shared` instead of defining inline.
1. Run tests after this change to verify nothing broke.

**Verification Checklist:**

- [ ] `src/lambda/appsync_resolvers/resolvers/` directory exists with `__init__.py` and
  `shared.py`
- [ ] `shared.py` contains all boto3 clients, env vars, and shared utilities
- [ ] `index.py` imports from `resolvers.shared`
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Run existing appsync_resolvers tests. They should pass without modification since the
  public interface (lambda_handler) has not changed.

**Commit Message Template:**

```text
refactor(appsync-resolvers): extract shared utilities into resolvers/shared.py

- Move boto3 clients, env vars, and helpers to dedicated module
- Replace _current_event global with explicit event parameter
- Prepare for domain-based resolver split
```

### Task 2: Extract Document Resolvers

**Goal:** Move all document-related resolver functions from `index.py` to
`resolvers/documents.py`.

**Files to Create:**

- `src/lambda/appsync_resolvers/resolvers/documents.py` -- Document resolver functions

**Files to Modify:**

- `src/lambda/appsync_resolvers/index.py` -- Remove moved functions, import from new module

**Prerequisites:** Task 1 complete

**Implementation Steps:**

1. Identify all document-related functions in `index.py`. These handle GraphQL fields
   related to document CRUD operations. Look for functions that:
   - List, get, delete, update documents
   - Handle document upload/processing triggers
   - Manage document metadata
1. Move each function to `resolvers/documents.py`. Each function should import what it
   needs from `resolvers.shared`.
1. Replace `get_current_user_id()` calls with explicit event parameter passing. The
   dispatcher in `index.py` will pass the event to each resolver function.
1. In `index.py`, update the dispatcher to call `documents.function_name(event)` instead
   of the local function. The dispatcher maps `event["info"]["fieldName"]` to handler
   functions.
1. Run tests after each batch of moved functions.

**Verification Checklist:**

- [ ] `resolvers/documents.py` contains all document resolver functions
- [ ] No document resolver functions remain in `index.py` (only the import and dispatch)
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Run existing appsync_resolvers tests. The lambda_handler interface is unchanged so all
  tests should pass.
- If tests directly import functions from `index.py`, update those imports to point to
  `resolvers.documents`.

**Commit Message Template:**

```text
refactor(appsync-resolvers): extract document resolvers to dedicated module

- Move document CRUD resolver functions to resolvers/documents.py
- Pass event explicitly instead of using global state
```

### Task 3: Extract Image Resolvers

**Goal:** Move all image-related resolver functions to `resolvers/images.py`.

**Files to Create:**

- `src/lambda/appsync_resolvers/resolvers/images.py` -- Image resolver functions

**Files to Modify:**

- `src/lambda/appsync_resolvers/index.py` -- Remove moved functions, update dispatcher

**Prerequisites:** Task 1 complete

**Implementation Steps:**

1. Identify all image-related functions in `index.py`. Look for functions handling:
   - Image upload, listing, deletion
   - Caption generation
   - Image metadata
1. Move to `resolvers/images.py` following the same pattern as Task 2.
1. Update dispatcher in `index.py`.

**Verification Checklist:**

- [ ] `resolvers/images.py` contains all image resolver functions
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Run existing tests. Update any direct imports if needed.

**Commit Message Template:**

```text
refactor(appsync-resolvers): extract image resolvers to dedicated module

- Move image CRUD and caption resolver functions to resolvers/images.py
```

### Task 4: Extract Scrape Resolvers

**Goal:** Move all web scraping-related resolver functions to `resolvers/scrape.py`.

**Files to Create:**

- `src/lambda/appsync_resolvers/resolvers/scrape.py` -- Scrape resolver functions

**Files to Modify:**

- `src/lambda/appsync_resolvers/index.py` -- Remove moved functions, update dispatcher

**Prerequisites:** Task 1 complete

**Implementation Steps:**

1. Identify scrape-related functions in `index.py`. Look for functions handling:
   - Scrape job creation, listing, status, deletion
   - Scrape URL management
1. Move to `resolvers/scrape.py` following the same pattern.
1. Update dispatcher in `index.py`.

**Verification Checklist:**

- [ ] `resolvers/scrape.py` contains all scrape resolver functions
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Run existing tests. Update any direct imports if needed.

**Commit Message Template:**

```text
refactor(appsync-resolvers): extract scrape resolvers to dedicated module

- Move scrape job and URL resolver functions to resolvers/scrape.py
```

### Task 5: Extract Metadata and Chat Resolvers

**Goal:** Move metadata and chat resolver functions to their own modules. Reduce `index.py`
to a pure dispatcher.

**Files to Create:**

- `src/lambda/appsync_resolvers/resolvers/metadata.py` -- Metadata resolver functions
- `src/lambda/appsync_resolvers/resolvers/chat.py` -- Chat/conversation resolver functions

**Files to Modify:**

- `src/lambda/appsync_resolvers/index.py` -- Should now be a thin dispatcher only

**Prerequisites:** Tasks 2-4 complete

**Implementation Steps:**

1. Move remaining metadata-related functions to `resolvers/metadata.py`
1. Move chat/conversation-related functions to `resolvers/chat.py`
1. Move any remaining reindex-related functions to the most appropriate module (likely
   `resolvers/documents.py` if they relate to document reprocessing, or a separate
   `resolvers/admin.py` if there are enough admin-only functions)
1. After this task, `index.py` should contain ONLY:
   - Imports from resolver modules
   - The `lambda_handler()` function
   - The dispatcher logic that maps field names to handler functions
   - The `_current_event` setter (if still needed) and its forwarding to resolvers
1. Target: `index.py` should be under 200 lines
1. Update `resolvers/__init__.py` to re-export the public API if needed for testing

**Verification Checklist:**

- [ ] `index.py` is under 200 lines
- [ ] `index.py` contains only dispatcher logic (no business logic)
- [ ] All resolver functions live in domain modules under `resolvers/`
- [ ] `npm run test:backend` passes
- [ ] `npm run check` passes (lint + tests)

**Testing Instructions:**

- Run full test suite. If any test directly imports internal functions from `index.py`,
  update those imports to the new module paths.
- Consider adding a simple test that verifies the dispatcher maps known field names to
  the correct handler functions.

**Commit Message Template:**

```text
refactor(appsync-resolvers): complete resolver split, reduce index.py to dispatcher

- Move metadata and chat resolvers to dedicated modules
- index.py now contains only dispatcher logic (<200 lines)
- All 50+ resolver functions organized by domain
```

### Task 6: Abstract Dual-Import Pattern in query_kb

**Goal:** Consolidate the `try/except ImportError` dual-import pattern into a single
`_compat.py` module. (Health audit finding 10, ADR-004)

**Files to Create:**

- `src/lambda/query_kb/_compat.py` -- Centralized import resolution

**Files to Modify:**

- `src/lambda/query_kb/handler.py` -- Import from `_compat` instead of dual pattern
- `src/lambda/query_kb/conversation.py` -- Same
- `src/lambda/query_kb/filters.py` -- Same
- `src/lambda/query_kb/retrieval.py` -- Same
- `src/lambda/query_kb/sources.py` -- Same
- `src/lambda/query_kb/media.py` -- Same

**Prerequisites:** Phase 2 Task 5 (S3 URI consolidation) complete

**Implementation Steps:**

1. Examine all `query_kb/*.py` files to catalog every import that uses the dual
   `try/except ImportError` pattern. List all symbols imported this way.
1. Create `src/lambda/query_kb/_compat.py` that handles the import resolution ONCE:

   ```python
   """Import compatibility layer for query_kb package.

   Handles both package-relative imports (when deployed as a package)
   and flat-directory imports (when deployed as individual files).
   """
   try:
       from ._clients import bedrock_agent, bedrock_runtime, ...
       from .conversation import get_conversation_history, ...
       # ... all shared imports
   except ImportError:
       from _clients import bedrock_agent, ...  # type: ignore[import-not-found,no-redef]
       from conversation import ...  # type: ignore[import-not-found,no-redef]
   ```

1. Update each consumer module (`handler.py`, `conversation.py`, etc.) to import from
   `_compat` using only the package-relative form:

   ```python
   from ._compat import bedrock_agent, get_conversation_history, ...
   ```

   Wait -- this will not work if the flat-directory import is what is used in Lambda.
   The `_compat` module itself handles the import resolution, but consumer modules that
   import from `_compat` also need to handle both modes.

   Better approach: Have `_compat.py` import external dependencies (ragstack_common
   modules) using the dual pattern, and have sibling modules import from `_compat` using
   the same dual pattern but only for `_compat` itself:

   ```python
   try:
       from ._compat import bedrock_agent, ...
   except ImportError:
       from _compat import bedrock_agent, ...  # type: ignore[import-not-found]
   ```

   This still has a try/except in each file, BUT it is only ONE try/except per file
   (for `_compat`) instead of 5-6 try/except blocks. The `# type: ignore` is only on
   one line per file instead of many.

1. Actually, the simplest approach: make `_compat.py` export everything, and each consumer
   module does ONE dual import of `_compat` and then accesses attributes. Review how
   `_clients.py` is already structured -- it may already serve as a partial compat layer.
1. Run tests after each module is updated.

**Verification Checklist:**

- [ ] `_compat.py` exists and handles all cross-module imports
- [ ] Each consumer module has at most ONE `try/except ImportError` block (for `_compat`)
- [ ] `# type: ignore` comments reduced to at most 1 per consumer module
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Run `uv run pytest tests/unit/python/test_query_kb.py -v` to verify query_kb tests pass
- Run `npm run check` to verify lint and type checking pass

**Commit Message Template:**

```text
refactor(query-kb): consolidate dual-import pattern into _compat.py

- Centralize try/except ImportError logic in single module
- Reduce type: ignore comments from ~30 to ~6
- Each consumer module has at most one import compatibility block
```

### Task 7: Deduplicate Filter and Retrieval Logic

**Goal:** Move shared `extract_kb_scalar()` and filter component initialization from
`search_kb/index.py` and `query_kb/filters.py` into `lib/ragstack_common/`. (Health
audit finding 5, ADR-007)

**Files to Create:**

- `lib/ragstack_common/kb_filters.py` -- Shared filter utilities

**Files to Modify:**

- `src/lambda/search_kb/index.py` -- Import from ragstack_common instead of local
- `src/lambda/query_kb/filters.py` -- Import from ragstack_common instead of local
- `lib/ragstack_common/__init__.py` -- Export new module if needed

**Prerequisites:** None

**Implementation Steps:**

1. Compare `extract_kb_scalar()` in `search_kb/index.py` (lines 50-65) and
   `query_kb/filters.py` (lines 24-38). They should be identical or near-identical.
1. Move the canonical version to `lib/ragstack_common/kb_filters.py`
1. Compare the lazy-init singleton patterns for `KeyLibrary`, `FilterGenerator`, and
   `MultiSliceRetriever` between the two files. Extract any truly shared initialization
   logic. Keep Lambda-specific configuration (env var reading, client creation) in each
   Lambda handler.
1. Update both `search_kb` and `query_kb` to import `extract_kb_scalar` from
   `ragstack_common.kb_filters`
1. Add `extract_kb_scalar` to `lib/ragstack_common/__init__.py` exports if the pattern
   in the codebase is to export from `__init__`
1. Run tests for both search_kb and query_kb

**Verification Checklist:**

- [ ] `extract_kb_scalar` exists in `lib/ragstack_common/kb_filters.py`
- [ ] Both `search_kb` and `query_kb` import from `ragstack_common`
- [ ] No duplicate `extract_kb_scalar` implementations in Lambda code
- [ ] `npm run test:backend` passes

**Testing Instructions:**

- Add a unit test for `extract_kb_scalar` in `tests/unit/python/` that covers:
  - `None` input returns `None`
  - Empty list returns `None`
  - List with quoted string: `['"0"']` returns `"0"`
  - Regular string passes through
- Run `npm run test:backend` to verify both Lambda test suites pass

**Commit Message Template:**

```text
refactor(kb-filters): deduplicate extract_kb_scalar to ragstack_common

- Move shared filter utility from search_kb and query_kb to shared library
- Single source of truth for KB metadata value extraction
- Prevents feature drift between search and chat filter paths
```

## Phase Verification

1. Run `npm run check` -- all lint and tests pass
1. Run `wc -l src/lambda/appsync_resolvers/index.py` -- should be under 200 lines
1. Verify `src/lambda/appsync_resolvers/resolvers/` contains domain modules
1. Verify `src/lambda/query_kb/_compat.py` exists
1. Verify `lib/ragstack_common/kb_filters.py` exists
1. Run `grep -rn "type: ignore" src/lambda/query_kb/` -- count should be significantly
   reduced compared to before (from ~30 to ~6)
1. Verify git log shows 7 atomic commits with conventional commit messages

## Known Limitations

- The resolver split does NOT improve cold start time (all domain modules are still
  imported). This is an intentional trade-off per ADR-002.
- The `_current_event` global may still exist in a reduced form in `index.py` for the
  dispatcher. Fully eliminating it requires changing how identity is threaded through
  resolvers. This phase passes identity explicitly where feasible.
- The `reindex_kb/index.py` 1502-line handler (health audit finding 9) is NOT addressed
  in this plan. It requires architectural changes (Step Functions decomposition) beyond
  the scope of this remediation.
