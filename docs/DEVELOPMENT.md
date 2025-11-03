# Development Guide

Local development, testing, and contribution guidelines for RAGStack-Lambda.

## Quick Setup

```bash
# Install dependencies (one-time)
npm install
cd src/ui && npm install && cd ../..

# Verify everything works
npm run test:all    # Lint + test
```

## Commands

### Testing

```bash
npm test                        # Run all unit tests (~3s)
npm run test:backend            # Python unit tests only (~1s)
npm run test:frontend           # React tests only (~2s)
npm run test:coverage           # Full coverage reports
npm run test:all                # Lint + all tests (recommended pre-commit)

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
│   ├── setup.py                # Package configuration
│   └── test_*.py               # Unit tests
│
├── src/
│   ├── lambda/                 # Lambda function handlers
│   │   ├── process_document/
│   │   ├── generate_embeddings/
│   │   ├── query_kb/
│   │   ├── appsync_resolvers/
│   │   ├── configuration_resolver/
│   │   ├── ingest_to_kb/
│   │   ├── kb_custom_resource/
│   │   └── start_codebuild/
│   ├── statemachine/           # Step Functions workflow
│   │   └── pipeline.asl.json
│   ├── api/                    # GraphQL schema
│   │   └── schema.graphql
│   └── ui/                     # React application
│       ├── src/
│       ├── package.json
│       └── vite.config.ts
│
├── tests/                      # Test files
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests (requires AWS)
│   ├── conftest.py             # pytest configuration
│   └── events/                 # Sample Lambda events
│
├── template.yaml               # CloudFormation/SAM template
├── samconfig.toml              # SAM build configuration
├── pyproject.toml              # Python linting config
├── pytest.ini                  # pytest configuration
├── publish.py                  # Deployment automation
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

## Common Development Tasks

### Adding a New Lambda Function

1. Create function directory:
   ```bash
   mkdir -p src/lambda/my_function
   ```

2. Add handler code (src/lambda/my_function/index.py):
   ```python
   def lambda_handler(event, context):
       """Lambda handler for my operation."""
       # Import from ragstack_common if needed
       from ragstack_common import storage
       config = ConfigurationManager()
       # ...
       return {"statusCode": 200, "body": "..."}
   ```

3. Create requirements.txt:
   ```
   ./lib
   boto3>=1.34.0
   ```

4. Add tests (tests/unit/test_my_function.py):
   ```python
   import pytest
   from src.lambda.my_function.index import lambda_handler

   def test_handler():
       event = {"key": "value"}
       result = lambda_handler(event, None)
       assert result["statusCode"] == 200
   ```

5. Add to template.yaml:
   ```yaml
   MyFunction:
     Type: AWS::Serverless::Function
     Properties:
       Handler: index.lambda_handler
       CodeUri: src/lambda/my_function/
       ...
   ```

6. Test:
   ```bash
   npm run test:backend
   sam build
   sam local invoke MyFunction -e tests/events/sample.json
   ```

### Modifying Configuration Schema

Configuration is managed by ConfigurationManager (lib/ragstack_common/config.py):

1. Update the schema in config.py:
   ```python
   class ConfigurationSchema:
       NEW_SETTING = {
           "description": "...",
           "type": str,
           "default": "...",
           "validation_regex": "...",
       }
   ```

2. Update tests (lib/ragstack_common/test_config.py):
   ```python
   def test_new_setting():
       config = ConfigurationManager()
       value = config.get_parameter("NEW_SETTING")
       assert value == "..."
   ```

3. Update configuration_resolver if needed (src/lambda/configuration_resolver/):
   - Add handler for getting/setting the new field
   - Update GraphQL schema if exposing via API

4. Test:
   ```bash
   npm run test:backend
   ```

### Adding React Components

1. Create component file (src/ui/src/components/MyComponent.tsx):
   ```typescript
   import React from 'react';

   export const MyComponent: React.FC = () => {
     return <div>Hello</div>;
   };
   ```

2. Add test (src/ui/src/components/MyComponent.test.tsx):
   ```typescript
   import { render, screen } from '@testing-library/react';
   import { MyComponent } from './MyComponent';

   test('renders component', () => {
     render(<MyComponent />);
     expect(screen.getByText('Hello')).toBeInTheDocument();
   });
   ```

3. Test:
   ```bash
   npm run test:frontend
   ```

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

### Writing Tests

**Python Unit Test** (tests/unit/test_my_lambda.py):
```python
import pytest

@pytest.fixture
def mock_config(monkeypatch):
    """Mock ConfigurationManager"""
    monkeypatch.setenv("CONFIGURATION_TABLE_NAME", "test-table")
    # Return mock or fixture

def test_my_function(mock_config):
    from src.lambda.my_lambda.index import lambda_handler
    event = {"key": "value"}
    result = lambda_handler(event, None)
    assert result["statusCode"] == 200
```

**React Test** (src/ui/src/components/MyComponent.test.tsx):
```typescript
import { render, screen } from '@testing-library/react';
import { MyComponent } from './MyComponent';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });
});
```

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

## Lambda Function Pattern

All Lambda handlers follow this pattern:

```python
def lambda_handler(event, context):
    """Lambda handler for [operation]."""
    try:
        config = ConfigurationManager()

        # Extract parameters
        param = event.get("param")

        # Use config for runtime settings
        setting = config.get_parameter("SETTING_NAME")

        # Perform operation
        result = do_something(param)

        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise  # Let Step Functions or AppSync handle error
```

## Environment Variables

Set in template.yaml:

```yaml
Globals:
  Function:
    Environment:
      Variables:
        LOG_LEVEL: INFO
        CONFIGURATION_TABLE_NAME: !Ref ConfigurationTable

MyFunction:
  Properties:
    Environment:
      Variables:
        SPECIFIC_VAR: value
```

## Related Documentation

- [Testing Guide](TESTING.md) - Comprehensive testing documentation
- [Architecture](ARCHITECTURE.md) - System design and components
- [Configuration](CONFIGURATION.md) - Runtime configuration options
- [Deployment](DEPLOYMENT.md) - How to deploy to AWS
