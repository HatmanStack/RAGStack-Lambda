# Plan Review: Collapsible Sources with Document Access

**Reviewer:** Tech Lead
**Date:** 2025-11-18
**Plan Location:** `docs/plans/collapsible-sources/`
**Status:** ❌ **REJECTED - CRITICAL ARCHITECTURE MISMATCH**

---

## Executive Summary

The plan is comprehensive, well-structured, and demonstrates strong architectural thinking. However, there is a **critical mismatch between the plan and the current codebase architecture**. The plan references an Amplify Gen 2 backend structure (`amplify/data/functions/`, `amplify/backend.ts`, etc.) that was **deleted from the repository**.

Recent commits show:
- `amplify/backend.ts` - **DELETED**
- `amplify/data/resource.ts` - **DELETED**
- `amplify/auth/resource.ts` - **DELETED**
- `amplify/bin/app.ts` - **DELETED**
- `amplify/cdk.json` - **DELETED**

**An implementer following this plan will fail immediately** when attempting to modify non-existent files in Phase 1.

---

## Critical Issues (Must Fix Before Approval)

### 1. Phase 1, All Tasks: Architecture Mismatch ⚠️ BLOCKER

**Files Referenced That Don't Exist:**
- `amplify/data/functions/conversation.ts` (Task 2, line 104-106)
- `amplify/data/functions/mapToOriginalDocument.ts` (Task 3, line 168)
- `amplify/lib/backend-stack.ts` (Task 5, line 380)
- `amplify/data/functions/conversation.integration.test.ts` (Task 6, line 456)

**Impact:**
- Implementer cannot complete any Phase 1 tasks
- Zero-context engineer will waste hours debugging non-existent paths
- Phase 2 and 3 depend on Phase 1 API contract, blocking entire project

**Required Fix:**
1. **Locate actual conversation Lambda handler:**
   - Use `Grep` to search for "bedrock", "conversation", "queryKnowledgeBase" in `src/lambda/`
   - Identify which Lambda function handles chat queries
   - Document actual file path (e.g., `src/lambda/query_kb/handler.ts` or similar)

2. **Update all file paths in Phase 1:**
   - Replace every instance of `amplify/data/functions/conversation.ts` with actual path
   - Update line number references to match current code
   - Verify files actually exist before referencing them

3. **Verify GraphQL layer still exists:**
   - Check if GraphQL API is still AppSync-based or moved to API Gateway
   - Update instructions accordingly

**Action Items for Planner:**
- [ ] Run `Glob` with pattern `src/lambda/**/*.{ts,js,py}` to find Lambda handlers
- [ ] Run `Grep` with pattern "bedrock.*query" to find conversation handler
- [ ] Read identified file and understand current structure
- [ ] Update Phase 1 Tasks 2-6 with correct file paths

---

### 2. Phase 1, Task 5: IAM Permissions Unimplementable ⚠️ BLOCKER

**Issue:**
Task 5 instructs modifying `amplify/lib/backend-stack.ts` to grant Lambda permissions. This file was deleted.

**Impact:**
- Conversation Lambda won't have permissions to read TrackingTable
- Conversation Lambda won't have permissions to generate S3 presigned URLs
- Feature will fail at runtime with "Access Denied" errors

**Required Fix:**
1. **Locate where IAM roles are actually defined:**
   - Most likely in `template.yaml` (SAM template)
   - Possibly in separate CloudFormation templates
   - Could be in CDK stack elsewhere

2. **Update Task 5 instructions:**
   - Replace CDK PolicyStatement syntax with SAM YAML syntax:
     ```yaml
     Policies:
       - DynamoDBReadPolicy:
           TableName: !Ref TrackingTable
       - S3ReadPolicy:
           BucketName: !Ref InputBucket
     ```
   - Or provide CloudFormation IAM::Policy syntax if using raw CFN

**Action Items for Planner:**
- [ ] Read `template.yaml` to understand current IAM role structure
- [ ] Identify where conversation Lambda's execution role is defined
- [ ] Update Task 5 with correct YAML/CloudFormation syntax (not CDK TypeScript)
- [ ] Verify TrackingTable and InputBucket are referenced correctly in template

---

### 3. Phase 1, Task 1: Line Numbers May Be Wrong ⚠️ HIGH

**Issue:**
Task 1 references `publish.py` lines ~1740-1830 for `seed_configuration_table()`. Git diff shows 159 lines were removed from `publish.py`.

