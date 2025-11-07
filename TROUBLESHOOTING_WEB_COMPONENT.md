# Web Component Registration Issue - Troubleshooting Report

**Date:** 2025-11-06
**Branch:** `claude/amplify-ts-documentation-011CUqVzG1sGFFSTKHhvBrV5`
**Status:** Web component builds and deploys but fails to register custom element

---

## Executive Summary

Successfully deployed entire RAGStack infrastructure including:
- ✅ SAM stack with Lambda functions, Step Functions, Bedrock Knowledge Base
- ✅ Amplify CDK backend with AppSync GraphQL API and Lambda resolvers
- ✅ Web component builds and uploads to S3
- ✅ CloudFront CDN serves the JavaScript file (HTTP 200)

**Current Issue:** The web component JavaScript file loads successfully but the custom element (`<amplify-chat>`) fails to register, preventing the component from working.

---

## Current Symptoms

When testing with `test-full-diagnostic.html`:

```
1. Console Errors: ❌ Script error. at :0:0
2. Script Load Status: ✓ Script loaded successfully (HTTP 200)
3. Global Scope Check: Found globals: AmplifyChat
4. Custom Element Status: ❌ Custom element NOT registered
5. Network Request: ❌ Fetch failed: Failed to fetch
6. Chat Component: (does not appear)
```

**Key observations:**
- JavaScript file loads (787KB, HTTP 200)
- `window.AmplifyChat` exists (indicates UMD/IIFE bundle loaded)
- "Script error. at :0:0" suggests uncaught exception during execution
- `customElements.get('amplify-chat')` returns `undefined`

---

## Architecture Overview

### Web Component Build Process

1. **Source:** `src/amplify-chat/` (React component + web component wrapper)
2. **Build Config:** `src/amplify-chat/vite.wc.config.ts` (Vite in library mode)
3. **Entry Point:** `src/amplify-chat/src/wc.ts`
4. **Output:** `dist/wc.js` (IIFE format) → deployed as `amplify-chat.js`
5. **Deploy:** CodeBuild project uploads to S3, served via CloudFront

### Build Pipeline

```
publish.py --chat-only
  → Packages src/amplify-chat/ source
  → Uploads to S3 as amplify-chat-source-{timestamp}.zip
  → Triggers WebComponentBuildProject CodeBuild
    → Downloads amplify_outputs.json from S3
    → Runs scripts/inject-amplify-config.js
      → Embeds amplify_outputs.json into amplify-config.generated.ts
    → Runs npm run build:wc
      → Vite builds with vite.wc.config.ts
      → Output: dist/wc.js (IIFE format)
    → Uploads dist/wc.js to S3 as amplify-chat.js
    → Invalidates CloudFront cache
```

### Registration Mechanism

The custom element should register via:

1. **Import side-effect** in `AmplifyChat.wc.ts`:
   ```typescript
   if (!customElements.get('amplify-chat')) {
     customElements.define('amplify-chat', AmplifyChat);
   }
   ```

2. **Fallback registration** in `wc.ts`:
   ```typescript
   if (!customElements.get('amplify-chat')) {
     customElements.define('amplify-chat', AmplifyChat);
   }
   ```

---

## What We've Tried

### 1. Build Format Changes ✅

**Issue:** UMD format doesn't auto-execute side effects
**Fix:** Changed Vite config from UMD to IIFE format

**File:** `src/amplify-chat/vite.wc.config.ts`
```typescript
formats: ['iife', 'es']  // Was: ['umd', 'es']
```

**Commit:** `f3ac6d0`

**Result:** IIFE format confirmed in CloudFront output, but registration still fails

### 2. Lambda Bundling Fixes ✅

**Issue:** TypeScript compilation failing during CDK Lambda bundling
**Fixes Applied:**
- Bundle from parent directory to resolve config.ts imports
- Use explicit TypeScript compiler path
- Add assetHash to bypass CDK caching

**Commits:** `2071415`, `ceb53aa`, `a38f3f5`

**Result:** CDK stack deploys successfully, Lambda functions work

### 3. CDK Permission Fixes ✅

**Issues:** CodeBuild couldn't access CDK bootstrap resources
**Fixes Applied:**
- Custom resource to update CDK assets bucket policy
- Custom resource to grant CDK deploy role iam:PassRole permission
- Added sts:AssumeRole for cdk-* roles

**Commits:** `40884ea`, `fd22372`, `9e7f45e`

