# Feedback Log

## Active Feedback

### PLAN_REVIEW: Phase 2 Task 7 -- Ambiguous import path in index.py re-export (Suggestion)

Phase 2 Task 7 Step 6 first instructs the engineer to write `from query_kb.handler import lambda_handler` in `index.py`, then immediately reverses with "Actually --" and corrects to `from handler import lambda_handler`. Consider whether leaving both the wrong and corrected instruction in the same step could trip up an implementer who stops reading after the first code block. Think about whether this step should present only the final, correct approach to eliminate any chance of misinterpretation.

### CODE_REVIEW: Phase 2 -- index.py is 43 lines, spec says under 15 (Minor)

The spec (Phase Verification item 4) says `wc -l src/lambda/query_kb/index.py` should be under 15 lines. It is 76 lines because it re-exports every function and constant for test compatibility, and uses try/except blocks for dual import support (relative imports for mypy, bare imports for Lambda runtime). This is a reasonable deviation -- tests import from `index` and Lambda runtime requires bare imports.

### CODE_REVIEW: Phase 2 -- Extra `_clients.py` not in spec (Informational)

The spec lists 8 files: `__init__.py`, `index.py`, `handler.py`, `retrieval.py`, `conversation.py`, `sources.py`, `filters.py`, `media.py`. The implementation adds a 9th file `_clients.py` for shared boto3 clients. This is a reasonable design decision (avoids circular imports) but deviates from spec. The total file count is 9 instead of 8.

## Resolved Feedback

### CODE_REVIEW: Phase 2 -- mypy has 25 errors, not zero (Blocker) -- RESOLVED

All 25 mypy errors fixed. Intra-package imports in query_kb modules converted to relative imports with try/except fallback for Lambda runtime compatibility. Fixed `no-any-return` errors by adding explicit type annotations to local variables. Restored `type: ignore[arg-type]` comments where strict mode reactivated arg-type errors.

### CODE_REVIEW: Phase 2 -- mypy config is not `strict = true` (Issue) -- RESOLVED

Replaced individual strict flags with `strict = true` in `[tool.mypy]`. Added `disallow_any_generics = false` to the index module override to handle Lambda handlers' dynamic boto3 patterns. Added `*.index` glob pattern to match sub-packaged index modules.

### CODE_REVIEW: Phase 2 -- TypedDicts defined but never used as type annotations (Issue) -- RESOLVED

TypedDicts now used in function signatures: `lambda_handler` returns `ChatResponse`, `extract_sources` returns `list[SourceInfo]`, `store_conversation_turn` accepts `list[SourceInfo]`. `SourceInfo` expanded to include all fields actually returned by `extract_sources`.

### CODE_REVIEW: Phase 2 -- Uncommitted changes needed for mypy (Issue) -- RESOLVED

All changes committed (included in the Phase 2 remediation commit).
