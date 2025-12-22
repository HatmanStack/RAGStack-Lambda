# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAGStack-Lambda is a serverless document processing pipeline with AI chat on AWS. Documents are uploaded → OCR processed (Textract/Bedrock) → vectorized → stored in Bedrock Knowledge Base → queryable via chat interface.

**Single SAM stack architecture:**
- Document processing pipeline (Lambda, Step Functions, S3, DynamoDB, Bedrock KB)
- Chat API (AppSync GraphQL, Cognito auth)
- `<ragstack-chat>` web component (CloudFront CDN)

## Prerequisites

- Python 3.13+ (use `uv` for all Python package management)
- Node.js 24+
- AWS CLI, SAM CLI (configured)
- Docker (required for Lambda layer builds)

## Common Commands

### Testing

```bash
# Run all tests (backend + frontend) with linting
python test.py              # Installs dependencies, runs npm run test:all

# Individual test suites
npm run test:backend                    # Python unit tests (uv run pytest)
npm run test:backend:integration        # Python integration tests
npm run test:backend:coverage          # Python tests with coverage report
npm run test:frontend                   # React UI tests (src/ui)
npm run test:ragstack-chat              # RagStackChat component tests
npm run test:all                        # All tests + linting

# Run single Python test
uv run pytest tests/unit/python/test_config.py::test_get_value -v

# Watch mode
cd src/ui && npm run test:watch
```

### Linting & Formatting

```bash
# Backend (Python) - uses ruff
npm run lint:backend        # uv run ruff check . --fix && uv run ruff format .
npm run format              # uv run ruff format .
npm run format:check        # uv run ruff format . --check

# Frontend (JavaScript/TypeScript)
npm run lint:frontend       # cd src/ui && npm run lint -- --fix
npm run lint                # Lint both backend and frontend
```

### Deployment

```bash
# Full deployment (defaults to us-east-1 for Nova Multimodal Embeddings)
python publish.py \
  --project-name my-docs \
  --admin-email admin@example.com

# Skip dashboard build (still builds web component)
python publish.py --project-name my-docs --admin-email admin@example.com --skip-ui

# Skip ALL UI builds (dashboard and web component)
python publish.py --project-name my-docs --admin-email admin@example.com --skip-ui-all
```

> **Region Note:** Currently requires us-east-1 (Nova Multimodal Embeddings). When available elsewhere, use `--region <region>`.

### Development

```bash
# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm install

# SAM local testing
sam build
sam local invoke ProcessDocumentFunction --event tests/events/s3-put.json
sam local start-api

# Frontend dev server
cd src/ui && npm run dev
```

## Architecture

### Repository Structure

```
├── lib/ragstack_common/          # Shared Python utilities (OCR, embeddings, config, storage)
├── src/
│   ├── lambda/                   # Lambda function handlers
│   │   ├── process_document/     # OCR extraction (Textract/Bedrock)
│   │   ├── ingest_to_kb/         # Ingest embeddings to Bedrock KB
│   │   ├── query_kb/             # Query knowledge base (chat API)
│   │   ├── appsync_resolvers/    # GraphQL resolvers for AppSync
│   │   └── configuration_resolver/ # DynamoDB config resolver
│   ├── ui/                       # React 19 + Vite dashboard (Cloudscape Design)
│   ├── ragstack-chat/            # Reusable chat React component + web component
│   ├── api/                      # GraphQL schema
│   └── statemachine/             # Step Functions state machine definition
├── tests/
│   ├── unit/python/              # Python unit tests (pytest)
│   ├── integration/              # Integration tests (marked with @pytest.mark.integration)
│   └── events/                   # Lambda test event JSON files
├── template.yaml                 # SAM template (infrastructure as code)
├── publish.py                    # Deployment orchestration script
└── test.py                       # Test runner (installs deps, runs all tests)
```

### Data Flow

1. **Upload:** User uploads to S3 → EventBridge triggers ProcessDocument Lambda
2. **Processing:** ProcessDocument (OCR) → IngestToKB → Bedrock Knowledge Base
3. **Query:** User queries via AppSync → QueryKB Lambda → Bedrock KB → results with source attribution
4. **Chat:** Web component (`<ragstack-chat>`) → SAM AppSync GraphQL API → QueryKB Lambda

### Key Components

- **lib/ragstack_common/:** Shared library used by all Lambdas (OCR, embeddings, config, storage)
- **ProcessDocument Lambda:** Extracts text from documents using Textract or Bedrock vision models
- **IngestToKB Lambda:** Creates embeddings (Nova Multimodal) and syncs to Bedrock Knowledge Base
- **QueryKB Lambda:** Retrieves relevant documents from KB with source attribution, handles chat with quota management
- **Step Functions:** Orchestrates document processing workflow
- **AppSync:** GraphQL API for UI and chat (queries, mutations, subscriptions)

## Testing Architecture

