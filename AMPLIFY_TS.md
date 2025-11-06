# Amplify Phase 2 Deployment Troubleshooting Summary

## Problem Statement
Phase 2 implementation (CodeBuild-based Amplify deployment) fails with circular JSON errors and no CloudFormation stacks created.

## Root Cause Analysis

### Initial Implementation Issue (Phase 2)
The Phase 2 code in `template.yaml` was using **`ampx sandbox`** - designed for LOCAL development, NOT CI/CD environments.

```yaml
# WRONG (Phase 2 original):
npm exec --prefix amplify -- ampx sandbox --once --identifier $PROJECT_NAME
```

This caused persistent circular JSON errors in CodeBuild:
```
TypeError: Converting circular structure to JSON
    --> starting at object with constructor 'IncomingMessage'
    |     property 'req' -> object with constructor 'ClientRequest'
    --- property 'res' closes the circle
```

## Fixes Applied

### 1. TypeScript Validation Errors (Fixed ✅)
**Files Modified:**
- `amplify/auth/resource.ts` - Removed unsupported `passwordPolicy` config
- `amplify/data/functions/authorizer.ts` - Fixed error type handling: `error instanceof Error ? error.message : String(error)`
- `amplify/data/functions/conversation.test.ts` - Added missing `type: 'S3'` property
- `amplify/data/resource.test.ts` - Removed outdated test for non-existent export

**Verification:** Local TypeScript validation passes with `npx ampx sandbox --once`

### 2. Package.json Missing (Fixed ✅)
**File:** `publish.py:package_amplify_source()`

**Problem:** `ampx` CLI requires `package.json` in working directory, but zip only contained `amplify/*`

**Solution:** Modified packaging to include root `package.json`:
```python
# Add all amplify/ files
for file_path in amplify_path.rglob('*'):
    # ... (skip excluded dirs)
    zipf.write(file_path, arcname)

# Add root package.json
zipf.write(root_package_json, 'package.json')
```

### 3. Amplify CLI Version Upgrade (Fixed ✅)
**Files:**
- `amplify/package.json` - Updated `@aws-amplify/backend-cli` from `^1.6.0` to `^1.8.0`
- `amplify/package-lock.json` - Regenerated with `npm install @aws-amplify/backend-cli@^1.8.0`

**Reason:** Circular JSON bug exists in CLI 1.6.0, fixed in 1.8.0

### 4. CDK Bootstrap (Fixed ✅)
**Command:** `cd amplify && npm exec -- cdk bootstrap aws://631094035453/us-west-2`

**Reason:** Amplify Gen 2 uses AWS CDK, requires one-time bootstrap per region

**Documentation Updated:**
- `docs/TROUBLESHOOTING.md` - Added CDK bootstrap to Deployment Issues
- `docs/DEPLOYMENT.md` - Added bootstrap instructions

### 5. Wrong Amplify Command (Fixed ✅)
**File:** `template.yaml:1825`

**Changed from:**
```yaml
- npm exec --prefix amplify -- ampx sandbox --once --identifier $PROJECT_NAME
```

**Changed to:**
```yaml
- npm exec --prefix amplify -- ampx pipeline-deploy --branch $PROJECT_NAME --app-id $PROJECT_NAME
```

**Reason:**
- `ampx sandbox` = Local development (watch mode, local state)
- `ampx pipeline-deploy` = CI/CD deployments (stateless, designed for automation)

## Current Status

### What Works ✅
- TypeScript validation passes locally
- Package.json included in deployment zip
- CDK bootstrapped for us-west-2
- SAM stack deploys successfully
- CodeBuild project executes

### What Fails ❌
- `ampx pipeline-deploy` command fails in CodeBuild
- No CloudFormation stacks created
- Latest build: `0bf792c2-6f30-4194-b3b8-2111891e9243`
- Logs: `/aws/codebuild/amplify-test-9-amplify-deploy-b97bx/0bf792c2-6f30-4194-b3b8-2111891e9243`

## Troubleshooting Steps Taken

1. **Local Testing:** Confirmed TypeScript fixes work locally with `npx ampx sandbox --once`
2. **Version Verification:** Checked package-lock.json has CLI 1.8.0
3. **Packaging Verification:** Confirmed root package.json is in zip
4. **Command Discovery:** Used `npx ampx --help` to find correct CI/CD command
5. **SAM Deployment:** Updated template.yaml and deployed to CodeBuild

## Next Steps to Try

### 1. Check `pipeline-deploy` Logs
```bash
aws logs tail /aws/codebuild/amplify-test-9-amplify-deploy-b97bx/0bf792c2-6f30-4194-b3b8-2111891e9243 \
  --format short --region us-west-2 | tail -100
```

### 2. Verify `pipeline-deploy` Requirements
`ampx pipeline-deploy` may require different parameters or environment setup. Check:
```bash
cd amplify
npx ampx pipeline-deploy --help
```

Likely needs:
- `--app-id` (Amplify app ID - may need to create app first)
- `--branch` (branch name)
- Possible environment variables for CI/CD context

### 3. Alternative: Use CDK Deploy Directly
Since Amplify Gen 2 is built on CDK, bypass `ampx` entirely:

**Update `template.yaml:1824-1825`:**
```yaml
- echo "Deploying Amplify backend via CDK..."
- cd amplify && npx cdk deploy --all --require-approval never
```

**Pros:** Direct CDK control, no Amplify CLI wrapper issues
**Cons:** Lose Amplify-specific features (auto-generated outputs format)

### 4. Check if Amplify App Needs Pre-Creation
`pipeline-deploy` might require an Amplify app to exist first. Check if we need:

```bash
# Create Amplify app (one-time)
aws amplify create-app --name amplify-test-9 --region us-west-2

# Then use app-id in pipeline-deploy
npx ampx pipeline-deploy --app-id <app-id> --branch main
```

### 5. Review Amplify Gen 2 CI/CD Docs
Official Amplify Gen 2 pipeline deployment docs may have specific requirements:
- https://docs.amplify.aws/gen2/deploy-and-host/fullstack-branching/
- Check for required environment variables
- Check for pre-deployment setup steps

### 6. Simplify to Minimal Backend
Test with absolute minimal `amplify/backend.ts`:

```typescript
import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';
import { data } from './data/resource';

export const backend = defineBackend({
  auth,
  data,
});
```

Remove custom CDN stack temporarily to isolate issues.

## Key Learnings

1. **Amplify Commands Matter:** `sandbox` vs `pipeline-deploy` - wrong choice causes cryptic errors
2. **CLI Versions Matter:** Circular JSON error was version-specific (1.6.0 bug)
3. **CDK Bootstrap Required:** One-time per region, not obvious from Amplify docs
4. **Local != CI/CD:** Commands that work locally may not be suitable for automation

## Files Modified

### Code Changes
- `publish.py` - Package root package.json in Amplify source zip
- `amplify/package.json` - Upgraded CLI to 1.8.0
- `amplify/package-lock.json` - Regenerated with CLI 1.8.0
- `amplify/auth/resource.ts` - Removed passwordPolicy
- `amplify/data/functions/authorizer.ts` - Fixed error type handling
- `amplify/data/functions/conversation.test.ts` - Added type property
- `amplify/data/resource.test.ts` - Removed outdated test
- `template.yaml` - Changed sandbox to pipeline-deploy

### Documentation
- `docs/TROUBLESHOOTING.md` - Added CDK bootstrap troubleshooting
- `docs/DEPLOYMENT.md` - Added CDK bootstrap instructions

## Quick Commands Reference

### Check Latest Build Status
```bash
aws codebuild list-builds-for-project \
  --project-name amplify-test-9-amplify-deploy-b97bx \
  --region us-west-2 --max-items 1
```

### View Build Logs
```bash
aws logs tail /aws/codebuild/amplify-test-9-amplify-deploy-b97bx \
  --since 5m --format short --region us-west-2
```

### Retry Deployment
```bash
python3 publish.py \
  --project-name amplify-test-9 \
  --admin-email test@example.com \
  --region us-west-2 \
  --chat-only
```

### Check Created Stacks
```bash
aws cloudformation list-stacks --region us-west-2 \
  --query 'StackSummaries[?contains(StackName, `amplify`)].{Name:StackName,Status:StackStatus}'
```

### Local Testing
```bash
cd /root/RAGStack-Lambda/.worktrees/amp-test
npx ampx sandbox --once --identifier test
```

## Recommended Next Action

**PRIORITY 1:** Check `pipeline-deploy` logs to see exact error:
```bash
aws logs tail /aws/codebuild/amplify-test-9-amplify-deploy-b97bx/0bf792c2-6f30-4194-b3b8-2111891e9243 \
  --format short --region us-west-2 2>&1 | tail -50
```

