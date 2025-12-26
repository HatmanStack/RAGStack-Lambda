# Development Guide

Local development, testing, and contribution guidelines for RAGStack-Lambda.

## Quick Setup

```bash
# Install dependencies (one-time)
npm install
cd src/ui && npm install && cd ../..

# Verify everything works
npm run check       # Lint + test
```

## Commands

### Testing

```bash
npm test                        # Run all unit tests (~3s)
npm run test:backend            # Python unit tests only (~1s)
npm run test:frontend           # React tests only (~2s)
npm run test:coverage           # Full coverage reports
npm run check                   # Lint + all tests (recommended pre-commit)

# Individual tests
uv run pytest tests/unit/test_config.py -v                    # Single Python test
uv run pytest tests/integration/ -m integration -v             # Integration tests
cd src/ui && npm test -- --run src/components/Button.test.tsx # Single React test
```

### Linting & Formatting

```bash
npm run lint                    # Auto-fix and lint all code
npm run lint:backend            # Lint Python (ruff)
npm run lint:frontend           # Lint React (ESLint)
npm run format                  # Format Python code (ruff)
npm run format:check            # Check formatting without modifying
```

### Building

```bash
sam build                       # Build Lambda functions
sam local invoke ProcessDocumentFunction -e tests/events/sample.json  # Test Lambda locally
```

## Project Structure

```
RAGStack-Lambda/
├── lib/ragstack_common/        # Shared Python library
│   ├── config.py               # Configuration management
│   ├── models.py               # Data models
│   ├── ocr.py                  # OCR backends
│   ├── bedrock.py              # Bedrock API utilities
│   ├── storage.py              # S3 operations
│   ├── image.py                # Image processing
│   └── appsync.py              # AppSync subscription publishing
│
├── src/
│   ├── lambda/                 # Lambda function handlers
│   │   ├── process_document/   # OCR extraction
│   │   ├── ingest_to_kb/       # Bedrock KB ingestion
│   │   ├── query_kb/           # Chat queries with sources
│   │   ├── process_image/      # Image ingestion
│   │   ├── appsync_resolvers/  # GraphQL resolvers
│   │   ├── configuration_resolver/
│   │   ├── kb_custom_resource/ # KB provisioning
│   │   ├── start_codebuild/    # Web component build trigger
│   │   ├── scrape_start/       # Web scraping initiation
│   │   ├── scrape_discover/    # URL discovery
│   │   ├── scrape_process/     # Content extraction
│   │   ├── scrape_status/      # Scrape job status
│   │   └── zip_processor/      # ZIP file handling
│   ├── statemachine/           # Step Functions workflow
│   │   └── pipeline.asl.json
│   ├── api/                    # GraphQL schema
│   │   └── schema.graphql
│   ├── ui/                     # React web UI (Cloudscape)
│   │   ├── src/
│   │   ├── package.json
│   │   └── vite.config.ts
│   └── ragstack-chat/          # AI chat web component
│       ├── src/
│       ├── package.json
│       └── vite.wc.config.ts
│
├── tests/                      # Test files
│   ├── unit/python/            # Python unit tests
│   ├── integration/            # Integration tests (requires AWS)
│   └── events/                 # Sample Lambda events
│
├── template.yaml               # SAM template
├── pyproject.toml              # Python linting (ruff)
├── pytest.ini                  # pytest configuration
├── publish.py                  # Deployment script
└── docs/                       # Documentation
```

## Code Style

### Python (Backend)
- **Linter/Formatter**: ruff
- **Line length**: 100 characters (AWS Lambda best practice)
- **Configuration**: pyproject.toml
- **Allowed exceptions** (per AWS Lambda patterns):
  - Unused function arguments (ARG001) - Lambda handlers have unused context
  - datetime.utcnow() (DTZ003) - Used for ISO8601 timestamps

### React (Frontend)
- **Linter**: ESLint
- **Language**: TypeScript
- **Framework**: Vite + React
- **Testing**: Vitest
- **UI Library**: Cloudscape Design System
- **State Management**: AWS Amplify DataStore

### Updating Dependencies

