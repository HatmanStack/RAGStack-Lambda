# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAGStack-Lambda is a serverless document processing pipeline on AWS that transforms unstructured documents (PDFs, images, Office docs) into searchable knowledge using OCR, semantic embeddings, and Amazon Bedrock Knowledge Base.

**Key Technologies**: Python 3.13 (backend), Node.js 24 (frontend), AWS SAM/CloudFormation, AppSync GraphQL, React UI

## Project Structure

```
RAGStack-Lambda/
├── lib/ragstack_common/          # Shared Python libraries (used by all Lambdas)
│   ├── config.py                 # ConfigurationManager for runtime settings
│   ├── models.py                 # Data models (Document, ProcessingStatus, etc.)
│   ├── ocr.py                    # OCR backends (Textract/Bedrock)
│   ├── bedrock.py                # Bedrock API utilities
│   ├── storage.py                # S3 operations
│   ├── image.py                  # Image processing
│   └── test_*.py                 # Unit tests for library
├── src/
│   ├── lambda/                   # Lambda function handlers
│   │   ├── process_document/     # Extracts text from documents via OCR
│   │   ├── generate_embeddings/  # Generates embeddings from extracted text
│   │   ├── query_kb/             # Queries Bedrock Knowledge Base
│   │   ├── appsync_resolvers/    # GraphQL API resolvers
│   │   ├── configuration_resolver/ # Handles configuration CRUD
│   │   ├── ingest_to_kb/         # Moves vectors to Bedrock KB
│   │   ├── kb_custom_resource/   # CloudFormation custom resource for KB
│   │   └── start_codebuild/      # Triggers UI build
│   ├── statemachine/             # Step Functions workflow
│   ├── api/                      # GraphQL schema
│   └── ui/                       # React application
├── tests/
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests (marked with @pytest.mark.integration)
│   ├── conftest.py               # pytest configuration
│   └── events/                   # Sample Lambda events for testing
├── template.yaml                 # SAM template (main infrastructure-as-code)
├── pyproject.toml                # Python linting config (ruff)
├── pytest.ini                    # pytest configuration
├── publish.py                    # Deployment automation script
└── docs/                         # Documentation
```

## Development Commands

### Building & Linting

All commands should be run from the project root. Backend uses `ruff`, frontend uses ESLint.

```bash
npm run lint:backend      # Auto-fix + lint Python code (backend)
npm run lint:frontend     # Auto-fix + lint React code (frontend)
npm run lint              # Lint both backend and frontend
npm run format            # Format Python code with ruff
npm run format:check      # Check formatting without modifying
```

### Testing

Run tests locally without AWS deployment. Tests are marked as unit or integration; by default pytest skips integration tests.

```bash
npm run test:backend                # Run Python unit tests only (~1s)
npm run test:backend:integration    # Run Python integration tests
npm run test:backend:coverage       # Generate Python coverage report
npm run test:frontend               # Run React tests with Vitest (~2s)
npm run test                        # Run all unit tests (backend + frontend)
npm run test:coverage               # Full coverage report
npm run test:all                    # Lint + all tests (recommended pre-commit)
```

**Running individual tests:**
```bash
# Backend unit test
uv run pytest tests/unit/test_config.py -v

# Backend integration test
uv run pytest tests/integration/ -m integration -v

# Frontend test
cd src/ui && npm test -- --run src/components/Button.test.tsx
```

### Deployment & Build

Deployment requires AWS credentials and SAM CLI.

```bash
npm run deploy        # Runs publish.py with required parameters
sam build             # Build Lambda functions
sam local invoke      # Test Lambda locally
```

The `publish.py` script handles:
1. Validation of Python 3.13+, Node.js 24+, AWS CLI, SAM CLI
2. Building Lambda dependencies via SAM
3. Deploying infrastructure via CloudFormation
4. Building and deploying React UI via CodeBuild
5. Configuring Bedrock Knowledge Base

## Key Architectural Decisions

### 1. Configuration Management (ADR-001)
**Pattern**: DynamoDB-backed runtime configuration with no caching

The `ConfigurationManager` class (lib/ragstack_common/config.py) reads configuration on every call from a DynamoDB table with structure:
- **Schema** entry: Defines available parameters and validation rules (read-only)
- **Default** entry: System defaults (read-only)
- **Custom** entry: User-overridden values (read-write)

Custom values override Defaults. This design prioritizes consistency over performance.

### 2. SAM for Lambda Deployment (ADR-002)
Use `AWS::Serverless::Function` in template.yaml for all Lambdas, not raw CloudFormation. Benefits:
- Local testing with `sam local invoke`
- Simpler dependency packaging
- Built-in support for function policies

### 3. Shared Library Approach (ADR-003)
All Lambdas import from `lib/ragstack_common/` which is copied to each Lambda's dependencies during `sam build`. This centralizes logic and ensures consistency across functions.

### 4. S3-Based Vector Storage
Use Bedrock Knowledge Base with S3 vectors instead of OpenSearch Serverless for cost efficiency (~$1/month vs $50/month).

## Testing Structure

### Test Organization
- **Unit tests**: Located in tests/unit/ and lib/ragstack_common/test_*.py
- **Integration tests**: Located in tests/integration/, marked with `@pytest.mark.integration`
- **Frontend tests**: Vitest files colocated with components (.test.tsx)

### pytest Configuration
- Config in pytest.ini marks tests as unit or integration
- Default behavior skips integration tests
- Run with `-m integration` to include integration tests
- Test discovery patterns: test_*.py, Test* classes, test_* functions