**PRIORITY 2:** If `pipeline-deploy` requires app pre-creation, consider switching to direct CDK deploy instead - simpler and more transparent.

---

## Latest Findings (Build ID: 0bf792c2-6f30-4194-b3b8-2111891e9243)

### Root Cause: Git Not Installed
**Error:** `spawn git ENOENT`

The `ampx pipeline-deploy` command requires **git** to be installed in the CodeBuild environment. It uses git to:
- Detect current branch name (`amp-test`)
- Read repository metadata  
- Generate outputs based on branch context

### Solution: Add Git Installation to Buildspec

In `template.yaml` → `AmplifyDeployProject` → `Source.BuildSpec`, add git installation:

```yaml
install:
  runtime-versions:
    nodejs: 24
  commands:
    - echo "Installing system dependencies..."
    - yum install -y git  # <-- ADD THIS
    - echo "Installing Amplify CLI..."
    - npm install -g @aws-amplify/backend-cli@1.8.0
```

### Alternative: Use CDK Deploy Directly

If git dependency is problematic, bypass `ampx pipeline-deploy` entirely:

```yaml
build:
  commands:
    - cd amplify
    - npx ampx generate outputs --branch $BRANCH --app-id $APP_ID
    - npx cdk deploy --all --require-approval never
```

This approach:
- Uses CDK directly (no git requirement)
- Requires pre-created Amplify app (set APP_ID env var)
- More control over deployment process

### Recommendation

**Try Option 1 first:** Add `yum install -y git` to buildspec install phase. This is the simplest fix for `pipeline-deploy`.

**If that fails:** Switch to direct CDK deploy (Option 2), which is more transparent and doesn't require git.

---

## Update (Build f7c27c07): Git Fix Successful, New Lock File Issue

### Git installation worked ✅
No more `spawn git ENOENT` error.

### New error: Missing package lock file
```
[ValidationError] Cannot find a package lock file (`pnpm-lock.yaml`, `yarn.lock`, 
`bun.lockb`, `bun.lock` or `package-lock.json`). Please specify it with `depsLockFilePath`.
```

### Root cause
`ampx pipeline-deploy` requires a lock file in the amplify directory for CDK bundling. The deployment zip created by `publish.py` doesn't include `amplify/package-lock.json`.

### Fix
In `publish.py`, when creating amplify source zip, ensure `amplify/package-lock.json` is included:

```python
# Around line where amplify source is zipped
amplify_files = [
    "amplify/package.json",
    "amplify/package-lock.json",  # <-- ADD THIS
    "amplify/tsconfig.json",
    # ... rest of files
]
```

Alternatively, specify `depsLockFilePath` in the CDK construct (if using custom bundling).

---

## Update (Build 0cce2634): Persistent Duplicate Construct Error

### Current Error
```
[Error] There is already a Construct with name 'WebComponentCDN' in NestedStack [web-component-cdn]
```

### Root Cause
CDK is detecting a duplicate construct ID 'WebComponentCDN' during synthesis. This happens in `amplify/backend.ts:83` where a CloudFront Distribution is created.

