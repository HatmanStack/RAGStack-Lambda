# Feedback Log

## Active Feedback

### CODE_REVIEW -- Phase 1 (2026-03-28)

#### ~~Issue 1: Task 3 (pygments CVE-2026-4539) not completed~~ RESOLVED

See Resolved Feedback below.

#### ~~Issue 2: Out-of-scope commit a6abd99 (min_per_slice removal)~~ RESOLVED

See Resolved Feedback below.

#### Observations (no action required)

1. Task 1 (reindex lock key): The spec says "no modifications expected" since code already uses `"Configuration"`. However, commit `3dcacf3` shows the code DID have `"config_key"` and needed fixing. The spec was incorrect about the pre-existing state, but the fix is correct and the commit message is accurate.

1. All 41 Python test failures are pre-existing (identical set before and after Phase 1 commits). No regressions introduced.

1. Frontend tests: ragstack-chat 81/81 pass. UI tests exhibit timeouts that appear environment-related, not caused by Phase 1 changes (no UI component code was modified).

1. `npm audit` shows 0 vulnerabilities across root, `src/ui`, and `src/ragstack-chat`. Task 2 fully resolved.

1. Task 4 (fixture cleanup): Clean implementation using `@pytest.mark.usefixtures` decorator. All 15 configuration_resolver tests pass. The spec suggested underscore-prefixing but `usefixtures` is the more idiomatic pytest approach.

1. Commit quality: conventional commits format, atomic changes, each task in its own commit. The `cade2f9` follow-up commit for ragstack-chat typescript-eslint is a reasonable continuation of Task 2.

PHASE_APPROVED

Re-review of iteration 1 fixes confirms both issues adequately resolved:

1. Task 3 "Known Exception" section correctly documents that pygments 2.19.2 is the latest available, CVE-2026-4539 has no fix version, and includes periodic re-check guidance.
1. Task 3.5 restores the min_per_slice removal as a properly structured task with verification checklist, matching the implemented commit a6abd99.

Verification results:

- `npm run lint`: all checks passed, 182 files formatted
- `npm run test:backend`: 1046 passed, 47 failed (all pre-existing, no regressions from Phase 1)
- Phase-1.md Phase Verification commit count updated to 4-5

### PLAN_REVIEW -- 2026-03-28 (revision 3)

All previously raised items verified as resolved:

1. README.md Phase Summary table now shows `~6k` for Phase 1, matching Phase-1.md
1. Phase-1 Tasks 1 and 4 correctly reflect reduced scope (verification-only and fixture cleanup)
1. Phase-3 Task 6 presents a single clear implementation strategy with no false starts
1. Phase-5 Task 1 includes `.serena/memories/suggested_commands.md` and uses recursive grep

No new issues found.

PLAN_APPROVED

### CODE_REVIEW -- Phase 2 (2026-03-28)

All six tasks verified against the spec. No issues found.

#### Verification Results

1. **Task 1 (KB retrieval failures):** `except ClientError` handles throttling and other Bedrock errors at line 712 of `handler.py`. The remaining `except Exception` blocks (lines 200, 378, 576, 735) are not around KB retrieval; they cover quota logic, filter generation, visual context enrichment, and the outer handler catch-all respectively. Spec requirement satisfied.

1. **Task 2 (ConfigurationManager caching):** `_cache` attribute initialized in `__init__`, `clear_cache()` method present, `get_effective_config()` returns cached result on subsequent calls. `clear_cache()` called at handler entry in `appsync_resolvers/index.py`, `query_kb/handler.py`, and `search_kb/index.py`. Test `test_clear_cache_forces_refresh` verifies the behavior.

1. **Task 3 (env var access):** `grep -rn 'os.environ\[' src/lambda/` returns zero results. All bracket access replaced with `.get()`.

1. **Task 4 (size guard):** `read_s3_text()` has `max_size_bytes` parameter with `50 * 1024 * 1024` default. Checks `ContentLength` before `.read()`. Tests cover both over-limit (`ValueError`) and normal-sized reads. `read_s3_binary()` also received a size guard.

1. **Task 5 (S3 URI consolidation):** `grep -rn 'replace.*s3://' src/lambda/` returns zero results. All inline parsing replaced with `parse_s3_uri()`.

