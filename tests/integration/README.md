# Integration Tests

Tests for the RAGStack-Lambda processing pipeline.

## Prerequisites

- AWS credentials configured
- Deployed stack (from Phase 3)
- Environment variables:
  - `STACK_NAME`: CloudFormation stack name
  - `INPUT_BUCKET`: S3 input bucket name
  - `TRACKING_TABLE`: DynamoDB tracking table name

## Running Tests

```bash
# Install dependencies
pip install pytest boto3

# Set environment
export STACK_NAME=RAGStack-dev
export INPUT_BUCKET=ragstack-dev-input-...
export TRACKING_TABLE=RAGStack-dev-Tracking

# Run tests
pytest tests/integration/
```

## Test Coverage

- ✅ Text-native PDF processing
- ✅ Scanned PDF OCR (Textract)
- ✅ Image OCR
- ✅ Embedding generation
- ✅ Knowledge Base indexing
