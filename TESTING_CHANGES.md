# Testing Changes & Consolidation Workflow

## Overview

This document explains the testing reorganization efforts to consolidate scattered test files across the RAGStack-Lambda repository into unified test suites organized by backend (Python/pytest) and frontend (JavaScript/vitest).

## Problem Statement

Tests were previously scattered in multiple locations:
- **Python tests**: `lib/ragstack_common/test_*.py` + `tests/unit/` (duplicate/inconsistent locations)
- **Frontend tests**: `src/ui/tests/`, `src/amplify-chat/tests/`, `amplify/data/*.test.ts` (separate configs)
- **Vitest versions**: Different versions across packages (0.34.0 vs 4.0.5)
- **No clear structure**: amplify backend tests had no test runner configured

## Solution: Three-Layer Test Architecture

### Layer 1: Backend Tests (Python/pytest)

**Location**: `tests/unit/python/`

**Contents**:
- Moved 6 utility tests from `lib/ragstack_common/test_*.py`
- Existing Lambda function tests in `tests/unit/`
- Integration tests in `tests/integration/`

**Running tests**:
```bash
npm run test:backend          # Run all unit tests (excludes integration)
npm run test:backend:integration  # Run integration tests
npm run test:backend:coverage     # With coverage report
```

**Key files**:
- `pytest.ini` - Pytest configuration
- `pyproject.toml` - Ruff linting rules for tests

### Layer 2: Frontend Tests (JavaScript/vitest)

**Location**: `src/ui/` (unified test runner)

**Contents**:
- **Original UI tests**: `src/ui/src/**/*.test.tsx`
- **Amplify Chat tests**: `src/ui/tests/amplify-chat/` (moved from `src/amplify-chat/tests/`)
- Unified vitest config discovers both test directories

**Running tests**:
```bash
npm run test:frontend        # Run all frontend tests (ui + amplify-chat)
cd src/ui && npm test        # Or run directly in src/ui
```

**Why consolidated?**
- AmplifyChat is a web component used within the UI app, not a separate published package
- Single vitest environment improves consistency (vitest 4.0.5)
- Unified setup/fixtures configuration
- Simpler CI/CD pipeline

**Key files**:
- `src/ui/vitest.config.js` - Discovers both `src/**/*.test.*` and `tests/**/*.test.*`
- `src/ui/tests/setup.ts` - Shared test setup (includes jest-dom matchers)
- `src/amplify-chat/package.json` - Test scripts removed (now in parent ui)

### Layer 3: Backend Config Tests (JavaScript/vitest)

**Location**: `amplify/`

**Contents**:
- `amplify/data/config.test.ts`
- `amplify/data/resource.test.ts`

**Running tests**:
```bash
npm run test:amplify         # Root script
cd amplify && npm test       # Or run directly in amplify/
```

**Key files**:
- `amplify/vitest.config.js` - New config (added v0.1)
- `amplify/package.json` - Test scripts added

## Root Package.json Scripts

```json
{
  "test:backend": "pytest tests/unit/python/",
  "test:frontend": "cd src/ui && npm test",
  "test:amplify": "cd amplify && npm test",
  "test": "npm run test:backend && npm run test:frontend",
  "test:all": "npm run lint && npm run test && npm run test:amplify"
}
```

## File Changes Summary

### Deleted
- `src/amplify-chat/tests/` (moved to `src/ui/tests/amplify-chat/`)
- `src/amplify-chat/vitest.config.ts` (not needed)
- `lib/ragstack_common/test_*.py` (moved to `tests/unit/python/`)
- All `__pycache__/` directories

### Created
- `src/ui/tests/amplify-chat/` (new location)
- `src/ui/tests/setup.ts` (shared jest-dom setup)
- `tests/unit/python/` directory with 6 moved tests
- `amplify/vitest.config.js` (new)

### Modified
- `src/ui/vitest.config.js` - Added test discovery for `tests/**/*.test.*`
- `amplify/package.json` - Added test scripts
- `src/amplify-chat/package.json` - Removed test scripts
- `package.json` - Updated test paths, removed old `test:amplify-chat`

## Path Fixes in Moved Tests

### `src/ui/tests/amplify-chat/inject-config.test.js`

When tests moved from `src/amplify-chat/tests/` to `src/ui/tests/amplify-chat/`, relative paths needed updating:

```javascript
// OLD (when in src/amplify-chat/tests/):
const testOutputsPath = path.join(__dirname, '../../../amplify_outputs.json');
const generatedConfigPath = path.join(__dirname, '../src/amplify-config.generated.ts');

// NEW (in src/ui/tests/amplify-chat/):
const testOutputsPath = path.join(__dirname, '../../../../../amplify_outputs.json');
const generatedConfigPath = path.join(__dirname, '../../../amplify-chat/src/amplify-config.generated.ts');

// Also updated execSync cwd paths:
cwd: path.join(__dirname, '../../../amplify-chat')
```

## Running All Tests

```bash
# Run everything
npm run test:all

# Or individually:
npm run test:backend
npm run test:frontend
npm run test:amplify
```

## Benefits

✓ **Single source of truth** for each test type
✓ **Consistent vitest versions** across frontend packages (4.0.5)
✓ **Simplified CI/CD** - clear test entry points
✓ **Better organization** - tests grouped by type (backend/frontend)
✓ **Easier debugging** - unified configs for each layer
✓ **Cleaner git history** - fewer scattered test directories

## Known Issues

- `inject-config.test.js` tests still have path resolution issues (need proper mock of amplify_outputs.json location)
- Some tests may need further investigation if they fail

## Next Steps

1. Fix remaining path issues in amplify-chat tests
2. Run full test suite to ensure all tests pass
3. Document test patterns and best practices
4. Consider adding pre-commit hooks for test validation
