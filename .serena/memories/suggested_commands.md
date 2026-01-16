# Suggested Commands

## Testing
```bash
npm run test              # All tests (backend + frontend)
npm run test:backend      # Python tests (pytest -n auto, parallel)
npm run test:frontend     # UI + ragstack-chat tests (vitest)
npm run test:integration  # Integration tests (requires deployed stack)
npm run test:coverage     # Coverage report (HTML in htmlcov/)

# Single test file
uv run pytest tests/unit/python/test_config.py -v
```

## Linting & Formatting
```bash
npm run lint              # Python (ruff check + format --check)
npm run lint:fix          # Python autofix
npm run lint:frontend     # TypeScript (ESLint --max-warnings 0 + tsc --noEmit)
npm run lint:all          # Both Python and frontend
npm run check             # Lint + test (CI equivalent)
```

## Development
```bash
sam build                 # Build SAM application
sam local invoke ProcessDocumentFunction --event tests/events/s3-put.json

# Frontend dev server
cd src/ui && npm run dev
```

## Deployment (DO NOT RUN WITHOUT USER REQUEST)
```bash
python publish.py --project-name my-docs --admin-email admin@example.com
python publish.py --project-name my-docs --admin-email admin@example.com --skip-ui      # Skip dashboard
python publish.py --project-name my-docs --admin-email admin@example.com --skip-ui-all  # Skip all UI
```

## Python Package Management
```bash
uv pip install <package>  # ALWAYS use uv, never pip directly
uvx ruff check .          # Run ruff without installing
uvx pytest                # Run pytest without installing
```

## Git (Standard Linux)
```bash
git status
git add .
git commit -m "message"
git push
git worktree list         # Verify worktree location before changes
```

## Utility Commands
```bash
ls, cd, pwd, cat, head, tail, grep, find  # Standard Linux utilities
```
