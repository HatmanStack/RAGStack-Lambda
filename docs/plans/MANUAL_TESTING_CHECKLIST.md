# Manual Testing Checklist - Runtime Configuration System

This checklist provides comprehensive end-to-end verification of the runtime configuration system.

## Prerequisites

Before starting the tests:

- [ ] Stack deployed with runtime configuration system (Phases 1-5 implemented)
- [ ] ConfigurationTable seeded with Schema and Default configurations
- [ ] At least 3 test documents uploaded (PDF, image, text) for re-embedding tests
- [ ] Browser with developer tools available (Chrome/Firefox recommended)
- [ ] Access to AWS Console for CloudWatch Logs verification
- [ ] AWS CLI configured with appropriate credentials

**Test Environment Information**:
- Stack Name: `_______________________`
- AWS Region: `_______________________`
- WebUI URL: `_______________________`
- Tester Name: `_______________________`
- Test Date: `_______________________`

---

## Test Suite

### 1. Settings Page - Basic Functionality

#### 1.1 Load Configuration

- [ ] Navigate to `/settings` URL
- [ ] Page loads without errors (check browser console - F12)
- [ ] All 5 configuration fields display:
  - [ ] OCR Backend dropdown
  - [ ] Bedrock OCR Model field (hidden by default)
  - [ ] Text Embedding Model dropdown
  - [ ] Image Embedding Model dropdown
  - [ ] Response Model dropdown
- [ ] Default values shown correctly
- [ ] No GraphQL errors in Network tab (F12 → Network → Filter: GraphQL)
- [ ] Loading indicator disappears after configuration loads

**Notes**: _______________________________________________________

#### 1.2 Field Rendering

- [ ] OCR Backend dropdown has 2 options: `textract`, `bedrock`
- [ ] Bedrock OCR Model field is **hidden** when Backend = `textract`
- [ ] Text Embedding Model shows 4 options (Titan v1/v2, Cohere English/Multilingual)
- [ ] Image Embedding Model shows 1 option (Titan Image v1)
- [ ] Response Model shows 3 options (Haiku, Sonnet, Opus)
- [ ] All dropdowns are clickable and functional
- [ ] Field labels match Schema descriptions

**Notes**: _______________________________________________________

#### 1.3 Conditional Field Visibility

- [ ] Change OCR Backend from `textract` to `bedrock`
- [ ] Bedrock OCR Model field **appears**
- [ ] Bedrock OCR Model shows 3 options (Haiku, Sonnet, Opus)
- [ ] Change OCR Backend back to `textract`
- [ ] Bedrock OCR Model field **hides**

**Notes**: _______________________________________________________

---

### 2. Configuration Saving

#### 2.1 Save Without Changes

- [ ] Click "Save changes" without modifying anything
- [ ] Success message appears: "Configuration saved successfully"
- [ ] No errors in browser console
- [ ] No GraphQL errors in Network tab

**Notes**: _______________________________________________________

#### 2.2 Save With Changes

- [ ] Change OCR Backend to `bedrock`
- [ ] Select Bedrock OCR Model: `claude-3-5-haiku`
- [ ] Click "Save changes"
- [ ] Success message appears
- [ ] Verify in DynamoDB that Custom item exists:
  ```bash
  aws dynamodb get-item \
    --table-name RAGStack-<project>-Configuration \
    --key '{"Configuration": {"S": "Custom"}}'
  ```
- [ ] Custom item contains `ocr_backend: "bedrock"`

**DynamoDB Verification**: _______________________________________________________

#### 2.3 Persistence After Reload

- [ ] Reload page (F5 or Ctrl+R)
- [ ] OCR Backend still shows `bedrock`
- [ ] Bedrock OCR Model still shows selected value
- [ ] "Customized from default" indicator visible (if implemented)

**Notes**: _______________________________________________________

#### 2.4 Reset Button

- [ ] Change Text Embedding Model to a different value
- [ ] **Do NOT save**
- [ ] Click "Reset" button
- [ ] Field reverts to previous saved value
- [ ] Success message disappears
- [ ] No unsaved changes indicator

**Notes**: _______________________________________________________

---

### 3. Lambda Integration - OCR Backend

#### 3.1 Textract OCR

- [ ] Set OCR Backend to `textract` in Settings
- [ ] Save configuration
- [ ] Upload a PDF document (via UI)
- [ ] Open CloudWatch Logs for ProcessDocumentFunction:
  ```bash
  aws logs tail /aws/lambda/RAGStack-<project>-ProcessDocument --follow
  ```
