---
type: repo-health
date: 2026-03-28
goal: General health check — scan all 4 vectors equally
deployment_target: Serverless (Lambda)
scope: Full repo, no constraints
existing_tooling: Full setup — linters, CI pipeline, pre-commit hooks, type checking
---

## CODEBASE HEALTH AUDIT

### EXECUTIVE SUMMARY
- **Overall health: FAIR**
- **Biggest structural risk:** `src/lambda/appsync_resolvers/index.py` is a 3520-line god module containing 50+ functions handling every GraphQL resolver in one Lambda, with module-level global mutable state and 7 boto3 clients initialized at import time
- **Biggest operational risk:** Reindex lock check in `appsync_resolvers/index.py:129` uses wrong DynamoDB key (`config_key`) while `reindex_kb/index.py:77` writes with key `Configuration` -- the lock is never detected by the resolver, defeating concurrent operation protection
- **Total findings: 3 critical, 6 high, 8 medium, 5 low**

---

### TECH DEBT LEDGER

#### CRITICAL

1. **[Operational Debt]** `src/lambda/appsync_resolvers/index.py:129` vs `src/lambda/reindex_kb/index.py:77`
   - **The Debt:** Reindex lock key mismatch. `appsync_resolvers` reads with `Key={"config_key": REINDEX_LOCK_KEY}` while `reindex_kb` writes with `Key={"Configuration": REINDEX_LOCK_KEY}`. The `queue_processor/index.py:50` correctly uses `{"Configuration": ...}`. The lock set by `reindex_kb` will never be found by `appsync_resolvers`' `check_reindex_lock()`.
   - **The Risk:** Document operations (reprocess, reindex, delete) proceed during a full KB reindex, potentially ingesting into an old KB that gets deleted, causing permanent data loss.

2. **[Structural Debt]** `src/lambda/appsync_resolvers/index.py:1-3520`
   - **The Debt:** Single 3520-line file containing 50+ functions for every AppSync resolver (documents, scraping, images, captions, metadata, chat, reindex). All share one Lambda with 7 module-level boto3 clients (`s3`, `dynamodb`, `sfn`, `lambda_client`, `bedrock_agent`, `dynamodb_client`, `bedrock_runtime`) initialized at import time, plus global mutable state (`_current_event`, `_config_manager`).
   - **The Risk:** Every cold start pays for all 7 client initializations even if the resolver only needs 1. A bug in any resolver risks the entire API surface. The file is beyond practical code-review scale. The `_current_event` global couples identity propagation to module-level mutable state.

3. **[Operational Debt]** `src/lambda/query_kb/handler.py:425-426`
   - **The Debt:** Knowledge Base retrieval failure is caught by a bare `except Exception` that logs a warning and continues execution with an empty `retrieval_results` list. The handler proceeds to generate an LLM response with "No relevant information found" context.
   - **The Risk:** Any Bedrock API failure (throttling, timeout, misconfiguration) is silently swallowed. The user receives an LLM hallucination based on zero context rather than being told the system failed. No error propagation to the frontend.

#### HIGH

4. **[Structural Debt]** `src/lambda/appsync_resolvers/index.py` (16 occurrences) vs `lib/ragstack_common/storage.py:45`
   - **The Debt:** Inline S3 URI parsing via `uri.replace("s3://", "").split("/", 1)` is duplicated at least 16 times across `appsync_resolvers`, `query_kb/sources.py`, `query_kb/handler.py`, and `process_image/index.py`, despite `parse_s3_uri()` existing in `lib/ragstack_common/storage.py`.
   - **The Risk:** Inconsistent error handling for malformed URIs across duplicated implementations. One location may handle edge cases (empty bucket, missing key) while others do not.

5. **[Structural Debt]** `src/lambda/search_kb/index.py:50-65,99-122` vs `src/lambda/query_kb/filters.py:24-38,66-89`
   - **The Debt:** `extract_kb_scalar()` and `_get_filter_components()` are copy-pasted between `search_kb` and `query_kb`. Both lazy-initialize identical `KeyLibrary`, `FilterGenerator`, and `MultiSliceRetriever` singletons with identical logic.
   - **The Risk:** Feature drift -- changes to filter behavior in one path may not propagate to the other, causing inconsistent search vs. chat results.

