# Phase 5 -- [DOC-ENGINEER] Documentation Drift Fixes and Prevention

## Phase Goal

Fix all documentation drift, gaps, stale references, and broken links identified in the
doc audit. Update docs to reflect code changes made in Phases 1-4. Add tooling to prevent
future drift.

**Success criteria:** All 25 doc audit findings resolved. Deployment commands work as
documented. Repository structure descriptions match reality. No broken internal links.

**Estimated tokens:** ~12k

## Prerequisites

- Phases 1-4 complete (code changes done, resolver split complete)
- `npm run check` passes

## Tasks

### Task 1: Fix Critical CLI Flag Drift

**Goal:** Fix the `--project-name` to `--stack-name` drift across ALL documentation files.
This is the single most impactful doc fix -- every deployment example is currently wrong.
(Doc audit drift 1, config drift 1, stale code examples 2)

**Files to Modify:**

- `README.md` -- All deployment examples
- `CLAUDE.md` -- Deployment commands section
- `docs/CONFIGURATION.md` -- Demo mode example
- `docs/TROUBLESHOOTING.md` -- Any deployment references
- `.serena/memories/suggested_commands.md` -- Deployment command examples (lines 35-37)

**Prerequisites:** None

**Implementation Steps:**

1. Search ALL files recursively for `--project-name` (not just top-level and docs):
   `grep -rn "\-\-project-name" --include="*.md" .`
1. Replace every occurrence of `--project-name` with `--stack-name` in all matched files,
   including `.serena/memories/suggested_commands.md`
1. Verify the replacement is correct by checking `publish.py` argument parser for the
   exact flag name and syntax
1. Also update any surrounding context if needed (e.g., if the help text says "project
   name" it should match what publish.py calls it)

**Verification Checklist:**

- [ ] `grep -rn "\-\-project-name" --include="*.md" .` returns zero results (excluding
  plan docs)
- [ ] All deployment examples use `--stack-name`
- [ ] Examples match `publish.py --help` output

**Testing Instructions:**

- Run `python publish.py --help` and verify the documented flags match

**Commit Message Template:**

```text
docs: fix --project-name to --stack-name across all documentation

- CLI flag was renamed in publish.py but docs were never updated
- Fix deployment examples in README, CLAUDE.md, CONFIGURATION, TROUBLESHOOTING
```

### Task 2: Fix README Quick Start to Use uv

**Goal:** Replace pip/venv instructions with uv in README Quick Start. (Doc audit stale
code examples 1, eval onboarding finding)

**Files to Modify:**

- `README.md` -- Quick Start section

**Prerequisites:** None

**Implementation Steps:**

1. Find the Quick Start section in README.md that instructs users to create a venv and
   run `pip install -r requirements.txt`
1. Replace with the `uv`-based workflow:
   ```text
   uv sync
   ```
1. If the Quick Start also references `python -m venv`, remove that as well
1. Ensure the instructions mention that `uv` is required (link to uv installation docs
   if not already present in prerequisites)
1. Also fix `CLAUDE.md` line 57: the `sam local invoke` example references
   `tests/events/s3-put.json` which does not exist. Replace it with
   `tests/events/sqs-processing-message.json`, which is the closest match to a document
   processing event trigger. Available event files for reference:
   `get_configuration.json`, `query_kb_expired_session.json`, `query_kb_new_session.json`,
   `query_kb_with_session.json`, `s3_put_video.json`, `scrape-start.json`,
   `search_kb.json`, `sqs-discovery-message.json`, `sqs-processing-message.json`,
   `step_functions_media_success.json`.

**Verification Checklist:**

- [ ] `grep -n "pip install" README.md` returns zero results
- [ ] `grep -n "python -m venv" README.md` returns zero results
- [ ] Quick Start uses `uv sync`
- [ ] `CLAUDE.md` references an event file that actually exists in `tests/events/`

**Testing Instructions:**

- Verify the referenced event files exist: `ls tests/events/`
- Run `uv sync` to verify the command works

**Commit Message Template:**

```text
docs: update Quick Start to use uv and fix event file reference

- Replace pip/venv with uv sync in README Quick Start
- Fix CLAUDE.md sam local invoke to reference existing event file
```

### Task 3: Fix DEVELOPMENT.md Drift

**Goal:** Fix all drift, stale, and broken references in DEVELOPMENT.md. (Doc audit
drift 2-7, 11; stale 1-3; broken links 2-3)

**Files to Modify:**

- `docs/DEVELOPMENT.md` -- Multiple sections

**Prerequisites:** None

**Implementation Steps:**

1. Fix script name documentation (drift 2-5):
   - `npm run lint` description: change from "Auto-fix and lint" to "Check lint (no
     auto-fix). Use `npm run lint:fix` for auto-fix."
   - Remove reference to `npm run lint:backend` (does not exist)
   - Update `npm run lint:frontend` description to mention it also runs tsc
   - Remove references to `npm run format` and `npm run format:check` (do not exist)
