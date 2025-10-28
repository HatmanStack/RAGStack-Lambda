# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**RAGStack-Lambda** is a serverless OCR-to-Knowledge Base pipeline on AWS. It processes multi-format documents (PDF, images, Office docs), extracts text via OCR, generates embeddings, and indexes them in an Amazon Bedrock Knowledge Base for natural language search.

**Based on**: This repository is derived from the accelerated-intelligent-document-processing-on-aws repository located at `~/accelerated-intelligent-document-processing-on-aws`.

## Common Commands

### Deployment

```bash
# Deploy to any environment
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region>

# Example: Deploy a customer docs project
python publish.py \
  --project-name customer-docs \
  --admin-email admin@example.com \
  --region us-east-1

# Example: Deploy to a different region
python publish.py \
  --project-name legal-archive \
  --admin-email admin@example.com \
  --region us-west-2

# Skip UI build (backend only - faster for backend changes)
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region> \
  --skip-ui
```

**Note**: All parameters are required. Project name must be lowercase alphanumeric + hyphens, 2-32 chars, starting with a letter. The `publish.py` script validates prerequisites (Python 3.12+, Node.js 18+, AWS CLI, SAM CLI) before deployment.

### Building and Testing

```bash
# Build Lambda functions and layers
sam build

# Build using Docker containers (ensures correct runtime environment)
sam build --use-container

# Test Lambda function locally
sam local invoke ProcessDocumentFunction -e tests/events/sample.json

# Start local API Gateway
sam local start-api

# Run unit tests
pytest tests/unit/

# Run integration tests (requires deployed stack)
pytest tests/integration/ --stack-name RAGStack-<project-name>
```

### UI Development

```bash
cd src/ui

# Install dependencies
npm install

# Start development server
npm start
# or
npm run dev

# Build for production
npm run build

# Lint code
npm run lint

# Deploy UI only (after backend is deployed)
npm run build
aws s3 sync build/ s3://ragstack-<project-name>-ui-<account-id>/ --delete
aws cloudfront create-invalidation --distribution-id <distribution-id> --paths "/*"
```

### Monitoring and Debugging

```bash
# View Lambda logs (real-time)
aws logs tail /aws/lambda/RAGStack-<project-name>-ProcessDocument --follow

# View Step Functions execution history
aws stepfunctions list-executions --state-machine-arn <arn>

# Check DynamoDB tracking table
aws dynamodb scan --table-name RAGStack-<project-name>-Tracking --max-items 10

# View CloudFormation stack events
aws cloudformation describe-stack-events --stack-name RAGStack-<project-name> --max-items 20

# Invalidate CloudFront cache (after UI updates)
aws cloudfront create-invalidation --distribution-id <distribution-id> --paths "/*"
```

### Stack Management

```bash
# Get stack outputs
aws cloudformation describe-stacks --stack-name RAGStack-<project-name> --query 'Stacks[0].Outputs'

# Delete stack (must empty S3 buckets first)
aws s3 rm s3://ragstack-<project-name>-input-<account-id>/ --recursive
aws s3 rm s3://ragstack-<project-name>-output-<account-id>/ --recursive
aws s3 rm s3://ragstack-<project-name>-vectors-<account-id>/ --recursive
aws s3 rm s3://ragstack-<project-name>-working-<account-id>/ --recursive
aws s3 rm s3://ragstack-<project-name>-ui-<account-id>/ --recursive
aws cloudformation delete-stack --stack-name RAGStack-<project-name>
```

## Architecture Overview

### High-Level Flow

```
User → CloudFront → React UI (S3)
         ↓
     AppSync API (GraphQL + Cognito)
         ↓
     Lambda Resolvers
         ↓
     S3 Upload → EventBridge → Step Functions
         ↓
     ProcessDocument Lambda (OCR) → GenerateEmbeddings Lambda
         ↓
     S3 Vectors → Bedrock Knowledge Base → QueryKB Lambda
```

### Key Components