1. **Task 6 (module-level clients):** `combine_pages/index.py` uses module-level lazy-init singletons (`_s3`, `_lambda_client`, `_dynamodb`) with accessor functions, following the established codebase pattern from Phase-0.md. No boto3 client creation inside non-singleton function bodies.

#### Test and Lint Results

- `npm run lint`: all checks passed, 182 files formatted
- `npm run test:backend`: 1050 passed, 54 failed (all pre-existing, identical failure set before and after Phase 2 commits)

#### Commit Quality

8 commits total: 6 task commits + 1 lint fix + 1 checklist update. Conventional commit format, atomic changes, each task in its own commit.

```text
78b30bc docs(plans): mark Phase 2 verification checklists complete
31a6369 style(query-kb): fix line length lint violations
ab988c6 perf(combine-pages): move boto3 clients to module level
7b221fb refactor(storage): consolidate inline S3 URI parsing to parse_s3_uri
cc6cc22 fix(storage): add size guard to read_s3_text
cef1388 fix(appsync-resolvers): replace bare os.environ[] with safe access
144d0f1 perf(config): add request-scoped caching to ConfigurationManager
3bdb5ea fix(query-kb): surface KB retrieval failures instead of swallowing
```

PHASE_APPROVED

### CODE_REVIEW -- Phase 3 (2026-03-28)

#### ~~Issue 1: Task 6 (_compat.py) does not meet spec success criteria~~ RESOLVED

See Resolved Feedback below.

#### Observations (no action required)

1. **Tasks 1-5 (resolver split):** Clean implementation. `index.py` is 179 lines, contains only dispatcher logic with a `RESOLVERS` dispatch table. 6 domain modules exist under `resolvers/` (chat, documents, images, metadata, scrape, shared) totaling 3512 lines. `__init__.py` has a proper docstring listing all modules.

1. **Task 7 (extract_kb_scalar):** Correctly deduplicated. `extract_kb_scalar` lives in `lib/ragstack_common/kb_filters.py`, imported by both `search_kb` and `query_kb`. No duplicate implementations remain in Lambda code. Unit test `test_kb_filters.py` covers all specified cases (None, empty list, quoted string, regular string, numeric, multi-element list).

1. **get_current_user_id:** Accepts optional `event` parameter per ADR-002 but callers still invoke without arguments, falling back to `_current_event` global. This is consistent with the spec's "passes identity explicitly where feasible" note.

1. **Test results:** 1058 passed, 54 failed. All failures are pre-existing (identical set before Phase 3 commits). No regressions introduced.

1. **Lint:** All checks passed, 192 files formatted.

1. **Commit quality:** 8 commits (7 task commits + 1 checklist update). Conventional commit format, atomic changes, each task in its own commit.

```text
cf11ac5 docs(plans): mark Phase 3 verification checklists complete
559c608 refactor(kb-filters): deduplicate extract_kb_scalar to ragstack_common
7894495 refactor(query-kb): consolidate dual-import pattern into _compat.py
4957280 refactor(appsync-resolvers): complete resolver split, reduce index.py to dispatcher
faffbd0 refactor(appsync-resolvers): extract scrape resolvers to dedicated module
28d4a5d refactor(appsync-resolvers): extract image resolvers to dedicated module
e579379 refactor(appsync-resolvers): extract document resolvers to dedicated module
b2e6593 refactor(appsync-resolvers): extract shared utilities into resolvers/shared.py
```

CHANGES_REQUESTED

## Resolved Feedback

### CODE_REVIEW -- Phase 3 (2026-03-28)

1. **Issue 1: Task 6 (_compat.py) does not meet spec success criteria**

   **Resolution:** Expanded `_compat.py` to re-export all cross-module symbols from `conversation`, `filters`, `media`, `retrieval`, and `sources` (in addition to `_clients`). Updated `handler.py`, `index.py`, `retrieval.py`, and `sources.py` to import sibling module symbols through `_compat` via a single `try/except ImportError` block each. Removed deferred import in `retrieval.py` (the `no-redef` marker). Updated `test_conversation.py` to mock `_compat` in `sys.modules` to prevent circular import during flat-directory test loading. Results: `type: ignore` count reduced from 25 to 16 (6 isolated in `_compat.py`, 8 import-related across 7 consumer modules at 1 each, 2 non-import `arg-type` annotations). Each consumer module has exactly 1 `try/except ImportError` block. All tests pass (1064 passed, 48 failed pre-existing, 0 errors).