- [ ] Verify log shows: `"Using OCR backend: textract"` or similar
- [ ] Document processes successfully (status → COMPLETED)
- [ ] No configuration-related errors in logs

**CloudWatch Log Snippet**: _______________________________________________________

#### 3.2 Bedrock OCR

- [ ] Set OCR Backend to `bedrock` in Settings
- [ ] Select Bedrock OCR Model: `claude-3-5-haiku`
- [ ] Save configuration
- [ ] Upload a new PDF document
- [ ] Check CloudWatch Logs for ProcessDocumentFunction
- [ ] Verify logs show:
  - `"Using OCR backend: bedrock"`
  - `"Using Bedrock model: anthropic.claude-3-5-haiku-20241022-v1:0"` or similar
- [ ] Document processes successfully
- [ ] No Bedrock invocation errors

**CloudWatch Log Snippet**: _______________________________________________________

---

### 4. Lambda Integration - Embedding Models

#### 4.1 Default Titan Embeddings

- [ ] Set Text Embedding Model to `amazon.titan-embed-text-v2:0`
- [ ] Save configuration
- [ ] Upload a document (or trigger re-embedding)
- [ ] Check CloudWatch Logs for GenerateEmbeddingsFunction:
  ```bash
  aws logs tail /aws/lambda/RAGStack-<project>-GenerateEmbeddings --follow
  ```
- [ ] Verify log shows: `"Using text embedding model: amazon.titan-embed-text-v2:0"`
- [ ] Embeddings generated successfully
- [ ] Vector file created in S3 Vectors bucket

**CloudWatch Log Snippet**: _______________________________________________________

#### 4.2 Cohere Embeddings

- [ ] Set Text Embedding Model to `cohere.embed-english-v3`
- [ ] Save configuration
- [ ] Upload a new document
- [ ] Check GenerateEmbeddingsFunction logs
- [ ] Verify log shows: `"Using text embedding model: cohere.embed-english-v3"`
- [ ] Embeddings generated successfully
- [ ] No Bedrock model errors

**CloudWatch Log Snippet**: _______________________________________________________

---

### 5. Lambda Integration - Response Model

#### 5.1 Haiku Response Model

- [ ] Set Response Model to `claude-3-5-haiku`
- [ ] Save configuration
- [ ] Go to Search page and perform a query
- [ ] Check CloudWatch Logs for QueryKBFunction:
  ```bash
  aws logs tail /aws/lambda/RAGStack-<project>-QueryKB --follow
  ```
- [ ] Verify log shows: `"Using response model: anthropic.claude-3-5-haiku-20241022-v1:0"`
- [ ] Search returns results
- [ ] Response quality is appropriate

**CloudWatch Log Snippet**: _______________________________________________________

#### 5.2 Sonnet Response Model

- [ ] Set Response Model to `claude-3-5-sonnet`
- [ ] Save configuration
- [ ] Perform another search query
- [ ] Check QueryKBFunction logs
- [ ] Verify model change reflected in logs
- [ ] Compare response quality (Sonnet should be more detailed than Haiku)

**Response Quality Comparison**: _______________________________________________________

---

### 6. Embedding Change Detection

#### 6.1 No Documents Scenario

- [ ] Delete all documents from the system (or start fresh)
- [ ] Verify document count is 0 on Dashboard
- [ ] Change Text Embedding Model to a different value
- [ ] Click "Save changes"
- [ ] Modal **does NOT appear**
- [ ] Configuration saves directly
- [ ] Success message appears

**Notes**: _______________________________________________________

#### 6.2 With Documents - Continue with Mixed Embeddings

- [ ] Upload 3 documents and wait for COMPLETED status
- [ ] Change Text Embedding Model to a different model
- [ ] Click "Save changes"
- [ ] Modal appears: "Embedding Model Change Detected"
- [ ] Modal shows document count: `3` documents
- [ ] Modal offers 3 options (Continue, Re-embed, Cancel)
- [ ] Click "Continue with mixed embeddings"
- [ ] Configuration saves
- [ ] **No re-embedding job triggered**
- [ ] Upload new document
- [ ] New document uses new embedding model
- [ ] Old documents keep old embeddings

**Document IDs Tested**: _______________________________________________________

#### 6.3 With Documents - Cancel

- [ ] Have 3+ completed documents
- [ ] Change Image Embedding Model
- [ ] Click "Save changes"
- [ ] Modal appears
- [ ] Click "Cancel"
- [ ] Modal closes
- [ ] Configuration **NOT saved**
- [ ] Embedding model reverts to previous value