**Result:** CDK deployment succeeds

### 4. CloudFront Access Fixes ✅

**Issue:** CloudFront returning 403 Forbidden
**Fix:** Changed S3 public access block settings to allow OAI

**File:** `template.yaml` - `WebComponentAssetsBucket`
```yaml
BlockPublicPolicy: false
RestrictPublicBuckets: false
```

**Commit:** `f822582`

**Result:** CloudFront serves files with HTTP 200

### 5. Import Structure Changes ✅

**Issue:** Module exports not executing side effects
**Fix:** Separate import from export to ensure side effects run

**File:** `src/amplify-chat/src/wc.ts`
```typescript
import { AmplifyChat } from './components/AmplifyChat.wc';
export { AmplifyChat };
```

**Commit:** `a38f3f5`

**Result:** Import executes, but registration still fails

### 6. Error Handling Added ✅

**Issue:** Silent failures make debugging impossible
**Fixes Applied:**
- Try-catch around Amplify.configure()
- Explicit fallback registration
- Console logging for all steps

**File:** `src/amplify-chat/src/wc.ts`
```typescript
try {
  Amplify.configure(AMPLIFY_OUTPUTS);
  console.log('[AmplifyChat] Amplify configured successfully');
} catch (error) {
  console.error('[AmplifyChat] Failed to configure Amplify:', error);
}
```

**Commit:** `1c914e5`

**Result:** Should provide detailed error messages (waiting for rebuild/test)

### 7. CloudFormation Deployment Fixes ✅

**Issue:** Fresh deployments failing with "Invalid project source"
**Fix:** Custom resource creates amplify-placeholder.zip

**Commits:** `31ce612`, `985d180`, `6238429`

**Result:** New deployments succeed

---

## Current Hypothesis

Based on symptoms, the most likely issue is:

### **Amplify.configure() is throwing an uncaught error**

