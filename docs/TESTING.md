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
| `npm run lint` | Auto-fix and lint all code (backend + frontend) | ~5s |
| `npm test` | Run all unit tests (backend + frontend) | ~3s |
| `npm run test:all` | Lint (with auto-fix) + test everything | ~8s |
| `npm run lint:backend` | Auto-fix and lint Python code | ~2s |
| `npm run lint:frontend` | Auto-fix and lint React code | ~3s |
| `npm run test:backend` | Run pytest unit tests only | ~1s |
| `npm run test:frontend` | Run Vitest tests only | ~2s |
| `npm run test:backend:integration` | Run pytest integration tests | Varies |
| `npm run test:coverage` | Generate coverage reports | ~5s |

### Backend Testing

#### Linting with Ruff

**Lint and auto-fix (default behavior):**

```bash
# Auto-fix and format all Python code
npm run lint:backend

# This runs:
# 1. ruff check . --fix  (auto-fix linting issues)
# 2. ruff format .        (format code)

# Or use ruff directly
ruff check . --fix
ruff format .

# Check specific directory
ruff check lib/ragstack_common/ --fix
```

**Format code separately:**

```bash
# Format all Python files
npm run format

# Check formatting without changing files (for CI)
npm run format:check
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

**Integration tests:**

```bash
# Run integration tests only (requires AWS credentials)
npm run test:backend:integration

# Or use pytest directly
pytest -m integration
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

#### Linting with ESLint

```bash
# Auto-fix and lint React code
npm run lint:frontend

# This runs ESLint with --fix flag automatically
```

#### Running Tests with Vitest

```bash
# Run all frontend tests
npm run test:frontend

# Run in watch mode (from src/ui directory)
cd src/ui && npm run test:watch

# Generate coverage report
npm run test:coverage  # Includes both backend and frontend
```

### Unified Commands

Run backend and frontend together:

```bash
# Auto-fix and lint everything (backend + frontend)
npm run lint

# Run all unit tests (backend + frontend)
npm test

# Complete validation (auto-fix lint + test)
npm run test:all
```

### Common Workflows

#### Pre-Commit Workflow

Before committing code:

```bash
# Run complete validation (auto-fixes issues, then tests)
npm run test:all

# If all pass, commit
git add .
git commit -m "feat: add new feature"
```

**Or step-by-step:**

```bash
# 1. Auto-fix and lint
npm run lint

# 2. Run tests
npm test

# 3. If all pass, commit
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

#### Lint command seems to hang

**Cause:** Auto-fix is processing many files.

**Solution:** This is normal - ruff is fixing issues automatically. Wait for it to complete (~5s).

### Performance Expectations

Typical timing on a standard development machine:

| Command | Expected Time | Notes |
|---------|--------------|-------|
| `npm run lint:backend` | < 2s | Auto-fix + format ~34 Python files |
| `npm run test:backend` | < 2s | 46 unit tests |
| `npm run lint:frontend` | < 3s | Auto-fix React/JSX files |
| `npm run test:frontend` | < 2s | Vitest unit tests |
| `npm run lint` | < 5s | Auto-fix backend + frontend |
| `npm test` | < 3s | All unit tests |
| `npm run test:all` | < 8s | Auto-fix lint + all tests |

**Note:** Times will increase as the codebase grows. Re-benchmark quarterly.

### Best Practices

1. **Run locally before pushing** - Catch issues early with `npm run test:all`
2. **Use watch mode during development** - Get instant feedback on changes
3. **Fix lint issues immediately** - Don't accumulate technical debt
4. **Write tests alongside code** - Maintain high coverage
5. **Keep dependencies updated** - Run `pip install -r requirements-dev.txt` regularly
6. **Use verbose mode when debugging** - `pytest -vs` shows full output

### Detailed Examples

#### Example 1: First-Time Setup (New Developer)

You've just cloned the repository and need to set up local testing.

**Step 1: Install backend dependencies**
```bash
pip install -r requirements-dev.txt

# Expected output:
# Successfully installed ruff-0.14.2 pytest-8.x.x ...
```

**Step 2: Install frontend dependencies**
```bash
cd src/ui
npm install
cd ../..

# Expected output:
# added 1234 packages in 30s
```

**Step 3: Verify installations**
```bash
ruff --version
# Output: ruff 0.14.2

pytest --version
# Output: pytest 8.x.x

npm --version
# Output: 10.x.x
```

**Step 4: Run your first test**
```bash
npm run test:all