**Notes**: _______________________________________________________

#### 6.4 With Documents - Re-embed All

- [ ] Have 3 completed documents
- [ ] Change Text Embedding Model
- [ ] Click "Save changes"
- [ ] Modal appears
- [ ] Click "Re-embed all documents"
- [ ] Configuration saves
- [ ] Progress banner appears immediately
- [ ] (Continue to Section 7 for re-embedding job tests)

**Notes**: _______________________________________________________

---

### 7. Re-embedding Job

#### 7.1 Job Initiation

- [ ] Trigger re-embedding (via Section 6.4)
- [ ] Progress banner appears at top of Settings page
- [ ] Banner displays: "Re-embedding documents: 0 / 3 completed (0%)"
- [ ] Check Step Functions console:
  ```bash
  aws stepfunctions list-executions \
    --state-machine-arn <state-machine-arn> \
    --max-results 10
  ```
- [ ] Verify 3 new executions started (one per document)
- [ ] Execution names include pattern: `reembed-<doc-id>-<job-id>`

**Step Functions Execution ARNs**: _______________________________________________________

#### 7.2 Job Progress Tracking

- [ ] Progress banner updates automatically (every 5 seconds)
- [ ] Banner shows progress: "Re-embedding documents: 1 / 3 completed (33%)"
- [ ] Check DynamoDB ConfigurationTable for job status:
  ```bash
  aws dynamodb get-item \
    --table-name RAGStack-<project>-Configuration \
    --key '{"Configuration": {"S": "ReEmbedJob_Latest"}}'
  ```
- [ ] ReEmbedJob item exists with:
  - `jobId`: UUID
  - `status`: `IN_PROGRESS`
  - `totalDocuments`: `3`
  - `processedDocuments`: Increments (0 → 1 → 2 → 3)
  - `startTime`: ISO timestamp

**Job ID**: _______________________________________________________

#### 7.3 Job Completion

- [ ] Wait for all documents to finish processing
- [ ] Progress banner updates to: "Re-embedding documents: 3 / 3 completed (100%)"
- [ ] Banner changes to success: "Re-embedding completed! All 3 documents have been processed."
- [ ] Green success alert appears
- [ ] Alert can be dismissed by clicking X
- [ ] Check DynamoDB job status again:
  - `status`: `COMPLETED`
  - `processedDocuments`: `3`
  - `completionTime`: ISO timestamp

**Completion Time**: _______________________________________________________

#### 7.4 Progress Updates in Lambda Logs

- [ ] Check GenerateEmbeddingsFunction CloudWatch logs
- [ ] Verify logs show:
  - `"Re-embed job progress: 1/3"` for first document
  - `"Re-embed job progress: 2/3"` for second document
  - `"Re-embed job progress: 3/3"` for third document
  - `"Re-embedding job <job-id> completed"` for final document

**CloudWatch Log Snippets**: _______________________________________________________

#### 7.5 Navigation During Re-embedding

- [ ] While re-embedding job is IN_PROGRESS, navigate to Dashboard
- [ ] Job continues in background
- [ ] Navigate back to Settings page
- [ ] Progress banner still displays current progress
- [ ] Percentage updates correctly

**Notes**: _______________________________________________________

---

### 8. Error Handling

#### 8.1 DynamoDB Unavailable (Simulated)

**Note**: This test requires temporarily restricting permissions.

- [ ] Restrict Lambda's DynamoDB permissions (IAM console or CLI)
- [ ] Trigger Lambda by uploading document or querying KB
- [ ] Check CloudWatch logs
- [ ] Verify Lambda fails with clear error message
- [ ] Error message mentions configuration or DynamoDB access
- [ ] Lambda does NOT hang indefinitely
- [ ] **Restore permissions** after test

**Error Message**: _______________________________________________________

#### 8.2 Invalid Configuration (Manual DynamoDB Write)

- [ ] Manually set invalid ocr_backend value via CLI:
  ```bash
  aws dynamodb put-item \
    --table-name RAGStack-<project>-Configuration \
    --item '{"Configuration": {"S": "Custom"}, "ocr_backend": {"S": "invalid-backend"}}'
  ```
- [ ] Upload a document
- [ ] Check Lambda logs
- [ ] Lambda should handle gracefully (use default, or fail with clear error)
- [ ] No cryptic error messages
- [ ] **Restore valid configuration** after test

**Lambda Behavior**: _______________________________________________________

#### 8.3 GraphQL Errors (Network Failure Simulation)

