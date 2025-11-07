# Web Component Troubleshooting Guide

## Current Issue: CloudFront 403 Forbidden

Your CloudFront URL (https://d2m6vpu87luaxh.cloudfront.net/amplify-chat.js) is returning a 403 error.

## Root Cause

The 403 error typically means one of these:

1. **Files not uploaded yet** - The CodeBuild project needs to run to build and upload the web component
2. **CloudFront cache issue** - Distribution may be caching an error page
3. **Bucket policy issue** - Origin Access Identity (OAI) permissions problem

## How to Fix

### Step 1: Deploy with the new CDK code

The code was just converted from Amplify Gen 2 to pure CDK. You need to redeploy:

```bash
cd /home/user/RAGStack-Lambda

# Deploy the full stack (includes CDK conversion)
python publish.py \
  --project-name amplify-test-13 \
  --admin-email your@email.com \
  --region us-west-2 \
  --deploy-chat
```

This will:
1. Deploy SAM stack with updated BuildSpec (CDK instead of ampx)
2. Run Amplify CodeBuild project → deploys backend with `cdk deploy`
3. Generate `amplify_outputs.json` from CDK stack outputs
4. Run Web Component CodeBuild project → builds and uploads JS files to S3
5. Invalidate CloudFront cache

### Step 2: Check deployment status

Run the diagnostic script:

```bash
./check-web-component.sh
```

This will show you:
- ✓ CloudFront distribution ID
- ✓ S3 bucket name
- ✓ Files in the bucket
- ✓ Whether amplify-chat.js exists

### Step 3: Monitor CodeBuild

Check if the web component build completed successfully:

```bash
# Get the build project name
BUILD_PROJECT=$(aws cloudformation describe-stacks \
  --stack-name RAGStack-amplify-test-13 \
  --query "Stacks[0].Outputs[?OutputKey=='WebComponentBuildProjectName'].OutputValue" \
  --output text)

echo "Build project: $BUILD_PROJECT"

# Get recent builds
aws codebuild list-builds-for-project --project-name "$BUILD_PROJECT" \
  --max-items 5 \
  --query "ids" \
  --output table

# Get latest build logs
LATEST_BUILD=$(aws codebuild list-builds-for-project --project-name "$BUILD_PROJECT" --max-items 1 --query "ids[0]" --output text)
aws codebuild batch-get-builds --ids "$LATEST_BUILD" --query "builds[0].{Phase:currentPhase,Status:buildStatus}"
```

### Step 4: Test the component

Once the files are uploaded, test with the HTML file I created:

```bash
# Open the test page in a browser
# It will show detailed debugging information
open test-web-component.html

# Or serve it locally
python3 -m http.server 8080
# Then visit: http://localhost:8080/test-web-component.html
```

### Step 5: Invalidate CloudFront if needed

If files are in S3 but CloudFront still returns 403:

```bash
DIST_ID=$(aws cloudformation describe-stacks \
  --stack-name RAGStack-amplify-test-13 \
  --query "Stacks[0].Outputs[?OutputKey=='WebComponentDistributionId'].OutputValue" \
  --output text)

aws cloudfront create-invalidation \
  --distribution-id $DIST_ID \
  --paths "/*"

echo "Invalidation created. Wait 2-3 minutes for CloudFront cache to clear."
```

## Expected Outcome

After successful deployment:

1. ✅ `amplify-chat.js` and `amplify-chat.esm.js` in S3
2. ✅ CloudFront serves files with 200 status
3. ✅ Web component loads in browser
4. ✅ Chat interface renders with Amplify auth
5. ✅ User can query the Knowledge Base

## Common Issues

### Issue: "amplify_outputs.json not found"
**Solution:** Amplify CodeBuild must run before Web Component CodeBuild. Check that Amplify deployment succeeded first.

### Issue: Web component loads but doesn't connect
**Solution:** Check `amplify_outputs.json` contents. It should have `auth` and `data` sections with real endpoints, not just `{"version": "1.4"}`.

### Issue: CORS errors in browser console
**Solution:** AppSync API needs CORS configured. Check the CDK stack's AppSync configuration.

### Issue: CloudFront still returns 403 after files uploaded
**Solution:**
1. Check bucket policy allows CloudFront OAI
2. Run invalidation (see Step 5 above)
3. Wait 2-3 minutes for CDN to update

## Files

- `test-web-component.html` - Test page with debugging
- `check-web-component.sh` - Diagnostic script
- `template.yaml` - CloudFront and S3 configuration
- `amplify/lib/backend-stack.ts` - CDK stack (Cognito + AppSync)
