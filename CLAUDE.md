# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAGStack-Lambda is a serverless OCR-to-Knowledge Base pipeline on AWS that transforms unstructured documents (PDFs, images, Office docs) into searchable knowledge using Amazon Bedrock. The system uses Step Functions to orchestrate OCR extraction (Textract or Bedrock), embedding generation (Titan models), and indexing in a Bedrock Knowledge Base with S3 vector storage.

## Development Commands

### Testing & Linting

**All commands run from repository root:**

```bash
# Quick validation (recommended before commits)
npm run test:all          # Lint + test everything (~8s)

# Individual commands
npm run lint              # Auto-fix backend (ruff) + frontend (ESLint)
npm test                  # Run all unit tests (pytest + Vitest)
npm run test:coverage     # Generate coverage reports

# Backend only
npm run test:backend      # Run pytest unit tests (~1s)
npm run lint:backend      # Ruff check + format with auto-fix

# Frontend only
npm run test:frontend     # Run Vitest tests (~2s)
npm run lint:frontend     # ESLint with auto-fix

# Integration tests (requires AWS deployment)
npm run test:backend:integration
```

**Python testing notes:**
- Use `uv run pytest` for direct pytest execution
- Unit tests exclude integration marker: `pytest -m 'not integration'`
- Shared library tests: `pytest lib/ragstack_common/`

**Frontend testing notes:**
- Tests use Vitest + React Testing Library + happy-dom
- Run from `src/ui/`: `npm test` or `npm run test:watch`
- Test files: `src/ui/src/**/*.test.jsx`

### Deployment

```bash
# Full deployment (required parameters)
python publish.py \
  --project-name <name> \        # lowercase, alphanumeric + hyphens, 2-32 chars
  --admin-email <email> \        # valid email for Cognito
  --region <region>              # e.g., us-east-1

# Skip UI build (backend changes only)
python publish.py --project-name <name> --admin-email <email> --region <region> --skip-ui
```

**What publish.py does:**
1. Validates prerequisites (Python 3.13+, Node 24+, AWS CLI, SAM CLI)
2. Creates/uses S3 artifact bucket
3. Packages UI source as zip and uploads to S3
4. Runs `sam build --parallel --cached` to package Lambda dependencies
5. Deploys via `sam deploy` (CloudFormation)
6. CloudFormation triggers `start_codebuild` Lambda (custom resource) which starts CodeBuild and polls until UI build completes
7. Outputs CloudFront URL and credentials

### SAM Local Testing

```bash
sam build                          # Build all Lambda functions
sam local invoke ProcessDocumentFunction -e tests/events/sample.json
sam local start-api                # Local API Gateway
```

### UI Development

```bash
cd src/ui
npm install
npm start     # or npm run dev
```

## Architecture

### High-Level Flow

```
User Upload → S3 (Input Bucket)
              ↓
         EventBridge Rule
              ↓
      Step Functions Pipeline
         ↓           ↓
  ProcessDocument   GenerateEmbeddings
  (OCR extraction)  (Titan embeddings)
         ↓           ↓
   S3 (Extracted)  S3 (Vector Bucket)
                        ↓
              Bedrock Knowledge Base
                        ↓
         AppSync GraphQL API ← React UI (CloudFront)
              ↓
        DynamoDB (Tracking)
```

### Core Components

**Lambda Functions:**
- `process_document/` - OCR extraction (Textract or Bedrock), text-native PDF detection, image extraction
- `generate_embeddings/` - Text/image embedding generation using Titan models, writes to S3 vector bucket
- `query_kb/` - Knowledge Base queries via Bedrock Agent Runtime, session management
- `appsync_resolvers/` - GraphQL resolvers for document management, presigned URLs, configuration
- `configuration_resolver/` - Runtime config merging (Schema → Default → Custom from DynamoDB)
- `kb_custom_resource/` - CloudFormation custom resource for Knowledge Base creation
- `start_codebuild/` - CloudFormation custom resource that triggers UI CodeBuild project and polls until complete

