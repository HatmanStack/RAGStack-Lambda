# Phase 2: Type Rigor and query_kb Refactor

## Phase Goal

Introduce TypedDicts for critical-path cross-module contracts, enforce mypy strict mode across all Python code, and split the 1,824-line `query_kb/index.py` monolith into a well-organized package. The test safety net from Phase 1 catches any breakage.

**Success criteria:**
- ~8-10 TypedDicts defined for cross-module contracts
- `uv run mypy --strict lib/ src/lambda/` passes with zero errors
- mypy added to CI pipeline
- `query_kb/` is a Python package with 6 modules (handler, retrieval, conversation, sources, filters, media)
- All existing tests pass unchanged (no logic changes)
- `boto3-stubs` added to requirements.txt

**Estimated tokens:** ~45,000

## Prerequisites

- Phase 1 complete (test safety net in place)
- Python 3.13 environment with dependencies installed
- Understanding of Python `TypedDict`, `mypy --strict`, and Python package structure

---

## Task 1: Add mypy and boto3-stubs to Dependencies

**Goal:** Add mypy and boto3-stubs to the project's development dependencies so type checking can run locally and in CI.

**Files to Modify:**
- `requirements.txt` -- Add mypy and boto3-stubs with service-specific extras

**Files to Read First:**
- `requirements.txt` -- Current dependencies

**Prerequisites:**
- None

**Implementation Steps:**
- Add `mypy>=1.10.0` to the development dependencies section of `requirements.txt`.
- Add `boto3-stubs[bedrock,bedrock-agent,bedrock-agent-runtime,s3,sqs,dynamodb,cognito-idp,stepfunctions,codebuild,cloudwatch]` for typed AWS SDK stubs.
- Run `uv pip install -r requirements.txt` to verify installation.

