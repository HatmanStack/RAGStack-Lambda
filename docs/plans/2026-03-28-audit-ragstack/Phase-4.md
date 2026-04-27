# Phase 4 -- [FORTIFIER] Guardrails and Type Safety

## Phase Goal

Add guardrails that prevent regression: narrow broad exception handling in critical paths,
clean up frontend type safety issues, remove console.log calls, add coverage enforcement
to CI, and improve test infrastructure.

**Success criteria:** Critical Lambda handlers have specific exception types instead of
bare `except Exception`. Frontend has zero `as any` casts on subscription clients. CI
enforces coverage threshold. Test infrastructure uses `pytest.importorskip` for optional
dependencies.

**Estimated tokens:** ~15k

## Prerequisites

- Phase 3 complete (architectural improvements done)
- `npm run check` passes

## Tasks

### Task 1: Narrow Exception Handling in query_kb

**Goal:** Replace broad `except Exception` catches with specific exception types in the
query_kb handler, the most critical user-facing Lambda. (Eval code quality finding,
ADR-005)

**Files to Modify:**

- `src/lambda/query_kb/handler.py` -- Narrow exception catches
- `src/lambda/query_kb/conversation.py` -- Narrow exception catches
- `src/lambda/query_kb/retrieval.py` -- Narrow exception catches

**Prerequisites:** Phase 2 Task 1 already fixed the most critical bare except. This task
handles the remaining broad catches.

**Implementation Steps:**

1. Search for `except Exception` in all `query_kb/*.py` files
1. For each catch, analyze what the try block is doing and determine the specific
   exceptions that could be raised:
   - boto3 calls: catch `botocore.exceptions.ClientError`
   - JSON parsing: catch `json.JSONDecodeError`
   - Key/index access: catch `KeyError`, `IndexError`
   - Type conversion: catch `ValueError`, `TypeError`
1. Replace `except Exception` with the specific exception type(s)
1. If a broad catch is genuinely needed as a safety net at the TOP-LEVEL handler (the
   outermost try/except in the lambda_handler), that is acceptable. Add a comment
   explaining why: `# Safety net: catch unexpected errors to return user-friendly message`
1. Do NOT change the error handling behavior -- only narrow the exception type. The
   existing error messages and logging should remain the same.
1. Run tests after each file.

**Verification Checklist:**

- [x] `grep -rn "except Exception" src/lambda/query_kb/` returns at most 1 result
  (the top-level safety net in handler.py)
- [x] Each narrowed except names specific exception types
- [x] `npm run test:backend` passes

**Testing Instructions:**

- Existing tests should pass since behavior is unchanged.
- For each narrowed catch, verify that the specific exception type is correct by tracing
  the code path in the try block.

**Commit Message Template:**

```text
refactor(query-kb): narrow except Exception to specific types

- Replace broad catches with ClientError, ValueError, KeyError, etc.
- Retain single top-level safety net in handler for user-friendly errors
- No behavior change, only exception type precision
```

### Task 2: Narrow Exception Handling in appsync_resolvers

**Goal:** Narrow broad exception catches in the split resolver modules. (Eval code quality)

**Files to Modify:**

- `src/lambda/appsync_resolvers/resolvers/documents.py`
- `src/lambda/appsync_resolvers/resolvers/images.py`
- `src/lambda/appsync_resolvers/resolvers/scrape.py`
- `src/lambda/appsync_resolvers/resolvers/metadata.py`
- `src/lambda/appsync_resolvers/resolvers/chat.py`
- `src/lambda/appsync_resolvers/index.py`

**Prerequisites:** Phase 3 Tasks 1-5 (resolver split) complete

**Implementation Steps:**

1. Search for `except Exception` across all resolver modules
1. Apply the same narrowing approach as Task 1. The resolver modules primarily interact
   with:
   - DynamoDB: `ClientError`
   - S3: `ClientError`
   - Step Functions: `ClientError`
   - Lambda invoke: `ClientError`
   - Bedrock: `ClientError`
   - JSON: `JSONDecodeError`
1. The dispatcher in `index.py` should have ONE top-level `except Exception` as a safety
   net that returns a GraphQL-compatible error response.
1. The silent `pass` in the except ClientError (health audit finding 19) should be replaced
   with a `logger.debug()` call so missing metadata sidecar files are at least visible in
   debug logs.

**Verification Checklist:**