**Shared Library (`lib/ragstack_common/`):**
- `bedrock.py` - Bedrock client wrapper, model invocations
- `ocr.py` - OCR backends (Textract sync/async, Bedrock vision)
- `image.py` - Image processing utilities
- `storage.py` - S3 operations (download, upload, presigned URLs)
- `models.py` - Pydantic data models
- `config.py` - Runtime configuration system (Schema → Default → Custom)

**Step Functions Pipeline (`src/statemachine/pipeline.asl.json`):**
1. ProcessDocument (OCR + text extraction)
2. GenerateEmbeddings (text + image embeddings)
3. MarkAsIndexed (success) or ProcessingFailed (error)

**Frontend (`src/ui/src/`):**
- React 19 + Vite + React Router
- Cloudscape Design System + Amplify UI for auth
- Components: `Auth/`, `Chat/`, `Dashboard/`, `Search/`, `Upload/`, `Settings/`
- GraphQL via Amplify (`src/ui/src/graphql/`)
- Hooks: `useDocuments`, `useUpload`, `useConfiguration`

**GraphQL API (`src/api/schema.graphql`):**
- Queries: `getDocument`, `listDocuments`, `queryKnowledgeBase`, `getConfiguration`
- Mutations: `createUploadUrl`, `processDocument`, `updateConfiguration`, `reEmbedAllDocuments`

### Key Architectural Patterns

**Shared Library Installation:**
- Lambda functions reference `./lib` in `requirements.txt`
- SAM build installs `ragstack_common` as pip package via `lib/setup.py`
- **NOT all Lambdas use it**: `query_kb`, `kb_custom_resource`, `appsync_resolvers`, and `start_codebuild` use boto3 directly
- Only `process_document` and `generate_embeddings` import `ragstack_common`

**Runtime Configuration System:**
Three-tier merge (Schema → Default → Custom):
1. **Schema Config** - CloudFormation parameters (OcrBackend, model IDs) - immutable after deploy
2. **Default Config** - Hard-coded defaults for optional settings (defined in publish.py:839-846)
3. **Custom Config** - User-modifiable via Settings UI, stored in DynamoDB

Configuration resolver Lambda merges these tiers. Changes to embedding models trigger automatic re-embedding of all documents.

**Text-Native PDF Optimization:**
`process_document` detects PDFs with embedded text and skips OCR, reducing cost and processing time.

**Embedding Change Detection:**
System tracks document count in DynamoDB. When embedding config changes, Settings UI triggers re-embedding job via Step Functions.

**UI Deployment via CloudFormation Custom Resource:**
- publish.py packages UI source and uploads to S3
- CloudFormation template defines `CodeBuildRun` custom resource
- `start_codebuild` Lambda handles the custom resource lifecycle:
  - On Create/Update: starts CodeBuild project and polls until complete
  - Returns success/failure to CloudFormation
  - This ensures CloudFormation waits for UI build before marking stack as complete

## Development Workflow

### Making Code Changes

**Backend (Lambda functions):**
1. Edit code in `src/lambda/<function>/` or `lib/ragstack_common/`
2. Run `npm run lint:backend` (auto-fixes issues)
3. Run `npm run test:backend` (unit tests)
4. Run `sam build` (if testing locally with SAM)
5. Deploy with `python publish.py` (or `--skip-ui` for backend-only)

**Frontend (React UI):**
1. Edit code in `src/ui/src/`
2. Run `npm run lint:frontend` (from repo root)
3. Run `npm run test:frontend` (from repo root)
4. Test locally: `cd src/ui && npm start`
5. Deploy with `python publish.py` (builds UI via CodeBuild)

**Shared Library:**
1. Edit `lib/ragstack_common/*.py`
2. Run `npm run test:backend` (includes `lib/ragstack_common/test_*.py`)
3. Run `sam build` to rebuild Lambda packages
4. Deploy to update Lambda functions

### Test File Locations

**Backend:**
- Unit tests: `tests/unit/` (pytest)
- Integration tests: `tests/integration/` (pytest, marked with `@pytest.mark.integration`)
- Shared library tests: `lib/ragstack_common/test_*.py`

**Frontend:**
- Unit tests: `src/ui/src/**/*.test.jsx` (Vitest)

### Configuration Changes