- [ ] Open Settings page
- [ ] Open browser DevTools → Network tab
- [ ] Throttle network to "Offline" (or disconnect internet)
- [ ] Try to save configuration
- [ ] Verify error message appears: "Failed to save configuration"
- [ ] Error alert is red and dismissible
- [ ] No browser crashes or infinite loading
- [ ] **Restore network** after test

**Error Message in UI**: _______________________________________________________

---

### 9. Performance

#### 9.1 Configuration Read Latency

- [ ] Check CloudWatch Lambda metrics for ProcessDocumentFunction
- [ ] Compare duration before and after configuration system
- [ ] Verify DynamoDB read latency < 10ms (check Lambda logs or X-Ray)
- [ ] No significant increase in Lambda duration (< 100ms overhead)

**Metrics**:
- Before: _______ ms
- After: _______ ms
- Overhead: _______ ms

#### 9.2 UI Responsiveness

- [ ] Navigate to Settings page
- [ ] Measure load time with DevTools (Network tab → DOMContentLoaded)
- [ ] Load time should be < 2 seconds
- [ ] Change multiple fields quickly (rapid clicks)
- [ ] UI remains responsive
- [ ] No lag or freezing

**Load Time**: _______ ms

---

### 10. Documentation Verification

#### 10.1 User Guide

- [ ] Read Settings section in `docs/USER_GUIDE.md`
- [ ] Follow instructions to modify configuration
- [ ] All steps work as documented
- [ ] No missing or incorrect information
- [ ] Screenshots/examples are accurate (if present)

**Issues Found**: _______________________________________________________

#### 10.2 Architecture Documentation

- [ ] Review `docs/ARCHITECTURE.md` Runtime Configuration section
- [ ] Verify diagrams match actual implementation
- [ ] Data flow descriptions are accurate
- [ ] Component descriptions match code structure

**Issues Found**: _______________________________________________________

---

## Test Summary

**Test Environment**:
- Stack Name: `_______________________`
- AWS Region: `_______________________`
- Tester: `_______________________`
- Date: `_______________________`

**Results**:
- Total Tests: `85`
- Passed: `_______`
- Failed: `_______`
- Skipped: `_______`

**Critical Issues** (blocking issues):
1. _______________________________________________________
2. _______________________________________________________
3. _______________________________________________________

**Minor Issues** (cosmetic or documentation issues):
1. _______________________________________________________
2. _______________________________________________________
3. _______________________________________________________

**Overall Assessment**:
- [ ] All critical functionality works
- [ ] System ready for production use
- [ ] Documentation is accurate and complete
- [ ] No blocking issues remain

**Sign-Off**:
- Tester Name: `_______________________`
- Signature: `_______________________`
- Date: `_______________________`

---

## Notes and Observations

Use this space for additional notes, observations, or suggestions:

_______________________________________________________
_______________________________________________________
_______________________________________________________
_______________________________________________________
_______________________________________________________

---

## Appendix: Useful Commands

### Check Configuration

```bash
# View Default config
aws dynamodb get-item \
  --table-name RAGStack-<project>-Configuration \
  --key '{"Configuration": {"S": "Default"}}'

# View Custom config
aws dynamodb get-item \
  --table-name RAGStack-<project>-Configuration \
  --key '{"Configuration": {"S": "Custom"}}'

# View Schema
aws dynamodb get-item \
  --table-name RAGStack-<project>-Configuration \
  --key '{"Configuration": {"S": "Schema"}}'
```

### Check Lambda Logs

```bash
# ProcessDocument logs
aws logs tail /aws/lambda/RAGStack-<project>-ProcessDocument --follow

# GenerateEmbeddings logs
aws logs tail /aws/lambda/RAGStack-<project>-GenerateEmbeddings --follow

# QueryKB logs
aws logs tail /aws/lambda/RAGStack-<project>-QueryKB --follow

# ConfigurationResolver logs
aws logs tail /aws/lambda/RAGStack-<project>-ConfigurationResolver --follow
```

### Check Re-embedding Job

```bash
# Get latest job status
aws dynamodb get-item \
  --table-name RAGStack-<project>-Configuration \
  --key '{"Configuration": {"S": "ReEmbedJob_Latest"}}'

# List Step Functions executions
aws stepfunctions list-executions \
  --state-machine-arn <arn> \
  --max-results 10
```

### Reset Configuration

```bash
# Remove all custom overrides
aws dynamodb put-item \
  --table-name RAGStack-<project>-Configuration \
  --item '{"Configuration": {"S": "Custom"}}'
```
