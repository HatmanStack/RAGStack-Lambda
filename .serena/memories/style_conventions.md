# Code Style and Conventions

## Python (Ruff)

### Configuration (pyproject.toml)
- **Line length**: 100 characters
- **Target version**: Python 3.13
- **Quote style**: Double quotes
- **Indent style**: Spaces

### Enabled Rules
- E, W: pycodestyle errors/warnings
- F: pyflakes
- I: isort (import sorting, ragstack_common is first-party)
- N: pep8-naming
- UP: pyupgrade (modern Python syntax)
- B: flake8-bugbear (common bugs)
- C4: flake8-comprehensions
- DTZ: flake8-datetimez
- PIE: flake8-pie
- RET: flake8-return
- SIM: flake8-simplify
- ARG: flake8-unused-arguments
- PTH: flake8-use-pathlib

### Notable Ignores
- ARG001: Unused function arguments (Lambda handlers have required signature)
- DTZ003/005: datetime.utcnow()/now() allowed for logging
- N803/N806: DynamoDB parameter names match AWS SDK conventions

### Import Order
1. Standard library
2. Third-party packages
3. First-party (ragstack_common)

## TypeScript/React

### ESLint
- `--max-warnings 0` enforced
- TypeScript strict mode (`tsc --noEmit`)

### Frontend Stack
- React 19 with Vite
- Cloudscape Design System (AWS UI library)
- Vitest for testing

## General Conventions
- Use type hints in Python where practical
- Prefer pathlib.Path over os.path (except in tests)
- Lambda handlers: `def handler(event, context)` signature required
- Underscore-prefix for intentionally unused variables: `_unused`