- [x] `grep -rn "except Exception" src/lambda/appsync_resolvers/` returns at most 1
  (the dispatcher safety net)
- [x] The silent `except ClientError: pass` (finding 19) now has a logger.debug call
- [x] `npm run test:backend` passes

**Testing Instructions:**

- Run existing appsync_resolvers tests. Behavior should be unchanged.

**Commit Message Template:**

```text
refactor(appsync-resolvers): narrow exception handling to specific types

- Replace broad except Exception with ClientError, ValueError, etc.
- Add debug logging for silently caught metadata sidecar errors
- Retain dispatcher safety net for GraphQL error formatting
```

### Task 3: Clean Up Frontend Type Safety

**Goal:** Remove `as unknown as string`, `as any` casts, and `eslint-disable` comments
in UI hooks and main.tsx. Replace with proper typed wrappers. (Health audit findings
12, 17; eval type rigor)

**Files to Modify:**

- `src/ui/src/hooks/useDocuments.ts` -- Replace subscription type casts
- `src/ui/src/main.tsx` -- Replace `as any` on Amplify.configure
- Other files with `as any` casts (search for `as any` across `src/ui/src/`)

**Prerequisites:** None

**Implementation Steps:**

1. Search `src/ui/src/` for `as any`, `as unknown as string`, and `eslint-disable` to
   catalog all type safety bypasses
1. For `useDocuments.ts` subscriptions (finding 12):
   - Investigate the Amplify v6 client API for proper subscription typing
   - If Amplify provides typed subscription helpers, use them
   - If not, create a thin wrapper type that narrows the subscription return type so
     the cast happens once in the wrapper, not at every call site
   - Remove the `eslint-disable` comments
1. For `main.tsx` (finding 17):
   - Check if `@aws-amplify/core` exports a config type that matches `awsConfig`
   - If so, type `awsConfig` as that type instead of using `as any`
   - If not, create a minimal type definition that matches the config shape
1. For `ChatPanel.tsx` (eval concern):
   - Replace `console.error` with proper error handling (display error in UI or use
     a logging utility)
   - Replace `key={idx}` with stable keys (e.g., message ID if available, or a
     combination of timestamp + content hash)
1. Run `npm run lint:frontend` after each file to verify no lint warnings.

**Verification Checklist:**

- [x] `grep -rn "as any" src/ui/src/hooks/useDocuments.ts` returns zero results
- [x] `grep -rn "as any" src/ui/src/main.tsx` returns zero results
- [x] `grep -rn "eslint-disable" src/ui/src/hooks/useDocuments.ts` returns zero results
- [x] `npm run lint:frontend` passes with `--max-warnings 0`
- [x] `npm run test:frontend` passes

**Testing Instructions:**

- Run `npm run test:frontend` to verify UI tests pass
- Run `npm run lint:frontend` to verify zero warnings

**Commit Message Template:**

```text
style(ui): remove type safety bypasses in hooks and config

- Replace as unknown as string casts with typed subscription wrappers
- Remove as any from Amplify.configure with proper config type
- Replace console.error with error handling in ChatPanel
- Use stable keys instead of array index for message list
```

### Task 4: Remove Frontend console.log Calls

**Goal:** Remove 66 console.log/error/warn calls across 20 frontend files. (Eval code
quality)

**Files to Modify:**

- Multiple files across `src/ui/src/` -- search for `console.log`, `console.error`,
  `console.warn`

**Prerequisites:** Task 3 (which handles ChatPanel console.error)

**Implementation Steps:**

1. Search `src/ui/src/` for `console.log`, `console.error`, `console.warn`
1. For each occurrence, decide:
   - If it is debug logging: remove it entirely
   - If it is error logging: either remove (if the error is handled elsewhere) or replace
     with proper error handling (e.g., display error state in UI)
   - If it is in a catch block: keep a minimal error log if the error is not surfaced to
     the user, but consider whether the error should be surfaced
1. After cleanup, add an ESLint rule to prevent future console usage. Check if the existing
   ESLint config already has `no-console` rule. If not, add it:
   ```text
   "no-console": ["error", { allow: ["warn"] }]
   ```
   Allow `console.warn` for development warnings only if needed.

**Verification Checklist:**

- [x] `grep -rn "console\.\(log\|error\|warn\)" src/ui/src/` returns zero results
  (or only approved exceptions)
- [x] ESLint `no-console` rule is configured
- [x] `npm run lint:frontend` passes
- [x] `npm run test:frontend` passes

