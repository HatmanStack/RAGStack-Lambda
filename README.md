# RAGStack-Lambda

Serverless document processing pipeline on AWS. Upload documents (PDF, images, Office), extract text with OCR, generate embeddings, and query using Amazon Bedrock Knowledge Base.

**Features**: Multi-format OCR • Dual backends (Textract/Bedrock) • Semantic search • Cost-effective S3 vector storage • React WebUI • One-click deployment

## Quick Start

### Prerequisites
- AWS Account with Bedrock access (models enabled in AWS Console)
- Python 3.13+, Node.js 24+
- AWS CLI, SAM CLI, Docker

### Deploy (5-minute setup)

```bash
git clone https://github.com/your-org/RAGStack-Lambda.git
cd RAGStack-Lambda

python publish.py \
  --project-name my-docs \
  --admin-email admin@example.com \
  --region us-east-1
```

The deployment:
1. ✅ Validates prerequisites
2. ✅ Builds and deploys Lambda functions
3. ✅ Deploys infrastructure (CloudFormation/SAM)
4. ✅ Builds and deploys React UI (CodeBuild)
5. ✅ Outputs CloudFront URL + temp credentials

See [Deployment Guide](docs/DEPLOYMENT.md) for detailed steps.

### Enable Bedrock Models

Before deploying, enable these models in AWS Console > Bedrock > Model access:
- `anthropic.claude-3-5-haiku-20241022-v1:0` (OCR)
- `amazon.titan-embed-text-v2:0` (Text embeddings)
- `amazon.titan-embed-image-v1` (Image embeddings)

## What It Does

```
Upload Document → Process (OCR) → Generate Embeddings → Bedrock KB
                                                          ↓
                    Search Interface (React UI) ←→ Query Bedrock KB
```

- **Upload page**: Drag-drop PDF, images, Office docs, text
- **Dashboard**: Monitor processing status
- **Search page**: Query documents, get results with sources

## Cost Estimate

For ~1000 documents/month (5 pages each):

| Service | Cost |
|---------|------|
| Textract + Embeddings | ~$5-15 |
| S3 + Lambda + DynamoDB | ~$2 |
| CloudFront + Bedrock | ~$0.5 |
| **Total** | **~$7-18/month** |

(Using Bedrock OCR instead: ~$25-75/month)

## Documentation

**Getting Started:**
- [Deployment Guide](docs/DEPLOYMENT.md) - Step-by-step deployment
- [Architecture Overview](docs/ARCHITECTURE.md) - System design and components
- [User Guide](docs/USER_GUIDE.md) - How to use the web UI

**Development:**
- [Development Guide](docs/DEVELOPMENT.md) - Local setup, testing, linting
- [Configuration Guide](docs/CONFIGURATION.md) - Runtime configuration options
- [Testing Guide](docs/TESTING.md) - Test structure and running tests

**Operations & Troubleshooting:**
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Optimization Guide](docs/OPTIMIZATION.md) - Performance tuning

## Local Development

```bash
# Install and test locally (no AWS deployment needed)
npm install
npm test              # Run all tests (~3s)
npm run lint          # Lint all code
npm run test:all      # Lint + test (recommended pre-commit)

# Available commands
npm run test:backend          # Python tests only
npm run test:frontend         # React tests only
npm run test:coverage         # Coverage reports
npm run lint:backend          # Python linting
npm run lint:frontend         # React linting
```

## Project Structure

```
RAGStack-Lambda/
├── src/
│   ├── lambda/                 # Lambda functions
│   │   ├── process_document/   # OCR extraction
│   │   ├── generate_embeddings/# Embedding generation
│   │   ├── query_kb/           # Knowledge Base queries
│   │   ├── appsync_resolvers/  # GraphQL API handlers
│   │   ├── configuration_resolver/  # Settings API
│   │   ├── ingest_to_kb/       # Vector indexing
│   │   ├── kb_custom_resource/ # CloudFormation resource
│   │   └── start_codebuild/    # UI build trigger
│   ├── statemachine/           # Step Functions workflow
│   ├── api/                    # GraphQL schema
│   └── ui/                     # React web UI
├── lib/ragstack_common/        # Shared Python library
├── tests/                      # Unit & integration tests
├── template.yaml               # CloudFormation/SAM template
├── publish.py                  # Deployment script
└── docs/                       # Documentation
```

## Architecture Highlights

- **Serverless**: No servers to manage, auto-scaling
- **Cost-effective**: S3-based vector storage (~$1/month vs $50+/month for OpenSearch)
- **Flexible OCR**: Choose Textract (cost) or Bedrock (multimodal)
- **GraphQL API**: AppSync with Cognito auth
- **Real-time UI**: React with AWS Amplify, Cloudscape Design System
- **Runtime config**: DynamoDB-backed settings, no code redeploy needed

## Deployment Parameters

```bash
python publish.py \
  --project-name <name>    # lowercase alphanumeric + hyphens, 2-32 chars
  --admin-email <email>    # for Cognito + alerts
  --region <region>        # AWS region (e.g., us-east-1)
  --skip-ui               # (optional) skip UI build
```

## Security

- ✅ Encryption at rest (S3 SSE, DynamoDB encryption)
- ✅ Encryption in transit (HTTPS/TLS)
- ✅ Least-privilege IAM policies
- ✅ Cognito authentication + optional MFA
- ✅ Public S3 access blocked
- ✅ CloudFront HTTPS-only

## Support

- Check [Troubleshooting](docs/TROUBLESHOOTING.md) for common issues
- Review [Development Guide](docs/DEVELOPMENT.md) for development problems
- Open a GitHub issue with error details

## License

MIT

## Contributing

Pull requests welcome! Please open an issue first to discuss proposed changes.