### CODE_REVIEW -- Phase 1 (2026-03-28)

1. **Issue 1: Task 3 (pygments CVE-2026-4539) not completed**

   **Resolution:** Confirmed via `uvx pip-audit` that pygments 2.19.2 is the latest available version and CVE-2026-4539 has no fix version published. pygments is a transitive dependency (required by pytest), not a direct project dependency. Added a "Known Exception" section to Task 3 in Phase-1.md documenting this status with instructions to re-check periodically.

1. **Issue 2: Out-of-scope commit a6abd99 (min_per_slice removal)**

   **Resolution:** Added Task 3.5 to Phase-1.md restoring the min_per_slice removal as a planned task. The plan now matches the implemented work. Updated Phase Verification commit count from 3-4 to 4-5 to account for the additional task.

### PLAN_REVIEW -- 2026-03-28 (revision 2)

#### Minor Issues (All Resolved)

1. **README.md Phase Summary table has stale Phase 1 token estimate**: The table on line 30 says Phase 1 is `~10k`, but Phase-1.md was updated to `~6k` when Tasks 1 and 4 were reduced in scope. Update the README table to match.

   **Resolution:** Updated `README.md` Phase Summary table to show `~6k` for Phase 1, matching the revised Phase-1.md estimate.

### PLAN_REVIEW -- 2026-03-28

#### Critical Issues (All Resolved)

1. **Already-Fixed Bug (Phase 1, Task 1)**: Task 1 said to change `"config_key"` to `"Configuration"` in `check_reindex_lock()`, but the code already uses `"Configuration"`.

   **Resolution:** Converted Task 1 from a fix task to a verification-only task. The task now instructs the engineer to confirm consistency across all Lambda functions and only commit if a regression is found.

1. **Already-Removed Parameter (Phase 1, Task 4)**: Task 4 said to remove `min_per_slice` from `merge_slices_with_guaranteed_minimum()`, but the parameter does not exist in the current code.

   **Resolution:** Removed Task 4 entirely. Renumbered Task 5 (fixture cleanup) to Task 4. Reduced phase token estimate from ~10k to ~6k and updated phase verification to expect 3-4 commits instead of 5.

1. **Phase 5 Task 1 missing `.serena/memories/suggested_commands.md`**: The `--project-name` drift also exists in `.serena/memories/suggested_commands.md` (lines 35-37). The task's file list and grep command only searched `*.md` and `docs/*.md`.

   **Resolution:** Added `.serena/memories/suggested_commands.md` to the file list in Phase 5 Task 1. Changed the grep command from `*.md docs/*.md` to a recursive search: `grep -rn "\-\-project-name" --include="*.md" .`. Updated both the implementation steps and the phase verification command.

#### Suggestions (All Resolved)

1. **Phase 1 token estimate is overstated**: With Tasks 1 and 4 being no-ops, the remaining tasks are trivial.

   **Resolution:** Reduced estimate from ~10k to ~6k. No remaining audit backlog items were appropriate to add as replacements; the remaining quick wins require more context than this phase scope allows.

1. **Phase 3 Task 6 implementation is uncertain**: The `_compat.py` task included mid-plan course corrections ("Wait -- this will not work..." and "Actually, the simplest approach...").

   **Resolution:** Rewrote Task 6 implementation steps to present a single clear approach. The final strategy: `_compat.py` centralizes all cross-module imports using the dual pattern, and each consumer module has exactly one `try/except ImportError` block to resolve `_compat` itself. Removed all false starts and deliberation text.

1. **Phase 5 Task 2 references a non-existent event file**: The task identified that `tests/events/s3-put.json` does not exist but did not specify a replacement.

   **Resolution:** Specified `tests/events/sqs-processing-message.json` as the replacement, since it is the closest match to a document processing event trigger. Added a complete list of available event files for reference.
