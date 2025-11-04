# Testing Architecture: Separated Package-Level Tests

## Overview

This document explains the testing architecture for RAGStack-Lambda. Tests are organized by package, with each package maintaining its own test runner and configuration. This preserves package boundaries and ensures proper module resolution.

## Architecture Principle: Respect Package Boundaries

Each package has its own test environment because:
- **tsconfig.json differs** - Each package defines its own path aliases and compiler options
- **package.json differs** - Each package has different dependencies and dev dependencies
- **Module resolution differs** - Cross-package imports can fail without complex configuration
- **Test environment differs** - Different test frameworks and setup requirements

Attempting to consolidate tests across packages breaks module resolution and test isolation.

## Three-Layer Test Architecture

### Layer 1: Backend Tests (Python/pytest)

**Location**: `tests/unit/python/`

**Contents**:
- 6 utility tests moved from `lib/ragstack_common/test_*.py`
- Lambda function tests
- Integration tests in `tests/integration/`

**Running tests**:
```bash
npm run test:backend          # Unit tests (excludes integration)
npm run test:backend:integration  # Integration tests
npm run test:backend:coverage     # With coverage report
```

**Why separate**: Python tests need pytest, not vitest. Completely different test runner.

---

### Layer 2: AmplifyChat Component Tests

**Location**: `src/amplify-chat/tests/`

**Package**: `@ragstack/amplify-chat` (published NPM package)

**Contents**:
- `tests/types.test.ts` - Type definitions
- `tests/AmplifyChat.wc.test.ts` - Web component tests
- Vitest v0.34.0 configuration
- Local test setup with jest-dom matchers

**Running tests**:
```bash
npm run test:amplify-chat     # Root script
cd src/amplify-chat && npm test  # Or run directly
```

**Why separate**:
- AmplifyChat is a published NPM package with its own module boundaries
- Uses older vitest v0.34.0 (different from UI package)
- Has its own tsconfig with specific path aliases
- Must run in its own vitest environment for proper module resolution

**Key files**:
- `src/amplify-chat/vitest.config.ts` - Package-level config
- `src/amplify-chat/package.json` - Test scripts and dependencies
- `src/amplify-chat/tsconfig.json` - Path aliases for this package

---

### Layer 3: UI Package Tests

**Location**: `src/ui/tests/` and `src/ui/src/**/*.test.tsx`

**Package**: Standalone UI application

**Contents**:
- Original UI component tests (`src/ui/src/**/*.test.tsx`)
- Shared test setup and fixtures
- Vitest v4.0.5 configuration

**Running tests**:
```bash
npm run test:frontend        # Root script
cd src/ui && npm test        # Or run directly
```

**Key files**:
- `src/ui/vitest.config.js` - Only discovers UI tests, not amplify-chat tests
- `src/ui/tests/setup.ts` - Shared test setup (jest-dom matchers)
- `src/ui/package.json` - Test scripts and v4.0.5 vitest

---

### Layer 4: Amplify Backend Config Tests

**Location**: `amplify/`

**Contents**:
- `amplify/data/config.test.ts`
- `amplify/data/resource.test.ts`

**Running tests**:
```bash
npm run test:amplify         # Root script
cd amplify && npm test       # Or run directly
```

**Key files**:
- `amplify/vitest.config.js` - Package-level config
- `amplify/package.json` - Test scripts

---

## Root Package.json Scripts

```json
{
  "test:backend": "uv run pytest tests/unit/python/ -m 'not integration'",
  "test:backend:integration": "uv run pytest -m integration",
  "test:backend:coverage": "uv run pytest tests/unit/python/ -m 'not integration' --cov=lib --cov=src/lambda --cov-report=html --cov-report=term --cov-report=xml",
  "test:frontend": "cd src/ui && npm test -- --run",
  "test:amplify-chat": "cd src/amplify-chat && npm test -- --run",
  "test:amplify": "cd amplify && npm test -- --run",
  "test": "npm run test:backend && npm run test:frontend",
  "test:all": "npm run lint && npm run test && npm run test:amplify-chat && npm run test:amplify"
}
```

---

## Why Not Consolidate Frontend Tests?

**Attempted**: Moving AmplifyChat tests into src/ui/tests/ with a unified vitest config

**Problem**: Module resolution failures
- AmplifyChat package has `vitest v0.34.0`, UI has `v4.0.5` (incompatible versions)
- AmplifyChat's tsconfig defines different path aliases than UI's tsconfig
- vitest can't resolve `src/amplify-chat/src/components/` from `src/ui/vitest.config.js`
- Cross-package imports break without manual configuration

**Solution**: Keep each package's tests in its own environment
- AmplifyChat tests run with AmplifyChat's vitest and tsconfig
- UI tests run with UI's vitest and tsconfig
- Each has proper module resolution for its own dependencies
- Root-level scripts still provide unified test execution

---

## Running All Tests

```bash
# Run everything (backend + frontend + amplify-chat + amplify)
npm run test:all

# Or selectively:
npm run test:backend
npm run test:frontend
npm run test:amplify-chat
npm run test:amplify
```

---

## Benefits of Separated Architecture

✓ **Proper module resolution** - Each package tests itself correctly
✓ **Package isolation** - Tests don't interfere across package boundaries
✓ **Independent configuration** - Each package has correct tsconfig and dependencies
✓ **Clear structure** - Each package owns its tests
✓ **Maintained vitest versions** - No version conflicts (0.34.0 vs 4.0.5)
✓ **Unified execution** - Root scripts still run all tests together
✓ **Publishable packages** - AmplifyChat package includes its own test suite

---

## Known Issues

- AmplifyChat tests may fail if path resolution isn't correct
- Cross-package test imports not supported (by design)
