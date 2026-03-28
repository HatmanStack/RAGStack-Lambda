# Phase 1 -- [HYGIENIST] Cleanup and Quick Wins

## Phase Goal

Remove dead code, fix dependency vulnerabilities, and apply quick-win fixes that require
minimal structural changes. This is subtractive work: delete or simplify before later
phases add structure.

**Success criteria:** All vulnerability scans clean, dead code removed, quick-win bug fix
deployed, tests green.

**Estimated tokens:** ~10k

## Prerequisites

- Phase 0 read and understood
- Repository cloned, `uv sync` and `npm install` completed
- `npm run check` passes before starting

## Tasks

### Task 1: Fix Reindex Lock Key Mismatch (CRITICAL)

**Goal:** Fix the DynamoDB key mismatch that defeats concurrent operation protection.
This is the highest-priority bug in the codebase. (Health audit finding 1, quick win 1)

**Files to Modify:**

- `src/lambda/appsync_resolvers/index.py` -- Fix key name in `check_reindex_lock()`

**Prerequisites:** None

**Implementation Steps:**

1. Open `src/lambda/appsync_resolvers/index.py` and find the `check_reindex_lock()` function
   (around line 117-143)
1. Find the `table.get_item()` call that uses `Key={"config_key": REINDEX_LOCK_KEY}`
1. Change `"config_key"` to `"Configuration"` to match the key used by
   `reindex_kb/index.py` and `queue_processor/index.py`
1. Verify the fix by searching the codebase for all references to `REINDEX_LOCK_KEY` to
   confirm `"Configuration"` is the correct partition key attribute name used everywhere else

**Verification Checklist:**

- [x] `grep -rn "config_key" src/lambda/appsync_resolvers/index.py` returns zero results
- [x] `grep -rn "REINDEX_LOCK_KEY" src/lambda/` shows consistent key attribute name across
  all files
- [x] `npm run test:backend` passes

**Testing Instructions:**

- The existing test suite should continue to pass. No new test is needed for this one-line
  fix -- the key name is validated by cross-referencing with `reindex_kb` and
  `queue_processor` which use the same DynamoDB table.

**Commit Message Template:**

```text
fix(appsync-resolvers): correct DynamoDB key for reindex lock check

- Change "config_key" to "Configuration" to match reindex_kb and queue_processor
- Fixes bug where reindex lock was never detected, risking data loss
```

### Task 2: Fix npm Vulnerabilities

**Goal:** Resolve 5 npm vulnerabilities in build tooling. (Health audit finding 14,
quick win 2)

**Files to Modify:**

- `package-lock.json` (auto-updated by npm)
- `src/ui/package-lock.json` (if present)
- `src/ragstack-chat/package-lock.json` (if present)

**Prerequisites:** None

**Implementation Steps:**

1. Run `npm audit` from the repo root to see current vulnerability list
1. Run `npm audit fix` from the repo root
1. Check if `src/ui/` and `src/ragstack-chat/` have their own `package-lock.json` files
   and run `npm audit fix` in each if so
1. Run `npm run check` to verify nothing broke
1. If `npm audit fix` cannot resolve all issues, run `npm audit fix --force` only if the
   semver-major bumps do not break tests. If they do break tests, document the remaining
   vulnerabilities and move on.

**Verification Checklist:**

- [x] `npm audit` shows 0 vulnerabilities (or documents why remaining ones cannot be fixed)
- [x] `npm run check` passes

**Testing Instructions:**

- Run `npm run test:frontend` to verify frontend tests still pass after dependency updates

**Commit Message Template:**

```text
chore(deps): fix npm audit vulnerabilities

- Resolve rollup arbitrary file write (GHSA-mw96-cpmx-2vgc)
- Resolve yaml stack overflow (GHSA-48c2-rrv3-qjmp)
```

### Task 3: Fix Python Dependency Vulnerability

**Goal:** Update pygments to resolve CVE-2026-4539. (Health audit finding 15)