**Lambda Functions** (located in `src/lambda/`):
- `process_document/` - OCR and text extraction (15 min timeout, 3008 MB)
- `generate_embeddings/` - Text/image embeddings generation (15 min timeout, 2048 MB)
- `query_kb/` - Knowledge Base query handler (60 sec timeout, 512 MB)
- `appsync_resolvers/` - GraphQL resolvers for AppSync (30 sec timeout, 512 MB)
- `kb_custom_resource/` - CloudFormation custom resource for KB creation (5 min timeout)
- `shared/` - Shared Lambda utilities

**Shared Library** (located in `lib/ragstack_common/`):
- `bedrock.py` - Bedrock client and model interactions
- `ocr.py` - OCR backends (Textract and Bedrock)
- `image.py` - Image processing utilities
- `storage.py` - S3 operations
- `models.py` - Data models and schemas

**React UI** (located in `src/ui/`):
- Built with Vite, React 19, CloudScape Design System
- Uses AWS Amplify for Cognito authentication and AppSync integration
- Routes: Dashboard, Upload, Search, Document Details

**Step Functions** (located in `src/statemachine/`):
- `pipeline.asl.json` - Main processing pipeline orchestration

**GraphQL API** (located in `src/api/`):
- `schema.graphql` - AppSync schema definition

### Data Flow

1. **Upload**: User uploads document → S3 Input bucket → EventBridge trigger
2. **ProcessDocument**: Detects format → Converts if needed → OCR or direct text extraction → Saves to S3 Output bucket
3. **GenerateEmbeddings**: Reads extracted text/images → Generates embeddings → Saves to S3 Vector bucket
4. **Knowledge Base**: Auto-syncs vectors → Indexes for search
5. **Query**: User searches → QueryKB Lambda → Bedrock KB retrieve API → Results

### Resource Naming Convention

All AWS resources follow consistent project-based naming:

**CloudFormation Stack:**
- Format: `RAGStack-<project-name>`
- Example: `--project-name customer-docs` → Stack: `RAGStack-customer-docs`

**S3 Buckets:**
- Input: `ragstack-<project-name>-input-<account-id>`
- Output: `ragstack-<project-name>-output-<account-id>`
- Vectors: `ragstack-<project-name>-vectors-<account-id>`
- Working: `ragstack-<project-name>-working-<account-id>`
- UI: `ragstack-<project-name>-ui-<account-id>`

**Lambda Functions:**
- Format: `RAGStack-<project-name>-<FunctionName>`
- Examples: `RAGStack-customer-docs-ProcessDocument`, `RAGStack-customer-docs-QueryKB`

**DynamoDB Tables:**
- Format: `RAGStack-<project-name>-<TableName>`
- Examples: `RAGStack-customer-docs-Tracking`, `RAGStack-customer-docs-Metering`

### Critical Design Decisions

**Text-Native PDF Detection**: ProcessDocument checks if PDFs have extractable text. If yes, skips OCR (saves cost and time). Uses PyMuPDF for direct text extraction.

**Dual OCR Backends**: Supports both AWS Textract (cost-effective, $1.50/1000 pages) and Bedrock OCR (multimodal, $25-75/1000 pages). Configured via `OcrBackend` parameter in template.yaml.

**Batch Processing**: GenerateEmbeddings batches pages into groups of 20 to avoid Lambda timeout on large documents (100+ pages). Includes rate limiting (2s delay between batches).

**S3 Vectors**: Uses S3-backed vectors instead of OpenSearch Serverless for cost optimization ($0.023/GB vs $0.24/GB).

**Manual Knowledge Base Setup**: Per ADR-002, Knowledge Base is created manually (not via CloudFormation custom resource in MVP) to reduce complexity. The custom resource exists in code but can be used for production deployments.

## Configuration

### Environment Variables (SAM Template)