# Expected output:
# > lint:backend && lint:frontend && test:backend && test:frontend
# All checks passed! (ruff) ✓ 34 files
# All checks passed! (eslint) ✓
# ================================ test session starts ================================
# collected 46 items
# ...
# ================================ 46 passed in 1.23s ================================
# Test Files  1 passed (1)
# Tests  X passed (X)
```

**Step 5: You're ready to develop!**

---

#### Example 2: Adding a New Lambda Function

You're implementing document validation functionality.

**Step 1: Create the function structure**
```bash
mkdir -p src/lambda/validate_document
touch src/lambda/validate_document/index.py
```

**Step 2: Write the function (example)**
```python
# src/lambda/validate_document/index.py
import json
from typing import Dict, Any

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Validate document metadata and content."""
    document_id = event.get('document_id')

    if not document_id:
        return {'statusCode': 400, 'body': 'Missing document_id'}

    # Validation logic here
    return {'statusCode': 200, 'body': json.dumps({'valid': True})}
```

**Step 3: Create tests (TDD approach)**
```bash
touch tests/unit/test_validate_document.py
```

```python
# tests/unit/test_validate_document.py
import pytest
import sys
import os

# Add Lambda to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/lambda/validate_document'))
import index

def test_lambda_handler_success():
    event = {'document_id': 'test-123'}
    result = index.lambda_handler(event, None)
    assert result['statusCode'] == 200

def test_lambda_handler_missing_id():
    event = {}
    result = index.lambda_handler(event, None)
    assert result['statusCode'] == 400
```

**Step 4: Run tests (should fail initially)**
```bash
pytest tests/unit/test_validate_document.py -v

# Expected: Tests pass if implementation is correct
```

**Step 5: Lint the code**
```bash
npm run lint:backend

# Output: Ruff will auto-fix and format your code
# All checks passed! (ruff) ✓ 35 files (1 file added)
```

**Step 6: Run full test suite**
```bash
npm run test:all

# Verify all tests still pass with new function
```

**Step 7: Commit your changes**
```bash
git add src/lambda/validate_document/ tests/unit/test_validate_document.py
git commit -m "feat(lambda): add document validation function"
```

---

#### Example 3: Fixing a Bug

You discovered a bug where text extraction fails on empty PDFs.

**Step 1: Reproduce the issue**
```bash
# Run specific test that's failing
pytest lib/ragstack_common/test_ocr.py::test_extract_text_from_pdf -vs

# Expected: Test fails with error message
```

**Step 2: Add a test case for the bug**
```python
# lib/ragstack_common/test_ocr.py
def test_extract_text_from_empty_pdf():
    """Test handling of empty PDFs."""
    # Create empty PDF test case
    result = extract_text_from_pdf(empty_pdf_path)
    assert result == ""  # Should return empty string, not crash
```

**Step 3: Run the new test (should fail)**
```bash
pytest lib/ragstack_common/test_ocr.py::test_extract_text_from_empty_pdf -vs

# Expected: FAILED - reproduces bug
```

**Step 4: Fix the bug**
```python
# lib/ragstack_common/ocr.py
def extract_text_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)

    # FIX: Handle empty PDFs
    if doc.page_count == 0:
        return ""

    text = ""
    for page in doc:
        text += page.get_text()
    return text
```

**Step 5: Run tests again**
```bash
pytest lib/ragstack_common/test_ocr.py::test_extract_text_from_empty_pdf -vs

# Expected: PASSED ✓
```

**Step 6: Run full backend tests**
```bash
npm run test:backend

# Ensure fix didn't break anything else
```

**Step 7: Lint and commit**
```bash
npm run lint:backend
git add lib/ragstack_common/ocr.py lib/ragstack_common/test_ocr.py
git commit -m "fix(ocr): handle empty PDFs gracefully"
```

---

#### Example 4: Responding to Code Review

Code reviewer requested changes to your PR.

**Reviewer comment**: "Please add type hints and fix the linting issues"

**Step 1: Pull latest changes**
```bash
git checkout your-feature-branch
git pull origin main
```

**Step 2: Add type hints**
```python
# Before
def process_document(document_id):
    # ...

# After
from typing import Dict, Any

def process_document(document_id: str) -> Dict[str, Any]:
    # ...
```

**Step 3: Run linter (will auto-fix many issues)**
```bash
npm run lint:backend

# Output shows auto-fixed issues:
# Fixed 3 errors:
#   - Added missing imports
#   - Removed unused variables
#   - Fixed line length
```

**Step 4: Check for remaining issues**
```bash
# If any manual fixes needed, ruff will show them
ruff check lib/ragstack_common/

# Expected: All checks passed! ✓
```

**Step 5: Run tests**
```bash
npm run test:all

# Expected: All pass
```

**Step 6: Commit and push**
```bash
git add .
git commit -m "refactor: add type hints and fix linting issues"
git push origin your-feature-branch
```

---

#### Example 5: Refactoring Code

You want to extract a reusable utility function.

**Step 1: Identify code duplication**
```python
# Multiple Lambda functions have this pattern:
result = boto3.client('s3').get_object(Bucket=bucket, Key=key)
content = result['Body'].read()
```

**Step 2: Create shared utility**
```python
# lib/ragstack_common/storage.py
import boto3
from typing import bytes

def read_s3_object(bucket: str, key: str) -> bytes:
    """Read object from S3 and return bytes."""
    s3 = boto3.client('s3')
    result = s3.get_object(Bucket=bucket, Key=key)
    return result['Body'].read()
```

**Step 3: Write tests for utility**
```python
# lib/ragstack_common/test_storage.py
from unittest.mock import Mock, patch
import pytest
from storage import read_s3_object

@patch('storage.boto3.client')
def test_read_s3_object(mock_boto3):
    mock_s3 = Mock()
    mock_boto3.return_value = mock_s3
    mock_s3.get_object.return_value = {
        'Body': Mock(read=lambda: b'test content')
    }

    result = read_s3_object('test-bucket', 'test-key')
    assert result == b'test content'
```

**Step 4: Run tests**
```bash
pytest lib/ragstack_common/test_storage.py -v

# Expected: PASSED ✓
```

**Step 5: Refactor Lambda functions to use utility**
```python
# Before
result = boto3.client('s3').get_object(Bucket=bucket, Key=key)
content = result['Body'].read()

# After
from ragstack_common.storage import read_s3_object
content = read_s3_object(bucket, key)
```

**Step 6: Run all tests to ensure refactoring didn't break anything**
```bash
npm run test:all

# Expected: All pass
```

**Step 7: Commit**
```bash
git add lib/ragstack_common/storage.py lib/ragstack_common/test_storage.py
git add src/lambda/*/index.py
git commit -m "refactor(storage): extract S3 read utility function"
```

---

#### Example 6: Daily Development Workflow

Typical development cycle.

**Morning: Start development**
```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements-dev.txt
cd src/ui && npm install && cd ../..

# Run tests to ensure everything works
npm run test:all
```

**During development: Continuous testing**
```bash
# Terminal 1: Watch backend tests
ptw -- -m "not integration"

# Terminal 2: Watch frontend tests
cd src/ui && npm run test:watch

# Make code changes, tests auto-run
```

**Before lunch: Quick validation**
```bash
# Run full test suite
npm run test:all

# If passes, commit work-in-progress
git add .
git commit -m "wip: add feature X - tests passing"
```

**End of day: Final validation**
```bash
# Run complete validation
npm run test:all

# Run integration tests (if applicable)
npm run test:backend:integration

# Commit final work
git add .
git commit -m "feat: complete feature X implementation"

# Push to remote
git push origin feature-branch
```

---

#### Example 7: Debugging a Failing Test

Test suddenly starts failing after dependency update.

**Step 1: Identify the failing test**
```bash
npm run test:backend

# Output shows:
# FAILED lib/ragstack_common/test_bedrock.py::test_generate_embedding
```

**Step 2: Run with verbose output**
```bash
pytest lib/ragstack_common/test_bedrock.py::test_generate_embedding -vs

# Output shows detailed error:
# AssertionError: Expected 1024 dimensions, got 256
```

**Step 3: Check recent changes**
```bash
git log --oneline lib/ragstack_common/bedrock.py

# Shows recent commits affecting this file
```

**Step 4: Run test with debugger**
```bash
pytest lib/ragstack_common/test_bedrock.py::test_generate_embedding -vs --pdb

# Drops into debugger at failure point
# Can inspect variables: print(result.shape)
```

**Step 5: Fix the issue**
```python
# Found: Embedding model was changed from v1 to v2
# Fix: Update test expectations
def test_generate_embedding():
    result = generate_embedding("test text")
    assert len(result) == 256  # Changed from 1024
```

**Step 6: Verify fix**
```bash
pytest lib/ragstack_common/test_bedrock.py::test_generate_embedding -vs

# Expected: PASSED ✓
```

**Step 7: Run full test suite**
```bash
npm run test:all

# Ensure no other tests broken
```

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
