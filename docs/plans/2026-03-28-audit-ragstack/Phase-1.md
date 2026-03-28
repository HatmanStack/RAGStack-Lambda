# Phase 1 -- [HYGIENIST] Cleanup and Quick Wins

## Phase Goal

Remove dead code, fix dependency vulnerabilities, and apply quick-win fixes that require
minimal structural changes. This is subtractive work: delete or simplify before later
phases add structure.

**Success criteria:** All vulnerability scans clean, dead code removed, quick-win bug fix
deployed, tests green.

**Estimated tokens:** ~6k

## Prerequisites

- Phase 0 read and understood
- Repository cloned, `uv sync` and `npm install` completed
- `npm run check` passes before starting

## Tasks

### Task 1: Verify Reindex Lock Key Consistency

**Goal:** Confirm that the DynamoDB key used in `check_reindex_lock()` is consistent
across all Lambda functions. The original audit flagged a `"config_key"` vs
`"Configuration"` mismatch, but the code already uses `"Configuration"`. This task
verifies the fix is in place and no regression exists. (Health audit finding 1)

**Files to Inspect (no modifications expected):**

- `src/lambda/appsync_resolvers/index.py` -- `check_reindex_lock()` function
- `src/lambda/reindex_kb/index.py` -- Reindex lock creation
- `src/lambda/queue_processor/index.py` -- Reindex lock check

**Prerequisites:** None

**Implementation Steps:**

1. Search the codebase for all references to `REINDEX_LOCK_KEY`:
   `grep -rn "REINDEX_LOCK_KEY" src/lambda/`
1. Verify every DynamoDB `Key=` expression that uses `REINDEX_LOCK_KEY` uses
   `"Configuration"` as the partition key attribute name
1. If any file still uses a different key name (e.g., `"config_key"`, `"PK"`), fix it.
   Otherwise, no changes are needed.

**Verification Checklist:**

- [x] `grep -rn "REINDEX_LOCK_KEY" src/lambda/` shows consistent `"Configuration"` key
  across all files
- [x] `grep -rn "config_key" src/lambda/` returns zero results

**Testing Instructions:**

- No code changes expected. If a fix was needed, run `npm run test:backend` to confirm.

**Commit Message Template:**

Only commit if a fix was needed:

```text
fix(appsync-resolvers): correct DynamoDB key for reindex lock check

- Change partition key attribute to "Configuration" to match all other Lambda functions
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

### Task 4: Clean Up Unused Test Fixture Variables

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
1. Verify git log shows 3-4 atomic commits with conventional commit messages (Task 1 may
   produce no commit if verification confirms the fix is already in place)