Edit `template.yaml` Parameters section:
- `ProjectName` - Resource name prefix (default: RAGStack)
- `OcrBackend` - OCR backend: `textract` or `bedrock` (default: textract)
- `BedrockOcrModelId` - Bedrock model for OCR (default: claude-3-5-haiku)
- `TextEmbedModelId` - Text embedding model (default: titan-embed-text-v2)
- `ImageEmbedModelId` - Image embedding model (default: titan-embed-image-v1)
- `AdminEmail` - Admin user email for Cognito

### SAM Configuration (samconfig.toml)

The project uses a minimal `samconfig.toml` with only build settings. All deployment parameters are provided via CLI arguments to `publish.py`.

### UI Configuration

UI configuration is generated during deployment by `scripts/configure_ui.sh`. Creates `src/ui/src/aws-exports.js` with:
- Cognito User Pool ID and Client ID
- Identity Pool ID
- AppSync API endpoint
- AWS region

## Development Workflow

### Making Changes to Lambda Functions

1. Edit code in `src/lambda/*/` or `lib/ragstack_common/`
2. Run `sam build` to package
3. Test locally: `sam local invoke <FunctionName> -e tests/events/sample.json`
4. Deploy: `python publish.py --project-name <project-name> --admin-email <email> --region <region> --skip-ui`
5. Monitor: `aws logs tail /aws/lambda/RAGStack-<project-name>-<FunctionName> --follow`

### Making Changes to UI

1. Edit code in `src/ui/src/`
2. Test locally: `cd src/ui && npm start` (requires deployed backend for API calls)
3. Build: `npm run build`
4. Deploy: `python publish.py --project-name <project-name> --admin-email <email> --region <region>` (includes UI build via CodeBuild)
5. Or deploy UI only: `aws s3 sync build/ s3://ragstack-<project-name>-ui-<account-id>/ --delete && aws cloudfront create-invalidation --distribution-id <distribution-id> --paths "/*"`

### Making Changes to Infrastructure

1. Edit `template.yaml` or `src/statemachine/pipeline.asl.json`
2. Run `sam build`
3. Deploy: `python publish.py --project-name <project-name> --admin-email <email> --region <region>`
4. Monitor stack update: `aws cloudformation describe-stack-events --stack-name RAGStack-<project-name> --max-items 20`

## Testing Strategy

### Unit Tests (pytest)

Located in `lib/ragstack_common/test_*.py` and `tests/unit/`:
```bash
pytest tests/unit/ -v
pytest lib/ragstack_common/test_bedrock.py -v
```

### Integration Tests (pytest)

Located in `tests/integration/`:
```bash
# Requires deployed stack
pytest tests/integration/ --stack-name RAGStack-<project-name> -v
```

### Manual End-to-End Testing

1. Deploy stack: `python publish.py --project-name <project-name> --admin-email <email> --region <region>`
2. Access UI (CloudFront URL from outputs)
3. Upload test document from `tests/sample-documents/`
4. Monitor Dashboard for status changes
5. Search for document content
6. Verify results match expected output

### Sample Documents

Test documents are located in `tests/sample-documents/`:
- `text-native.pdf` - PDF with embedded text (tests direct extraction)
- `scanned.pdf` - Scanned PDF image (tests OCR)
- `invoice.jpg` - Image (tests image OCR)
- `spreadsheet.xlsx` - Excel (tests format conversion)
- `document.docx` - Word (tests format conversion)

## Important Implementation Details

### ProcessDocument Lambda

**Key files**: `src/lambda/process_document/index.py`, `lib/ragstack_common/ocr.py`

**Flow**:
1. Downloads document from S3 Input bucket
2. Detects format (PDF, image, Office doc, text)
3. Converts Office docs to PDF using LibreOffice (included in Lambda layer)
4. Checks if PDF is text-native using PyMuPDF
5. If text-native: extracts text directly (fast, no cost)
6. If scanned: runs OCR (Textract or Bedrock)
7. Extracts embedded images from PDFs
8. Saves extracted text and images to S3 Output bucket
9. Updates DynamoDB tracking table

**Memory**: 3008 MB (maximum) for OCR processing and format conversion
**Timeout**: 15 minutes for large documents