**Impact:**
- Line numbers are likely incorrect
- Function may have moved or been restructured
- Implementer will modify wrong code section

**Required Fix:**
1. **Verify current publish.py structure:**
   - Read `publish.py` and locate `seed_configuration_table()` function
   - Document actual line numbers
   - Verify function still uses same schema/default pattern

2. **Update Task 1 with correct line numbers**

**Action Items for Planner:**
- [ ] Run `Grep` with pattern "seed_configuration_table" in `publish.py`
- [ ] Read function to verify structure matches plan expectations
- [ ] Update line number references in Task 1

---

### 4. Phase 0, Lines 395-398: Tech Stack Dependencies Wrong Location 🔧 MEDIUM

**Issue:**
Phase-0 "Tech Stack & Libraries" section states:

> Required:
> - `@aws-sdk/client-dynamodb`: DynamoDB operations
> - `@aws-sdk/client-s3`: S3 operations
> - `@aws-sdk/s3-request-presigner`: Generate presigned URLs

But implies installation in `amplify/data/functions/` which no longer exists.

**Impact:**
- Implementer doesn't know where to install Node.js dependencies
- May install in wrong location, causing Lambda build failures

**Required Fix:**
1. **Determine if conversation Lambda is Node.js or Python:**
   - Check `src/lambda/query_kb/` (or actual conversation Lambda location)
   - If Python: Need boto3, not @aws-sdk packages
   - If Node.js: Need to specify correct package.json location

2. **Update Tech Stack section:**
   - If Python: Replace with `boto3` examples
   - If Node.js: Specify exact directory for `npm install` (e.g., `src/lambda/conversation/`)

**Action Items for Planner:**
- [ ] Verify conversation Lambda language (Python or Node.js)
- [ ] Update Phase-0 tech stack section with correct package manager and location
- [ ] If Python, rewrite backend examples to use boto3 instead of AWS SDK v3

---

### 5. Phase 2, Task 4: Admin UI Path Verification Needed 🔧 MEDIUM

**Issue:**
Task 4 references `src/ui/src/pages/Configuration.tsx` for admin UI configuration. Need to verify this file exists and hasn't been restructured.

**Impact:**
- If file doesn't exist, implementer cannot add configuration toggle
- Feature will work on backend but have no admin control

**Required Fix:**
1. **Verify admin UI still exists:**
   - Check if `src/ui/` directory exists
   - Verify React app structure
   - Confirm Configuration page location

2. **Update Task 4 if needed**

**Action Items for Planner:**
- [ ] Run `Glob` with pattern `src/ui/**/*.tsx` to verify UI structure
- [ ] Run `Grep` with pattern "Configuration" in src/ui/ to find config page
- [ ] Update Task 4 with correct file path if different

---

### 6. Phase 3, Task 6: Deployment Command May Not Work ⚠️ MEDIUM

**Issue:**
Task 6 shows deployment command with `--deploy-chat` flag (line 611):

```bash
python publish.py \
  --project-name production \
  --admin-email admin@example.com \
  --region us-east-1 \
  --deploy-chat
```

But Amplify chat stack was removed. This flag may be deprecated or non-functional.

**Impact:**
- Deployment may fail
- Implementer may not know correct deployment command

**Required Fix:**
1. **Verify publish.py command-line arguments:**
   - Read `publish.py` to see available flags
   - Check if `--deploy-chat` still exists and what it does
   - Update deployment command if flag was removed

**Action Items for Planner:**
- [ ] Run `Grep` with pattern "deploy-chat|deploy_chat" in `publish.py`
- [ ] Verify flag still exists and its current behavior
- [ ] Update deployment instructions in Task 6 if needed

---

## Suggestions (Nice to Have)

### 1. Add Pre-Implementation Architecture Verification Task

**Suggestion:**
Add a new "Task 0" in Phase 1 before coding begins:

