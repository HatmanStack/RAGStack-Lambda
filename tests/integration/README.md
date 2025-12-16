# Integration Tests

Tests for the RAGStack-Lambda processing pipeline against a deployed AWS stack.

## Quick Start

```bash
# Set environment variables
export STACK_NAME=RAGStack-dev
export DATA_BUCKET=ragstack-dev-data-xxxxx
export TRACKING_TABLE=RAGStack-dev-Tracking

# Run tests
npm run test:backend:integration
# or
pytest tests/integration/ -m integration -v
```

## Prerequisites

- AWS credentials configured
- Deployed SAM stack
- Environment variables set (see above)

## Test Coverage

- ✅ Text-native PDF processing
- ✅ Scanned PDF OCR (Textract)
- ✅ Image OCR
- ✅ Embedding generation
- ✅ Knowledge Base indexing

## Full Documentation

See **[docs/TESTING.md](../../docs/TESTING.md#integration-testing)** for:
- Detailed setup instructions
- Running individual tests
- Troubleshooting failed tests
- Performance testing
- End-to-end test workflows

## Sample Test Documents

Generate test data:
```bash
cd ../sample-documents
python3 generate_samples.py
```

See **[docs/TESTING.md](../../docs/TESTING.md#sample-test-documents)** for details.
