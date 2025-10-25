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

# Deploy to AWS
./publish.sh

# When prompted, enter:
# - Admin email address (for initial login)
# - Project name (default: RAGStack)

# Access UI
# Check terminal output for CloudFront URL
```

The deployment script will:
1. Validate prerequisites
2. Build Lambda functions
3. Deploy infrastructure via CloudFormation
4. Build and deploy React UI
5. Configure CloudFront for HTTPS
6. Output the UI URL and credentials

### Upload a Document

1. Navigate to CloudFront URL (shown in deployment output)
2. Sign in (check email for temporary password)
3. Go to Upload page
4. Drag and drop a PDF or image
5. Monitor processing on Dashboard
6. Search documents once indexed

## Configuration

You can customize the deployment by passing additional parameters:

```bash
# Custom project name
./publish.sh --project-name MyDocProcessor

# Different region
./publish.sh --region us-west-2

# Use Bedrock OCR instead of Textract
# (requires updating template.yaml OcrBackend parameter)
```

Edit `template.yaml` parameters for advanced configuration:
- `OcrBackend`: Choose between `textract` or `bedrock`
- `BedrockOcrModelId`: Bedrock model for OCR
- `TextEmbedModelId`: Bedrock model for text embeddings
- `ImageEmbedModelId`: Bedrock model for image embeddings

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
```

### Running Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests (requires deployed stack)
pytest tests/integration/
```

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - Detailed system architecture and design decisions
- [Testing Guide](docs/TESTING.md) - End-to-end testing procedures

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
├── samconfig.toml                 # SAM configuration
├── publish.py                     # Deployment automation
├── publish.sh                     # Deployment wrapper
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
aws cloudformation describe-stack-events --stack-name RAGStack-prod
```

### Runtime Issues

**Problem**: Documents stuck in PROCESSING
```bash
# Check Step Functions execution
aws stepfunctions list-executions --state-machine-arn <ARN>

# Check Lambda logs
aws logs tail /aws/lambda/RAGStack-prod-ProcessDocument --follow
```

**Problem**: UI not loading
```bash
# Invalidate CloudFront cache
./scripts/invalidate_cloudfront.sh RAGStack-prod

# Check S3 bucket
aws s3 ls s3://ragstack-ui-<account-id>/
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

Pull requests welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Support

For issues or questions:
- Check [docs/TESTING.md](docs/TESTING.md) for troubleshooting
- Review CloudWatch logs for errors
- Open a GitHub issue with error details
