# Test Files Usage Guide

All test files have been updated with the latest deployment data:
- **CDN URL:** `https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js`
- **Project Name:** `cdk-test-1`
- **Stack Name:** `RAGStack-cdk-test-1`

## Browser Tests

### test-full-diagnostic.html
The most comprehensive test - shows detailed diagnostics and error capture.

**Features:**
- Intercepts all errors and console messages
- Tests script loading
- Checks custom element registration
- Shows global scope inspection
- Displays network request details
- Attempts manual registration if needed

**Usage:**
```bash
# Open in browser
open test-full-diagnostic.html
# OR
firefox test-full-diagnostic.html

# Then open DevTools (F12) to see console logs
```

**What to look for:**
- `[AmplifyChat] Amplify configured successfully`
- `[AmplifyChat] Custom element registered successfully`
- Green checkmarks for all status checks

---

### test-web-component.html
Simple test with debug output panel.

**Usage:**
```bash
open test-web-component.html
```

**Shows:**
- Load status
- Component properties
- Debug logs in panel

---

### test-cache-bust.html
Tests with cache-busting and manual UMD registration fallback.

**Features:**
- Adds timestamp query param to prevent caching
- Detects UMD vs IIFE format
- Attempts manual registration from various export paths

**Usage:**
```bash
open test-cache-bust.html
```

---

### test-web-component-debug.html
Minimal test with comprehensive error logging.

**Usage:**
```bash
open test-web-component-debug.html
```

## Shell Scripts

All scripts now accept command-line arguments for flexibility.

### CDN and Bundle Tests

#### check-cdn-version.sh
Check what's being served from CloudFront.

```bash
./check-cdn-version.sh
```

**Shows:**
- Response headers (cache status, content-length)
- Presence of `customElements.define()`
- Presence of `Amplify.configure()`
- File size
- Cache hit/miss status

---

#### check-bundle-format.sh
Determine if bundle is UMD or IIFE format.

```bash
./check-bundle-format.sh
```

**Output:**
- ✅ IIFE = will auto-register
- ❌ UMD = won't auto-register (old version)

---

#### wait-for-cdn.sh
Poll CDN until it returns HTTP 200 (max 10 minutes).

```bash
./wait-for-cdn.sh
# OR with custom URL
./wait-for-cdn.sh https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js
```

**Use when:**
- Just deployed
- Waiting for CodeBuild to complete
- CloudFront still deploying

---

### AWS Infrastructure Tests

**Note:** These require AWS CLI and appropriate IAM permissions.

#### check-web-component.sh
Check S3 and CloudFront configuration.

```bash
# Use default project name (cdk-test-1)
./check-web-component.sh

# OR specify project
./check-web-component.sh my-project
```

**Shows:**
- CloudFront distribution ID
- S3 bucket name
- Files in bucket
- Distribution status

---

#### check-wc-build-status.sh
Detailed S3 bucket inspection.

```bash
# Use default (cdk-test-1)
./check-wc-build-status.sh

# OR specify project
./check-wc-build-status.sh my-project
```

**Shows:**
- All files in S3
- `amplify-chat.js` metadata
- First 500 bytes of file
- UMD vs IIFE format

---

#### check-amplify-build.sh
Check Amplify CodeBuild project status.

```bash
# Use default
./check-amplify-build.sh

# OR specify stack name
./check-amplify-build.sh RAGStack-my-project
```

**Shows:**
- Latest build status
- Build phases and durations
- Commands to view logs

---

#### check-cdk-stack.sh
Verify CDK backend stack exists.

```bash
# Use default (cdk-test-1)
./check-cdk-stack.sh

# OR specify project
./check-cdk-stack.sh my-project
```

**Shows:**
- Stack status
- Stack outputs (GraphQL endpoint, etc.)
- Creation/update times

---

#### check-amplify-outputs.sh
View amplify_outputs.json from S3.

```bash
# Use default
./check-amplify-outputs.sh

# OR specify stack
./check-amplify-outputs.sh RAGStack-my-project
```

**Shows:**
- Contents of amplify_outputs.json
- Auth configuration
- Data (GraphQL) configuration

---