1. Fix "State Management" claim (drift 6):
   - Change "AWS Amplify DataStore" to describe what the UI actually uses for state
     management (React state + Amplify for auth/API)
1. Fix directory names (drift 7, 11):
   - Change `zip_processor/` to `process_zip/`
   - Add `scrape.asl.json` and `reindex.asl.json` to statemachine directory listing
1. Fix test location claims (stale 1):
   - Remove claim about `lib/ragstack_common/test_*.py` -- all tests are in
     `tests/unit/python/`
1. Fix setup.py path (stale 2):
   - Change `lib/ragstack_common/setup.py` to `lib/setup.py`
1. Fix integration test script name (stale 3):
   - Change `npm run test:backend:integration` to `npm run test:integration`
1. Fix file references (broken links 2-3):
   - Change `src/ui/vite.config.ts` to `src/ui/vite.config.js`
   - Change `.github/workflows/test.yml` to `.github/workflows/ci.yml`
1. Fix event file reference (drift 9):
   - Change `tests/events/sample.json` to an actual event file that exists

**Verification Checklist:**

- [ ] No references to `lint:backend`, `format`, `format:check`, or
  `test:backend:integration` scripts that do not exist
- [ ] `zip_processor` replaced with `process_zip`
- [ ] All referenced file paths verified to exist
- [ ] `npm run lint` description accurately describes check-only behavior

**Testing Instructions:**

- For each referenced file path, verify it exists with `ls`
- For each referenced npm script, verify it exists in `package.json`

**Commit Message Template:**

```text
docs(development): fix 12 drift and stale findings

- Fix script descriptions to match package.json
- Fix directory names and file paths to match codebase
- Remove references to non-existent scripts and files
- Update state management description
```

### Task 4: Fix TROUBLESHOOTING.md DynamoDB Key Reference

**Goal:** Fix the DynamoDB partition key name in troubleshooting query example. (Doc audit
drift 10)

**Files to Modify:**

- `docs/TROUBLESHOOTING.md` -- DynamoDB query example

**Prerequisites:** None

**Implementation Steps:**

1. Find the DynamoDB query example around line 237-238 in TROUBLESHOOTING.md
1. Change `"PK"` to `"Configuration"` to match the actual partition key attribute name
   used in `lib/ragstack_common/config.py`
1. Verify the correct key name by checking the DynamoDB table definition in
   `template.yaml` (search for the config table resource)

**Verification Checklist:**

- [ ] `grep -n '"PK"' docs/TROUBLESHOOTING.md` returns zero results
- [ ] DynamoDB query example uses `"Configuration"` as the key attribute

**Testing Instructions:**

- Cross-reference with `template.yaml` DynamoDB table definition

**Commit Message Template:**

```text
docs(troubleshooting): fix DynamoDB partition key name in query example

- Change "PK" to "Configuration" to match actual table schema
```

### Task 5: Fix Config Caching Documentation Contradiction

**Goal:** Resolve the contradiction between "no caching" claims and the 60-second frontend
cache. (Doc audit config drift 2-3)

**Files to Modify:**

- `docs/CONFIGURATION.md` -- Clarify caching behavior
- `docs/RAGSTACK_CHAT.md` -- Ensure consistent caching description (if referenced)

**Prerequisites:** Phase 2 Task 2 (ConfigurationManager caching) -- the caching behavior
may have changed

**Implementation Steps:**

1. After Phase 2, ConfigurationManager now has request-scoped caching. Update the docs to
   accurately describe the current behavior:
   - Lambda-side: request-scoped cache (reads once per invocation, cleared per request)
   - Frontend-side: if there is a 60-second cache in the Amplify chat component, document
     it explicitly
1. In CONFIGURATION.md, find the "no caching" claims and update them:
   - Change "no caching issues" to describe the actual behavior: "Lambda reads config
     once per invocation (request-scoped cache). Changes take effect on the next Lambda
     invocation."
1. In CONFIGURATION.md, find the "Changes apply within 60 seconds" claim:
   - If this refers to the frontend Amplify component caching, clarify that this is
     client-side caching, not Lambda-side
   - If it is inaccurate, remove or correct it
1. Check RAGSTACK_CHAT.md line 151 for the 60-second claim and ensure consistency

**Verification Checklist:**

- [ ] No contradictory caching claims across docs
- [ ] Lambda caching behavior accurately described
- [ ] Frontend caching behavior (if any) accurately described and distinguished from
  Lambda behavior

**Testing Instructions:**

- Read through CONFIGURATION.md and RAGSTACK_CHAT.md to verify consistency

**Commit Message Template:**

```text
docs(configuration): resolve caching documentation contradictions

- Clarify Lambda uses request-scoped cache (once per invocation)
- Distinguish Lambda-side from frontend-side caching behavior
- Remove misleading "no caching" claims
```