6. **[Structural Debt]** Lazy-init singleton pattern duplicated across 8+ Lambda handlers
   - **The Debt:** `get_config_manager()`, `get_key_library()`, `get_metadata_extractor()` are independently implemented with `global` mutable state in `appsync_resolvers`, `query_kb/filters.py`, `search_kb`, `reindex_kb`, `process_image`, `ingest_to_kb`, `metadata_analyzer`, `ingest_media`.
   - **The Risk:** Boilerplate duplication increases maintenance burden. Each implementation has slightly different initialization logic (some return `None`, some raise).

7. **[Architectural Debt]** `template.yaml:1-5350` (5350 lines, 166 resources)
   - **The Debt:** Single monolithic CloudFormation template with 32 Lambda functions, 38 AppSync resolvers, 10 SQS queues, 7 DynamoDB tables, 3 Step Functions state machines, 8 EventBridge rules, and 8 CloudWatch alarms.
   - **The Risk:** Approaching CloudFormation resource limits (500 resources after transforms). Deployment is all-or-nothing -- a typo in a scrape-related resource blocks deployment of unrelated chat features. Change blast radius is the entire stack.

8. **[Operational Debt]** `src/lambda/appsync_resolvers/index.py:66-79` (cold start impact)
   - **The Debt:** Seven boto3 clients initialized at module level: `s3`, `dynamodb`, `sfn`, `lambda_client`, `bedrock_agent`, `dynamodb_client`, `bedrock_runtime`. All are created on every cold start regardless of which resolver is invoked.
   - **The Risk:** Unnecessary cold start latency. A `getDocument` call (needs only DynamoDB) still initializes Bedrock, Step Functions, and Lambda clients. Each boto3 client creation involves HTTP connection setup and credential resolution.

9. **[Operational Debt]** `src/lambda/reindex_kb/index.py:1-1502`
   - **The Debt:** 1502-line Lambda handler performing full KB migration with inline metadata extraction, S3 operations, DynamoDB updates, and Bedrock ingestion in a single execution context.
   - **The Risk:** At 15-minute Lambda max timeout, large knowledge bases may timeout mid-migration leaving the KB in an inconsistent state. The lock release in `finally` depends on Lambda completing normally.

#### MEDIUM

10. **[Code Hygiene]** `src/lambda/query_kb/handler.py:19-67`
    - **The Debt:** Dual import pattern with `try/except ImportError` to handle both package-relative and flat-directory imports, requiring `# type: ignore[import-not-found,no-redef]` on every fallback import. Repeated across `handler.py`, `retrieval.py`, `conversation.py`, `filters.py`.
    - **The Risk:** Type checking is partially disabled for these modules. The dual import pattern obscures actual import errors during development.

11. **[Operational Debt]** `src/lambda/sync_coordinator/index.py:64-92`
    - **The Debt:** Synchronous polling loop with `time.sleep(10)` inside a Lambda function to wait for KB sync completion, consuming Lambda execution time while idle.
    - **The Risk:** Lambda billed for idle sleep time. With `ReservedConcurrentExecutions=1`, the single instance is blocked during polling, queuing all new sync requests.

12. **[Code Hygiene]** `src/ui/src/hooks/useDocuments.ts:527-567`
    - **The Debt:** Three subscription setups use `as unknown as string` then `as any` type casts on GraphQL client calls, with eslint-disable comments for each.
    - **The Risk:** Type safety completely bypassed for the real-time subscription layer -- the most error-prone part of the frontend.

13. **[Structural Debt]** `src/lambda/combine_pages/index.py:55,102`
    - **The Debt:** boto3 clients created inside helper functions rather than at module level, counter to Lambda best practices for connection reuse across warm invocations.
    - **The Risk:** Each invocation creates new HTTP connections to AWS services rather than reusing them, adding latency.

14. **[Operational Debt]** npm audit: 5 vulnerabilities (1 moderate, 4 high)
    - **The Debt:** `rollup` (high -- arbitrary file write via path traversal), `yaml` in vitest (moderate -- stack overflow via deep nesting). All fixable via `npm audit fix`.
    - **The Risk:** Supply chain vulnerability in build tooling. While not deployed to production, compromised build pipeline could inject malicious code.