### Adding Tests
For new functionality:
1. Add unit tests for isolated logic in tests/unit/ or colocated in lib/ragstack_common/
2. Add integration tests if testing AWS services interaction
3. Use @pytest.mark.integration to mark integration tests
4. Run `npm run test:all` before committing

## Python Development

### Environment & Package Management
- **Python**: 3.13+ (checked by publish.py)
- **Package Manager**: `uv` (not pip - see CLAUDE.md root for uv usage)
- **Linting/Formatting**: ruff (config in pyproject.toml)

### Dependencies
- Backend: See requirements.txt and requirements-dev.txt
- Frontend: See src/ui/package.json
- SAM dependencies: Specified in template.yaml for each Lambda

### Code Style
- Line length: 100 characters (AWS Lambda best practice)
- Ruff rules in pyproject.toml configured for AWS Lambda patterns
- Unused function arguments allowed in Lambdas (ARG001)
- datetime.utcnow() allowed for ISO8601 timestamps (DTZ003)

## React/Frontend Development

### Structure
- Built with Vite (dev server) and Vitest (testing)
- Uses AWS Amplify for auth and GraphQL
- Cloudscape Design System components
- Location: src/ui/

### Available Commands
```bash
cd src/ui
npm start             # Start dev server (localhost:5173)
npm run dev           # Alternative to start
npm build             # Production build
npm test              # Run tests
npm test:watch       # Watch mode
npm test:coverage    # Coverage report
npm run lint         # Lint from root
```

## Lambda Function Patterns

Each Lambda function handler:
1. Receives event and context parameters
2. Uses ConfigurationManager for runtime settings
3. Logs with structured logging (LOG_LEVEL env var)
4. Returns JSON response
5. Raises exceptions (handled by Step Functions or AppSync)

**Example handler structure** (src/lambda/process_document/index.py):
```python
def lambda_handler(event, context):
    """Lambda handler for processing documents."""
    config = ConfigurationManager()
    # Use config.get_parameter('key') for settings
    # ...
    return {"statusCode": 200, "body": "..."}
```

## Deployment & Environment

### SAM Configuration
- Location: samconfig.toml (build settings only)
- Infrastructure: template.yaml (CloudFormation/SAM)
- Parameters validated in publish.py

### Deployment Parameters (required)
- `--project-name`: Lowercase alphanumeric + hyphens, 2-32 chars, starts with letter
- `--admin-email`: Valid email for Cognito and alerts
- `--region`: AWS region (e.g., us-east-1)
- `--skip-ui` (optional): Skip UI build for backend-only changes

### Environment Variables
Set in template.yaml Globals and function-specific sections:
- `LOG_LEVEL`: Control logging verbosity
- `CONFIGURATION_TABLE_NAME`: DynamoDB table for runtime config
- `OCR_BACKEND`: Choice between "textract" or "bedrock"
- Function-specific vars like `KNOWLEDGE_BASE_ID`, `S3_BUCKET_NAME`

## Debugging & Local Development

### Local Testing Without Deployment
All unit tests run without AWS credentials. Integration tests require AWS access.

### SAM Local Testing
```bash
sam build
sam local invoke ProcessDocumentFunction -e tests/events/sample.json
sam local start-api  # Start local GraphQL API
```

### Viewing Logs
- **Local**: pytest and SAM commands show logs directly
- **Deployed**: `aws logs tail /aws/lambda/RAGStack-<project-name>-<function-name> --follow`

### Common Issues
1. **Tests fail with import errors**: Run `sam build` to copy lib/ragstack_common to Lambda directories
2. **DynamoDB config not found**: Check CONFIGURATION_TABLE_NAME env var and table exists
3. **OCR failing**: Verify Bedrock models are enabled in AWS Console > Bedrock > Model access

## CI/CD Integration

GitHub Actions workflow (.github/workflows/test.yml):
- Runs on every push
- Uses uv for Python dependencies
- Tests Python 3.13, Node 22
- Runs linting and unit tests
- Generates coverage reports

To enable: This workflow is already present; CI/CD runs automatically on push.

## Common Development Tasks

### Adding a New Lambda Function
1. Create directory: src/lambda/my_function/
2. Add index.py with lambda_handler(event, context)
3. Create tests in tests/unit/test_my_function.py
4. Add function definition to template.yaml
5. Import from lib/ragstack_common/ as needed
6. Run `npm run test:all` before committing

### Modifying Configuration Schema
1. Edit lib/ragstack_common/config.py (ConfigurationSchema class)
2. Update lib/ragstack_common/test_config.py
3. Update src/lambda/configuration_resolver/ to handle new fields
4. Run tests: `npm run test:backend`

### Updating Dependencies
- **Python**: Add to requirements.txt, run `uv pip install -r requirements.txt`
- **Node**: `cd src/ui && npm install <package>`
- **Lambda-specific**: May need SAM layer or modify sam build process

### Debugging GraphQL Queries
Check appsync_resolvers for resolver logic. Test with AWS AppSync console or Amplify DataStore in UI.

## Documentation References

- **Architecture**: docs/ARCHITECTURE.md (system design, ADRs, components)
- **Testing**: docs/TESTING.md (comprehensive testing guide)
- **Deployment**: docs/DEPLOYMENT.md (prerequisites, step-by-step guide)
- **Configuration**: docs/CONFIGURATION.md (runtime settings)
- **User Guide**: docs/USER_GUIDE.md (UI features)
- **Troubleshooting**: docs/TROUBLESHOOTING.md (common issues)
- **Optimization**: docs/OPTIMIZATION.md (performance tuning)