#### check-cdn-permissions.sh
Diagnose S3 and CloudFront permission issues.

```bash
./check-cdn-permissions.sh cdk-test-1 us-east-1
```

**Checks:**
- CloudFront distribution exists
- S3 bucket contents
- OAI configuration
- Bucket policy

---

#### test-deployment.sh
Quick validation after deployment.

```bash
./test-deployment.sh
```

**Runs 7 tests:**
1. CDN accessibility (HTTP 200?)
2. File size
3. Content-Type
4. Bundle format (IIFE?)
5. Embedded Amplify config
6. customElements.define present?
7. CloudFront cache status

---

## Typical Testing Workflow

### 1. Right After Deployment

```bash
# Wait for CDN to become available
./wait-for-cdn.sh

# Once available, run quick validation
./test-deployment.sh
```

### 2. Check Bundle Format

```bash
# Verify IIFE format
./check-bundle-format.sh

# Should show: ✅ Format: IIFE
```

### 3. Browser Testing

```bash
# Open comprehensive diagnostic test
open test-full-diagnostic.html

# In browser:
# 1. Open DevTools (F12)
# 2. Check Console tab for [AmplifyChat] messages
# 3. Verify all status indicators are green
```

### 4. If Issues Occur

```bash
# Check S3 contents
./check-wc-build-status.sh cdk-test-1

# Check CloudFront cache
./check-cdn-version.sh

# Check build logs
./check-amplify-build.sh RAGStack-cdk-test-1

# Check CDK stack
./check-cdk-stack.sh cdk-test-1
```

## Expected Success Indicators

### Browser Console (test-full-diagnostic.html)
```
✓ Script loaded successfully (no network error)
✓ No errors detected
✓ Custom element IS registered!
Found globals: window.AmplifyChat
```

### Shell Scripts
```bash
# check-bundle-format.sh
✅ Format: IIFE (new - will auto-register!)

# check-cdn-version.sh
✓ Found: customElements.define() call
✓ Found: Amplify.configure() call
File size: ~787 KB
✓ Fresh from origin (new version)
```

### In Page
The `<amplify-chat>` element should render with the chat UI visible.

## Common Issues

### 403 Access Denied
- **Cause:** CodeBuild still running, or CloudFront OAI not configured
- **Fix:** Wait 5-10 minutes, or check `./check-cdn-permissions.sh`

### Custom Element Not Registered
- **Cause:** Bundle is UMD format (old) or Amplify.configure() threw error
- **Fix:** Check `./check-bundle-format.sh` and browser console errors

### Cached Old Version
- **Cause:** CloudFront serving stale version
- **Fix:** Use `test-cache-bust.html` or run invalidation

## Getting Help

1. **Check browser console first** - Most issues show up as JavaScript errors
2. **Run test-deployment.sh** - Quick overview of all checks
3. **Check DEPLOYMENT_STATUS.md** - Comprehensive troubleshooting guide
4. **Review TROUBLESHOOTING_WEB_COMPONENT.md** - Historical context

## Script Reference

| Script | Purpose | Requires AWS CLI |
|--------|---------|------------------|
| `test-full-diagnostic.html` | Comprehensive browser test | No |
| `test-web-component.html` | Simple browser test | No |
| `test-cache-bust.html` | Cache-busted test with UMD fallback | No |
| `test-web-component-debug.html` | Minimal test with error capture | No |
| `check-cdn-version.sh` | Check what CloudFront serves | No |
| `check-bundle-format.sh` | UMD vs IIFE detection | No |
| `wait-for-cdn.sh` | Poll until CDN available | No |
| `test-deployment.sh` | Quick validation suite | No |
| `check-web-component.sh` | S3/CloudFront config | Yes |
| `check-wc-build-status.sh` | S3 bucket inspection | Yes |
| `check-amplify-build.sh` | CodeBuild status | Yes |
| `check-cdk-stack.sh` | CDK stack verification | Yes |
| `check-amplify-outputs.sh` | View amplify_outputs.json | Yes |
| `check-cdn-permissions.sh` | Diagnose permission issues | Yes |

---

**Last updated:** 2025-11-07  
**Deployment:** cdk-test-1  
**CDN URL:** https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js