**Testing Instructions:**

- Run `npm run test:frontend` and `npm run lint:frontend`

**Commit Message Template:**

```text
style(ui): remove console.log calls and add no-console lint rule

- Remove 66 console.log/error/warn calls across frontend files
- Add ESLint no-console rule to prevent regression
```

### Task 5: Add Coverage Enforcement to CI

**Goal:** Prevent coverage regression by adding `--cov-fail-under` to CI. (Eval test
value finding)

**Files to Modify:**

- `package.json` -- Update `test:backend` script or add `test:backend:ci` variant
- `.github/workflows/ci.yml` -- Use coverage-enforcing test command

**Prerequisites:** None

**Implementation Steps:**

1. Run `npm run test:coverage` to determine the current coverage percentage
1. Set `--cov-fail-under` to 5 points below the current coverage (rounded down to nearest
   5). For example, if coverage is 78%, set the threshold to 70%.
1. Update the CI workflow to use the coverage-enforcing command. Two approaches:
   - Option A: Add `--cov-fail-under=XX` to the `test:backend` script in `package.json`
   - Option B: Add a separate `test:backend:ci` script that includes coverage, and update
     `.github/workflows/ci.yml` to use it
1. Option A is simpler. Go with Option A unless running coverage locally is noticeably
   slower.
1. Also replace `pytest.skip()` guards for optional libraries with `pytest.importorskip()`
   at module level where found (eval test value finding). Search for
   `pytest.skip("` in test files.

**Verification Checklist:**

- [x] `--cov-fail-under` is configured in the pytest invocation
- [x] CI workflow uses the coverage-enforcing command
- [x] `pytest.importorskip` is used instead of manual skip guards where applicable
- [x] `npm run check` passes (including coverage threshold)

**Testing Instructions:**

- Run the coverage command locally to verify it passes the threshold
- Temporarily lower the threshold to verify the CI would fail on regression

**Commit Message Template:**

```text
ci(tests): add coverage enforcement and improve skip guards

- Add --cov-fail-under=XX to CI pytest invocation
- Replace pytest.skip() with pytest.importorskip() for optional deps
- Prevents silent coverage regression
```

### Task 6: Add Pre-commit Hook Configuration

**Goal:** Add `.pre-commit-config.yaml` for local development guardrails. (Eval
reproducibility finding)

**Files to Create:**

- `.pre-commit-config.yaml` -- pre-commit hook configuration

**Prerequisites:** None

**Implementation Steps:**

1. Create `.pre-commit-config.yaml` at the repo root with hooks for:
   - `ruff` (check + format) -- use the ruff-pre-commit mirror
   - `eslint` -- for frontend files
   - Conventional commit linting (optional, via `commitlint`)
1. Use the same ruff version as specified in `pyproject.toml` to avoid config drift
1. Example structure:

   ```yaml
   repos:
     - repo: https://github.com/astral-sh/ruff-pre-commit
       rev: v0.x.x  # Match pyproject.toml ruff version
       hooks:
         - id: ruff
           args: [--fix]
         - id: ruff-format
   ```

1. Do NOT add `pre-commit install` to any CI script -- it is for local use only.
   Document in the commit message that developers should run `pre-commit install` to
   enable hooks.

**Verification Checklist:**

- [x] `.pre-commit-config.yaml` exists at repo root
- [x] `pre-commit run --all-files` passes (if pre-commit is installed)
- [x] Hook versions match project tool versions

**Testing Instructions:**

- Install pre-commit locally: `uv tool install pre-commit`
- Run `pre-commit run --all-files` to verify all hooks pass on the current codebase

**Commit Message Template:**

```text
ci(hooks): add pre-commit configuration for ruff and eslint

- Configure ruff check + format hooks matching pyproject.toml
- Developers run 'pre-commit install' to enable local hooks
```

## Phase Verification

1. Run `npm run check` -- all lint and tests pass
1. Run `npm run lint:frontend` -- zero warnings
1. Verify `grep -rn "except Exception" src/lambda/query_kb/` returns at most 1
1. Verify `grep -rn "except Exception" src/lambda/appsync_resolvers/` returns at most 1
1. Verify `grep -rn "as any" src/ui/src/hooks/useDocuments.ts` returns zero
1. Verify `.pre-commit-config.yaml` exists
1. Verify git log shows 6 atomic commits
