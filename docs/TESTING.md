# Testing Guide

## Overview

This guide covers testing RAGStack-Lambda from development to production, including unit tests, integration tests, end-to-end workflows, and performance benchmarks.

## Table of Contents

- [Overview](#overview)
- [Local Testing](#local-testing)
- [Quick Start](#quick-start)
- [Test Levels](#test-levels)
- [Prerequisites](#prerequisites)
- [Sample Documents](#sample-documents)
- [End-to-End Test Flow](#end-to-end-test-flow)
- [Integration Testing with pytest](#integration-testing-with-pytest)
- [Performance Testing](#performance-testing)
- [Monitoring During Tests](#monitoring-during-tests)
- [Troubleshooting](#troubleshooting)
- [Test Cleanup](#test-cleanup)
- [Automated Testing](#automated-testing-with-github-actions)
- [Common Test Scenarios](#common-test-scenarios)

---

## Local Testing

Run tests and linting locally without AWS deployment for rapid development iteration.

### Purpose & Benefits

Local testing enables:

- ✅ **Fast feedback** - No deployment required, tests run in seconds
- ✅ **Cost savings** - No AWS charges during development
- ✅ **Offline development** - Work without internet connection
- ✅ **Pre-commit validation** - Catch issues before pushing code
- ✅ **CI/CD readiness** - Same commands work in GitHub Actions

### Prerequisites

**One-time setup:**

```bash
# Backend dependencies (Python)
pip install -r requirements-dev.txt

# Frontend dependencies (Node.js) - NOTE: Currently has dependency issues
cd src/ui
npm install
cd ../..
```

**Verify installations:**

```bash
# Check ruff
ruff --version
# Output: ruff 0.14.2

# Check pytest
pytest --version
# Output: pytest 8.x.x
```

### Quick Reference

| Command | Purpose | Time |
|---------|---------|------|
| `npm run lint` | Lint backend + frontend | ~15s |
| `npm run lint:fix` | Auto-fix lint issues | ~15s |
| `npm test` | Run all unit tests | ~5s |
| `npm run test:all` | Lint + test everything | ~20s |
| `npm run lint:backend` | Lint Python code only | ~3s |
| `npm run test:backend` | Run pytest unit tests only | ~1s |
| `npm run lint:frontend` | Lint React code only (needs fix) | ~5s |
| `npm run test:frontend` | Run Vitest tests only (needs fix) | ~2s |

### Backend Testing

#### Linting with Ruff

**Check code quality:**

```bash
# Lint all Python code
npm run lint:backend

# Or use ruff directly
ruff check .

# Check specific directory
ruff check lib/ragstack_common/
```

**Auto-fix issues:**

```bash
# Fix all auto-fixable violations
npm run lint:backend:fix

# Or use ruff directly
ruff check . --fix
```

**Format code:**

```bash
# Format all Python files
npm run format:backend

# Check formatting without changing files
npm run format:backend:check
```

#### Running Tests with pytest

**Unit tests only (fast):**

```bash
# Run all unit tests (excludes integration tests)
npm run test:backend

# Or use pytest directly
pytest -m "not integration"

# Run specific test file
pytest lib/ragstack_common/test_bedrock.py

# Run specific test function
pytest lib/ragstack_common/test_config.py::test_init_with_table_name
```

**All tests (includes integration):**

```bash
# Run all tests including integration (requires AWS credentials)
npm run test:backend:all

# Or use pytest directly
pytest
```

**With coverage:**

```bash
# Generate coverage report
npm run test:backend:coverage

# View HTML coverage report
open htmlcov/index.html
```

**Verbose output:**

```bash
# Show detailed test output
pytest -v

# Show print statements
pytest -s

# Both verbose and print
pytest -vs
```

#### Understanding Test Markers

Tests are marked with pytest markers:

- `@pytest.mark.integration` - Integration tests (require AWS)
- No marker - Unit tests (no AWS required)

### Frontend Testing

**⚠️ Note:** Frontend testing currently has dependency version issues in `src/ui/package.json`. The commands are configured correctly in root `package.json`, but need `src/ui/package.json` fixes before they'll work.

#### Linting with ESLint (once fixed)

```bash
# Lint React code
npm run lint:frontend

# Auto-fix lint issues
npm run lint:frontend:fix
```

#### Running Tests with Vitest (once fixed)

```bash
# Run all frontend tests
npm run test:frontend

# Run in watch mode
npm run test:frontend:watch

# Generate coverage report
npm run test:frontend:coverage
```

### Unified Commands

Run backend and frontend together:

```bash
# Lint everything
npm run lint

# Auto-fix everything
npm run lint:fix

# Run all tests
npm test

# Complete validation (lint + test)
npm run test:all
```

### Common Workflows

#### Pre-Commit Workflow

Before committing code:

```bash
# 1. Format and lint
npm run format
npm run lint:fix

# 2. Run tests
npm test

# 3. Check for errors
npm run lint

# 4. If all pass, commit
git add .
git commit -m "feat: add new feature"
```

#### Debugging Failed Tests

**Step 1: Identify the failure**

```bash
# Run tests with verbose output
pytest -vs

# Run specific failing test
pytest path/to/test_file.py::test_function_name -vs
```

**Step 2: Check the code**

```bash
# Lint the file to check for issues
ruff check path/to/file.py
```

**Step 3: Fix and re-test**

```bash
# Make changes, then re-run
pytest path/to/test_file.py::test_function_name -vs
```

#### Continuous Testing During Development

**Python/Backend:**

```bash
# Install pytest-watch for auto-rerunning
pip install pytest-watch

# Watch for changes and auto-run tests
ptw -- -m "not integration"
```

**Frontend:**

```bash
# Vitest has built-in watch mode
npm run test:frontend:watch
```

### Troubleshooting

#### "ruff: command not found"

**Solution:**

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Verify installation
ruff --version
```

#### "pytest: command not found"

**Solution:**

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Verify installation
pytest --version
```

#### "Module not found" in frontend tests

**Solution:**

```bash
# Install frontend dependencies
cd src/ui
npm install
cd ../..
```

#### Tests fail with import errors

**Cause:** Some Lambda function tests have path setup issues (pre-existing).

**Workaround:** Run only working tests:

```bash
# Run only ragstack_common tests
pytest lib/ragstack_common/ tests/unit/test_ragstack_common_install.py
```

#### Frontend commands fail

**Cause:** `src/ui/package.json` has invalid vitest version (^6.0.3 doesn't exist).

**Status:** Known issue, needs `src/ui/package.json` update to fix vitest version.

**Workaround:** Test backend only for now:

```bash
npm run lint:backend
npm run test:backend
```

### Performance Expectations

Typical timing on a standard development machine:

| Command | Expected Time | Notes |
|---------|--------------|-------|
| `npm run lint:backend` | < 5s | ~34 Python files |
| `npm run test:backend` | < 2s | 46 unit tests |
| `npm run lint:frontend` | < 5s | Once dependencies fixed |
| `npm run test:frontend` | < 3s | Once dependencies fixed |
| `npm run lint` | < 10s | Backend + frontend |
| `npm test` | < 5s | All unit tests |
| `npm run test:all` | < 15s | Lint + all tests |

**Note:** Times will increase as the codebase grows. Re-benchmark quarterly.

### Best Practices

1. **Run locally before pushing** - Catch issues early with `npm run test:all`
2. **Use watch mode during development** - Get instant feedback on changes
3. **Fix lint issues immediately** - Don't accumulate technical debt
4. **Write tests alongside code** - Maintain high coverage
5. **Keep dependencies updated** - Run `pip install -r requirements-dev.txt` regularly
6. **Use verbose mode when debugging** - `pytest -vs` shows full output

---

## Quick Start

**Test your deployment in 5 minutes:**

```bash
# 1. Deploy the stack
python publish.py --project-name <project-name> --admin-email <email> --region <region> --admin-email your@email.com

# 2. Sign in to the WebUI (check email for password)
# URL in deployment outputs

# 3. Upload a test document
# Dashboard → Upload → Drag & drop a PDF

# 4. Monitor processing
# Dashboard → Watch status change to INDEXED

# 5. Search for content
# Search → Enter query → Verify results
```

## Test Levels

1. **Unit Tests** - Individual functions and utilities
2. **Integration Tests** - Lambda functions + AWS services
3. **End-to-End Tests** - Full pipeline from upload to search
4. **UI Tests** - React components and user workflows
5. **Performance Tests** - Load, concurrency, and throughput

## Prerequisites

Before testing, ensure you have:

- ✅ Deployed stack (run `python publish.py`)
- ✅ Sample documents in `tests/sample-documents/`
- ✅ AWS CLI configured with valid credentials
- ✅ Access to CloudWatch logs
- ✅ pytest installed (`pip install pytest boto3`)

## Sample Documents

We provide test documents in `tests/sample-documents/`:

| File | Type | Purpose |
|------|------|---------|
| text-native.pdf | PDF with embedded text | Test direct text extraction |
| scanned.pdf | Scanned PDF image | Test OCR processing |
| invoice.jpg | Image | Test image OCR |
| spreadsheet.xlsx | Excel | Test format conversion |
| document.docx | Word | Test format conversion |

## End-to-End Test Flow

### Test 1: Text-Native PDF

**Expected behavior:** Should skip OCR and use direct text extraction.

```bash
# 1. Upload via UI
# - Navigate to Upload page
# - Upload tests/sample-documents/text-native.pdf
# - Note document ID

# 2. Monitor processing
# - Go to Dashboard
# - Watch status change: UPLOADED → PROCESSING → OCR_COMPLETE → EMBEDDING_COMPLETE → INDEXED
# - Verify "Text Native" column shows ✓

# 3. Check output
DOCUMENT_ID="<your-document-id>"
STACK_NAME="RAGStack-<project-name>"

OUTPUT_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`OutputBucketName`].OutputValue' \
  --output text)

# Download extracted text
aws s3 cp "s3://$OUTPUT_BUCKET/$DOCUMENT_ID/full_text.txt" /tmp/extracted.txt
cat /tmp/extracted.txt

# Should contain extracted text, not OCR artifacts
```

**Success criteria:**
- ✅ Status reaches INDEXED
- ✅ is_text_native = true
- ✅ Text extracted correctly
- ✅ Processing time < 30 seconds

### Test 2: Scanned PDF OCR

**Expected behavior:** Should run OCR (Textract or Bedrock).

```bash
# 1. Upload tests/sample-documents/scanned.pdf via UI

# 2. Monitor processing (will take longer due to OCR)

# 3. Check OCR results
# Download and verify text quality
```

**Success criteria:**
- ✅ Status reaches INDEXED
- ✅ is_text_native = false
- ✅ OCR confidence > 80% (if using Textract)
- ✅ Processing time < 2 minutes

### Test 3: Image OCR

**Expected behavior:** Should process single-page image.

```bash
# 1. Upload tests/sample-documents/invoice.jpg via UI

# 2. Verify single-page document processed
```

**Success criteria:**
- ✅ total_pages = 1
- ✅ Text extracted from image
- ✅ Image embedding generated

### Test 4: Format Conversion

**Expected behavior:** Should convert Office doc to PDF, then process.

```bash
# 1. Upload tests/sample-documents/spreadsheet.xlsx via UI

# 2. Verify conversion happened
# Check working bucket for converted PDF
```

**Success criteria:**
- ✅ Document converted to PDF
- ✅ Text extracted from cells
- ✅ Processing completes

### Test 5: Knowledge Base Search

**Expected behavior:** Should find indexed documents via semantic search.

```bash
# 1. Wait for all test documents to be INDEXED

# 2. Go to Search page

# 3. Enter query: "invoice"

# 4. Verify results include invoice.jpg

# 5. Enter query: "What is in the spreadsheet?"

# 6. Verify results include spreadsheet.xlsx content
```

**Success criteria:**
- ✅ Search returns relevant results
- ✅ Relevance scores > 60%
- ✅ Source documents correctly attributed
- ✅ Search latency < 3 seconds

### Test 6: Error Handling

**Expected behavior:** Should handle failures gracefully.

```bash
# 1. Upload an unsupported file (e.g., .exe)
# Expected: Should show error "Unsupported file type"

# 2. Upload a corrupted PDF
# Expected: Status should change to FAILED with error message
```

**Success criteria:**
- ✅ Unsupported files rejected at upload
- ✅ Processing errors recorded in DynamoDB
- ✅ Error messages visible in UI
- ✅ No stuck documents in PROCESSING state

## Integration Testing with pytest

```bash
# Run integration tests
cd tests/integration
pip install pytest boto3

# Set environment variables
export STACK_NAME=RAGStack-<project-name>
export INPUT_BUCKET=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==`InputBucketName`].OutputValue' --output text)
export TRACKING_TABLE=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==`TrackingTableName`].OutputValue' --output text)

# Run tests
pytest test_pipeline.py -v
```

## Performance Testing

### Concurrent Upload Test

```bash
# Upload 10 documents simultaneously
for i in {1..10}; do
  cp tests/sample-documents/text-native.pdf /tmp/test-$i.pdf
  # Upload via UI or AWS CLI
done

# Monitor processing
# All should complete without errors
```

**Success criteria:**
- ✅ All 10 documents process successfully
- ✅ No Lambda throttling errors
- ✅ No DynamoDB throttling

### Large Document Test

```bash
# Upload a large PDF (100+ pages)
# Monitor Lambda execution time
# Should not timeout (15 min limit)
```

**Success criteria:**
- ✅ Processing completes within Lambda timeout
- ✅ All pages processed
- ✅ Memory usage acceptable

## Monitoring During Tests

### Check CloudWatch Logs

```bash
# View ProcessDocument logs
aws logs tail /aws/lambda/RAGStack-<project-name>-ProcessDocument --follow

# View Step Functions executions
aws stepfunctions list-executions \
  --state-machine-arn <ARN> \
  --max-results 10
```

### Check DynamoDB for Metering

```bash
# Query metering data
METERING_TABLE=$(aws cloudformation describe-stacks \
  --stack-name RAGStack-<project-name> \
  --query 'Stacks[0].Outputs[?OutputKey==`MeteringTableName`].OutputValue' \
  --output text)

aws dynamodb scan \
  --table-name $METERING_TABLE \
  --limit 10
```

## Troubleshooting

### Document Stuck in PROCESSING

```bash
# Check Step Functions execution
aws stepfunctions list-executions \
  --state-machine-arn <ARN> \
  --status-filter RUNNING

# Check Lambda errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/RAGStack-<project-name>-ProcessDocument \
  --filter-pattern "ERROR"
```

### Knowledge Base Not Indexing

```bash
# Check if embeddings were generated
VECTOR_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name RAGStack-<project-name> \
  --query 'Stacks[0].Outputs[?OutputKey==`VectorBucketName`].OutputValue' \
  --output text)

aws s3 ls "s3://$VECTOR_BUCKET/" --recursive

# Manually trigger KB sync (if needed)
# See ADR-004 in architecture decisions
```

### UI Not Loading

```bash
# Check CloudFront distribution
aws cloudfront get-distribution \
  --id <DISTRIBUTION_ID>

# Invalidate cache
./scripts/invalidate_cloudfront.sh RAGStack-<project-name>

# Check S3 UI bucket
UI_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name RAGStack-<project-name> \
  --query 'Stacks[0].Outputs[?OutputKey==`UIBucketName`].OutputValue' \
  --output text)

aws s3 ls "s3://$UI_BUCKET/"
```

## Test Cleanup

```bash
# Delete test documents from S3
aws s3 rm "s3://$INPUT_BUCKET/" --recursive
aws s3 rm "s3://$OUTPUT_BUCKET/" --recursive
aws s3 rm "s3://$VECTOR_BUCKET/" --recursive

# Delete tracking records from DynamoDB
# (Optional - will auto-cleanup based on TTL if configured)
```

## Automated Testing with GitHub Actions

See `.github/workflows/test.yml` for CI/CD pipeline.

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run unit tests
        run: pytest tests/unit/
      - name: Deploy to test environment
        run: python publish.py --project-name test-project --admin-email test@example.com --region us-east-1
      - name: Run integration tests
        run: pytest tests/integration/ --stack-name RAGStack-test-project
```

## Test Coverage Goals

| Component | Target Coverage | Current |
|-----------|----------------|---------|
| Shared Library | 90% | TBD |
| Lambda Functions | 80% | TBD |
| Step Functions | 100% (all paths) | TBD |
| UI Components | 70% | TBD |

Run coverage reports:
```bash
# Python coverage
pytest --cov=lib --cov=src/lambda --cov-report=html

# JavaScript coverage
cd src/ui
npm run test:coverage
```

## Performance Benchmarks

Expected performance for standard documents:

| Document Type | Pages | Processing Time | Cost |
|--------------|-------|----------------|------|
| Text-native PDF | 10 | < 5 sec | $0.001 |
| Scanned PDF (Textract) | 10 | < 30 sec | $0.015 |
| Scanned PDF (Bedrock) | 10 | < 45 sec | $0.25 |
| Image (JPG) | 1 | < 10 sec | $0.002 |
| Office Doc | 5 | < 15 sec | $0.008 |

## Common Test Scenarios

### Scenario 1: First-Time User

1. Deploy stack
2. Receive Cognito temporary password via email
3. Sign in to UI
4. Change password
5. Upload first document
6. Wait for processing
7. Search for document content

### Scenario 2: Bulk Upload

1. Upload 100 documents
2. Monitor processing dashboard
3. Verify all complete within expected time
4. Check cost metrics in metering table

### Scenario 3: Mixed Document Types

1. Upload PDF, image, Word doc, Excel spreadsheet
2. Verify each processes correctly
3. Search across all document types
4. Verify results include all formats

## Test Data Management

Create realistic test documents:

```python
# Generate sample PDF
import fitz

doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), """
Sample Invoice

Date: 2025-01-15
Invoice #: INV-001
Amount: $1,234.56

Items:
- Product A: $500
- Product B: $734.56
""")

doc.save("tests/sample-documents/text-native.pdf")
doc.close()
```

## Continuous Testing

Set up automated tests to run:
- **On every commit**: Unit tests
- **On pull request**: Integration tests
- **Nightly**: Full end-to-end tests with cleanup
- **Weekly**: Performance benchmarks

## Support

For testing issues:
- Check CloudWatch logs first
- Review DynamoDB tracking table
- Verify Step Functions execution history
- Consult [Troubleshooting Guide](TROUBLESHOOTING.md)
- Open GitHub issue with test details

---

## Related Documentation

- **[Deployment Guide](DEPLOYMENT.md)** - How to deploy the system for testing
- **[User Guide](USER_GUIDE.md)** - How to use the WebUI for manual testing
- **[Architecture Guide](ARCHITECTURE.md)** - Understanding the system components
- **[Configuration Guide](CONFIGURATION.md)** - Test environment configuration
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Debugging failed tests
