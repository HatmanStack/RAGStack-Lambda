# Task Completion Checklist

## Before Declaring a Task Complete

### 1. Run Linting
```bash
npm run lint        # Python (ruff)
npm run lint:fix    # Auto-fix if needed
```

For frontend changes:
```bash
npm run lint:frontend  # ESLint + TypeScript check
```

### 2. Run Tests
```bash
npm run test:backend   # Python unit tests
npm run test:frontend  # Frontend tests (if UI changed)
```

Or run specific test file:
```bash
uv run pytest tests/unit/python/test_<file>.py -v
```

### 3. Verify Git State
```bash
git worktree list  # Ensure you're in the correct worktree
git status         # Review changed files
```

### 4. Do NOT Deploy
- Never run `sam build`, `sam deploy`, `cdk deploy`, or `publish.py` without explicit user request
- Make code changes, run tests/lint, but let user handle deployment

## Problem-Solving Discipline

Before declaring any fix complete:
1. **Trace the full flow** - If a GraphQL field is missing, diff the entire query against the schema
2. **Check related systems** - If CSP blocks one resource type, check all resource types
3. **Question existence** - If a file causes problems, ask whether it should exist at all
4. **Follow the data** - Trace from UI → GraphQL → resolver → Lambda → S3/DynamoDB and back

**First action on error is investigation, not a fix.**
