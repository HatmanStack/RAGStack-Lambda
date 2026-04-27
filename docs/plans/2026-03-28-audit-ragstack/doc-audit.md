---
type: doc-health
date: 2026-03-28
doc_scope: All docs, no constraints
language_stack: Both JS/TS and Python
drift_prevention: Markdown linting (markdownlint) + link checking (lychee)
---

## DOCUMENTATION AUDIT

### SUMMARY
- Docs scanned: 34 Markdown files (14 in `docs/`, 10 in `docs/library/`, 3 in `src/`, plus README.md, CLAUDE.md, CHANGELOG.md, and ancillary files)
- Code modules scanned: 32 Lambda functions, 24 library modules, 2 frontend projects, 1 deployment script
- Total findings: **11 drift**, **5 gaps**, **3 stale**, **3 broken links/refs**, **3 config drift**

---

### DRIFT (doc exists, doesn't match code)

1. **`README.md:93`, `README.md:227-236`, `CLAUDE.md:49-53`, `docs/CONFIGURATION.md:401`, `docs/TROUBLESHOOTING.md:107`** --> `publish.py:964-966`
   - Doc says: `--project-name`
   - Code says: `--stack-name`
   - The CLI flag was renamed to `--stack-name` in `publish.py` but **every doc** still references `--project-name`. This is the single most critical finding -- every deployment command in documentation is wrong.

2. **`docs/DEVELOPMENT.md:36`** --> `package.json:8`
   - Doc says: `npm run lint` does "Auto-fix and lint all code"
   - Code says: `lint` script runs `--check` (no auto-fix). The auto-fix script is `lint:fix`.

3. **`docs/DEVELOPMENT.md:37`** --> `package.json`
   - Doc says: `npm run lint:backend` exists for "Lint Python (ruff)"
   - Code: No `lint:backend` script exists in `package.json`.

4. **`docs/DEVELOPMENT.md:38`** --> `package.json`
   - Doc says: `npm run lint:frontend` for "Lint React (ESLint)"
   - Code: `lint:frontend` exists but runs BOTH `src/ui` lint AND `src/ragstack-chat` lint with `tsc --noEmit`. More than just "ESLint".

5. **`docs/DEVELOPMENT.md:39`** --> `package.json`
   - Doc says: `npm run format` and `npm run format:check` exist
   - Code: Neither `format` nor `format:check` scripts exist in `package.json`.

6. **`docs/DEVELOPMENT.md:119`**
   - Doc says: "State Management: AWS Amplify DataStore"
   - Code: The UI uses AWS Amplify for auth/API calls but NOT Amplify DataStore for state management. No DataStore import found in any UI source file.

7. **`docs/DEVELOPMENT.md:78`**
   - Doc says: `src/lambda/` contains `zip_processor/`
   - Code: The directory is actually `process_zip/`, not `zip_processor/`.

8. **`CLAUDE.md:57`** --> `tests/events/`
   - Doc says: `sam local invoke ProcessDocumentFunction --event tests/events/s3-put.json`
   - Code: `tests/events/s3-put.json` does not exist. Available events: `s3_put_video.json`, `query_kb_*.json`, `scrape-start.json`, etc.

9. **`docs/DEVELOPMENT.md:47`** --> `tests/events/`
   - Doc says: `sam local invoke ProcessDocumentFunction -e tests/events/sample.json`
   - Code: `tests/events/sample.json` does not exist.

10. **`docs/TROUBLESHOOTING.md:237-238`** --> `lib/ragstack_common/config.py:291`
    - Doc says: DynamoDB key is `'{"PK": {"S": "Schema"}}'`
    - Code says: The partition key attribute is `Configuration`, not `PK`. Correct query would use `'{"Configuration": {"S": "Schema"}}'`.

11. **`docs/DEVELOPMENT.md:80-81`** --> actual statemachine directory
    - Doc says: `src/statemachine/` contains only `pipeline.asl.json`
    - Code: Directory also contains `scrape.asl.json` and `reindex.asl.json`.

---

### GAPS (code exists, no doc)

1. **`src/lambda/admin_user_provisioner/`** -- Lambda function not mentioned in ARCHITECTURE.md component table or any doc.