15. **[Code Hygiene]** Python vulnerability: `pygments 2.19.2` (CVE-2026-4539)
    - **The Debt:** Known vulnerability in dev dependency.
    - **The Risk:** Development-only dependency, not deployed to Lambda, but still a supply chain risk in CI.

16. **[Structural Debt]** `lib/ragstack_common/multislice_retriever.py:141`
    - **The Debt:** `min_per_slice` parameter in `merge_slices_with_guaranteed_minimum()` is accepted but never used (confirmed by vulture and docstring "Unused, kept for API compatibility").
    - **The Risk:** Misleading API surface -- callers pass `min_per_slice=min(3, num_results)` (line 378) believing it affects behavior when it does not.

17. **[Code Hygiene]** `src/ui/src/main.tsx:11`
    - **The Debt:** `Amplify.configure(awsConfig as any)` casts away type safety on the core configuration object.
    - **The Risk:** Configuration structure changes in Amplify SDK updates will not be caught by TypeScript at compile time.

#### LOW

18. **[Code Hygiene]** `src/lambda/configuration_resolver/test_handler.py` (12 instances)
    - **The Debt:** Unused `mock_env` fixture variables at lines 56, 74, 91, 99, 118, 141, 161, 171, 177, 187, 207, 218.
    - **The Risk:** Test code readability -- unclear whether the fixtures are needed for side effects or are simply dead test setup.

19. **[Code Hygiene]** `src/lambda/appsync_resolvers/index.py:1096`
    - **The Debt:** Silent `pass` in `except ClientError` when reading metadata sidecars during scraped content reindexing.
    - **The Risk:** Missing sidecar files during reindex are silently ignored -- may cause metadata to be lost without any indication.

20. **[Structural Debt]** `src/ui/src/hooks/useDocuments.ts` (614 lines)
    - **The Debt:** Single hook managing document list, image list, scrape job list, all three subscription types, and all CRUD operations.
    - **The Risk:** High cognitive load for maintenance. State management for three entity types interleaved in one hook.

21. **[Structural Debt]** `src/ui/src/components/Settings/index.tsx` (992 lines)
    - **The Debt:** Largest frontend component at 992 lines, handling all admin settings in a single file.
    - **The Risk:** Difficult to test and maintain individual setting sections independently.

22. **[Code Hygiene]** `src/lambda/appsync_resolvers/index.py:214-215`
    - **The Debt:** `global _current_event` stores the AppSync event in a module-level variable so that `get_current_user_id()` can access identity without explicit parameter passing.
    - **The Risk:** Fragile implicit coupling -- any refactor that processes events in non-sequential order (batching, async) would break identity resolution silently.

---

### QUICK WINS

1. `src/lambda/appsync_resolvers/index.py:129` -- Change `"config_key"` to `"Configuration"` to match the key used by `reindex_kb/index.py:77` and `queue_processor/index.py:50`. (estimated effort: < 15 minutes)
2. `npm audit fix` -- Resolve 5 npm vulnerabilities in build tooling. (estimated effort: < 15 minutes)
3. `lib/ragstack_common/multislice_retriever.py:141` -- Remove unused `min_per_slice` parameter or implement the documented minimum-per-slice guarantee. (estimated effort: < 1 hour)

---

### AUTOMATED SCAN RESULTS

**Dead code (vulture):**
- 1 unused variable in production code: `min_per_slice` in `multislice_retriever.py:141`
- 12 unused `mock_env` variables in `configuration_resolver/test_handler.py` (test fixtures, likely needed for side effects)

**Vulnerability scan (npm audit):**
- 4 high severity: rollup arbitrary file write (GHSA-mw96-cpmx-2vgc)
- 1 moderate: yaml stack overflow (GHSA-48c2-rrv3-qjmp)
- All fixable via `npm audit fix`

**Vulnerability scan (pip-audit):**
- 1 known vulnerability: pygments 2.19.2 (CVE-2026-4539), dev-only dependency

**Secrets scan:**
- No hardcoded credentials, API keys, or high-entropy strings found in source
- `.gitignore` properly excludes `.env`, `.env.local`, `.env.amplify`, and token files

**Git hygiene:**
- Clean history with conventional commits
- No committed build artifacts
- `.gitignore` comprehensive for Python, Node, AWS SAM, and IDE files
