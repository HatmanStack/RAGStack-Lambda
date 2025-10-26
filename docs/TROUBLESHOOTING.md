# Troubleshooting Guide

This guide covers common issues and their solutions for RAGStack-Lambda.

## Table of Contents

- [Deployment Issues](#deployment-issues)
- [Document Processing Issues](#document-processing-issues)
- [Knowledge Base Issues](#knowledge-base-issues)
- [UI Issues](#ui-issues)
- [Performance Issues](#performance-issues)
- [Authentication Issues](#authentication-issues)
- [Log Analysis](#log-analysis)
- [Getting Help](#getting-help)

---

## Deployment Issues

### CloudFormation Stack Fails to Create

**Symptoms:**
- Stack creation fails with `ROLLBACK_COMPLETE`
- Error messages in CloudFormation events

**Common Causes & Solutions:**

#### 1. Bedrock Model Access Not Enabled

**Error:**
```
ResourceNotFoundException: Could not resolve the foundation model from model identifier
```

**Solution:**
```bash
# Enable models in AWS Console
1. Go to AWS Console → Bedrock → Model access
2. Enable these models:
   - anthropic.claude-3-5-haiku-20241022-v1:0
   - amazon.titan-embed-text-v2:0
   - amazon.titan-embed-image-v1
3. Wait 5-10 minutes for access to be granted
4. Retry deployment
```

#### 2. Invalid Admin Email Format

**Error:**
```
Parameter validation failed: Invalid email address
```

**Solution:**
```bash
# Use a valid email format
./publish.sh --env dev --admin-email valid@example.com
```

#### 3. IAM Permissions Insufficient

**Error:**
```
User is not authorized to perform: iam:CreateRole
```

**Solution:**
- Ensure you have administrator access or equivalent permissions
- Required permissions:
  - `iam:*` for creating roles and policies
  - `cloudformation:*` for stack operations
  - `lambda:*` for function creation
  - `s3:*` for bucket operations

#### 4. S3 Bucket Name Already Exists

**Error:**
```
Bucket name already exists
```

**Solution:**
```bash
# Change the ProjectName parameter to make bucket names unique
./publish.sh --env dev --admin-email admin@example.com

# Bucket names include AWS account ID, so this error is rare
# If it occurs, modify ProjectName in samconfig.toml
```

### SAM Build Fails

**Symptoms:**
- `sam build` command fails
- Missing dependencies error

**Solutions:**

#### 1. Python Version Mismatch

**Error:**
```
Python 3.13 or later required
```

**Solution:**
```bash
# Check Python version
python3.13 --version

# Install Python 3.13 if needed
# macOS
brew install python@3.13

# Ubuntu
sudo apt install python3.13

# Update publish.sh if needed to use correct Python
```

#### 2. Docker Not Running

**Error:**
```
Cannot connect to Docker daemon
```

**Solution:**
```bash
# Start Docker
# macOS/Windows
# Open Docker Desktop

# Linux
sudo systemctl start docker

# Verify Docker is running
docker ps
```

#### 3. Lambda Layer Build Fails

**Error:**
```
Error building PyMuPDF layer
```

**Solution:**
```bash
# Rebuild layers manually
cd layers/pymupdf
docker run --rm \
  -v $(pwd):/var/task \
  public.ecr.aws/sam/build-python3.13 \
  pip install PyMuPDF==1.23.0 -t python/

# Retry deployment
./publish.sh --env dev --admin-email admin@example.com
```

---

## Document Processing Issues

### Documents Stuck in UPLOADED Status

**Symptoms:**
- Document status never changes from UPLOADED
- No Step Functions execution started

**Diagnosis:**
```bash
# Check EventBridge rules
aws events list-rules --name-prefix RAGStack

# Check Step Functions state machine
aws stepfunctions list-executions \
  --state-machine-arn <ARN> \
  --status-filter RUNNING
```

**Solutions:**

#### 1. EventBridge Rule Not Triggering

**Solution:**
```bash
# Verify EventBridge is enabled on input bucket
aws s3api get-bucket-notification-configuration \
  --bucket ragstack-input-<account-id>

# Should show EventBridgeConfiguration: EventBridgeEnabled: true

# If not, redeploy the stack
./publish.sh --env dev --admin-email admin@example.com
```

#### 2. Manual Trigger

**Temporary workaround:**
```bash
# Manually start Step Functions execution
aws stepfunctions start-execution \
  --state-machine-arn <ARN> \
  --input '{
    "bucket": "ragstack-input-<account-id>",
    "key": "path/to/document.pdf",
    "document_id": "<document-id>"
  }'
```

### Documents Stuck in PROCESSING Status

**Symptoms:**
- Status changes to PROCESSING but never completes
- Processing takes >30 minutes

**Diagnosis:**
```bash
# Find the Step Functions execution
STACK_NAME="RAGStack-dev"
STATE_MACHINE_ARN=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
  --output text)

# List recent executions
aws stepfunctions list-executions \
  --state-machine-arn $STATE_MACHINE_ARN \
  --status-filter RUNNING \
  --max-results 10

# Get execution details
aws stepfunctions describe-execution \
  --execution-arn <EXECUTION_ARN>

# View Lambda logs
aws logs tail /aws/lambda/${STACK_NAME}-ProcessDocument --follow
```

**Common Causes & Solutions:**

#### 1. Lambda Timeout

**Error in logs:**
```
Task timed out after 900.00 seconds
```

**Solution:**
- Large documents (>100 pages) may exceed 15-minute timeout
- Split document into smaller files
- Or increase Lambda timeout (not recommended beyond 15 min)

#### 2. Textract Throttling

**Error in logs:**
```
ProvisionedThroughputExceededException: Rate exceeded
```

**Solution:**
```bash
# Request Textract quota increase
1. Go to AWS Console → Service Quotas
2. Search for "Textract"
3. Request increase for "Concurrent DetectDocumentText requests"
4. Wait for approval (usually 1-2 business days)

# Temporary workaround: Add retry delay in code
# Already implemented in lib/ragstack_common/ocr.py
```

#### 3. Bedrock Throttling

**Error in logs:**
```
ThrottlingException: Rate exceeded for model
```

**Solution:**
```bash
# Check Bedrock quotas
aws service-quotas get-service-quota \
  --service-code bedrock \
  --quota-code L-xxxx

# Request quota increase or reduce concurrency
# Add delays between API calls (already implemented)
```

#### 4. Out of Memory

**Error in logs:**
```
Runtime exited with error: signal: killed
MemoryError: Cannot allocate memory
```

**Solution:**
```yaml
# Increase Lambda memory in template.yaml
Globals:
  Function:
    MemorySize: 4096  # Increase from 2048

# Redeploy
./publish.sh --env dev --admin-email admin@example.com
```

### Documents Fail with Error Status

**Symptoms:**
- Status changes to FAILED
- Error message in document details

**Diagnosis:**
```bash
# Check DynamoDB for error message
TRACKING_TABLE=$(aws cloudformation describe-stacks \
  --stack-name RAGStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`TrackingTableName`].OutputValue' \
  --output text)

aws dynamodb get-item \
  --table-name $TRACKING_TABLE \
  --key '{"document_id": {"S": "<document-id>"}}'

# Look for error_message field
```

**Common Errors:**

#### 1. Unsupported File Format

**Error:**
```
UnsupportedFileTypeError: File type .exe is not supported
```

**Solution:**
- Only upload supported formats: PDF, images (JPG, PNG, TIFF), Office docs (.docx, .xlsx, .pptx), text files
- Convert file to PDF first if possible

#### 2. Corrupted PDF

**Error:**
```
PDFError: Cannot open PDF file
```

**Solution:**
- Verify PDF is not corrupted
- Try opening in Adobe Reader or other PDF viewer
- Re-create or repair the PDF

#### 3. Text Extraction Failed

**Error:**
```
OCRError: Failed to extract text from document
```

**Solution:**
- Check document image quality (need 150+ DPI)
- Verify text is readable in original document
- Try using Bedrock OCR instead of Textract:
  ```toml
  # In samconfig.toml
  parameter_overrides = ["OcrBackend=bedrock"]
  ```

---

## Knowledge Base Issues

### Search Returns No Results

**Symptoms:**
- Documents are INDEXED
- Search queries return empty results

**Diagnosis:**
```bash
# Check if Knowledge Base exists
aws bedrock-agent list-knowledge-bases

# Check data source sync status
aws bedrock-agent list-ingestion-jobs \
  --knowledge-base-id <KB_ID> \
  --data-source-id <DATA_SOURCE_ID>

# Check vector bucket for embeddings
VECTOR_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name RAGStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`VectorBucketName`].OutputValue' \
  --output text)

aws s3 ls s3://$VECTOR_BUCKET/ --recursive
```

**Solutions:**

#### 1. Knowledge Base Not Created

**Solution:**
- Follow [Deployment Guide](DEPLOYMENT.md#post-deployment-configuration) to create KB manually
- Store KB ID and Data Source ID in Parameter Store

#### 2. Data Source Not Synced

**Solution:**
```bash
# Manually trigger sync
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id <KB_ID> \
  --data-source-id <DATA_SOURCE_ID>

# Monitor sync status
aws bedrock-agent list-ingestion-jobs \
  --knowledge-base-id <KB_ID> \
  --data-source-id <DATA_SOURCE_ID> \
  --max-results 5
```

#### 3. Embeddings Not Generated

**Solution:**
```bash
# Check if GenerateEmbeddings Lambda ran
aws logs filter-log-events \
  --log-group-name /aws/lambda/RAGStack-dev-GenerateEmbeddings \
  --filter-pattern "ERROR"

# Check vector bucket
aws s3 ls s3://$VECTOR_BUCKET/ --recursive
# Should show files like: <document-id>/embeddings.json

# If missing, manually trigger Step Functions
```

### Search Results Are Irrelevant

**Symptoms:**
- Search returns results but they don't match query
- Low relevance scores (<50%)

**Solutions:**

#### 1. Query Too Vague

**Solution:**
- Use more specific queries with context
- Bad: "revenue"
- Good: "What was the total revenue in Q4 2024?"

#### 2. Wrong Embedding Model

**Solution:**
```bash
# Verify Titan Embed Text V2 is being used
aws bedrock-agent get-knowledge-base --knowledge-base-id <KB_ID>

# Should show: embeddingModelArn: amazon.titan-embed-text-v2:0

# If wrong model, recreate KB with correct model
```

#### 3. Insufficient Context

**Solution:**
- Knowledge Base chunking may be too small
- Recreate KB with larger chunk size:
  - Current: 300 tokens
  - Try: 500-1000 tokens

---

## UI Issues

### UI Not Loading

**Symptoms:**
- Blank page or 404 error
- CloudFront URL returns error

**Diagnosis:**
```bash
# Get CloudFront distribution ID
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name RAGStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' \
  --output text)

# Check distribution status
aws cloudfront get-distribution --id $DISTRIBUTION_ID

# Check UI bucket
UI_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name RAGStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`UIBucketName`].OutputValue' \
  --output text)

aws s3 ls s3://$UI_BUCKET/
```

**Solutions:**

#### 1. CloudFront Cache Issue

**Solution:**
```bash
# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*"

# Wait 2-3 minutes, then refresh browser
```

#### 2. UI Not Deployed

**Solution:**
```bash
# Redeploy UI
cd src/ui
npm install
npm run build

# Upload to S3
aws s3 sync build/ s3://$UI_BUCKET/ --delete

# Invalidate cache
aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*"
```

#### 3. Wrong CloudFront URL

**Solution:**
```bash
# Get correct URL
aws cloudformation describe-stacks \
  --stack-name RAGStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`WebUIUrl`].OutputValue' \
  --output text

# Should be: https://d<random>.cloudfront.net
```

### Login Fails

**Symptoms:**
- "Invalid username or password"
- Email/password don't work

**Solutions:**

#### 1. Temporary Password Expired

**Solution:**
```bash
# Reset password via AWS Console
1. Go to Cognito → User Pools → RAGStack-dev-UserPool
2. Find your user
3. Click "Reset password"
4. Check email for new temporary password
```

#### 2. User Not Created

**Solution:**
```bash
# List Cognito users
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name RAGStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
  --output text)

aws cognito-idp list-users --user-pool-id $USER_POOL_ID

# If user missing, create manually
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username admin@example.com \
  --temporary-password TempPass123!
```

#### 3. Wrong User Pool

**Solution:**
- Verify you're using the correct environment (dev vs prod)
- Check deployment outputs for correct User Pool ID

### Upload Fails

**Symptoms:**
- Upload button doesn't work
- Upload progress stuck at 0%

**Solutions:**

#### 1. Presigned URL Generation Failed

**Diagnosis:**
```bash
# Check AppSync logs
aws logs tail /aws/lambda/RAGStack-dev-AppSyncResolvers --follow
```

**Solution:**
- Verify IAM permissions for S3 bucket
- Check AppSync API is accessible
- Try uploading a smaller file first

#### 2. CORS Error

**Error in browser console:**
```
Access to XMLHttpRequest has been blocked by CORS policy
```

**Solution:**
```bash
# Verify S3 CORS configuration
aws s3api get-bucket-cors --bucket ragstack-input-<account-id>

# Should allow CloudFront origin
# Redeploy if CORS missing
```

---

## Performance Issues

### Slow Document Processing

**Symptoms:**
- Documents take >10 minutes to process
- Processing time varies significantly

**Diagnosis:**
```bash
# Check Lambda durations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=RAGStack-dev-ProcessDocument \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum

# Check Textract API latency
aws cloudwatch get-metric-statistics \
  --namespace AWS/Textract \
  --metric-name ResponseTime \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

**Solutions:**

#### 1. Cold Start Latency

**Solution:**
- First invocation after deployment is slower (cold start)
- Subsequent invocations are faster
- Consider provisioned concurrency for production (increases cost)

#### 2. Large Documents

**Solution:**
- Split documents into smaller files
- Expected: ~2-3 seconds per page for OCR
- 100-page document = 3-5 minutes minimum

#### 3. Textract Delays

**Solution:**
```bash
# Switch to Bedrock OCR for faster results
# In samconfig.toml
parameter_overrides = ["OcrBackend=bedrock"]

# Note: Bedrock is more expensive but often faster
```

### High Costs

**Symptoms:**
- AWS bill higher than expected
- Cost per document unexpectedly high

**Diagnosis:**
```bash
# Check metering data
METERING_TABLE=$(aws cloudformation describe-stacks \
  --stack-name RAGStack-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`MeteringTableName`].OutputValue' \
  --output text)

aws dynamodb scan --table-name $METERING_TABLE --limit 10

# Check CloudWatch costs
aws ce get-cost-and-usage \
  --time-period Start=2025-01-01,End=2025-01-31 \
  --granularity MONTHLY \
  --metrics UnblendedCost \
  --group-by Type=SERVICE
```

**Solutions:**

#### 1. Using Bedrock OCR Instead of Textract

**Solution:**
```bash
# Switch to Textract (cheaper)
# In samconfig.toml
parameter_overrides = ["OcrBackend=textract"]

# Cost savings: ~$20-60/month for 1000 documents
```

#### 2. Not Detecting Text-Native PDFs

**Solution:**
- Verify ProcessDocument Lambda is checking for text
- Should see "Text native: true" in logs
- If not, update ragstack_common/ocr.py

#### 3. Excessive Lambda Memory

**Solution:**
```yaml
# Reduce Lambda memory if possible
# In template.yaml
Globals:
  Function:
    MemorySize: 1769  # Try lower values
```

---

## Authentication Issues

### MFA Not Working

**Symptoms:**
- MFA code rejected
- Cannot complete MFA setup

**Solution:**
```bash
# Disable MFA (if needed)
aws cognito-idp admin-set-user-mfa-preference \
  --user-pool-id $USER_POOL_ID \
  --username admin@example.com \
  --sms-mfa-settings Enabled=false

# Or reset MFA device
aws cognito-idp admin-reset-user-password \
  --user-pool-id $USER_POOL_ID \
  --username admin@example.com
```

### Session Expired Frequently

**Symptoms:**
- Logged out after short time
- Session timeout errors

**Solution:**
- Sessions last 1 hour by default
- Sign in again when prompted
- For longer sessions, modify Cognito token expiry (not recommended)

---

## Log Analysis

### Finding Lambda Logs

```bash
# List all log groups
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/RAGStack

# Tail logs in real-time
aws logs tail /aws/lambda/RAGStack-dev-ProcessDocument --follow

# Filter for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/RAGStack-dev-ProcessDocument \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '1 hour ago' +%s)000

# Get specific execution logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/RAGStack-dev-ProcessDocument \
  --filter-pattern "<request-id>"
```

### Understanding Log Patterns

**Normal Processing:**
```
START RequestId: abc-123
INFO: Processing document: document.pdf
INFO: Document type: PDF
INFO: Text native: true
INFO: Extracted 1234 characters
INFO: Saved to s3://bucket/output/
END RequestId: abc-123
REPORT Duration: 2345.67 ms Memory Used: 512 MB
```

**Error Patterns:**
```
ERROR: Failed to extract text
ERROR: Bedrock throttling exception
ERROR: Out of memory
ERROR: Task timed out
```

### Step Functions Execution History

```bash
# Get execution history
aws stepfunctions get-execution-history \
  --execution-arn <EXECUTION_ARN> \
  --max-results 100

# Check for failed states
aws stepfunctions describe-execution \
  --execution-arn <EXECUTION_ARN>
```

---

## Getting Help

### Before Asking for Help

1. ✅ Check this troubleshooting guide
2. ✅ Review CloudWatch logs for errors
3. ✅ Check DynamoDB tracking table for status
4. ✅ Verify Step Functions execution history
5. ✅ Try redeploying the stack

### Information to Include

When opening a GitHub issue, include:

- **Stack name and region**
- **Error message** (exact text)
- **CloudWatch logs** (relevant excerpts)
- **Document details** (file type, size, pages)
- **Steps to reproduce**
- **Expected vs actual behavior**
- **Configuration** (OCR backend, model IDs)

### Useful Commands

```bash
# Get stack outputs
aws cloudformation describe-stacks --stack-name RAGStack-dev

# Get stack events (deployment issues)
aws cloudformation describe-stack-events --stack-name RAGStack-dev --max-items 20

# Get Lambda function details
aws lambda get-function --function-name RAGStack-dev-ProcessDocument

# Get DynamoDB table details
aws dynamodb describe-table --table-name RAGStack-dev-Tracking

# Get S3 bucket contents
aws s3 ls s3://ragstack-input-<account-id>/ --recursive

# Get CloudWatch metric data
aws cloudwatch get-metric-data --cli-input-json file://metrics.json
```

---

## Related Documentation

- **[Deployment Guide](DEPLOYMENT.md)** - Deployment troubleshooting
- **[Testing Guide](TESTING.md)** - Test troubleshooting
- **[Architecture Guide](ARCHITECTURE.md)** - Understanding the system
- **[User Guide](USER_GUIDE.md)** - UI troubleshooting
- **[Configuration Guide](CONFIGURATION.md)** - Configuration issues
