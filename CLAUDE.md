# CLAUDE.md

Guidance for Claude Code when working with this repository.

## READ FIRST - Problem Solving Discipline

**Never fix a symptom without investigating what else shares that pattern.**

Before declaring any fix complete:
1. **Trace the full flow** - If a GraphQL field is missing, diff the entire query against the entire schema
2. **Check related systems** - If CSP blocks one resource type, check all resource types the component uses
3. **Question existence** - If a file causes problems, ask whether it should exist at all
4. **Follow the data** - Trace from UI → GraphQL → resolver → Lambda → S3/DynamoDB and back

When you encounter an error, your first action is investigation, not a fix.

---

## Project Overview

RAGStack-Lambda is a serverless document processing pipeline with AI chat on AWS. Documents are uploaded → OCR processed (Textract/Bedrock) → vectorized → stored in Bedrock Knowledge Base → queryable via chat interface.

**Single SAM stack:** Document processing pipeline (Lambda, Step Functions, S3, DynamoDB, Bedrock KB), Chat API (AppSync GraphQL, Cognito auth), `<ragstack-chat>` web component (CloudFront CDN)

## Prerequisites

- Python 3.13+ (use `uv` for all Python package management)
- Node.js 24+
- AWS CLI, SAM CLI (configured)
- Docker (required for Lambda layer builds)

## Common Commands

```bash
# Testing
npm run test              # All tests (backend + frontend)
npm run test:backend      # Python tests (pytest -n auto)
npm run test:frontend     # UI + ragstack-chat tests (vitest)
npm run test:integration  # Integration tests (requires deployed stack)
uv run pytest tests/unit/python/test_config.py -v  # Single test file

# Linting
npm run lint              # Python (ruff check + format --check)
npm run lint:fix          # Python autofix
npm run lint:frontend     # TypeScript (ESLint --max-warnings 0)
npm run check             # Lint + test (CI equivalent)

# Deployment (defaults to us-east-1 for Nova Multimodal Embeddings)
python publish.py --project-name my-docs --admin-email admin@example.com
python publish.py --project-name my-docs --admin-email admin@example.com --skip-ui      # Skip dashboard
python publish.py --project-name my-docs --admin-email admin@example.com --skip-ui-all  # Skip all UI
python publish.py --project-name my-docs --admin-email admin@example.com --demo-mode   # Enable demo mode (rate limits, disabled features)
python publish.py --project-name my-docs --admin-email admin@example.com --demo-mode    # Enable demo mode

# Development
sam build
sam local invoke ProcessDocumentFunction --event tests/events/s3-put.json
cd src/ui && npm run dev  # Frontend dev server
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
│   ├── integration/              # Integration tests (@pytest.mark.integration)
│   └── events/                   # Lambda test event JSON files
├── template.yaml                 # SAM template (infrastructure as code)
└── publish.py                    # Deployment orchestration script
```

### Data Flow

1. **Upload:** User uploads to S3 → EventBridge triggers ProcessDocument Lambda
2. **Processing:** ProcessDocument (OCR) → IngestToKB → Bedrock Knowledge Base
3. **Query:** User queries via AppSync → QueryKB Lambda → Bedrock KB → results with source attribution
4. **Chat:** Web component (`<ragstack-chat>`) → AppSync GraphQL API → QueryKB Lambda

### Key Components

- **lib/ragstack_common/:** Shared library (OCR, embeddings, config, storage)
- **ProcessDocument Lambda:** Extracts text using Textract or Bedrock vision models
- **IngestToKB Lambda:** Creates embeddings (Nova Multimodal) and syncs to Bedrock KB
- **QueryKB Lambda:** Retrieves documents from KB with source attribution, handles chat with quota management
- **Step Functions:** Orchestrates document processing workflow
- **AppSync:** GraphQL API for UI and chat

## Testing

- **Python:** `tests/unit/python/` (pytest), integration tests marked with `@pytest.mark.integration`
- **Frontend:** `src/ui/src/**/*.test.{ts,tsx}`, `src/ragstack-chat/src/**/*.test.{ts,tsx}` (Vitest)
- **Coverage:** `npm run test:coverage` generates HTML report in `htmlcov/`

## Python Code Standards

- Always use `uv`: `uv pip install <package>`, `uvx ruff`, `uvx pytest`
- Ruff config in `pyproject.toml`: 100 char line length, Python 3.13

## Important Notes

- **Worktrees:** Verify location with `git worktree list` and `pwd` before changes
- **Configuration:** Runtime config in DynamoDB. See [docs/CONFIGURATION.md](docs/CONFIGURATION.md)
- **OCR Backends:** textract (default) or bedrock. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Web Component:** See [docs/RAGSTACK_CHAT.md](docs/RAGSTACK_CHAT.md) for `<ragstack-chat>` usage
- **Lambda Layer:** `lib/ragstack_common/` packaged as Lambda layer (Docker required for build)
- **Demo Mode:** `--demo-mode` enables rate limits (5 uploads/day, 30 chats/day) and disables reindex/reprocess/delete
- **Troubleshooting:** See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