### GenerateEmbeddings Lambda

**Key files**: `src/lambda/generate_embeddings/index.py`, `lib/ragstack_common/bedrock.py`

**Flow**:
1. Reads extracted text from S3 Output bucket
2. Chunks text (300 tokens, 15% overlap)
3. Generates text embeddings via Bedrock Titan Embed Text V2
4. For each extracted image:
   - Reads image bytes from S3
   - Generates image embedding via Bedrock Titan Embed Image
5. Batches processing if >20 pages (with 2s delay between batches)
6. Saves embeddings to S3 Vector bucket in format expected by Bedrock KB
7. Updates DynamoDB tracking and metering tables

**Memory**: 2048 MB
**Timeout**: 15 minutes for large documents

### Knowledge Base Setup

Per ADR-002, the Knowledge Base is created manually after stack deployment:

1. AWS Console → Bedrock → Knowledge bases → Create
2. Select S3 data source, point to Vector bucket from stack outputs
3. Configure chunking (300 tokens, 15% overlap)
4. Use Titan Embed Text V2 for embeddings
5. Store KB ID and Data Source ID in SSM Parameter Store
6. Update QueryKB Lambda environment variable with KB ID

For production deployments, the custom resource at `src/lambda/kb_custom_resource/` can automate this.

## Troubleshooting

### Deployment Fails

- Check SAM CLI version: `sam --version` (requires 1.100.0+)
- Verify Python 3.12+ and Node.js 18+
- Check AWS credentials: `aws sts get-caller-identity`
- Review CloudFormation events: `aws cloudformation describe-stack-events --stack-name RAGStack-<project-name>`

### Documents Stuck in PROCESSING

- Check Step Functions execution: `aws stepfunctions list-executions --state-machine-arn <arn>`
- View Lambda logs: `aws logs tail /aws/lambda/RAGStack-<project-name>-ProcessDocument --follow`
- Common causes: Bedrock throttling, Lambda timeout, unsupported format

### UI Not Loading

- Check CloudFront distribution status
- Invalidate cache: `aws cloudfront create-invalidation --distribution-id <distribution-id> --paths "/*"`
- Verify S3 bucket has files: `aws s3 ls s3://ragstack-<project-name>-ui-<account-id>/`
- Check browser console for errors (often authentication issues)

### Search Returns No Results

- Verify Knowledge Base is created and synced
- Check KB ID is set in QueryKB Lambda environment variables
- Wait 2-10 minutes after first document upload for initial KB sync
- View KB sync status in AWS Console → Bedrock → Knowledge bases

## Security Notes

- All S3 buckets have public access blocked and encryption at rest (SSE-S3)
- CloudFront serves UI over HTTPS only
- Cognito enforces strong password policies (8+ chars, uppercase, lowercase, number, symbol)
- Lambda functions use least-privilege IAM roles
- CloudTrail logs all S3 and Lambda operations
- DynamoDB tables have encryption at rest and point-in-time recovery enabled

## Cost Optimization

- Text-native PDF detection reduces OCR costs by 50%+
- S3 Vectors are 10x cheaper than OpenSearch Serverless
- Working bucket has 7-day lifecycle policy for temp files
- DynamoDB uses on-demand billing (pay per request)
- Lambda memory is right-sized for each function
- CloudWatch logs have 30-day retention
- Monthly budget alarm at $100 with 80% threshold alert

## Related Documentation

- `README.md` - Project overview and quick start
- `docs/ARCHITECTURE.md` - Detailed architecture and ADRs
- `docs/DEPLOYMENT.md` - Deployment prerequisites and steps
- `docs/CONFIGURATION.md` - Configuration options and tuning
- `docs/USER_GUIDE.md` - WebUI usage instructions
- `docs/TESTING.md` - Testing procedures and benchmarks
- `docs/TROUBLESHOOTING.md` - Common issues and solutions
- `docs/OPTIMIZATION.md` - Performance tuning strategies