### Task 6: Update Repository Structure in CLAUDE.md and DEVELOPMENT.md

**Goal:** Fix the severely abbreviated Lambda function listings. (Doc audit gaps 1-3, 5;
structure issues 1-2)

**Files to Modify:**

- `CLAUDE.md` -- Repository structure section
- `docs/DEVELOPMENT.md` -- Repository structure section
- `docs/ARCHITECTURE.md` -- Component table (add missing entries)

**Prerequisites:** Phase 3 complete (resolver split changes directory structure)

**Implementation Steps:**

1. For CLAUDE.md, the repository structure (lines 63-78) lists only 5 Lambda functions.
   Do NOT list all 32 -- that would be unmaintainable. Instead:
   - Keep the current abbreviated tree but add a comment: `# ... and 27 more (see
     docs/ARCHITECTURE.md for complete list)`
   - Or list the 8-10 most important Lambda functions with a note about the full list
1. For DEVELOPMENT.md, apply the same approach -- abbreviated tree with pointer to
   ARCHITECTURE.md
1. For ARCHITECTURE.md component table, add the three missing Lambda functions:
   - `admin_user_provisioner` -- brief description of what it does (check the code)
   - `initial_sync` -- brief description
   - `dlq_replay` -- brief description
1. Update CLAUDE.md repository structure to reflect the Phase 3 resolver split:
   - Show `src/lambda/appsync_resolvers/resolvers/` subdirectory

**Verification Checklist:**

- [ ] CLAUDE.md notes the abbreviated listing and points to ARCHITECTURE.md
- [ ] ARCHITECTURE.md lists `admin_user_provisioner`, `initial_sync`, `dlq_replay`
- [ ] CLAUDE.md shows the new `resolvers/` subdirectory under `appsync_resolvers`

**Testing Instructions:**

- Verify listed directories exist: `ls src/lambda/admin_user_provisioner/`,
  `ls src/lambda/initial_sync/`, `ls src/lambda/dlq_replay/`

**Commit Message Template:**

```text
docs: update repository structure and add missing Lambda functions

- Note abbreviated listings in CLAUDE.md and DEVELOPMENT.md
- Add admin_user_provisioner, initial_sync, dlq_replay to ARCHITECTURE.md
- Reflect resolver split in directory structure
```

### Task 7: Fix Documentation Index and Missing Links

**Goal:** Add missing documentation links to README index. (Doc audit gaps 4; structure
issues 3)

**Files to Modify:**

- `README.md` -- Documentation index section

**Prerequisites:** None

**Implementation Steps:**

1. Find the documentation index in README.md (around lines 204-213)
1. Add links for:
   - `docs/IMAGE_UPLOAD.md` (if it exists and is not linked)
   - `docs/API_REFERENCE.md` (if it exists and is not linked)
   - `docs/MIGRATION.md` (if it exists and is not linked)
1. Only add links for files that actually exist. Verify each path before adding.
1. Organize links logically (group by topic: setup, usage, reference, troubleshooting)

**Verification Checklist:**

- [ ] All `.md` files in `docs/` are linked from README.md or have a clear reason not to
  be (e.g., internal-only docs)
- [ ] All links in README.md point to files that exist

**Testing Instructions:**

- For each link added, verify the file exists: `ls docs/IMAGE_UPLOAD.md`, etc.

**Commit Message Template:**

```text
docs(readme): add missing documentation links to index

- Link IMAGE_UPLOAD.md, API_REFERENCE.md, MIGRATION.md from README
- Ensure all docs/ files are discoverable from README
```

## Phase Verification

1. Run `grep -rn "\-\-project-name" --include="*.md" .` -- should return zero results
   (excluding plan docs)
1. Run `grep -rn "pip install" README.md` -- should return zero results
1. Verify all referenced file paths in docs actually exist
1. Verify no contradictory caching claims remain
1. Verify ARCHITECTURE.md has all 32 Lambda functions (or explicitly notes which are
   excluded and why)
1. Verify git log shows 7 atomic commits with conventional commit messages

## Known Limitations

- The monolithic `template.yaml` (health audit finding 7) is NOT addressed in this plan.
  Splitting into nested stacks is a major infrastructure change with deployment risk that
  exceeds the scope of a remediation plan.
- The `useDocuments.ts` 614-line hook (health audit finding 20) and `Settings/index.tsx`
  992-line component (finding 21) are NOT split in this plan. They are lower priority than
  the appsync_resolvers monolith and can be tracked as follow-up work.
- The `sync_coordinator` sleep-polling pattern (health audit finding 11) is NOT addressed.
  Replacing it with Step Functions or SQS-based polling is an architectural change beyond
  remediation scope.
- httpx client-per-request in scraper (eval concern) is NOT addressed. It is an
  optimization best done when the scraper module is next modified.
