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

CHANGES_RESOLVED

### PLAN_REVIEW -- 2026-03-28 (revision 3)

All previously raised items verified as resolved:

1. README.md Phase Summary table now shows `~6k` for Phase 1, matching Phase-1.md
1. Phase-1 Tasks 1 and 4 correctly reflect reduced scope (verification-only and fixture cleanup)
1. Phase-3 Task 6 presents a single clear implementation strategy with no false starts
1. Phase-5 Task 1 includes `.serena/memories/suggested_commands.md` and uses recursive grep

No new issues found.

PLAN_APPROVED

## Resolved Feedback

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