2. **`src/lambda/initial_sync/`** -- Lambda function not mentioned in ARCHITECTURE.md component table or any doc.

3. **`src/lambda/dlq_replay/`** -- Lambda function not mentioned in ARCHITECTURE.md component table. (Has tests in `tests/unit/python/test_dlq_replay.py`.)

4. **`docs/IMAGE_UPLOAD.md`** -- This doc exists but is not linked from README.md documentation section or any navigation index.

5. **`CLAUDE.md` repository structure** (lines 63-78) -- Lists only 5 Lambda functions (`process_document`, `ingest_to_kb`, `query_kb`, `appsync_resolvers`, `configuration_resolver`). The actual `src/lambda/` directory has 32 Lambda functions. Massive undercount that could mislead contributors.

---

### STALE (doc exists, code doesn't)

1. **`docs/DEVELOPMENT.md:147`** -- "Unit tests: Located in `tests/unit/` and `lib/ragstack_common/test_*.py`"
   - No `test_*.py` files exist in `lib/ragstack_common/`. All library tests are in `tests/unit/python/`.

2. **`docs/DEVELOPMENT.md:141`** -- "Common libraries should go in lib/ragstack_common/setup.py"
   - The packaging file is at `lib/setup.py`, not `lib/ragstack_common/setup.py`.

3. **`docs/DEVELOPMENT.md:153-154`** -- Claims `npm run test:backend:integration` script exists.
   - No such script in `package.json`. The actual integration test command is `npm run test:integration`.

---

### BROKEN LINKS / REFERENCES

1. **`CLAUDE.md:57`** -- References `tests/events/s3-put.json` which does not exist.

2. **`docs/DEVELOPMENT.md:87`** -- References `src/ui/vite.config.ts`
   - Actual file is `src/ui/vite.config.js` (JavaScript, not TypeScript).

3. **`docs/DEVELOPMENT.md:257`** -- References CI workflow as `.github/workflows/test.yml`
   - Actual file is `.github/workflows/ci.yml`.

---

### STALE CODE EXAMPLES

1. **`README.md:86-89`** -- Quick Start instructs:
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   But CLAUDE.md and project conventions say to use `uv` for all Python package management. The README contradicts the project's own standard toolchain.

2. **All deployment examples across all docs** -- Use `--project-name` which does not exist as a CLI flag. The correct flag is `--stack-name`.

---

### CONFIG DRIFT

1. **`docs/CONFIGURATION.md:401`** -- Demo mode enable command uses `--project-name demo` but publish.py expects `--stack-name`.

2. **`docs/CONFIGURATION.md:150`** -- States "Changes apply within 60 seconds (DynamoDB config cache)" for document access settings. But CONFIGURATION.md header (line 3) and DEVELOPMENT.md ADR-001 (line 222) both state "no caching" -- "reads from DynamoDB table" with "no caching issues". The 60-second claim in RAGSTACK_CHAT.md line 151 contradicts the "no caching" claim elsewhere. One of these is wrong.

3. **`docs/TROUBLESHOOTING.md:189`** -- "Config cached 60s (Amplify chat)" confirms there IS caching on the frontend side, but this contradicts the prominent "no caching" claim in CONFIGURATION.md line 3 and DEVELOPMENT.md ADR-001. The docs should clarify: Lambda reads are uncached, but the Amplify frontend caches for 60s.

---

### STRUCTURE ISSUES

1. **CLAUDE.md and DEVELOPMENT.md repository trees** are severely abbreviated. CLAUDE.md lists 5 Lambda functions; DEVELOPMENT.md lists 15. The actual codebase has 32 Lambda functions. Both trees should either be complete or explicitly state they are abbreviated.

2. **`docs/ARCHITECTURE.md`** component table (lines 20-49) is the most complete Lambda listing but is still missing `admin_user_provisioner`, `initial_sync`, and `dlq_replay`.

3. **Documentation index** in README.md (lines 204-213) is missing links to: `docs/IMAGE_UPLOAD.md`, `docs/API_REFERENCE.md`, `docs/MIGRATION.md`.
