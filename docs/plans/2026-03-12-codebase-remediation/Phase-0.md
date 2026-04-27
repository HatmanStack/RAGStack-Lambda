# Phase 0: Foundation

This phase defines the architecture decisions, conventions, and testing strategy that apply to all subsequent phases. Read this entirely before starting any implementation phase.

## Architecture Decisions

### ADR-1: Phase Ordering -- Tests, Types, Defense

Tests first creates a safety net for the refactoring in Phase 2 and infrastructure changes in Phase 3. Type rigor second because TypedDicts define the contracts used in the query_kb refactor. Defensive infrastructure last because it benefits from both test coverage and cleaner module boundaries.

### ADR-2: query_kb Refactor -- Package Split Only

Turn `src/lambda/query_kb/` into a Python package with `__init__.py` and separate modules. Move functions into logically grouped files with identical signatures. No logic changes. Existing tests catch import breakage.

### ADR-3: TypedDict Scope -- Critical Path Only

Define ~8-10 TypedDicts for structures crossing module boundaries (Bedrock responses, KB queries, document metadata, DynamoDB tracking items). Internal helper dicts stay as `dict[str, Any]`.

### ADR-4: mypy Strict in CI

All Python code must pass `mypy --strict`. Added to CI alongside ruff. Existing untyped code gets properly annotated. Minimize use of `# type: ignore` -- each instance requires a comment explaining why.

### ADR-5: DLQ Strategy -- Replay Lambda

DLQs already exist for all 5 SQS queues. Add a replay Lambda that moves messages from a specified DLQ back to its source queue. Manual trigger via CLI/console. Add CloudWatch alarms for all 5 DLQs (currently only ProcessingDLQ has one).

### ADR-6: Observability -- Consistent document_id in Logs

No X-Ray or Powertools (cost). Audit log statements for consistent inclusion of `document_id` / `image_id` / `scrape_id` while writing tests in Phase 1. No new infrastructure.

### ADR-7: S3 Size Guard -- HEAD Before Read

`read_s3_binary()` gets a configurable `max_size_bytes` parameter. HEAD the object first, raise `FileSizeLimitExceeded` if over limit. Only 2 call sites need updating.

### ADR-8: React Error Boundaries -- Route-Level + Critical Components

Wrap each route (Dashboard, Upload, Chat, Search, Settings, Scrape) plus ChatInterface and DocumentTable independently. ~8 boundaries total. Uses a single reusable `ErrorBoundary` component.

### ADR-9: Replace window.alert() with Cloudscape Flashbar

Flashbar is part of the existing Cloudscape Design System. Introduce a notification context at the layout level, passed down via React context. Replace all 4 `window.alert()` calls in `DocumentTable.tsx`.

## Tech Stack

No new runtime dependencies. Development/CI additions only:

- **mypy** -- Added to CI for Python type checking (`uv pip install mypy boto3-stubs[bedrock,bedrock-agent,bedrock-agent-runtime,s3,sqs,dynamodb,cognito-idp,stepfunctions,codebuild,cloudwatch]`)
- **boto3-stubs** -- Type stubs for AWS SDK, used by mypy only
- All existing: Python 3.13, pytest, ruff, React 19, Vite, Cloudscape Design System, Vitest

## Testing Strategy

### Python Test Patterns

All Lambda handler tests follow the same pattern established in the codebase:

1. **Module loading**: Use `importlib.util.spec_from_file_location()` to load Lambda handler modules dynamically, avoiding the `sys.modules['index']` caching problem. Give each module a unique name (e.g., `"admin_user_provisioner_index"`).

2. **AWS mocking**: Use `@patch` decorators or `patch.dict("os.environ", ...)` for environment variables and `MagicMock` for boto3 clients/resources. Never make real AWS calls.

3. **Environment variables**: Set via `monkeypatch.setenv()` in fixtures or `@patch.dict("os.environ", ...)`.

4. **Test file naming**: `test_{handler_name}.py` in `tests/unit/python/`.

5. **Test class grouping**: Group tests by function or behavior using `class TestFunctionName:`.

6. **Fixture pattern**: Use `autouse=True` fixtures for env vars that every test in a class needs.

**Reference implementation**: `tests/unit/python/test_process_media_lambda.py` is the canonical example of the module loading pattern.

### Frontend Test Patterns

- Vitest with happy-dom for React components
- Test files co-located with components: `Component.test.tsx`
- Use `@testing-library/react` for rendering and assertions

### Running Tests

```bash
# All backend tests
uv run pytest tests/unit/python/ -m 'not integration' -v --tb=short -n auto

# Single test file
uv run pytest tests/unit/python/test_admin_user_provisioner.py -v

# Frontend tests
cd src/ui && npm test
cd src/ragstack-chat && npm test

# Full check (lint + test)
npm run check
```

## Commit Convention

Format: `type(scope): brief description`

Types:
- `test` -- Adding or modifying tests
- `feat` -- New feature (DLQ replay Lambda, error boundaries, Flashbar)
- `refactor` -- Code restructuring with no behavior change (query_kb split, TypedDicts)
- `fix` -- Bug fix
- `ci` -- CI/CD changes (mypy in CI)
- `chore` -- Maintenance (dependency additions)

Scopes: Use the handler name, library module, or component name (e.g., `test(admin_user_provisioner)`, `refactor(query_kb)`, `feat(dlq-replay)`, `feat(ui-error-boundary)`).

Do NOT include `Co-Authored-By` or `Generated-By` lines.

## File Organization

### Lambda Handler Test File Template

```python
"""Unit tests for {HandlerName} Lambda."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_{handler_name}_module():
    """Load the {handler_name} index module dynamically."""
    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src" / "lambda" / "{handler_name}" / "index.py"
    ).resolve()

    spec = importlib.util.spec_from_file_location("{handler_name}_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["{handler_name}_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    """Set required environment variables for all tests."""
    env_vars = {
        # Add handler-specific env vars here
    }
    with patch.dict(os.environ, env_vars):
        yield
```

### Version

This remediation targets version 2.4.0 (current: 2.3.8).
