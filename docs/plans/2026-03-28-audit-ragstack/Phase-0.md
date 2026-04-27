# Phase 0 -- Foundation

## Architecture Decision Records

### ADR-001: Remediation sequencing -- subtractive before additive

**Context:** Three audits produced overlapping findings. Fixing documentation before code
would create double-work. Adding guardrails before cleanup would generate false positives
on code about to be removed.

**Decision:** Sequence phases as HYGIENIST -> IMPLEMENTER -> FORTIFIER -> DOC-ENGINEER.

**Consequence:** Later phases may need to update earlier phase artifacts (e.g., new modules
from Phase 3 need docs in Phase 5). Each phase must leave tests green.

### ADR-002: Resolver split strategy -- domain modules with thin dispatcher

**Context:** `src/lambda/appsync_resolvers/index.py` is 3520 lines with 50+ functions.
Two options: (a) split into separate Lambda functions per resolver, or (b) split into
domain modules within the same Lambda.

**Decision:** Option (b) -- split into domain modules (`resolvers/documents.py`,
`resolvers/images.py`, `resolvers/scrape.py`, `resolvers/metadata.py`, `resolvers/chat.py`)
with a thin dispatcher in `index.py`. The Lambda function stays as one deployment unit.

**Rationale:** Splitting into separate Lambdas requires SAM template changes (already 5350
lines), new IAM roles, new AppSync resolver mappings, and risks deployment failure. Domain
modules achieve the maintainability goal without infrastructure changes.

**Consequence:** Cold start cost does not improve (all modules still imported). That is
acceptable -- the primary goal is maintainability and review-ability, not cold start.

### ADR-003: ConfigurationManager caching -- request-scoped, not TTL

**Context:** `ConfigurationManager.get_parameter()` makes 2 DynamoDB reads per call,
called ~8 times per chat request = ~16 reads. Options: (a) TTL cache with 60s expiry,
(b) request-scoped cache cleared per Lambda invocation.

**Decision:** Option (b) -- add a `_cache` dict to ConfigurationManager, populated on
first `get_effective_config()` call, with an explicit `clear_cache()` method called at
handler entry points.

**Rationale:** TTL caching in Lambda is risky because warm containers persist state.
Request-scoped caching gives the same performance benefit (1 read per invocation instead
of 16) without stale data risk.

### ADR-004: Import compatibility pattern -- single `_compat.py` module

**Context:** `query_kb/` uses a dual `try/except ImportError` pattern in every module to
handle both package-relative and flat-directory imports. This disables type checking with
`# type: ignore` on every fallback.

**Decision:** Create a single `query_kb/_compat.py` that handles the import resolution
once, re-exporting all shared symbols. Other modules import from `_compat`.

**Rationale:** Consolidates the ugly pattern into one place. Type checking works for all
consumer modules. The `_compat.py` itself still needs `# type: ignore` but it is isolated.

### ADR-005: Exception narrowing -- progressive, not all-at-once

**Context:** 129 `except Exception` catches across Lambda handlers. Narrowing all at once
is high risk.

**Decision:** Phase 4 narrows exceptions in the highest-impact files first (query_kb,
appsync_resolvers after split) where the audit identified specific failure modes.
Remaining files are tracked as follow-up work.

### ADR-006: S3 URI parsing consolidation -- use existing utility

**Context:** Inline `replace("s3://", "").split("/", 1)` appears 17 times across 6 files.
`lib/ragstack_common/storage.py` already exports `parse_s3_uri()`.

**Decision:** Replace all inline S3 URI parsing with calls to `parse_s3_uri()` from
`ragstack_common.storage`. Do not create a new abstraction.

### ADR-007: Filter/retrieval code deduplication -- extract shared module

**Context:** `search_kb/index.py` and `query_kb/filters.py` have copy-pasted
`extract_kb_scalar()` and lazy-init singletons. Both Lambdas share the ragstack_common
layer.

**Decision:** Move shared filter/retrieval logic into `lib/ragstack_common/` so both
Lambdas import from the shared layer. Keep Lambda-specific glue in each handler.

## Testing Strategy

- All changes must keep `npm run check` green (lint + test)
- New code requires unit tests; refactored code must maintain existing test coverage
- Python tests: `uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short -n auto`
- Frontend tests: `cd src/ui && npm test && cd ../ragstack-chat && npm test`
- Mocking: Use `unittest.mock.patch` for boto3 clients; use `pytest` fixtures from `tests/conftest.py`
- No live AWS resources in unit tests; integration tests are `@pytest.mark.integration`
- Lambda handler tests use `importlib.reload(index)` pattern to reset module-level state

## Commit Convention

All commits use conventional commits format:

```text
type(scope): brief description

- Detail 1
- Detail 2
```

Types: `fix`, `refactor`, `chore`, `docs`, `test`, `ci`, `style`

Scopes match the area being changed: `appsync-resolvers`, `query-kb`, `config`, `storage`,
`ui`, `docs`, `ci`, `deps`

## Shared Patterns

### Lazy-init singleton

The codebase uses a pattern of module-level `_variable = None` with a `get_variable()`
function. When creating new singletons or refactoring existing ones, follow this pattern:

```python
_client: SomeType | None = None

def get_client() -> SomeType:
    global _client
    if _client is None:
        _client = SomeType()
    return _client
```

### S3 URI parsing

Always use `from ragstack_common.storage import parse_s3_uri` rather than inline
`uri.replace("s3://", "").split("/", 1)`.

### Environment variable access

Use `os.environ.get("VAR")` with explicit error handling rather than bare
`os.environ["VAR"]` which causes opaque `KeyError` on cold start.