**Python**:
```bash
# Add to requirements.txt, then:
uv pip install -r requirements.txt
npm run test:backend
```

**Node (Frontend)**:
```bash
cd src/ui
npm install <package>
npm test
```

**Lambda-specific dependencies**:
- Each Lambda has its own requirements.txt
- During `sam build`, dependencies are installed per-function
- Common libraries should go in lib/ragstack_common/setup.py

## Testing

### Test Organization

- **Unit tests**: Located in `tests/unit/` and `lib/ragstack_common/test_*.py`
  - Run with `npm run test:backend` (exclude integration tests by default)
  - Fast (~1s), no AWS credentials needed

- **Integration tests**: Located in `tests/integration/`, marked with `@pytest.mark.integration`
  - Run with `npm run test:backend:integration`
  - Require AWS credentials and actual AWS services

- **Frontend tests**: Vitest files colocated with components (`*.test.tsx`)
  - Run with `npm run test:frontend` or `npm test`

### pytest Configuration

- Config: pytest.ini
- By default, integration tests are skipped
- Run with `-m integration` to include them
- Test discovery: test_*.py files, Test* classes, test_* functions

## Debug Tips

### Local Testing Without AWS

All unit tests run without AWS credentials:
```bash
npm run test:backend    # No AWS needed
npm run test:frontend   # No AWS needed
```

### SAM Local Invoke

Test Lambda functions locally with actual handlers:
```bash
sam build
sam local invoke ProcessDocumentFunction -e tests/events/sample.json
```

Check tests/events/ for sample event files.

### View Logs

**Local**:
- pytest and SAM commands show logs directly to console
- Use `--log-level=DEBUG` for verbose output

**Deployed**:
```bash
# Stream logs from deployed Lambda
aws logs tail /aws/lambda/RAGStack-<project-name>-ProcessDocument --follow

# View full output
aws logs get-log-events --log-group-name /aws/lambda/RAGStack-<project-name>-ProcessDocument --log-stream-name <stream>
```

### Common Issues

**Tests fail with import errors**:
```bash
sam build    # Copies lib/ragstack_common to Lambda directories
npm test
```

**Module not found in Lambda**:
- Check Lambda's requirements.txt includes necessary packages
- Verify package name matches import statement
- Run `sam build` to refresh

**Configuration not found at runtime**:
- Check CONFIGURATION_TABLE_NAME environment variable
- Verify DynamoDB table exists
- Check AWS credentials have DynamoDB access

## Architecture Decisions (ADRs)

### ADR-001: Configuration Management
**Pattern**: DynamoDB-backed runtime configuration with no caching

ConfigurationManager reads from DynamoDB table with structure:
- **Schema** entry: Defines available parameters (read-only)
- **Default** entry: System defaults (read-only)
- **Custom** entry: User-overridden values (read-write)

Benefits:
- ✅ Runtime changes without redeployment
- ✅ No caching issues
- ✅ Centralized configuration
- ✅ Audit trail via DynamoDB

### ADR-002: SAM for Lambda Deployment
Use `AWS::Serverless::Function` in template.yaml (not raw CloudFormation).

Benefits:
- ✅ Local testing with `sam local invoke`
- ✅ Simpler dependency packaging
- ✅ Built-in function policies

### ADR-003: Shared Library Approach
All Lambdas import from lib/ragstack_common/.

How it works:
1. Each Lambda's requirements.txt includes `./lib`
2. During `sam build`, pip installs the package from ./lib
3. Makes code available as: `from ragstack_common import <module>`

Benefits:
- ✅ No duplication
- ✅ Consistent logic across functions
- ✅ Easy to maintain

## CI/CD Integration

GitHub Actions workflow (.github/workflows/test.yml):
- Runs on every push and PR
- Tests Python 3.13, Node 24
- Lints backend (ruff) and frontend (ESLint)
- Runs all unit tests (pytest + Vitest)
- Generates coverage reports
- Already enabled - no setup needed

## Related Documentation

- [Architecture](ARCHITECTURE.md) - System design
- [Configuration](CONFIGURATION.md) - Runtime config
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