**Verification Checklist:**
- [ ] `uv pip install -r requirements.txt` succeeds
- [ ] `uv run mypy --version` shows installed version
- [ ] `uv run mypy --strict lib/ragstack_common/logging_utils.py` runs (may have errors, that's expected)

**Commit Message Template:**
```
chore(deps): add mypy and boto3-stubs for type checking
```

---

## Task 2: Create mypy Configuration

**Goal:** Add mypy configuration to `pyproject.toml` with strict mode and appropriate per-module overrides.

**Files to Modify:**
- `pyproject.toml` -- Add `[tool.mypy]` section

**Files to Read First:**
- `pyproject.toml` -- Current configuration
- `lib/ragstack_common/__init__.py` -- Package structure

**Prerequisites:**
- Task 1 complete

**Implementation Steps:**
- Add a `[tool.mypy]` section to `pyproject.toml`:
  ```toml
  [tool.mypy]
  python_version = "3.13"
  strict = true
  warn_return_any = true
  warn_unused_configs = true

  # Lambda handlers all named index.py, need explicit paths
  files = ["lib/ragstack_common/", "src/lambda/"]

  # Third-party libraries without stubs
  [[tool.mypy.overrides]]
  module = [
      "ebooklib.*",
      "docx.*",
      "openpyxl.*",
      "fitz.*",
      "bs4.*",
      "markdownify.*",
      "lxml.*",
  ]
  ignore_missing_imports = true
  ```
- Adjust overrides based on what mypy reports. The goal is zero errors from our code, with third-party stubs explicitly ignored.
- Run `uv run mypy --strict lib/ragstack_common/logging_utils.py` as an initial test to verify config is picked up.

**Verification Checklist:**
- [ ] `pyproject.toml` has `[tool.mypy]` section with `strict = true`
- [ ] Third-party modules without stubs listed in overrides
- [ ] `uv run mypy lib/ragstack_common/logging_utils.py` runs without config errors

**Commit Message Template:**
```
ci(mypy): add mypy strict configuration to pyproject.toml
```

---

## Task 3: Define TypedDicts for Cross-Module Contracts

**Goal:** Create TypedDict definitions for the ~8-10 data structures that cross module boundaries in the critical path.

**Files to Create:**
- `lib/ragstack_common/types.py` -- Central TypedDict definitions

**Files to Read First:**
- `src/lambda/query_kb/index.py` -- Understand the data structures flowing through query_kb (this is the main consumer)
- `lib/ragstack_common/storage.py` -- S3 URI parsing return types
- `lib/ragstack_common/ingestion.py` -- Ingestion data structures
- `lib/ragstack_common/config.py` -- Configuration data structures
- `lib/ragstack_common/sources.py` -- Source citation structures

**Prerequisites:**
- Task 2 complete (mypy configured)

**Implementation Steps:**
- Read the query_kb handler and the ragstack_common modules to identify dict structures that flow between modules.
- Define TypedDicts in `lib/ragstack_common/types.py` using Python 3.13 syntax.
- Use `typing.TypedDict` (not `typing_extensions`).
- Use `str | None` syntax, not `Optional[str]`.
- Focus on these categories:
  1. **Bedrock responses** -- KB retrieve/retrieve-and-generate response structures
  2. **Chat/Query types** -- ChatResponse, QueryResult, ConversationTurn
  3. **Document metadata** -- DocumentTrackingItem (DynamoDB tracking table schema)
  4. **Source citations** -- SourceInfo, CitationSource
  5. **Filter structures** -- FilterConfig, FilterComponent
  6. **Ingestion types** -- IngestionResult, EmbeddingDocument
- Each TypedDict should have a docstring explaining what it represents and where it flows.
- Use `total=False` for TypedDicts where not all fields are always present.
- Export all types from `lib/ragstack_common/__init__.py`.

**Example structure:**
```python
"""Type definitions for cross-module contracts.

These TypedDicts define the shapes of data structures that flow between
ragstack_common modules and Lambda handlers. Internal helper dicts
remain as dict[str, Any].
"""

from typing import Any, TypedDict


class ChatResponse(TypedDict):
    """Response from the query_kb Lambda handler."""
    answer: str
    conversationId: str
    sources: list[dict[str, Any]]
    error: str | None


class SourceInfo(TypedDict, total=False):
    """A single source citation from KB retrieval."""
    documentId: str
    pageNumber: int | None
    s3Uri: str
    snippet: str
    score: float | None
```

**Verification Checklist:**
- [ ] `lib/ragstack_common/types.py` exists with 8-10 TypedDicts
- [ ] Each TypedDict has a docstring
- [ ] All use Python 3.13 syntax (`str | None`, `dict[str, Any]`)
- [ ] `uv run mypy lib/ragstack_common/types.py` passes
- [ ] Types are exported from `lib/ragstack_common/__init__.py`
- [ ] No logic changes in any existing file

**Testing Instructions:**
```bash
uv run mypy lib/ragstack_common/types.py
uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short -n auto
```

**Commit Message Template:**
```
refactor(types): add TypedDicts for cross-module contracts

- ChatResponse, SourceInfo, DocumentTrackingItem, etc.
- Critical-path types only, internal dicts remain dict[str, Any]
```

---

## Task 4: Annotate ragstack_common Library for mypy Strict

**Goal:** Add type annotations to all functions in `lib/ragstack_common/` so they pass `mypy --strict`.

**Files to Modify:**
- All `.py` files in `lib/ragstack_common/` (approximately 20+ files)

**Files to Read First:**
- `lib/ragstack_common/` -- All files (read each before annotating)

**Prerequisites:**
- Tasks 1-3 complete (mypy configured, TypedDicts defined)

**Implementation Steps:**
- Work through each file in `lib/ragstack_common/` alphabetically.
- For each file:
  1. Read the file.
  2. Add return type annotations to all functions.
  3. Add parameter type annotations where missing.
  4. Replace `Optional[X]` with `X | None` and `Dict[str, Any]` with `dict[str, Any]`.
  5. Use TypedDicts from `types.py` where applicable.
  6. Run `uv run mypy lib/ragstack_common/{file}.py` after each file.
- When encountering boto3 service calls, the `boto3-stubs` package provides types. Use `mypy_boto3_{service}` types where helpful.
- For callback/hook patterns where precise typing is difficult, use `Callable[..., Any]` with a `# type: ignore[misc]` comment explaining why.
- Minimize `# type: ignore` usage. Each instance must have an inline comment (e.g., `# type: ignore[no-untyped-def]  # boto3 mock`).

**Important constraint:** Do NOT change any runtime behavior. Only add annotations and fix type issues that mypy flags. If a type annotation would require changing function logic, document it as a follow-up.

**Verification Checklist:**
- [ ] `uv run mypy --strict lib/ragstack_common/` passes
- [ ] All functions have return type annotations
- [ ] All function parameters have type annotations
- [ ] No `Optional[X]` or `Dict[str, Any]` (use modern syntax)
- [ ] Each `# type: ignore` has an explanatory comment
- [ ] `uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short -n auto` still passes
- [ ] `uv run ruff check lib/` passes

**Commit Message Template:**
```
refactor(types): annotate ragstack_common for mypy strict compliance

- Add type annotations to all functions in lib/ragstack_common/
- Use TypedDicts for cross-module contracts
- Modern Python 3.13 syntax throughout
```

---

## Task 5: Annotate Lambda Handlers for mypy Strict

**Goal:** Add type annotations to all Lambda handler files so they pass `mypy --strict`.

**Files to Modify:**
- All `src/lambda/*/index.py` files (31 handlers)

**Files to Read First:**
- Read each handler before annotating

**Prerequisites:**
- Task 4 complete (library annotations in place, TypedDicts available)

**Implementation Steps:**
- Work through each handler alphabetically.
- For each handler:
  1. Read the file.
  2. Add return type annotations to all functions.
  3. Add parameter type annotations where missing.
  4. The `lambda_handler(event, context)` signature should be `lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any] | None`.
  5. Use TypedDicts from `ragstack_common.types` where applicable.
  6. Run `uv run mypy src/lambda/{handler}/index.py` after each handler.
- For handlers that use `ragstack_common` imports, the library annotations from Task 4 provide the base types.
- CloudFormation custom resource handlers (`admin_user_provisioner`, `initial_sync`, `kb_custom_resource`) have `context` parameter used for `log_stream_name` -- type as `Any` since `LambdaContext` type is from `awslambdaric` which may not have stubs.

**Important constraint:** Do NOT change any runtime behavior. Only add type annotations.

**Verification Checklist:**
- [ ] `uv run mypy --strict src/lambda/` passes
- [ ] All `lambda_handler` functions have type annotations
- [ ] All helper functions have type annotations
- [ ] `uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short -n auto` still passes
- [ ] `uv run ruff check src/lambda/` passes

**Commit Message Template:**
```
refactor(types): annotate all Lambda handlers for mypy strict compliance
```

---

## Task 6: Add mypy to CI Pipeline

**Goal:** Add mypy type checking to the CI pipeline so type regressions are caught automatically.

**Files to Modify:**
- `.github/workflows/ci.yml` -- Add mypy step to backend-lint job

**Files to Read First:**
- `.github/workflows/ci.yml` -- Current CI configuration

**Prerequisites:**
- Tasks 4-5 complete (all code passes mypy)

**Implementation Steps:**
- Add a mypy step to the `backend-lint` job in `.github/workflows/ci.yml`, after the ruff steps.
- The step should run: `uv run mypy --strict lib/ragstack_common/ src/lambda/`
- This goes in the existing `backend-lint` job since it's a static analysis tool (like ruff).

**Verification Checklist:**
- [ ] `.github/workflows/ci.yml` has a mypy step
- [ ] Step runs after dependency installation
- [ ] `uv run mypy --strict lib/ragstack_common/ src/lambda/` passes locally

**Commit Message Template:**
```
ci(mypy): add mypy strict type checking to CI pipeline
```

---

## Task 7: Split query_kb into a Python Package -- Create Package Structure

**Goal:** Convert `src/lambda/query_kb/` from a single `index.py` into a Python package with `__init__.py` and 6 modules.

**Files to Create:**
- `src/lambda/query_kb/__init__.py`
- `src/lambda/query_kb/handler.py`
- `src/lambda/query_kb/retrieval.py`
- `src/lambda/query_kb/conversation.py`
- `src/lambda/query_kb/sources.py`
- `src/lambda/query_kb/filters.py`
- `src/lambda/query_kb/media.py`

**Files to Read First:**
- `src/lambda/query_kb/index.py` -- The entire 1,824-line file (read in chunks)
- The brainstorm document's "query_kb Function Groupings" section for the intended split

**Prerequisites:**
- Tasks 1-6 complete (types defined, mypy passing)

**Implementation Steps:**

This is the most complex task in the plan. Follow these steps carefully:

1. **Read the entire `index.py`** in chunks (it's 1,824 lines). Map every function to its target module:
   - **media.py** (~350 lines): `fetch_image_for_converse`, `generate_media_url`, `extract_source_url_from_content`, `extract_image_caption_from_content`
   - **filters.py** (~220 lines): `extract_kb_scalar`, `get_config_manager`, `_get_filter_components`, `_get_filter_examples`
   - **conversation.py** (~100 lines): `get_conversation_history`, `store_conversation_turn`
   - **retrieval.py** (~270 lines): `_extract_id_pattern`, `_augment_with_id_lookup`, `build_retrieval_query`, `_rewrite_query_with_llm`, `build_conversation_messages`, `format_timestamp`
   - **sources.py** (~500 lines): `extract_sources` and its helpers (full citation parsing)
   - **handler.py** (~500 lines): `lambda_handler` and orchestration logic

2. **Create each module file** by moving the relevant functions from `index.py`. Keep function signatures identical. Add appropriate imports at the top of each module.

3. **Handle cross-module imports.** The modules will import from each other. Map the dependency graph:
   - `handler.py` imports from all other modules
   - `sources.py` may import from `media.py`
   - `retrieval.py` may import from `filters.py`
   - Avoid circular imports by structuring dependencies as a DAG

4. **Handle module-level state.** The current `index.py` has module-level boto3 clients:
   ```python
   s3_client = boto3.client("s3")
   dynamodb = boto3.resource("dynamodb")
   # etc.
   ```
   Move these to `handler.py` and pass them as parameters, OR keep them in a shared module. Read the code to determine which approach minimizes changes.

5. **Create `__init__.py`** that re-exports `lambda_handler` so SAM's `Handler: index.lambda_handler` still works:
   ```python
   from .handler import lambda_handler

   __all__ = ["lambda_handler"]
   ```

6. **Update `index.py`** to become a thin re-export:
   ```python
   """Query KB Lambda - re-exports from package modules.

   SAM Handler path: index.lambda_handler
   This file exists for backwards compatibility with the SAM handler path.
   """
   from query_kb.handler import lambda_handler  # noqa: F401
   ```

   Actually -- SAM's handler path `index.lambda_handler` expects to find `lambda_handler` in the `index` module. Since the directory is `query_kb/` and SAM will look for `index.py` in that directory, the simplest approach is:
   - Keep `index.py` as a re-export file
   - Put all logic in the package modules
   - `index.py` just does: `from handler import lambda_handler` (relative import within the Lambda's sys.path)

7. **Verify SAM handler resolution.** The SAM template has `Handler: index.lambda_handler`. When Lambda loads the code from the `query_kb/` directory, it adds that directory to `sys.path` and does `import index`. With `index.py` re-exporting `lambda_handler`, this should work unchanged. Read the SAM template entry for QueryKBFunction to confirm the handler path.

**Critical constraint:** No logic changes. Every function keeps its exact signature, behavior, and return values. This is a pure file reorganization.

**Verification Checklist:**
- [ ] `src/lambda/query_kb/` contains: `__init__.py`, `handler.py`, `retrieval.py`, `conversation.py`, `sources.py`, `filters.py`, `media.py`, `index.py`
- [ ] `index.py` is a thin re-export (under 15 lines)
- [ ] All functions have the same signatures as before
- [ ] No circular imports (verify by importing each module individually)
- [ ] `uv run mypy --strict src/lambda/query_kb/` passes
- [ ] `uv run ruff check src/lambda/query_kb/` passes
- [ ] All existing query_kb tests pass: `uv run pytest tests/unit/python/test_query_kb*.py -v`
- [ ] Full test suite passes: `uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short -n auto`

**Testing Instructions:**
```bash
# Verify imports work
python -c "import sys; sys.path.insert(0, 'src/lambda/query_kb'); from handler import lambda_handler; print('OK')"

# Run existing tests
uv run pytest tests/unit/python/test_query_kb.py tests/unit/python/test_query_kb_media.py -v

# Full suite
uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short -n auto
```

**Commit Message Template:**
```
refactor(query_kb): split 1824-line monolith into package modules

- handler.py: Lambda handler orchestration
- retrieval.py: KB query building and rewriting
- conversation.py: conversation history management
- sources.py: citation extraction and parsing
- filters.py: KB filter generation
- media.py: image/media URL generation
- index.py: thin re-export for SAM handler compatibility
- No logic changes, identical function signatures
```

---

## Task 8: Update query_kb Tests for Package Structure

**Goal:** Ensure existing query_kb tests work with the new package structure and add import smoke tests.

**Files to Modify:**
- `tests/unit/python/test_query_kb.py` -- May need import path adjustments
- `tests/unit/python/test_query_kb_media.py` -- May need import path adjustments

**Files to Read First:**
- `tests/unit/python/test_query_kb.py` -- Current test structure
- `tests/unit/python/test_query_kb_media.py` -- Current test structure

**Prerequisites:**
- Task 7 complete

**Implementation Steps:**
- Read the existing test files. They use `sys.path.insert(0, ...)` and `import index`.
- After the package split, `import index` should still work because `index.py` re-exports `lambda_handler`.
- If tests import specific functions from `index` (e.g., `from index import extract_source_url_from_content`), update those imports to go through the re-export or directly to the new module.
- Add smoke tests that verify each module can be imported independently.
- Run the full test suite to verify no regressions.

**Verification Checklist:**
- [ ] `uv run pytest tests/unit/python/test_query_kb.py -v` passes
- [ ] `uv run pytest tests/unit/python/test_query_kb_media.py -v` passes
- [ ] Full test suite passes
- [ ] No `import index` at module level (all inside test functions or fixtures)

**Commit Message Template:**
```
test(query_kb): update tests for package structure
```

---

## Phase Verification

After completing all tasks:

1. `uv run mypy --strict lib/ragstack_common/ src/lambda/` -- zero errors
2. `uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short -n auto` -- all tests pass
3. `uv run ruff check . && uv run ruff format . --check` -- all linting passes
4. `wc -l src/lambda/query_kb/index.py` -- under 15 lines (thin re-export)
5. `ls src/lambda/query_kb/*.py | wc -l` -- 8 files (init, index, handler, retrieval, conversation, sources, filters, media)
6. `.github/workflows/ci.yml` includes mypy step
7. `lib/ragstack_common/types.py` exists with 8-10 TypedDicts

**Known limitations:**
- Some `# type: ignore` comments may be necessary for dynamic patterns (e.g., DynamoDB response parsing, boto3 mock interactions in tests). Each must have an explanatory comment.
- The `tests/` directory is NOT included in mypy strict checking (test code with extensive mocking is impractical to type strictly).
- Third-party libraries without stubs (ebooklib, python-docx, openpyxl, PyMuPDF, beautifulsoup4, markdownify) are excluded from import checking via mypy overrides.