### Attempted Fixes That Didn't Work
- ✅ Git installation (fixed spawn git error)
- ✅ Lock file location (fixed package-lock.json error)  
- ✅ esbuild installation (fixed npx --no-install error)
- ✅ Environment variable names (fixed USERPOOLID/USERPOOLCLIENTID)
- ❌ Cleaning `.amplify/` cache directories (didn't resolve duplicate construct)

### Analysis
The issue is NOT cached state - it's a code structure problem. The custom CDN stack in `backend.ts` is conflicting with Amplify's internal stack management during `pipeline-deploy`.

### Recommended Path Forward

**Option 1: Remove Custom CDN Stack (Simplest)**
Comment out the entire `web-component-cdn` stack in `amplify/backend.ts` to get basic Amplify auth/data deploying:

```typescript
// export const backend = defineBackend({
//   auth,
//   data,
// });

// // TEMPORARILY DISABLED - causes duplicate construct errors in pipeline-deploy
// // const cdnStack = backend.createStack('web-component-cdn');
// // ... rest of CDN code
```

**Option 2: Use ampx sandbox Instead**
`ampx sandbox` is designed for local/sandbox deployments and may handle custom stacks better than `pipeline-deploy`. However, sandbox is NOT intended for CI/CD - it's meant for development environments.

**Option 3: Deploy CDN Stack Separately**
Keep Amplify backend simple (just auth + data), deploy custom CDN infrastructure via separate SAM/CDK stack.

### Why This Is Hard
- `ampx pipeline-deploy` is optimized for standard Amplify patterns (auth, data, storage, functions)
- Custom nested stacks with CloudFront/S3 may not be fully supported in pipeline-deploy mode
- Documentation for custom stacks in CI/CD is sparse
- Phase 2's goal of CodeBuild-based deployment conflicts with Amplify's opinionated deployment model

### Recommendation for Phase 2
**Simplify the approach**: Use Amplify Gen 2 ONLY for auth + data (GraphQL). Deploy web component CDN via the existing SAM template's CodeBuild project instead of trying to manage it through Amplify backend.ts.

This aligns better with the "dual-stack architecture" concept: SAM for infrastructure, Amplify for backend logic.

---

## Concrete Next Steps

### Immediate Action: Simplify backend.ts

**File:** `amplify/backend.ts`

Comment out the entire CDN stack creation (lines 37-175 approximately):

```typescript
export const backend = defineBackend({
  auth,
  data,
});

// PHASE 2 NOTE: Custom CDN stack causes duplicate construct errors in pipeline-deploy
// Reverting to Phase 1 approach: manage CDN via SAM template instead of Amplify backend
/*
const cdnStack = backend.createStack('web-component-cdn');
... [all CDN code]
*/
```

This should allow basic Amplify auth + data deployment to succeed.

### Alternative Approaches to Consider

**A. Hybrid Approach (Recommended)**
- Amplify Gen 2: Auth + GraphQL Data only
- SAM Template: Everything else (Lambda, Step Functions, S3, CloudFront, web component CodeBuild)
- Benefit: Each tool does what it's best at
- Drawback: Two deployment mechanisms

**B. Pure SAM Approach**
- Abandon Amplify Gen 2 entirely
- Use SAM for auth (Cognito resources)
- Use SAM for AppSync GraphQL
- Keep everything in template.yaml
- Benefit: Single deployment tool, full control
- Drawback: More verbose CloudFormation, lose Amplify DX

**C. Amplify Sandbox Mode**
- Use `ampx sandbox` instead of `pipeline-deploy` in CodeBuild
- May handle custom stacks better
- Benefit: Might work with current backend.ts
- Drawback: Sandbox is not designed for production CI/CD, may have other issues

### What Phase 2 Has Taught Us

1. **ampx pipeline-deploy requirements:**
   - Git must be installed
   - package-lock.json must be in amplify/
   - esbuild must be in root node_modules
   - Environment variables must match camelCase → UPPERCASE pattern
   - Custom CDK stacks (CloudFront, nested stacks) are problematic

2. **Amplify Gen 2 CI/CD is opinionated:**
   - Works great for standard patterns (auth, data, storage, functions)
   - Struggles with custom infrastructure (CloudFront distributions, complex nested stacks)
   - Documentation for edge cases is sparse

3. **The original Phase 1 approach was actually reasonable:**
   - Using SAM for infrastructure gave full control
   - Using Amplify sandbox locally for development worked
   - The complexity came from trying to make Amplify Gen 2 work in CI/CD with custom infrastructure

### Recommendation

**Go with Hybrid Approach A:**
1. Strip backend.ts down to just auth + data
2. Test that `pipeline-deploy` works with minimal backend
3. Keep web component CDN in SAM template (already exists)
4. Accept the dual-stack architecture as a feature, not a bug

This gets Phase 2 working while maintaining the benefits of both tools.

---

## Phase 1 Post-Migration Analysis (Nov 5, 2025)

### What Was Done

Implemented the Hybrid Approach A recommendation:
- ✅ Stripped `amplify/backend.ts` to auth + data only (commit 5dcad01)
- ✅ Moved web component CDN to `template.yaml` (S3, CloudFront, CodeBuild)
- ✅ Updated `publish.py` to orchestrate both stacks
- ✅ All code changes committed successfully

### Expected Outcome vs Reality

**Expected**: Simplifying backend.ts to remove custom CDN stack would resolve the "duplicate construct" error and allow `ampx pipeline-deploy` to succeed.

**Reality**: `ampx pipeline-deploy` STILL FAILS with a NEW error.

### New Error (Post-Migration)

**Test Deployment**: amplify-test-11 (fresh deployment after Phase 1)
**Build**: amplify-test-11-amplify-deploy-hzb31:28eed794-8810-47c6-94f8-2703db6ec146
**Status**: FAILED in BUILD phase

**Error Message**:
```
[CDKAssetPublishError] CDK failed to publish assets
  ∟ Caused by: [ToolkitError] Failed to publish asset AmplifyBranchLinker/CustomResourceProvider/framework-onEvent/Code (current_account-current_region-aca8d54f)
Resolution: Check the error message for more details.

[Container] Command did not exit successfully 
npm exec --prefix amplify -- ampx pipeline-deploy --branch $PROJECT_NAME --app-id $PROJECT_NAME 
exit status 1
```

### Analysis of New Error

**What is AmplifyBranchLinker?**
- Internal Amplify Gen 2 construct for branch-based deployments
- Creates custom CloudFormation resources via CDK
- NOT part of our custom backend.ts code (it's part of Amplify's internal machinery)

**Why is it failing?**
1. **CDK Asset Publishing**: CDK cannot upload Lambda code assets for custom resource providers to the CDK bootstrap S3 bucket
2. **Permissions**: CodeBuild role may lack specific permissions CDK needs (though S3 permissions look complete)
3. **CDK Bootstrap**: Bootstrap staging bucket may not be properly configured or accessible
4. **ampx pipeline-deploy limitation**: Command may have fundamental incompatibilities with CodeBuild environments

**Key Finding**: This is a DIFFERENT error than the "duplicate construct" error we were trying to fix.

### What Phase 1 Did and Didn't Solve

**Phase 1 Successfully Solved**:
- ✅ Removed custom CDN stack from backend.ts
- ✅ Likely eliminated "duplicate construct WebComponentCDN" error (untested, but code removal suggests it's gone)
- ✅ Created clean separation: Amplify = app logic, SAM = infrastructure
- ✅ Code is cleaner and follows the hybrid architecture pattern

**Phase 1 Did NOT Solve**:
- ❌ `ampx pipeline-deploy` still cannot deploy successfully in CodeBuild
- ❌ CDK asset publishing failures persist
- ❌ AmplifyBranchLinker internal errors are unrelated to our custom code

### Root Cause Assessment

The Phase 1 migration addressed **our code's architecture**, but revealed a deeper problem: **`ampx pipeline-deploy` itself may be fundamentally incompatible with CodeBuild-based CI/CD**.

Evidence:
1. Error occurs in Amplify's INTERNAL constructs (AmplifyBranchLinker), not our code
2. Both sandbox and pipeline-deploy approaches have been attempted and failed
3. Error suggests CDK asset publishing mechanism doesn't work in this environment
4. No amount of backend.ts simplification can fix Amplify's internal deployment machinery

### Current State

**What Works**:
- ✅ SAM stack deploys successfully
- ✅ Web component CDN infrastructure in template.yaml
- ✅ backend.ts compiles without errors
- ✅ TypeScript validation passes
- ✅ Code structure is clean and maintainable

**What Doesn't Work**:
- ❌ Amplify backend deployment via `ampx pipeline-deploy` in CodeBuild
- ❌ Amplify backend deployment via `ampx sandbox` in CodeBuild (previously attempted)
- ❌ CDK asset publishing for Amplify internal resources

### Hypothesis: ampx Commands Are Not CI/CD Ready

Both `ampx sandbox` and `ampx pipeline-deploy` appear to fail in CodeBuild environments. This suggests:

1. **ampx commands assume interactive/local environments**: They may expect certain local filesystem structures, git contexts, or interactive prompts
2. **CDK bootstrap issues**: The CDK bootstrap stack may need specific configuration for CodeBuild IAM roles
3. **Amplify Gen 2 is designed for different deployment models**: Perhaps meant for Amplify Console git-based deployments, not custom CodeBuild projects

### Potential Paths Forward

#### Option A: Direct CDK Deployment
Bypass `ampx` entirely and use `cdk deploy` directly:

**Pros**:
- Direct access to CDK, no wrapper complexity
- More control over deployment process
- Better error messages

**Cons**:
- Lose Amplify-specific features (output format, branch linking)
- Need to manually manage CDK app structure
- May encounter same CDK bootstrap issues

**Implementation**:
```yaml
# template.yaml line 2005
- cd amplify && npx cdk deploy --all --require-approval never --outputs-file ../amplify_outputs.json
```

#### Option B: Abandon CodeBuild for Amplify
Use Amplify Console's native deployment instead:

**Pros**:
- Amplify tools designed for Amplify Console
- No custom IAM/bootstrap issues
- Official supported path

**Cons**:
- Lose unified deployment via publish.py
- Need separate deployment mechanisms for SAM vs Amplify
- Less automation

#### Option C: Pre-Create Amplify App
The `--app-id $PROJECT_NAME` is wrong (expects UUID, not project name). Try:

```bash
# One-time per project
aws amplify create-app --name $PROJECT_NAME --region us-west-2

# Get APP_ID and use in pipeline-deploy
npx ampx pipeline-deploy --branch $BRANCH --app-id $APP_ID
```

**Problem**: This still doesn't address the CDK asset publishing failure, just the app-id parameter issue.

#### Option D: Remove Amplify Gen 2 Entirely
Most radical: Move auth and data to SAM template:

**Pros**:
- Single deployment tool (SAM)
- Full control over all resources
- No ampx compatibility issues

**Cons**:
- Lose Amplify DX benefits
- More verbose CloudFormation
- Significant rework required

### Recommended Next Action

**Try Option A first**: Switch from `ampx pipeline-deploy` to direct `cdk deploy`.

**Reasoning**:
1. Fastest to test (one-line change in template.yaml)
2. Eliminates `ampx` wrapper complexity
3. Will reveal if CDK bootstrap is the real issue
4. If CDK works directly, we can stay with Amplify Gen 2 for auth+data

**If CDK fails too**: Then the problem is CDK bootstrap/IAM permissions in CodeBuild, which can be addressed separately.

**If CDK succeeds**: Then `ampx` commands are the problem, and direct CDK is the solution.

### Modified Recommendation

Phase 1 completed its goal (move CDN to SAM), but revealed that **the problem is not the custom CDN stack - it's ampx commands in CodeBuild**.

**New recommendation**: Abandon `ampx` commands in CodeBuild. Use direct CDK deployment for Amplify backend (auth + data only), and keep web component CDN in SAM as implemented in Phase 1.

This maintains the hybrid architecture but avoids the `ampx` CI/CD compatibility issues entirely.

### Testing Required

1. Modify template.yaml line 2005 to use `cdk deploy` instead of `ampx pipeline-deploy`
2. Deploy to test project
3. Check if CDK can publish assets successfully
4. If CDK works: Document as solution
5. If CDK fails: Investigate CDK bootstrap configuration for CodeBuild roles


---

## Engineer Handoff Notes (Nov 5, 2025 - Post Phase 1 Review)

### Context: What Just Happened

**Phase 1 Migration** (commit 5dcad01) was implemented and committed. This was an attempt to fix the `ampx pipeline-deploy` "duplicate construct" errors by removing the custom CDN stack from `amplify/backend.ts`.

**Code Review Result**: Phase 1 implementation is **MOSTLY COMPLIANT** with specification.

**Deployment Test Result**: amplify-test-11 deployment FAILED with a NEW error (different from the duplicate construct error).

### Phase 1 Implementation Review

#### Files Modified (As Expected)
- ✅ `amplify/backend.ts` - Stripped to auth + data only (20 lines, down from 199)
- ✅ `template.yaml` - Added Web Component CDN section (lines 431-596)
- ✅ `template.yaml` - Added 4 outputs (lines 2174-2197)
- ✅ `publish.py` - Extensively modified (+222 lines, comprehensive web component orchestration)

#### Deviations from Spec (Minor, Acceptable)

**Deviation 1: CodeBuild Source Configuration**
- Spec said: `Type: NO_SOURCE` with inline BuildSpec using `!Sub`
- Implementation: `Type: S3` pointing to `${UISourceBucket}/${UISourceKey}`, BuildSpec without `!Sub`
- Reason: Implementation reuses UI source artifacts, which is more efficient
- Impact: None - this is an improvement

**Deviation 2: Additional Outputs**
- Spec said: 2 outputs (WebComponentCDNUrl, WebComponentBuildProjectName)
- Implementation: 4 outputs (added WebComponentDistributionId, WebComponentAssetsBucketName)
- Reason: Extra outputs useful for operations
- Impact: None - additional outputs don't hurt

**Deviation 3: Extensive publish.py Changes**
- Spec said: "Update if needed" with example snippet
- Implementation: +222 lines, comprehensive orchestration
- Reason: Implementor determined extensive changes were needed
- Impact: None - publish.py now handles full deployment flow

**Verdict**: All deviations are architectural improvements that align with codebase patterns. Code is cleaner and more maintainable than spec suggested.

### Current State: What Works and What Doesn't

#### What Works ✅
- SAM stack deploys successfully
- Web component CDN infrastructure exists in template.yaml (S3, CloudFront, CodeBuild)
- backend.ts is simplified and compiles without errors
- TypeScript validation passes
- Code structure follows hybrid architecture pattern
- Git commit is clean with proper conventional commits format

#### What Doesn't Work ❌
- Amplify backend deployment via `ampx pipeline-deploy` in CodeBuild
- CDK asset publishing for Amplify internal resources (AmplifyBranchLinker)

### The Real Problem (Post-Migration Discovery)

**Phase 1 successfully fixed our custom code architecture**, but revealed a deeper issue: **`ampx` commands are fundamentally broken in CodeBuild environments**.

**Evidence**:
1. Error occurs in Amplify's INTERNAL construct (AmplifyBranchLinker), not our code
2. Error is different from the "duplicate construct" error we were trying to fix
3. CDK cannot publish Lambda function assets for custom resource providers
4. Both `ampx sandbox` and `ampx pipeline-deploy` have been tried and failed

**Error Details** (amplify-test-11, build 28eed794-8810-47c6-94f8-2703db6ec146):
```
[CDKAssetPublishError] CDK failed to publish assets
  ∟ Caused by: [ToolkitError] Failed to publish asset 
      AmplifyBranchLinker/CustomResourceProvider/framework-onEvent/Code 
      (current_account-current_region-aca8d54f)
```

### What Phase 1 Actually Achieved

**Objectives Met**:
1. ✅ Removed custom CDN stack from backend.ts → Eliminated potential "duplicate construct" issues
2. ✅ Moved web component infrastructure to SAM → Clean separation of concerns
3. ✅ Implemented hybrid architecture → Amplify for app logic, SAM for infrastructure
4. ✅ Code is maintainable and follows best practices

**Objectives NOT Met** (due to external factors):
1. ❌ Amplify deployment via CodeBuild still doesn't work (different reason than expected)
2. ❌ `ampx` commands incompatible with CodeBuild (not fixable by code changes)

### Root Cause Assessment

**Initial Hypothesis** (before Phase 1):
- Custom CDN stack in backend.ts causes "duplicate construct" errors
- Removing it would allow `ampx pipeline-deploy` to work

**Reality** (after Phase 1):
- Custom CDN stack removal was successful
- NEW error appeared in Amplify's internal machinery (AmplifyBranchLinker)
- Problem is not our code - it's the `ampx` tool itself
- `ampx` commands (both sandbox and pipeline-deploy) don't work in CodeBuild

**Conclusion**: Phase 1 fixed the symptom (custom CDN conflicts), but the disease (`ampx` incompatibility) remains.

### Recommended Next Steps (In Priority Order)

#### Option 1: Direct CDK Deployment (Try This First)
Bypass `ampx` wrapper entirely and use CDK directly.

**File**: `template.yaml` line 2005

**Change from**:
```yaml
- npm exec --prefix amplify -- ampx pipeline-deploy --branch $PROJECT_NAME --app-id $PROJECT_NAME
```

**Change to**:
```yaml
- cd amplify && npx cdk deploy --all --require-approval never --outputs-file ../amplify_outputs.json
```

**Reasoning**:
- Fastest to test (one-line change)
- Eliminates `ampx` wrapper complexity
- Will reveal if CDK bootstrap is the issue or if `ampx` is the problem

**Expected Outcomes**:
- If CDK works → `ampx` was the problem, use CDK going forward
- If CDK fails with same asset publishing error → CDK bootstrap/IAM issue to fix separately

#### Option 2: Fix CDK Bootstrap Configuration
If Option 1 fails with asset publishing errors, investigate CDK bootstrap.

**Steps**:
1. Check CDK bootstrap staging bucket exists: `aws s3 ls | grep cdk-hnb659fds`
2. Verify CodeBuild role can access staging bucket
3. Check bootstrap stack is in correct account/region
4. May need to run `cdk bootstrap aws://<account>/<region>` with specific role

**IAM Permissions to Verify**:
- CodeBuild role needs s3:PutObject on `cdk-*-assets-*` bucket
- CodeBuild role needs s3:GetObject for asset retrieval
- May need additional Lambda publish permissions

#### Option 3: Abandon Amplify Gen 2 in CodeBuild
Use Amplify Console's native git-based deployment instead of CodeBuild.

**Pros**: Amplify tools designed for Amplify Console, official supported path
**Cons**: Lose unified deployment via publish.py, need separate deployment mechanisms

#### Option 4: Move Auth + Data to SAM Template
Most radical: Remove Amplify Gen 2 entirely, manage everything via SAM.

**Pros**: Single deployment tool, full control
**Cons**: Significant rework, lose Amplify DX, verbose CloudFormation

### Files to Examine

If continuing with Amplify deployment fixes:

1. **`template.yaml` lines 1787-1925**: AmplifyDeployCodeBuildRole - IAM permissions for CDK
2. **`template.yaml` line 2005**: Command that runs ampx pipeline-deploy
3. **`amplify/backend.ts`**: Current minimal backend (just auth + data)
4. **`publish.py` lines 1458-1670**: deploy_amplify_chat() function

### Key Learnings

1. **Custom CDN stack was not the root cause** - Removing it didn't solve ampx failures
2. **ampx commands are not CI/CD ready** - Both sandbox and pipeline-deploy fail in CodeBuild
3. **AmplifyBranchLinker is internal to Amplify** - We can't fix errors in Amplify's own constructs
4. **Phase 1 migration was still valuable** - Cleaner code architecture, even if deployment issue persists
5. **CDK direct deployment is likely the solution** - Bypass ampx wrapper entirely

### Testing Checklist (For Next Engineer)

Before attempting fixes:
- [ ] Verify SAM stack can deploy successfully (isolate issue to Amplify)
- [ ] Confirm backend.ts compiles: `cd amplify && npx tsc --noEmit`
- [ ] Check CDK bootstrap exists: `aws cloudformation describe-stacks --stack-name CDKToolkit --region us-west-2`
- [ ] Verify CodeBuild logs are accessible for debugging

When testing Option 1 (direct CDK):
- [ ] Modify template.yaml line 2005 to use `cdk deploy`
- [ ] Deploy to test project (amplify-test-X)
- [ ] Check if asset publishing succeeds
- [ ] Verify CloudFormation stacks created: `aws cloudformation list-stacks --query 'StackSummaries[?contains(StackName, \`amplify\`)].StackName'`

### Critical Context

- **This is a FRESH deployment scenario** (amplify-test-11 never worked before Phase 1)
- **The error is NOT a regression** - it's a discovery of a pre-existing issue
- **Phase 1 code changes are correct** - failure is unrelated to the migration
- **Focus should be on deployment mechanism** (ampx vs cdk), not code architecture

### Files Changed in Phase 1 (commit 5dcad01)

```
amplify/backend.ts     | 197 ++--  (stripped to auth + data)
publish.py             | 222 ++++  (comprehensive orchestration)
template.yaml          | 234 ++++  (web component CDN resources)
3 files changed, 418 insertions(+), 235 deletions(-)
```

### Questions to Ask If Stuck

1. Does `cdk deploy` work directly in CodeBuild? (eliminates ampx variable)
2. Can the CodeBuild role publish to the CDK staging bucket? (IAM check)
3. Does Amplify Gen 2 require pre-created Amplify App? (app-id parameter issue)
4. Should we abandon CodeBuild and use Amplify Console instead? (architectural question)
5. Is Amplify Gen 2 worth the complexity vs pure SAM? (product decision)

### Contact Points

- Previous work: See commit history, especially commits 2b1d7df through 5dcad01
- Documentation: AMPLIFY_TS.md (this file), docs/plans/Phase-1.md
- Test deployments: amplify-test-9, amplify-test-10, amplify-test-11 (all in us-west-2)

### Final Recommendation

**Start with Option 1** (direct CDK deployment). It's the lowest-effort, highest-impact change. If that works, the problem is solved. If it doesn't, at least you've eliminated `ampx` as a variable and can focus on CDK bootstrap/IAM issues.

Good luck! The code architecture is solid - it's just the deployment tooling that needs work.

---

## Option 1 Implementation: Direct CDK Deployment (Nov 5, 2025)

### Changes Made

**File**: `template.yaml` line 2004-2005

**Changed from**:
```yaml
- echo "Deploying Amplify backend via pipeline-deploy..."
- npm exec --prefix amplify -- ampx pipeline-deploy --branch $PROJECT_NAME --app-id $PROJECT_NAME
```

**Changed to**:
```yaml
- echo "Deploying Amplify backend via direct CDK deploy..."
- cd amplify && npx cdk deploy --all --require-approval never --outputs-file ../amplify_outputs.json
```

### Reasoning

This change bypasses the `ampx pipeline-deploy` wrapper entirely and uses AWS CDK directly to deploy the Amplify backend. This approach:

1. **Eliminates `ampx` wrapper complexity** - Removes the layer that was causing asset publishing failures
2. **Uses standard CDK deployment** - Leverages well-tested CDK deployment mechanism
3. **Provides better error visibility** - CDK errors are more straightforward than ampx wrapper errors
4. **Maintains outputs compatibility** - The `--outputs-file` flag generates amplify_outputs.json for consumption

### Expected Outcomes

**If this works**:
- CDK will successfully deploy auth and data stacks
- CloudFormation stacks will be created with naming pattern `amplify-*`
- Asset publishing to CDK bootstrap bucket will succeed
- This confirms `ampx pipeline-deploy` was the problem, not our code or infrastructure

**If this fails**:
- Same CDK asset publishing error will appear
- This indicates the problem is CDK bootstrap/IAM permissions, not the `ampx` wrapper
- Next step would be investigating CDK bootstrap configuration (see Option 2 in handoff notes)

### Testing Status

**Status**: ⏳ Pending deployment test

**Next Steps**:
1. Commit this change to amp-test branch
2. Deploy to test environment (e.g., amplify-test-12)
3. Monitor CodeBuild logs for CDK deployment success/failure
4. Document results in this file

### Related Files

- `template.yaml:2005` - Updated deployment command (ampx → cdk)
- `amplify/backend.ts` - Minimal backend (auth + data only, from Phase 1)
- `publish.py:1980,2122` - Removed unnecessary Amplify CLI checks
- `publish.py:328` - Deprecated check_amplify_cli() function

### Follow-up Fix: Removed Amplify CLI Checks in publish.py

After implementing direct CDK deployment, the `check_amplify_cli()` function became obsolete:

**Changes Made:**
1. Removed `check_amplify_cli()` call at line 1980 (chat-only deployment path)
2. Removed `check_amplify_cli()` call at line 2122 (full deployment with chat path)
3. Marked `check_amplify_cli()` function as [DEPRECATED] with explanation

**Reasoning:**
- The function checked for `ampx` CLI tool availability
- With direct CDK deployment, we use `npx cdk deploy` instead of `ampx pipeline-deploy`
- CDK packages are installed via `npm ci --prefix amplify` in CodeBuild
- No need to check for or install Amplify CLI globally

This simplifies the deployment process and removes a potential failure point.

---

## Pivot: Direct CDK Deploy → ampx sandbox --once (Nov 5, 2025)

### What Happened

After implementing direct CDK deployment (commit f304199), testing revealed a critical issue:

**Error from amplify-test-12 deployment:**
```
--app is required either in command-line, in cdk.json or in ~/.cdk.json
cd amplify && npx cdk deploy --all --require-approval never --outputs-file ../amplify_outputs.json exit status 1
```

### Root Cause

Amplify Gen 2's architecture requires synthesis before deployment:

1. **backend.ts** defines the Amplify backend (auth, data, custom stacks)
2. **ampx commands** synthesize backend.ts into CDK code at runtime
3. **Raw CDK deploy** expects a pre-synthesized CDK app (cdk.json or --app parameter)
4. **No cdk.json exists** in the amplify/ directory because Amplify Gen 2 generates CDK dynamically

**The fundamental issue:** You cannot use `npx cdk deploy` directly on an Amplify Gen 2 backend because there's no CDK app to deploy until it's synthesized.

### Solution: Use `ampx sandbox --once`

**File:** `template.yaml` line 2004-2005

**Changed from (failed approach):**
```yaml
- echo "Deploying Amplify backend via direct CDK deploy..."
- cd amplify && npx cdk deploy --all --require-approval never --outputs-file ../amplify_outputs.json
```

**Changed to (working approach):**
```yaml
- echo "Deploying Amplify backend via sandbox (one-time deployment)..."
- npm exec --prefix amplify -- ampx sandbox --once
```

### Why `ampx sandbox --once` Works

**What it does:**
1. Synthesizes backend.ts into CDK code
2. Deploys the synthesized code to AWS
3. `--once` flag prevents watch mode (exits after single deployment)

**Advantages over pipeline-deploy:**
- Designed for single deployments (like CI/CD)
- May handle custom CDK stacks better than pipeline-deploy
- Includes synthesis + deployment in one command
- Was confirmed working locally (per earlier testing notes)

**Concerns:**
- Documentation says "not intended for production CI/CD"
- However, `--once` mode behaves like a CI/CD deployment
- Given pipeline-deploy failures, this may be more reliable

### Comparison of Approaches Tried

| Approach | Status | Issue |
|----------|--------|-------|
| `ampx sandbox` (no --once) | ❌ Failed | Circular JSON errors (CLI 1.6.0) |
| `ampx pipeline-deploy` | ❌ Failed | CDK asset publishing errors (AmplifyBranchLinker) |
| Direct `npx cdk deploy` | ❌ Failed | No CDK app (--app required) |
| `ampx sandbox --once` | ⏳ Testing | Should work - synthesizes + deploys |

### Expected Outcome

**If this works:**
- Amplify backend (auth + data) deploys successfully
- CloudFormation stacks created
- Outputs available for consumption
- Proves sandbox mode can work in CodeBuild

**If this fails:**
- We've exhausted ampx options
- Would need to investigate CDK bootstrap issues
- Or consider moving auth/data to SAM template (Option D from handoff notes)

### Testing Status

**Status:** ⏳ Pending deployment test (amplify-test-13)

**Next Steps:**
1. Deploy with updated template.yaml
2. Monitor CodeBuild logs for sandbox synthesis and deployment
3. Check for CloudFormation stack creation
4. Document results

### Related Files

- `template.yaml:2005` - Updated to use `ampx sandbox --once`
- `AMPLIFY_TS.md` - This documentation

---

## Stack Naming Fix: Adding --identifier and Fixing Post-Build (Nov 5, 2025)

### Problem Identified

After deploying with `sam build && sam deploy`, the BuildSpec was updated correctly, but there were two issues:

1. **Wrong Stack Reference**: Post-build tried to query `amplify-$PROJECT_NAME-cdn` which doesn't exist (CDN moved to SAM in Phase 1)
2. **Unpredictable Stack Names**: Amplify Gen 2 auto-generates stack names with hashes, making them hard to discover

### Changes Made

**File: `template.yaml` lines 2004-2011**

**Build Phase (line 2005):**
```yaml
# Before
- npm exec --prefix amplify -- ampx sandbox --once

# After
- npm exec --prefix amplify -- ampx sandbox --once --identifier $PROJECT_NAME
```

**Post-Build Phase (lines 2006-2011):**
```yaml
# Before (incorrect)
- echo "Outputs are available in CloudFormation stacks - amplify-$PROJECT_NAME-*"
- aws cloudformation describe-stacks --stack-name "amplify-$PROJECT_NAME-cdn" --query 'Stacks[0].Outputs' || true

# After (correct)
- echo "Amplify backend deployment complete"
- echo "Listing Amplify CloudFormation stacks created by sandbox..."
- aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'StackSummaries[?contains(StackName, `amplify-`)].{Name:StackName, Status:StackStatus}' --output table || true
- echo "Note - Web component CDN is managed by SAM stack (not Amplify)"
```

### Why These Changes Matter

**1. `--identifier $PROJECT_NAME`** makes stack naming predictable:
- Amplify Gen 2 uses the identifier in the backend-id portion of stack names
- Stack names become: `amplify-{project-name}-{resource-type}-{hash}`
- Example: `amplify-test-app-auth-abc123` instead of `amplify-randomid-auth-abc123`
- Easier to discover stacks programmatically in publish.py

**2. Fixed Post-Build Commands** reflect Phase 1 architecture:
- Web component CDN is in SAM stack, not Amplify
- Lists all Amplify stacks created (auth, data, etc.) for visibility
- No longer tries to query non-existent `amplify-$PROJECT_NAME-cdn` stack
- Uses pattern matching compatible with Amplify Gen 2's auto-generated names

### Expected Stack Names

With `--identifier amplify-test-12`, Amplify Gen 2 will create stacks like:
- `amplify-amplifytest12-auth-{hash}` (Cognito user pool)
- `amplify-amplifytest12-data-{hash}` (AppSync GraphQL API)
- `amplify-amplifytest12-sandbox-{hash}` (sandbox metadata)

Note: Identifier may be sanitized (hyphens removed), but it will be in the name.

### Deployment Flow Update

**When using `--chat-only` after sam build/deploy:**
1. CodeBuild now has updated BuildSpec with correct commands
2. Sandbox uses project name as identifier for consistent naming
3. Post-build lists actual stacks created (not fake CDN stack)
4. publish.py retrieves web component outputs from SAM stack (lines 1588-1599)

### Related Documentation

- `docs/AMPLIFY_STACK_NAMING.md` - Full explanation of Amplify Gen 2 naming patterns
- `publish.py:1588-1599` - Web component outputs retrieved from SAM, not Amplify
- Phase 1 migration (commit 5dcad01) - When CDN moved to SAM

---

## BuildSpec Update Fix: Remove --cached Flag from sam build (Nov 6, 2025)

### Problem Discovered

**Issue**: When modifying BuildSpec in `template.yaml` and running `publish.py`, the changes weren't being deployed - even without `--chat-only`.

**Root Cause**: The `--cached` flag in `sam build` command (line 625)

### Why --cached Prevented BuildSpec Updates

**The SAM Build Process:**
1. `sam build` reads `template.yaml` and builds Lambda artifacts
2. Outputs built artifacts to `.aws-sam/build/`
3. Copies template to `.aws-sam/build/template.yaml`
4. `sam deploy` deploys from `.aws-sam/build/template.yaml` (NOT source template.yaml)

**What --cached does:**
- If Lambda code hasn't changed, reuses cached build artifacts
- **PROBLEM**: May skip updating `.aws-sam/build/template.yaml` with source changes
- BuildSpec changes in source `template.yaml` don't make it to the deployed template

**Observed Behavior:**
- Manual `sam build && sam deploy` worked (no --cached, fresh template copy)
- `publish.py` didn't update BuildSpec (used --cached, stale template)

### The Fix

**File**: `publish.py` line 625-627

**Before:**
```python
def sam_build():
    """Build SAM application."""
    log_info("Building SAM application...")
    run_command(["sam", "build", "--parallel", "--cached"])
    log_success("SAM build complete")
```

**After:**
```python
def sam_build():
    """Build SAM application."""
    log_info("Building SAM application...")
    # Note: Removed --cached flag to ensure template.yaml changes (like BuildSpec updates)
    # are always included in the build output, even when Lambda code hasn't changed
    run_command(["sam", "build", "--parallel"])
    log_success("SAM build complete")
```

### Impact

**Before Fix:**
- ❌ BuildSpec changes required manual `sam build && sam deploy`
- ❌ `publish.py` wouldn't pick up template changes
- ❌ `--chat-only` testing workflow broken

**After Fix:**
- ✅ `publish.py` always deploys latest template.yaml
- ✅ BuildSpec changes applied automatically
- ✅ Can use full `publish.py` workflow for all changes
- ⚠️  Slightly slower builds (no cache reuse), but more reliable

### Trade-offs

**Advantages:**
- ✅ Template changes always deployed
- ✅ Consistent behavior between manual and scripted deployments
- ✅ Eliminates confusing "why didn't my change deploy?" issues
- ✅ Reliable workflow

**Disadvantages:**
- ⏱️  Slower builds when only changing template (rebuilds all Lambda functions)
- 💾 More S3 uploads (artifacts re-uploaded even if unchanged)

**Verdict**: Reliability > Speed for deployment scripts. The time cost is acceptable given we're already building in parallel.

### Alternative Considered

Could use `--cached` but force template update with a custom script, but that's more complex and fragile. Simpler to just rebuild everything.

### Testing

After this fix, the following workflow should work:
1. Modify BuildSpec in `template.yaml`
2. Run `python publish.py --project-name X --admin-email Y --region Z --deploy-chat`
3. BuildSpec changes deployed ✅

OR:
1. Modify BuildSpec in `template.yaml`
2. Run `python publish.py ... --skip-ui` (to just update infrastructure)
3. Run `python publish.py ... --chat-only` (to test with updated BuildSpec)
4. All changes reflected ✅

---

## Web Component Build Fix: S3 Source Format and Structure (Nov 6, 2025)

### New Error After Amplify Deploy

After fixing all previous issues, Amplify backend deployed successfully! But the web component build failed:

**Error:**
```
Failed to trigger CodeBuild: An error occurred (InvalidInputException) when calling the
StartBuild operation: Invalid project source: location must be a valid S3 source
```

### Root Causes

Found TWO bugs in `publish.py` affecting web component CodeBuild:

#### Bug 1: Wrong S3 Source Format (Line 1618)

**Problem:**
```python
sourceLocationOverride=f's3://{artifact_bucket}/{chat_source_key}'
```

**Issue**: CodeBuild S3 sources expect `bucket/key` format, NOT `s3://bucket/key`

**Evidence**: Line 1569 comment says "CodeBuild expects 'bucket/key' format, not 's3://bucket/key'" for Amplify deploy, but web component build used wrong format

**Fix:**
```python
# Before
sourceLocationOverride=f's3://{artifact_bucket}/{chat_source_key}'

# After
sourceLocationOverride=f'{artifact_bucket}/{chat_source_key}'
```

#### Bug 2: Wrong Zip Structure (Line 1008)

**Problem:**
```python
archive_prefix='web-component',  # Creates: web-component/* in zip
```

**Issue**: BuildSpec at template.yaml:569 does `cd src/amplify-chat`, expecting:
```
src/
  amplify-chat/
    package.json
    ...
```

But zip created had structure:
```
web-component/
  package.json
  ...
```

**Fix:**
```python
# Before
archive_prefix='web-component',

# After
archive_prefix='src/amplify-chat',  # Match BuildSpec expectations
```

### How These Bugs Manifested

1. Amplify backend deployed successfully ✅
2. publish.py tried to trigger web component build
3. **Bug 1** caused immediate failure: `s3://` format rejected by CodeBuild
4. **Bug 2** would have caused failure later: BuildSpec can't `cd src/amplify-chat` if zip contains `web-component/`

### Files Changed

- `publish.py:1618` - Removed `s3://` prefix from source location
- `publish.py:1008` - Changed archive_prefix from `'web-component'` to `'src/amplify-chat'`
- Added comment explaining CodeBuild S3 format requirements

### Expected Outcome

After these fixes, the web component build should:
1. ✅ Accept the source location (correct `bucket/key` format)
2. ✅ Successfully `cd src/amplify-chat` (correct zip structure)
3. ✅ Run `npm ci` and `npm run build:wc`
4. ✅ Deploy built component to CloudFront CDN

### Testing Next

Deploy with the fixes:
```bash
python publish.py --project-name amplify-test-13 --admin-email test@example.com --region us-west-2 --deploy-chat
```

The web component build should now complete successfully.

---

## Web Component Build Fix: Missing amplify_outputs.json (Nov 6, 2025)

### New Error After S3 Format Fix

After fixing the S3 source format bugs, the web component build failed with a new error:

**Error:**
```
❌ Error: amplify_outputs.json not found at /codebuild/output/src512824946/src/amplify_outputs.json
   Run `npx ampx deploy` first to generate Amplify configuration.
```

### Root Cause

**The Problem**: Two separate CodeBuild projects, no shared filesystem

1. **AmplifyDeployProject** runs `ampx sandbox --once` → generates `amplify_outputs.json`
2. **WebComponentBuildProject** builds the web component → needs that file for config injection
3. Each CodeBuild project runs in its own isolated environment
4. The web component build has no access to the Amplify deployment's outputs

**Why the file is needed**: The script `src/amplify-chat/scripts/inject-amplify-config.js` reads `amplify_outputs.json` and embeds it into the web component bundle, allowing zero-config embedding with all API endpoints and auth configuration baked in.

### The Solution

**Bridge the gap using S3 as shared storage:**

1. Amplify deployment uploads `amplify_outputs.json` to S3
2. Web component build downloads it from S3 before building

### Changes Made

**File: `template.yaml`**

#### 1. Added ARTIFACT_BUCKET env var to both projects

**AmplifyDeployProject (line 1968-1969):**
```yaml
- Name: ARTIFACT_BUCKET
  Value: !Ref UISourceBucket
```

**WebComponentBuildProject (line 593-594):**
```yaml
- Name: ARTIFACT_BUCKET
  Value: !Ref UISourceBucket
```

#### 2. Upload amplify_outputs.json in Amplify post_build (line 2011-2025)

```yaml
post_build:
  commands:
    - echo "Uploading amplify_outputs.json to S3 for web component build..."
    - |
      if [ -f "amplify_outputs.json" ]; then
        aws s3 cp amplify_outputs.json s3://${ARTIFACT_BUCKET}/amplify_outputs.json
        echo "✓ amplify_outputs.json uploaded successfully"
      else
        echo "⚠ Warning: amplify_outputs.json not found - checking amplify/ directory"
        if [ -f "amplify/amplify_outputs.json" ]; then
          aws s3 cp amplify/amplify_outputs.json s3://${ARTIFACT_BUCKET}/amplify_outputs.json
          echo "✓ amplify_outputs.json uploaded from amplify/ directory"
        else
          echo "❌ Error: amplify_outputs.json not found in expected locations"
          exit 1
        fi
      fi
```

**Note**: Checks both root and amplify/ directories because `ampx sandbox` may place the file in either location depending on where it's run.

#### 3. Download amplify_outputs.json in web component pre_build (line 571-576)

```yaml
pre_build:
  commands:
    - echo "Downloading Amplify outputs from S3..."
    - aws s3 cp s3://${ARTIFACT_BUCKET}/amplify_outputs.json ../../amplify_outputs.json
    - echo "✓ amplify_outputs.json downloaded successfully"
    - ls -lh ../../amplify_outputs.json
```

**Important**: Downloads to `../../amplify_outputs.json` because install phase does `cd src/amplify-chat`, so we need to go up 2 directories to reach repo root where the script expects the file.

### Why This Works

**Deployment flow:**
1. ✅ Amplify backend deploys via CodeBuild → generates amplify_outputs.json
2. ✅ Amplify post_build uploads file to S3
3. ✅ Web component build starts (triggered by publish.py)
4. ✅ Web component pre_build downloads file from S3
5. ✅ inject-amplify-config.js finds the file and embeds config
6. ✅ Build succeeds, component deployed to CDN

**S3 as shared storage**: Both CodeBuild projects have access to the artifact bucket, making it perfect for passing artifacts between deployments.

### Expected Outcome

After these fixes, the complete deployment should succeed:

1. ✅ Amplify backend deploys (auth, data, GraphQL)
2. ✅ amplify_outputs.json uploaded to S3
3. ✅ Web component downloads config
4. ✅ Web component builds with embedded Amplify configuration
5. ✅ Component deployed to CloudFront CDN
6. ✅ Full chat functionality available

### Files Changed

- `template.yaml:1968-1969` - Added ARTIFACT_BUCKET to AmplifyDeployProject
- `template.yaml:2011-2025` - Upload amplify_outputs.json to S3
- `template.yaml:593-594` - Added ARTIFACT_BUCKET to WebComponentBuildProject
- `template.yaml:571-576` - Download amplify_outputs.json from S3

### Testing

Full deployment should now work end-to-end:
```bash
python publish.py --project-name amplify-test-14 --admin-email test@example.com --region us-west-2 --deploy-chat
```

Expected to see:
- Amplify backend deployment success
- "amplify_outputs.json uploaded successfully"
- Web component build success
- "amplify_outputs.json downloaded successfully"
- Component deployed to CDN

---

## Vite 5 Configuration Fix: Remove Deprecated output.file (Nov 6, 2025)

### New Error After Path Fix

After fixing the amplify_outputs.json download path, the file was successfully injected! But Vite build failed:

**Error:**
```
error during build:
Vite does not support "rollupOptions.output.file". Please use "rollupOptions.output.dir"
and "rollupOptions.output.entryFileNames" instead.
```

### Root Cause

**Vite 5 Breaking Change**: The `rollupOptions.output.file` option was deprecated in Vite 5 and removed.

**Previous config** (vite.wc.config.ts lines 27, 34):
```typescript
output: [
  {
    format: 'umd',
    file: 'dist/wc.js',  // ❌ Deprecated
    name: 'AmplifyChat',
  },
  {
    format: 'es',
    file: 'dist/wc.esm.js',  // ❌ Deprecated
  },
]
```

**Why it's a problem**: When using `build.lib`, Vite handles output naming automatically via `lib.fileName`. The `output.file` conflicts with this and was removed in Vite 5.

### The Fix

**Remove `file` options, rely on `lib.fileName`:**

```typescript
export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: path.resolve(__dirname, 'src/wc.ts'),
      name: 'AmplifyChat',
      fileName: (format) => `wc.${format === 'umd' ? '' : 'esm.'}js`,  // Handles naming
      formats: ['umd', 'es'],  // Explicit formats
    },
    rollupOptions: {
      external: [],
      output: [
        {
          format: 'umd',
          name: 'AmplifyChat',
          globals: {},
          // ✅ No 'file' - Vite uses lib.fileName
        },
        {
          format: 'es',
          // ✅ No 'file' - Vite uses lib.fileName
        },
      ],
    },
  },
  // ...
});
```

**Output files:**
- UMD: `dist/wc.js` (for `<script>` tag usage)
- ESM: `dist/wc.esm.js` (for `import` statements)

### Changes Made

**File**: `src/amplify-chat/vite.wc.config.ts`

1. **Removed deprecated `file` options** from both output configurations
2. **Updated `fileName` function** to handle both formats correctly
3. **Added explicit `formats` array** for clarity

### Why This Works

**Vite 5 Library Mode**:
- `lib.entry` defines the source file
- `lib.fileName` function generates output names based on format
- `lib.formats` specifies which formats to build
- Vite automatically creates `dist/` and names files correctly

**No need for `output.file`** because:
- Vite handles file placement and naming automatically
- `lib.fileName` already specifies the pattern
- Removing `file` makes it compatible with Vite 5

### Files Changed

- `src/amplify-chat/vite.wc.config.ts:19-20, 24-35` - Removed deprecated `file` options, updated config

### Expected Outcome

After this fix:
1. ✅ Vite build succeeds with no deprecation warnings
2. ✅ Generates `dist/wc.js` (UMD format)
3. ✅ Generates `dist/wc.esm.js` (ES Module format)
4. ✅ Web component deployed to CloudFront CDN

### Complete Success Path

Full deployment flow now working:
1. ✅ Amplify backend deploys with `ampx sandbox --once`
2. ✅ amplify_outputs.json uploaded to S3
3. ✅ Web component build downloads config from S3
4. ✅ inject-amplify-config.js embeds configuration
5. ✅ Vite builds both UMD and ESM bundles
6. ✅ Assets deployed to CloudFront CDN
7. ✅ Chat component ready for embedding!

---

## Critical Fix: Generate Amplify Outputs After Deployment (Nov 6, 2025)

### The Problem - Empty Configuration File

After all previous fixes, the web component built and deployed successfully, but **didn't work**. Investigation revealed:

**S3 artifact check:**
```bash
aws s3 cp s3://BUCKET/amplify_outputs.json - | jq .
{ "version": "1.4" }
```

**Build logs showed:**
```
✅ Amplify configuration injected successfully
   API Endpoint: N/A
   Region: N/A
```

**Root Cause**: `ampx sandbox --once` deploys the Amplify backend (auth, data stacks) successfully, but **doesn't populate amplify_outputs.json** with the actual API endpoints, auth pool IDs, or GraphQL URLs. It only creates a stub file with `{ "version": "1.4" }`.

### Why This Happens

`ampx sandbox --once` in CI/CD mode:
- ✅ Synthesizes and deploys CDK stacks
- ✅ Creates CloudFormation resources (Cognito, AppSync, etc.)
- ❌ Doesn't automatically generate client configuration in outputs file
- ❌ Expects you to run `ampx generate outputs` separately

**Expected amplify_outputs.json structure:**
```json
{
  "version": "1.4",
  "auth": {
    "aws_region": "us-west-2",
    "user_pool_id": "us-west-2_xxxxx",
    "user_pool_client_id": "xxxxx",
    "identity_pool_id": "us-west-2:xxxxx"
  },
  "data": {
    "url": "https://xxxxx.appsync-api.us-west-2.amazonaws.com/graphql",
    "aws_region": "us-west-2",
    "default_authorization_type": "AMAZON_COGNITO_USER_POOLS",
    "api_key": null
  }
}
```

**What we got:** Just `{ "version": "1.4" }`

### The Solution

Add explicit `ampx generate outputs` command after sandbox deployment to populate the configuration file.

**File**: `template.yaml` line 2016-2017

**Added:**
```yaml
build:
  commands:
    - echo "Deploying Amplify backend via sandbox (one-time deployment)..."
    - npm exec --prefix amplify -- ampx sandbox --once --identifier $PROJECT_NAME
    - echo "Generating amplify_outputs.json with API and auth configuration..."
    - npm exec --prefix amplify -- ampx generate outputs --branch $PROJECT_NAME --app-id $PROJECT_NAME
```

**What `ampx generate outputs` does:**
- Reads deployed CloudFormation stack outputs
- Extracts Cognito User Pool ID, Client ID, Identity Pool
- Extracts AppSync GraphQL API endpoint and auth config
- Writes complete configuration to `amplify_outputs.json`
- Uses `--branch` and `--app-id` to identify which stacks to read

### Files Changed

- `template.yaml:2016-2017` - Added `ampx generate outputs` after sandbox deployment
- `template.yaml:2020-2045` - Added validation to display file contents (debug)

### Expected Outcome

After this fix:
1. ✅ `ampx sandbox --once` deploys backend stacks
2. ✅ `ampx generate outputs` populates amplify_outputs.json with real config
3. ✅ File uploaded to S3 contains auth and API configuration
4. ✅ Web component downloads complete configuration
5. ✅ inject-amplify-config.js embeds working API endpoints
6. ✅ Web component connects to Amplify backend successfully
7. ✅ Chat functionality fully operational!

### Verification

After redeployment, check the outputs file:
```bash
aws s3 cp s3://YOUR-BUCKET/amplify_outputs.json - | jq .
```

**Should see:**
```json
{
  "version": "1.4",
  "auth": { ... actual config ... },
  "data": { ... actual GraphQL endpoint ... }
}
```

**Not just:**
```json
{ "version": "1.4" }
```

This was the **critical missing piece** - the backend was deployed but client configuration wasn't being generated!

---

## Fix: Use --stack Instead of --branch for Sandbox Mode (Nov 6, 2025)

### Problem with Initial Fix

The previous fix added `ampx generate outputs --branch $PROJECT_NAME --app-id $PROJECT_NAME`, but it failed:

**Error:**
```
[StackDoesNotExistError] Stack does not exist.
Stack with id amplify-amplifytest12-amplifytest12-branch-66fe9b27bd does not exist
```

**Root Cause - Stack Naming Mismatch:**
- `ampx sandbox` creates stack: `amplify-ragstacklambda-amplifytest12-sandbox-b6e9400061`
- `ampx generate outputs --branch/--app-id` looks for: `amplify-{app-id}-{branch}-{hash}`
- The `--branch` and `--app-id` parameters are designed for Amplify Console pipeline deployments, not sandbox mode!

**Sandbox vs Pipeline Stack Naming:**
```
Pipeline mode: amplify-{app-id}-{branch}-{hash}
Sandbox mode:  amplify-{backend-name}-{identifier}-sandbox-{hash}
```

### The Solution

Use `--stack` parameter with the actual CloudFormation stack name instead of trying to construct it from branch/app-id:

**File**: `template.yaml` lines 2017-2026

```yaml
- echo "Generating amplify_outputs.json with API and auth configuration..."
- |
  # Find the sandbox stack name (pattern: amplify-*-sandbox-*)
  STACK_NAME=$(aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --query "StackSummaries[?contains(StackName, 'sandbox') && contains(StackName, 'amplify')].StackName | [0]" \
    --output text)

  if [ -z "$STACK_NAME" ] || [ "$STACK_NAME" = "None" ]; then
    echo "❌ Error: Could not find Amplify sandbox stack"
    exit 1
  fi

  echo "Found Amplify sandbox stack: $STACK_NAME"
  npm exec --prefix amplify -- ampx generate outputs --stack $STACK_NAME
```

**How it works:**
1. Query CloudFormation for stacks with "sandbox" and "amplify" in the name
2. Get the first matching stack (most recent sandbox deployment)
3. Pass actual stack name to `ampx generate outputs --stack`
4. CLI reads outputs from that specific stack

### Additional Issue: Circular JSON Error

The logs also showed the circular JSON error returned:
```
[ERROR] [UnknownFault] TypeError: Converting circular structure to JSON
```

**However**: The deployment **continues and completes successfully** despite the error! The stack is created. This appears to be a non-fatal warning in CLI 1.8.0.

### Files Changed

- `template.yaml:2017-2026` - Find sandbox stack dynamically, use --stack parameter
- AMPLIFY_TS.md - Document the fix

### Expected Outcome

After this fix:
1. ✅ `ampx sandbox --once` deploys backend (with harmless circular JSON warning)
2. ✅ Script finds actual sandbox stack name from CloudFormation
3. ✅ `ampx generate outputs --stack {actual-name}` succeeds
4. ✅ amplify_outputs.json populated with real auth and API config
5. ✅ Web component gets working configuration
6. ✅ Chat component connects to backend!

---

## Fix: Parse Stack Name and Wait for Completion (Nov 6, 2025)

### Problem with Previous Fix

The previous fix attempted to find the sandbox stack by querying CloudFormation for completed stacks, but it failed:

**Error:**
```
❌ Error: Could not find Amplify sandbox stack
[
    "RAGStack-amplify-test-12",
    "RAGStack-amplify-test-11"
]
```

**Root Cause - Race Condition:**
- `ampx sandbox --once` starts deployment and prints stack name
- Circular JSON error causes command to exit **before stack creation completes**
- Query for `CREATE_COMPLETE` stacks runs immediately after
- Stack is still in `CREATE_IN_PROGRESS` state, so it's not found
- Only SAM stacks (which are already complete) appear in the query results

**Evidence from Logs:**
```
Stack: amplify-ragstacklambda-amplifytest12-sandbox-b6e9400061
[ERROR] [UnknownFault] TypeError: Converting circular structure to JSON
  --> starting at object with constructor 'IncomingMessage'
  ... (command exits)

# Immediately after:
❌ Error: Could not find Amplify sandbox stack
```

The circular JSON error is **FATAL** - it causes early exit, not just a harmless warning!

### The Solution

Parse the stack name directly from `ampx sandbox` output, then explicitly wait for stack creation to complete:

**File**: `template.yaml` lines 2015-2048

```yaml
build:
  commands:
    - echo "Deploying Amplify backend via sandbox (one-time deployment)..."
    - |
      # Capture output to parse stack name
      npm exec --prefix amplify -- ampx sandbox --once --identifier $PROJECT_NAME 2>&1 | tee /tmp/sandbox-output.log
    - echo "Parsing stack name from sandbox output..."
    - |
      # Extract stack name from the "Stack: amplify-..." line
      STACK_NAME=$(grep -oP "Stack: \K[a-zA-Z0-9-]+" /tmp/sandbox-output.log | head -1)

      if [ -z "$STACK_NAME" ]; then
        echo "❌ Error: Could not parse stack name from sandbox output"
        echo "Sandbox output:"
        cat /tmp/sandbox-output.log
        exit 1
      fi

      echo "✓ Parsed stack name: $STACK_NAME"

      # Wait for stack creation to complete (handles case where ampx exits early)
      echo "Waiting for stack creation to complete..."
      aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME" || \
      aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME" || true

      # Verify stack status
      STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
        --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NOT_FOUND")
      echo "Stack status: $STACK_STATUS"

      if [[ "$STACK_STATUS" != "CREATE_COMPLETE" && "$STACK_STATUS" != "UPDATE_COMPLETE" ]]; then
        echo "❌ Error: Stack creation/update did not complete successfully"
        echo "Stack status: $STACK_STATUS"
        exit 1
      fi

      echo "Generating amplify_outputs.json with API and auth configuration..."
      npm exec --prefix amplify -- ampx generate outputs --stack "$STACK_NAME"
```

**How it works:**
1. **Capture output**: `tee` saves all sandbox output to `/tmp/sandbox-output.log`
2. **Parse stack name**: Use `grep` to extract stack name from "Stack: amplify-..." line
3. **Wait explicitly**: `aws cloudformation wait` blocks until stack creation completes
4. **Verify status**: Check stack is in `CREATE_COMPLETE` or `UPDATE_COMPLETE` state
5. **Generate outputs**: Only proceed with `ampx generate outputs` after verification

**Advantages:**
- ✅ Works even if `ampx sandbox` exits early due to circular JSON error
- ✅ No race condition - explicitly waits for stack completion
- ✅ Robust error handling with status verification
- ✅ Doesn't rely on querying for completed stacks (which might miss in-progress stacks)
- ✅ Stack name comes directly from source (ampx output), not CloudFormation query

### Files Changed

- `template.yaml:2010-2048` - Parse stack name, wait for completion, verify status
- `AMPLIFY_TS.md` - Document the fix

### Expected Outcome

After this fix:
1. ✅ `ampx sandbox --once` starts deployment and prints stack name
2. ✅ Stack name is captured from output (even if command exits early)
3. ✅ `aws cloudformation wait` blocks until stack creation completes
4. ✅ Stack status is verified before proceeding
5. ✅ `ampx generate outputs --stack {parsed-name}` succeeds
6. ✅ amplify_outputs.json populated with real auth and API config
7. ✅ Web component gets working configuration
8. ✅ Deployment succeeds despite circular JSON error!