**Files to Modify:**

- `pyproject.toml` -- Update pygments version constraint if pinned
- `uv.lock` -- Auto-updated by uv

**Prerequisites:** None

**Implementation Steps:**

1. Run `uv pip list | grep -i pygments` to confirm current version
1. Run `uv lock --upgrade-package pygments` to update to the latest patched version
1. Run `npm run test:backend` to verify nothing broke

**Verification Checklist:**

- [x] `uv run pip-audit` shows no known vulnerabilities (or documents exceptions)
- [x] `npm run test:backend` passes

**Testing Instructions:**

- Run `npm run test:backend` -- pygments is a dev dependency so only test tooling is affected

**Commit Message Template:**

```text
chore(deps): update pygments to fix CVE-2026-4539

- Upgrade pygments dev dependency to patched version
```

### Task 4: Remove Unused `min_per_slice` Parameter

**Goal:** Clean up dead parameter in multislice retriever. (Health audit finding 16,
quick win 3, vulture scan result)

**Files to Modify:**

- `lib/ragstack_common/multislice_retriever.py` -- Remove parameter from function signature
  and docstring

**Prerequisites:** None

**Implementation Steps:**

1. Open `lib/ragstack_common/multislice_retriever.py` and find
   `merge_slices_with_guaranteed_minimum()` (around line 139)
1. Remove the `min_per_slice` parameter from the function signature
1. Update the docstring to remove any reference to `min_per_slice`
1. Search the entire codebase for all callers of `merge_slices_with_guaranteed_minimum`
1. Remove `min_per_slice=...` from all call sites
1. Search for any tests that pass `min_per_slice` and update them

**Verification Checklist:**

- [x] `grep -rn "min_per_slice" .` returns zero results (excluding this plan)
- [x] `npm run test:backend` passes

**Testing Instructions:**

- Run existing tests for multislice_retriever. If `min_per_slice` appears in test calls,
  remove it from those calls as well.

**Commit Message Template:**

```text
refactor(retrieval): remove unused min_per_slice parameter

- Parameter was accepted but never used (confirmed by vulture scan)
- Remove from function signature, docstring, and all call sites
```

### Task 5: Clean Up Unused Test Fixture Variables

**Goal:** Fix unused `mock_env` fixture variables in configuration_resolver tests.
(Health audit finding 18)

**Files to Modify:**

- `src/lambda/configuration_resolver/test_handler.py` -- Prefix unused fixture params
  with underscore or use `_` directly

**Prerequisites:** None

**Implementation Steps:**

1. Open `src/lambda/configuration_resolver/test_handler.py`
1. Examine each of the 12 test functions that accept `mock_env` as a parameter
1. For each, determine whether `mock_env` is needed for its side effect (e.g., setting
   environment variables via a pytest fixture) or is truly unused
1. If the fixture IS needed for its side effect but the variable is unused in the test body,
   prefix the parameter name with underscore: `_mock_env`
1. If the fixture is NOT needed at all, remove it from the test function signature
1. Run ruff to check that no new lint issues are introduced

**Verification Checklist:**

- [x] `uv run ruff check src/lambda/configuration_resolver/test_handler.py` passes cleanly
- [x] `npm run test:backend` passes

**Testing Instructions:**

- Run `uv run pytest src/lambda/configuration_resolver/test_handler.py -v` to verify the
  specific test file still passes

**Commit Message Template:**

```text
style(tests): prefix unused mock_env fixture variables with underscore

- 12 test functions use mock_env for side effects but don't reference the variable
- Prefix with underscore to satisfy linters and clarify intent
```

## Phase Verification

1. Run `npm run check` -- all lint and tests must pass
1. Run `npm audit` -- should show 0 vulnerabilities
1. Run `grep -rn "config_key" src/lambda/appsync_resolvers/index.py` -- should return nothing
1. Run `grep -rn "min_per_slice" lib/ src/` -- should return nothing
1. Verify git log shows 5 atomic commits with conventional commit messages
