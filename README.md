# RAGStack-Lambda

Serverless OCR-to-Knowledge Base pipeline on AWS. Upload documents, extract text with OCR, generate embeddings, and query using Amazon Bedrock Knowledge Base.

## Features

- ✅ **Multi-format support** - PDF, images, Office docs, text files
- ✅ **Dual OCR backends** - AWS Textract or Amazon Bedrock
- ✅ **Intelligent routing** - Text-native PDF optimization
- ✅ **Multimodal embeddings** - Text + image embeddings
- ✅ **S3 vector storage** - Cost-effective Knowledge Base backend
- ✅ **React WebUI** - Upload, monitor, and search documents
- ✅ **One-click deployment** - AWS SAM automation

## Architecture

```
User → CloudFront → React UI
         ↓
     AppSync API
         ↓
     Lambda Functions → Step Functions → OCR → Embeddings → S3 Vectors
         ↓                                                        ↓
     DynamoDB Tracking                                 Bedrock Knowledge Base
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture.

## Quick Start

### Prerequisites

- AWS Account with Bedrock access
- AWS CLI configured
- Python 3.13+
- Node.js 22+
- SAM CLI
- Docker (for local testing)

### Enable Bedrock Models

Go to AWS Console > Bedrock > Model access and enable:
- `anthropic.claude-3-5-haiku-20241022-v1:0`
- `amazon.titan-embed-text-v2:0`
- `amazon.titan-embed-image-v1`

### Deploy

```bash
# Clone repository
git clone https://github.com/your-org/RAGStack-Lambda.git
cd RAGStack-Lambda

# Deploy stack (all parameters required)
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region>

# Example: Deploy customer docs project
python publish.py \
  --project-name customer-docs \
  --admin-email admin@example.com \
  --region us-east-1

# Access UI (CloudFront URL shown in output)
# Check email for temporary password
```

**Note**: Project name must be lowercase alphanumeric + hyphens, 2-32 chars, starting with a letter.

The deployment will:
1. Validate inputs and check prerequisites (Python 3.13+, Node.js 22+, AWS CLI, SAM CLI)
2. Copy shared libraries to Lambda functions
3. Build Lambda functions via SAM
4. Deploy infrastructure via CloudFormation
5. Build and deploy React UI via CodeBuild
6. Output CloudFront URL and credentials

### Upload a Document

1. Navigate to CloudFront URL (shown in deployment output)
2. Sign in (check email for temporary password)
3. Go to Upload page
4. Drag and drop a PDF or image
5. Monitor processing on Dashboard
6. Search documents once indexed

## Configuration

Deploy with required parameters:

```bash
# All parameters required
python publish.py \
  --project-name <project-name> \      # lowercase, alphanumeric + hyphens, 2-32 chars
  --admin-email <email> \              # valid email for Cognito and alerts
  --region <region>                    # AWS region (e.g., us-east-1)

# Optional: Skip UI build for backend-only changes
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region> \
  --skip-ui
```

**Advanced Configuration:**

Edit `template.yaml` parameters for model configuration:
- `OcrBackend`: Choose between `textract` (cost-effective) or `bedrock` (multimodal)
- `BedrockOcrModelId`: Bedrock model for OCR (default: claude-3-5-haiku)
- `TextEmbedModelId`: Text embedding model (default: titan-embed-text-v2)
- `ImageEmbedModelId`: Image embedding model (default: titan-embed-image-v1)

## Cost Estimate

For ~1000 documents/month (5 pages each):

| Service | Monthly Cost |
|---------|-------------|
| Textract | $5-15 |
| Bedrock Embeddings | $0.10-0.30 |
| S3 | $0.23 |
| Lambda | $0.20 |
| DynamoDB | $1.25 |
| CloudFront | $0.10 |
| **Total** | **~$7-17/month** |

Using Bedrock OCR instead of Textract: **~$27-77/month**

## Development

### Local Testing

RAGStack-Lambda supports comprehensive local testing without AWS deployment.

**Quick Start:**

```bash
# Install dependencies (one-time setup)
pip install -r requirements-dev.txt
cd src/ui && npm install && cd ../..

# Run all tests
npm test

# Lint all code
npm run lint

# Full test suite (lint + tests)
npm run test:all
```

**Available Commands:**

| Command | Purpose | Time |
|---------|---------|------|
| `npm run lint` | Auto-fix and lint all code | ~5s |
| `npm test` | Run all unit tests | ~3s |
| `npm run test:all` | Lint + test everything | ~8s |
| `npm run test:backend` | Run backend tests only | ~1s |
| `npm run test:frontend` | Run frontend tests only | ~2s |
| `npm run test:coverage` | Generate coverage reports | ~5s |

**Benefits:**
- ✅ Instant feedback (no deployment required)
- ✅ No AWS costs during development
- ✅ Work offline
- ✅ Pre-commit validation

For detailed testing documentation, see [TESTING.md](docs/TESTING.md).

### SAM Local Testing (Optional)

Test Lambda functions locally with SAM:

```bash
# Build
sam build