```markdown
### Task 0: Verify Current Architecture

**Goal:** Understand actual codebase structure before implementation

**Steps:**
1. Locate conversation Lambda handler
   - Search for Bedrock query code in `src/lambda/`
   - Identify file that handles chat/conversation requests
   - Document file path and current structure

2. Verify SAM template structure
   - Read `template.yaml`
   - Locate conversation Lambda resource definition
   - Identify where IAM roles are defined
   - Note TrackingTable and ConfigurationTable resource names

3. Verify GraphQL API layer
   - Check if AppSync still used or migrated to API Gateway
   - Locate schema definition
   - Understand how frontend calls backend

4. Confirm data flow
   - Trace: User query → API → Lambda → Bedrock → Response
   - Verify TrackingTable structure (document_id, input_s3_uri, filename)
   - Verify ConfigurationTable structure

**Verification Checklist:**
- [ ] Conversation Lambda file path documented
- [ ] Lambda language confirmed (Python or Node.js)
- [ ] IAM role definition location identified
- [ ] GraphQL/API structure understood
- [ ] All referenced AWS resources exist in template
```

**Rationale:**
- Prevents implementer from starting with wrong assumptions
- Catches architecture mismatches early
- Builds necessary context for zero-context engineer

---

### 2. Add Architectural Context to Phase-0

**Suggestion:**
Add a new section to Phase-0 after "Architecture Decision Records":

```markdown
## Current Architecture (Post-Amplify Migration)

**Important Context:**
This codebase previously used AWS Amplify Gen 2 for the chat backend. The Amplify stack was removed in favor of a SAM-based architecture. Understanding this context is critical for implementation.

**What Was Removed:**
- `amplify/backend.ts` - Amplify CDK backend definition
- `amplify/data/resource.ts` - GraphQL schema and resolvers
- `amplify/auth/resource.ts` - Cognito authentication config
- Amplify CLI deployment workflow

**What Remains:**
- SAM stack (`template.yaml`) - Core infrastructure
- S3 buckets (InputBucket, OutputBucket)
- DynamoDB tables (TrackingTable, ConfigurationTable)
- Lambda functions in `src/lambda/` (SAM-deployed)
- React UI in `src/ui/` (deployed to S3/CloudFront)

**Lambda Structure:**
- Functions are in `src/lambda/` directory
- Each function has own directory (e.g., `src/lambda/process_document/`)
- Handlers are Python or Node.js (verify for conversation Lambda)
- IAM roles defined in `template.yaml` SAM template

**Deployment:**
- Uses `publish.py` orchestration script
- SAM CLI for backend (`sam build`, `sam deploy`)
- Direct S3 upload for frontend UI
- No Amplify CLI involved
```

**Rationale:**
- Explains why file paths in plan might seem unfamiliar
- Helps implementer understand they're working with SAM, not Amplify
- Prevents confusion when references to "Amplify" appear in code comments

---

### 3. Clarify Python vs Node.js Throughout Plan

**Suggestion:**
Phase-0 and Phase-1 mix Python and Node.js examples. If conversation Lambda is Python (which is likely based on `lib/ragstack_common/`), then:

- Update all AWS SDK v3 examples to boto3
- Change `@aws-sdk/s3-request-presigner` to `boto3.generate_presigned_url()`
- Update mock examples to use Python testing patterns (pytest, moto)
- Change TypeScript types to Python type hints

**Example Update Needed:**

Current (Phase-0, line 304):
```typescript
const url = await generatePresignedUrl(bucket, key);
```

Should be (if Python):
```python
url = s3_client.generate_presigned_url(
    'get_object',
    Params={'Bucket': bucket, 'Key': key},
    ExpiresIn=3600
)
```

---

### 4. Add File Path Summary Table

**Suggestion:**
Add to Phase-0 after "Shared Conventions":

```markdown
## File Path Reference

Quick reference for implementers:

| Component | File Path | Language |
|-----------|-----------|----------|
| Conversation Lambda | `src/lambda/[VERIFY]/handler.py` | Python |
| TrackingTable Schema | `template.yaml` (Resources section) | YAML |
| Configuration Seeding | `publish.py` (seed_configuration_table) | Python |
| IAM Roles | `template.yaml` (SAM Policies) | YAML |
| Admin UI Config Page | `src/ui/src/pages/Configuration.tsx` | TypeScript |
| React Chat Component | `src/amplify-chat/src/ChatComponent.tsx` | TypeScript |
| GraphQL Schema | `src/api/schema.graphql` | GraphQL |

*Note: Paths marked [VERIFY] must be confirmed before implementation begins.*
```

**Rationale:**
- Single source of truth for file locations
- Easy to update if paths change during verification
- Helps implementer navigate unfamiliar codebase

---

## Token Estimate Concerns

**Observation:**
Total plan is ~205,000 tokens across 4 phases. This is within budget but leaves little room for conversation and debugging.