**Evidence:**
- "Script error. at :0:0" indicates exception during execution
- Custom element never registers (code after error doesn't run)
- `window.AmplifyChat` exists (bundle loaded and parsed successfully)

**Possible causes:**

1. **Invalid amplify_outputs.json**
   - Empty or malformed JSON from CDK deployment
   - Missing required fields (auth, data sections)
   - Incorrect API endpoint URLs

2. **Amplify SDK version mismatch**
   - aws-amplify v6 expects specific config format
   - Generated config might be incompatible

3. **Missing dependencies**
   - React or other peer dependencies not bundled
   - Vite library mode might exclude required modules

4. **CORS or CSP issues**
   - Amplify.configure() might try to make network requests
   - Browser security policies blocking initialization

---

## Next Troubleshooting Steps

### Immediate Actions (High Priority)

#### 1. Rebuild Web Component with Error Handling

The latest commit (`1c914e5`) adds comprehensive error logging. Rebuild and test:

```bash
python publish.py \
    --project-name amplify-test-14 \
    --admin-email your@email.com \
    --region us-west-2 \
    --chat-only
```

Then open `test-full-diagnostic.html` with browser console (F12) and look for:
- `[AmplifyChat] Amplify configured successfully` (or error details)
- `[AmplifyChat] Custom element registered successfully` (or error details)
- `[AmplifyChat] AMPLIFY_OUTPUTS: {...}` (shows embedded config)

**Expected outcome:** Console will show exact error message and stack trace

#### 2. Verify amplify_outputs.json Content

Check what was embedded in the build:

```bash
# Download the component and search for AMPLIFY_OUTPUTS
curl -s https://d2m6vpu87luaxh.cloudfront.net/amplify-chat.js | \
  grep -A 50 "AMPLIFY_OUTPUTS.*="
```

**Look for:**
- `data.url` (AppSync GraphQL endpoint)
- `auth.aws_region` (AWS region)
- `auth.user_pool_id` (Cognito User Pool)

**Expected:** Valid JSON with all fields populated

#### 3. Test with Minimal Configuration

Create a test page that manually configures Amplify before loading the component:

```html
<!DOCTYPE html>
<html>
<head><title>Manual Config Test</title></head>
<body>
  <h1>Manual Configuration Test</h1>
  <amplify-chat conversation-id="test"></amplify-chat>

  <script type="module">
    // Import Amplify separately
    import { Amplify } from 'https://cdn.jsdelivr.net/npm/aws-amplify@6/+esm';

    // Configure with known-good config
    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId: 'us-west-2_gjxUX59r5',
          userPoolClientId: '3kj63vlhl9g7ohh78u2l4gfvev'
        }
      },
      API: {
        GraphQL: {
          endpoint: 'https://rli3ite2vrfo7edr5j4mvmb6qu.appsync-api.us-west-2.amazonaws.com/graphql',
          region: 'us-west-2',
          defaultAuthMode: 'lambda'
        }
      }
    });

    console.log('Amplify configured manually');
  </script>

  <!-- Load component (should skip Amplify.configure if already configured) -->
  <script src="https://d2m6vpu87luaxh.cloudfront.net/amplify-chat.js"></script>

  <script>
    setTimeout(() => {
      const registered = customElements.get('amplify-chat');
      console.log('Custom element registered:', !!registered);
    }, 1000);
  </script>
</body>
</html>
```

**Expected outcome:** If this works, it confirms Amplify config is the issue

#### 4. Check Build Output Locally

Build the component locally to see error messages:

```bash
cd src/amplify-chat
npm install

# Create dummy amplify_outputs.json
cat > ../../amplify_outputs.json << EOF
{
  "version": "1.4",
  "auth": {
    "aws_region": "us-west-2",
    "user_pool_id": "us-west-2_gjxUX59r5",
    "user_pool_client_id": "3kj63vlhl9g7ohh78u2l4gfvev"
  },
  "data": {
    "url": "https://rli3ite2vrfo7edr5j4mvmb6qu.appsync-api.us-west-2.amazonaws.com/graphql",
    "aws_region": "us-west-2",
    "default_authorization_type": "AMAZON_COGNITO_USER_POOLS"
  }
}
EOF

# Build
npm run build:wc

# Check output
ls -lh dist/
head -100 dist/wc.js
```

**Expected outcome:** Local build should show any errors during bundling

### Secondary Investigation (Medium Priority)

#### 5. Verify Vite Bundle Output

Check if Vite is actually producing IIFE format:

```bash
cd src/amplify-chat
npm run build:wc

# Check format of output
head -20 dist/wc.js
```

**Look for:**
- IIFE: `(function(){...})()`
- UMD: `var AmplifyChat=function()`

**Expected:** IIFE format with immediate execution

#### 6. Check React Dependency Bundling

Ensure React is bundled (not externalized):

```typescript
// In vite.wc.config.ts, verify:
rollupOptions: {
  external: [],  // Nothing external (should bundle everything)
}
```

Test if React is included:

```bash
curl -s https://d2m6vpu87luaxh.cloudfront.net/amplify-chat.js | \
  grep -c "react.createElement"
```

**Expected:** Should find React code (count > 0)

#### 7. Test Without Amplify

Temporarily remove Amplify.configure() to isolate the issue:

```typescript
// In src/amplify-chat/src/wc.ts
// Comment out:
// Amplify.configure(AMPLIFY_OUTPUTS);

// Keep registration:
if (!customElements.get('amplify-chat')) {
  customElements.define('amplify-chat', AmplifyChat);
}
```

**Expected outcome:** If this registers successfully, confirms Amplify.configure() is the problem

### Long-term Solutions (Low Priority)

#### 8. Migrate to Rollup Plugin

Vite's library mode might have limitations. Consider using Rollup directly:

```bash
npm install --save-dev rollup @rollup/plugin-node-resolve @rollup/plugin-commonjs @rollup/plugin-typescript
```

Create `rollup.config.js` with explicit IIFE output.

#### 9. Split Amplify Config from Bundle

Instead of embedding config, load it dynamically:

```typescript
// Fetch config at runtime
fetch('/amplify_outputs.json')
  .then(r => r.json())
  .then(config => {
    Amplify.configure(config);
    // Register component after config loaded
  });
```

#### 10. Use Web Component Polyfill

Add custom elements polyfill for better compatibility:

```html
<script src="https://unpkg.com/@webcomponents/webcomponentsjs@2/webcomponents-loader.js"></script>
```

---

## Diagnostic Tools Created

All diagnostic tools are in the repository root:

1. **test-full-diagnostic.html** - Comprehensive error capture and logging
2. **test-cache-bust.html** - Tests with cache-busting query params
3. **test-web-component-debug.html** - Shows component structure
4. **check-bundle-format.sh** - Verifies IIFE vs UMD format
5. **check-cdn-version.sh** - Shows cache status and file details
6. **check-wc-build-status.sh** - Verifies S3 contents and build status
7. **fix-cdn-cache.sh** - Invalidates CloudFront cache

---

## Key Files Modified

### Web Component Source
- `src/amplify-chat/vite.wc.config.ts` - Changed to IIFE format
- `src/amplify-chat/src/wc.ts` - Added error handling and explicit registration
- `src/amplify-chat/src/components/AmplifyChat.wc.ts` - Custom element definition

### Infrastructure
- `template.yaml` - Multiple fixes:
  - CloudFront OAI permissions
  - CDK bootstrap role permissions
  - Custom resources for placeholder and permissions
- `amplify/lib/backend-stack.ts` - Lambda bundling fixes
- `amplify/data/functions/package.json` - Added TypeScript dependency

### Deployment
- `publish.py` - Updated comments about placeholder handling

---

## Stack Outputs (Working)

From successful CDK deployment:

```
GraphQLApiEndpoint: https://rli3ite2vrfo7edr5j4mvmb6qu.appsync-api.us-west-2.amazonaws.com/graphql
UserPoolId: us-west-2_gjxUX59r5
UserPoolClientId: 3kj63vlhl9g7ohh78u2l4gfvev
Region: us-west-2
```

CDN URL: `https://d2m6vpu87luaxh.cloudfront.net/amplify-chat.js`

---

## Related Issues

### Issue 1: Cache Invalidation
CloudFront aggressively caches files. After rebuilding, always:
```bash
bash fix-cdn-cache.sh
```

### Issue 2: Browser Cache
Even after CloudFront invalidation, browsers cache JavaScript. Always test with:
- Hard refresh: `Ctrl+Shift+R`
- Incognito/private window
- Or cache-bust test pages

### Issue 3: Build Timing
The `amplify_outputs.json` must exist before web component builds. The build pipeline handles this by:
1. CDK deploys → creates `amplify_outputs.json`
2. Uploads to S3
3. WebComponentBuildProject downloads it
4. Embeds into component

---

## Success Criteria

The web component will be working when:

1. **Custom element registers:**
   ```javascript
   customElements.get('amplify-chat') !== undefined
   ```

2. **No script errors:**
   ```
   Console Errors: ✓ No errors detected
   ```

3. **Component appears:**
   ```html
   <amplify-chat conversation-id="test">
     <!-- Shadow DOM with chat UI -->
   </amplify-chat>
   ```

4. **Can send messages:**
   - Type in input field
   - Click send
   - Receive response from Bedrock via AppSync

---

## Additional Context

### Why This Architecture?

The web component approach allows embedding the chat interface in any web application:

```html
<!-- Just include the script and use the tag -->
<script src="https://d2m6vpu87luaxh.cloudfront.net/amplify-chat.js"></script>
<amplify-chat conversation-id="my-site"></amplify-chat>
```

Zero configuration needed - all API endpoints and auth config are embedded at build time.

### Why IIFE Format?

- **UMD**: Waits for module system, side effects don't run automatically
- **IIFE**: Executes immediately, perfect for script tag inclusion
- **ESM**: Requires `<script type="module">`, not as universally compatible

### Why CDK Instead of Amplify Gen 2?

Original Amplify Gen 2 deployment had circular JSON issues in CodeBuild. Migrated to pure CDK for better control and debugging.

---

## Contact & Resources

- **Branch:** `claude/amplify-ts-documentation-011CUqVzG1sGFFSTKHhvBrV5`
- **Project:** RAGStack-Lambda
- **Commits:** See git log from `f3ac6d0` to `1c914e5`

### Key Commits for This Issue

- `f3ac6d0` - Changed UMD to IIFE format
- `a38f3f5` - Fixed module imports to ensure registration
- `1c914e5` - Added error handling and explicit registration (LATEST)

### Documentation

- `CLAUDE.md` - Project overview and commands
- `docs/AMPLIFY_CHAT.md` - Web component API documentation
- `docs/ARCHITECTURE.md` - System architecture

---

## Final Notes

**Most Promising Next Step:** Rebuild web component with latest error handling (`1c914e5`) and check browser console. The detailed logging should reveal exactly what's failing during Amplify.configure() or custom element registration.

**Estimated Time to Fix:** 1-2 hours once error messages are visible in console.

**Confidence Level:** High - the infrastructure is solid, this is likely a configuration or bundling issue that will be obvious once we see the actual error messages.

---

*Report generated: 2025-11-06*
*Last commit: 1c914e5*