**Deployment-time config (requires re-deploy):**
Edit `template.yaml` parameters:
- `OcrBackend` (textract or bedrock)
- `BedrockOcrModelId` (Claude model for OCR)
- `TextEmbedModelId` (Titan text embedding model)
- `ImageEmbedModelId` (Titan image embedding model)

**Runtime config (no re-deploy):**
Use Settings UI or `updateConfiguration` mutation to modify custom config in DynamoDB. Changes to embedding models trigger automatic re-embedding.

## Common Development Patterns

### Adding a New Lambda Function

1. Create directory: `src/lambda/<function_name>/`
2. Add `index.py` with handler function
3. Add `requirements.txt` (include `./lib` if using shared library)
4. Add function to `template.yaml`:
```yaml
NewFunction:
  Type: AWS::Serverless::Function
  Properties:
    CodeUri: src/lambda/<function_name>/
    Handler: index.lambda_handler
    Runtime: python3.13
    Environment:
      Variables:
        TABLE_NAME: !Ref DocumentTable
```
5. Run `sam build && python publish.py ...`

### Modifying GraphQL Schema

1. Edit `src/api/schema.graphql`
2. Update resolvers in `src/lambda/appsync_resolvers/index.py`
3. Update frontend GraphQL queries in `src/ui/src/graphql/`
4. Deploy with `python publish.py`

### Working with Step Functions

1. Edit `src/statemachine/pipeline.asl.json`
2. Test locally: Use Step Functions Local or AWS Console
3. Deploy updates automatically with `sam deploy`

## Troubleshooting

### Deployment Issues

**SAM build fails:**
```bash
sam build --use-container    # Build in Docker (cross-platform)
```

**Missing Bedrock permissions:**
Enable models in AWS Console → Bedrock → Model access:
- `anthropic.claude-3-5-haiku-20241022-v1:0`
- `amazon.titan-embed-text-v2:0`
- `amazon.titan-embed-image-v1`

**CloudFormation stack fails:**
```bash
aws cloudformation describe-stack-events --stack-name RAGStack-<project-name>
```

**UI CodeBuild fails:**
Check CodeBuild console for logs. Common issues:
- Node.js version mismatch in buildspec
- Missing environment variables
- Vite build errors

### Runtime Issues

**Documents stuck in PROCESSING:**
```bash
# Check Step Functions
aws stepfunctions list-executions --state-machine-arn <ARN>

# Check Lambda logs
aws logs tail /aws/lambda/RAGStack-<project-name>-ProcessDocument --follow
```

**UI not loading:**
```bash
# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
```

### Test Failures

**Backend tests fail:**
- Check Python version: `python --version` (must be 3.13+)
- Reinstall dependencies: `uv pip install -r requirements.txt`
- Run with verbose: `uv run pytest -v`

**Frontend tests fail:**
- Check Node version: `node --version` (must be 24+)
- Reinstall: `cd src/ui && rm -rf node_modules package-lock.json && npm install`
- Run with verbose: `cd src/ui && npm test -- --reporter=verbose`

## Documentation

**Core docs:**
- `docs/ARCHITECTURE.md` - Detailed architecture, ADRs, design decisions
- `docs/DEPLOYMENT.md` - Deployment prerequisites and procedures
- `docs/CONFIGURATION.md` - Configuration system and customization
- `docs/TESTING.md` - End-to-end testing guide, CI/CD integration
- `docs/USER_GUIDE.md` - Using the WebUI
- `docs/TROUBLESHOOTING.md` - Common issues and solutions
- `docs/OPTIMIZATION.md` - Performance tuning and cost optimization

**When making architecture changes, update `docs/ARCHITECTURE.md` with ADR entries.**

## Important Notes

**Git Worktree:**
- Verify location before changes: `git worktree list && pwd`
- Each worktree is a separate branch - never modify base repository

**Package Management:**
- Python: Always use `uv pip install` or `uvx` (never pip directly per global CLAUDE.md)
- Node: Use `npm` (managed via nvm v24 LTS)

**File Creation:**
- Prefer editing existing files over creating new ones
- Search thoroughly before creating (multiple patterns, check docs)
- Never create markdown/documentation files unless explicitly requested