# Test Lambda locally
sam local invoke ProcessDocumentFunction -e tests/events/sample.json

# Start local API
sam local start-api
```

### UI Development

```bash
cd src/ui
npm install
npm start
# or
npm run dev
```

### Subagent System

This project includes specialized AI subagents for exploring the base repository patterns:

**Available Subagents:**
- `explore-base-testing` - Testing patterns and configurations
- `explore-base-architecture` - Lambda structure and design patterns
- `explore-base-docs` - Documentation style and structure
- `explore-base-infrastructure` - SAM templates and deployment patterns
- `explore-base-general` - General-purpose base repo explorer

**Using Subagents:**

List all available subagents:
```bash
/agents
```

Invoke a specific subagent:
```bash
Use explore-base-testing to find pytest configuration patterns
```

The subagents can be invoked automatically when Claude judges they're helpful for the current task, or explicitly invoked as shown above.

**Documentation:** See [.claude/SUBAGENTS_USAGE.md](.claude/SUBAGENTS_USAGE.md) for detailed usage guide.

### CI/CD Integration

GitHub Actions workflow automatically runs all tests on every push and PR:
- Lints backend (ruff) and frontend (ESLint)
- Runs all unit tests (pytest + Vitest)
- Generates coverage reports
- Optional integration tests on main branch

**Workflow location:** `.github/workflows/test.yml`

See [docs/TESTING.md](docs/TESTING.md#cicd-integration) for CI/CD setup details.

## Documentation

### Core Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - System architecture, components, and design decisions
- [Deployment Guide](docs/DEPLOYMENT.md) - Prerequisites, deployment steps, and post-deployment setup
- [Configuration Guide](docs/CONFIGURATION.md) - Configuring the system and customizing parameters
- [User Guide](docs/USER_GUIDE.md) - Using the WebUI to upload, monitor, and search documents
- [Testing Guide](docs/TESTING.md) - End-to-end testing procedures
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

### Advanced Topics

- [Optimization Guide](docs/OPTIMIZATION.md) - Performance tuning and cost optimization strategies

## Project Structure

```
RAGStack-Lambda/
├── lib/                           # Shared libraries
│   └── ragstack_common/           # Common utilities
├── src/
│   ├── lambda/                    # Lambda functions
│   │   ├── process_document/      # Document processor
│   │   ├── generate_embeddings/   # Embedding generator
│   │   ├── query_kb/              # Knowledge Base query
│   │   └── appsync_resolvers/     # AppSync resolvers
│   ├── statemachine/              # Step Functions
│   │   └── pipeline.asl.json
│   ├── api/                       # GraphQL API
│   │   └── schema.graphql
│   └── ui/                        # React WebUI
├── template.yaml                  # CloudFormation/SAM template
├── samconfig.toml                 # SAM configuration (build settings only)
├── publish.py                     # Deployment automation
└── docs/                          # Documentation
```

## Troubleshooting

### Deployment Issues

**Problem**: SAM build fails
```bash
# Clean and rebuild
sam build --use-container
```

**Problem**: Missing Bedrock permissions
- Ensure models are enabled in AWS Console > Bedrock > Model access
- Wait 5-10 minutes after enabling models

**Problem**: CloudFormation stack fails
```bash
# Check stack events
aws cloudformation describe-stack-events --stack-name RAGStack-<project-name>
```

### Runtime Issues

**Problem**: Documents stuck in PROCESSING
```bash
# Check Step Functions execution
aws stepfunctions list-executions --state-machine-arn <ARN>

# Check Lambda logs
aws logs tail /aws/lambda/RAGStack-<project-name>-ProcessDocument --follow
```

**Problem**: UI not loading
```bash
# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id <distribution-id> --paths "/*"

# Check S3 bucket
aws s3 ls s3://ragstack-<project-name>-ui-<account-id>/
```

## Security

- **Encryption at rest**: S3 SSE, DynamoDB encryption
- **Encryption in transit**: HTTPS/TLS everywhere
- **IAM**: Least-privilege policies for all resources
- **Cognito**: MFA optional, password policies enforced
- **S3**: Public access blocked
- **CloudFront**: HTTPS-only with custom error pages

## License

MIT

## Contributing

Pull requests welcome! Please open an issue first to discuss proposed changes.

## Support

For issues or questions:
- Check [docs/TESTING.md](docs/TESTING.md) for troubleshooting
- Review CloudWatch logs for errors
- Open a GitHub issue with error details