**Breakdown:**
- Phase 0: 15,000 tokens
- Phase 1: 75,000 tokens ⚠️ (close to context limit)
- Phase 2: 70,000 tokens ⚠️ (close to context limit)
- Phase 3: 45,000 tokens

**Recommendation:**
Consider splitting Phase 1 into two sub-phases:
- **Phase 1A:** Configuration + Document Mapping (Tasks 1-3) - ~47,000 tokens
- **Phase 1B:** Integration + IAM + Testing (Tasks 4-6) - ~28,000 tokens

This provides breathing room for debugging and keeps each phase under 50k tokens.

---

## Plan Structure ✅ GOOD

**Positive observations:**

✅ README.md provides excellent overview
✅ Phase-0 establishes clear architectural decisions (ADRs)
✅ Each task has clear goal, prerequisites, and verification criteria
✅ Commit message templates follow conventional commits
✅ Testing strategy is comprehensive (unit, integration, E2E)
✅ Accessibility requirements are well-documented
✅ Security considerations are thorough (presigned URL expiry, permissions)
✅ Phase dependencies are clearly stated

**Minor improvements:**
- Add more "Why not X?" rationale to ADRs
- Include more specific error messages in verification checklists
- Add time estimates per task (not just token estimates)

---

## Recommended Changes

### Immediate Actions Required (Blocking Approval)

1. **Architecture Audit** (CRITICAL)
   - [ ] Use `Glob` to find all Lambda handlers in `src/lambda/`
   - [ ] Use `Grep` to find conversation/chat handler (search "bedrock", "queryKnowledgeBase")
   - [ ] Read identified file and confirm structure
   - [ ] Read `template.yaml` to understand SAM stack structure
   - [ ] Verify TrackingTable and ConfigurationTable resource definitions

2. **Update Phase 1 File Paths** (CRITICAL)
   - [ ] Replace ALL instances of `amplify/data/functions/conversation.ts` with actual path
   - [ ] Update Task 5 IAM instructions from CDK to SAM YAML syntax
   - [ ] Verify and update `publish.py` line numbers in Task 1
   - [ ] Confirm file language (Python vs Node.js) and update all code examples

3. **Update Phase-0 Tech Stack** (HIGH)
   - [ ] Verify conversation Lambda language
   - [ ] If Python: Replace @aws-sdk examples with boto3
   - [ ] Update dependency installation instructions with correct paths
   - [ ] Add clarification about SAM-based (not Amplify-based) architecture

4. **Verify Phase 2 Paths** (MEDIUM)
   - [ ] Confirm `src/ui/src/pages/Configuration.tsx` exists
   - [ ] Confirm `src/amplify-chat/` directory structure
   - [ ] Update if UI structure has changed

5. **Update Phase 3 Deployment** (MEDIUM)
   - [ ] Verify `--deploy-chat` flag still exists in `publish.py`
   - [ ] Update deployment commands if flags changed
   - [ ] Confirm post-Amplify deployment workflow

### Suggested Enhancements (Non-Blocking)

- [ ] Add "Task 0: Architecture Verification" to Phase 1
- [ ] Add "Current Architecture" section to Phase-0
- [ ] Add file path reference table to Phase-0
- [ ] Consider splitting Phase 1 into 1A and 1B for better token distribution
- [ ] Add troubleshooting section for "file not found" issues

---

## Decision

**STATUS: ❌ REJECTED**

**Reason:** Critical architecture mismatch. Plan references deleted Amplify structure. Implementer would fail immediately.

**Next Steps:**

1. **Planner:** Perform architecture audit using tools (Glob, Grep, Read)
2. **Planner:** Update all file paths to match current SAM-based structure
3. **Planner:** Resubmit plan for review
4. **Reviewer:** Re-review updated plan for approval

**Estimated Time to Fix:** 2-4 hours (architecture audit + path updates)

---

## Questions for Planner

Before resubmitting, please answer:

1. **What language is the conversation Lambda?** (Python or Node.js)
2. **Where is the conversation Lambda handler located?** (exact file path)
3. **Is GraphQL still AppSync-based or migrated?** (API Gateway, direct Lambda?)
4. **Where are IAM roles defined?** (`template.yaml` SAM policies? Separate CFN?)
5. **Does `publish.py` still have `--deploy-chat` flag?** (verify current arguments)

---

**Reviewed by:** Tech Lead
**Date:** 2025-11-18
**Plan Version:** v1.0
**Next Review:** After architecture audit and path updates