**Python tests (pytest):**
- Unit tests: `tests/unit/python/` (run by default)
- Integration tests: `tests/integration/` (marked with `@pytest.mark.integration`, skipped by default)
- Test config: `pytest.ini` (adds `lib/` to Python path, defines markers)
- Mock events: `tests/events/` (S3, EventBridge, AppSync event JSON files)

**Frontend tests (Vitest):**
- UI tests: `src/ui/src/**/*.test.{ts,tsx}`
- RagStackChat tests: `src/ragstack-chat/src/**/*.test.{ts,tsx}`

**Coverage:** `npm run test:coverage` generates HTML coverage report in `htmlcov/`

## Python Code Standards

**Always use `uv` for Python package management:**
- Install: `uv pip install <package>`
- Run tools: `uvx ruff`, `uvx pytest`
- Never use `pip` directly

**Ruff configuration (pyproject.toml):**
- Line length: 100 chars
- Target: Python 3.13
- Enabled rules: pycodestyle, pyflakes, isort, pep8-naming, pyupgrade, flake8-bugbear, etc.
- Ignored: ARG001 (Lambda handlers), DTZ003/DTZ005 (internal datetime), N803/N806 (AWS SDK conventions)

**Import structure:**
```python
from ragstack_common import ConfigurationManager
from ragstack_common.ocr import extract_text
from ragstack_common.bedrock import generate_embeddings
```

## Deployment Process (publish.py)

The `publish.py` script orchestrates:

1. **Validation:** Email format, project name (2-32 chars, lowercase alphanumeric + hyphens)
2. **SAM build/deploy:** Builds Lambda layers (Docker), packages, deploys via CloudFormation
3. **UI build/upload:** Builds React UI (Vite), uploads to S3, invalidates CloudFront cache
4. **Web component build:** Triggers CodeBuild to build and deploy `<ragstack-chat>` to CDN
5. **Outputs:** Knowledge Base ID, GraphQL API endpoint, CloudFront URLs, Cognito user pool

**Parameters:**
- `--project-name`: Unique project identifier (used in resource names)
- `--admin-email`: Admin user email (Cognito, CloudWatch alerts)
- `--region`: AWS region (default: us-east-1, required for Nova Multimodal Embeddings)
- `--skip-ui`: Skip React UI dashboard build (still builds web component)
- `--skip-ui-all`: Skip all UI builds (dashboard and web component)

## Important Notes

### Worktree Usage
This project uses git worktrees for branch isolation. Always verify you're in the correct worktree before making changes:
```bash
git worktree list
pwd
```

### Configuration Management
Runtime configuration is stored in DynamoDB (table: `{ProjectName}-config-{Suffix}`). Changes apply immediately without redeployment. Access via `ConfigurationManager` class in `lib/ragstack_common/config.py`.

**Chat Configuration Options:**
- `chat_require_auth` - Enable/disable authentication (default: false)
- `chat_primary_model` - Primary chat model ARN
- `chat_fallback_model` - Fallback chat model ARN
- `chat_global_quota_daily` - Daily query limit for all users (default: 10000)
- `chat_per_user_quota_daily` - Daily query limit per user (default: 100)
- `chat_allow_document_access` - Enable/disable source document downloads (default: false)

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for detailed configuration guide.

### OCR Backends
- **textract (default):** AWS Textract ($1.50/1000 pages), faster, better for forms/tables
- **bedrock:** Bedrock vision models (variable cost), slower, better for complex layouts

Configured via `OcrBackend` parameter in `template.yaml` or `--ocr-backend` in `publish.py`.

### Web Component
`src/ragstack-chat/` exports both React component and web component (custom element `<ragstack-chat>`). Web component is built and deployed to CloudFront CDN via CodeBuild project defined in `template.yaml`.

**Usage:**
```html
<script src="https://YOUR_CLOUDFRONT_DOMAIN/ragstack-chat.js"></script>
<ragstack-chat conversation-id="my-site"></ragstack-chat>
```

### Lambda Layer
Shared Python library (`lib/ragstack_common/`) is packaged as Lambda layer during SAM build. Docker is required for building layer with native dependencies (Pillow, etc.).

## Troubleshooting

**"Docker not running"**: Start Docker daemon before running `python publish.py` or `sam build`

**"ModuleNotFoundError: ragstack_common"**: Run `pip install -e lib/` or ensure Lambda layer is built correctly

**"Test discovery: no tests found"**: Ensure test files match pattern `test_*.py` and are in `tests/` directory

**Web component not loading**: Check CloudFront distribution status, verify CodeBuild project completed successfully

## Documentation

- [README.md](README.md) - Quick start
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Deployment guide
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - Local development
- [docs/RAGSTACK_CHAT.md](docs/RAGSTACK_CHAT.md) - Chat component API
- [docs/IMAGE_UPLOAD.md](docs/IMAGE_UPLOAD.md) - Image upload API with captions
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) - Runtime configuration
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Common issues
