#!/bin/bash
#
# Check Amplify configuration and S3 artifacts
#

STACK_NAME="${1:-RAGStack-cdk-test-1}"

echo "🔍 Checking Amplify Configuration"
echo "=================================="
echo ""

# Get artifact bucket from CloudFormation
echo "1️⃣ Getting artifact bucket name..."
ARTIFACT_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" \
  --output text 2>/dev/null)

if [ -z "$ARTIFACT_BUCKET" ] || [ "$ARTIFACT_BUCKET" = "None" ]; then
  echo "   ❌ Could not find artifact bucket"
  echo "   This means the stack was deployed without UI (--skip-ui flag used)"
  echo "   or the BuildUI condition is false."
  exit 1
fi

echo "   Artifact Bucket: $ARTIFACT_BUCKET"
echo ""

# Check if amplify_outputs.json exists in S3
echo "2️⃣ Checking for amplify_outputs.json in S3..."
if aws s3 ls "s3://$ARTIFACT_BUCKET/amplify_outputs.json" &>/dev/null; then
  echo "   ✅ amplify_outputs.json EXISTS in S3"
  echo ""
  echo "   Contents:"
  aws s3 cp "s3://$ARTIFACT_BUCKET/amplify_outputs.json" - 2>/dev/null | jq '.' 2>/dev/null || aws s3 cp "s3://$ARTIFACT_BUCKET/amplify_outputs.json" -
else
  echo "   ❌ amplify_outputs.json NOT FOUND in S3"
  echo ""
  echo "   This means AmplifyDeployProject failed to upload the config."
  echo "   Check AmplifyDeployProject logs for errors."
fi

echo ""
echo "3️⃣ Getting CloudFront distribution ID..."
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='WebComponentDistributionId'].OutputValue" \
  --output text 2>/dev/null)

if [ -z "$DISTRIBUTION_ID" ] || [ "$DISTRIBUTION_ID" = "None" ]; then
  echo "   ❌ Could not find distribution ID"
  exit 1
fi

echo "   Distribution ID: $DISTRIBUTION_ID"
echo ""

# Check CloudFront distribution configuration
echo "4️⃣ Checking CloudFront CORS configuration..."
RESPONSE_HEADERS_POLICY=$(aws cloudfront get-distribution-config \
  --id "$DISTRIBUTION_ID" \
  --query "DistributionConfig.DefaultCacheBehavior.ResponseHeadersPolicyId" \
  --output text 2>/dev/null)

if [ -z "$RESPONSE_HEADERS_POLICY" ] || [ "$RESPONSE_HEADERS_POLICY" = "None" ]; then
  echo "   ❌ No ResponseHeadersPolicyId configured!"
  echo "   This is why you're seeing 'Script error. at :0:0'"
  echo ""
  echo "   The WebComponentCORSPolicy needs to be attached to the distribution."
else
  echo "   ✅ ResponseHeadersPolicyId: $RESPONSE_HEADERS_POLICY"
  echo ""
  echo "   Policy details:"
  aws cloudfront get-response-headers-policy --id "$RESPONSE_HEADERS_POLICY" \
    --query "ResponseHeadersPolicy.ResponseHeadersPolicyConfig.CorsConfig" \
    --output json 2>/dev/null | jq '.' 2>/dev/null || echo "   (Use jq to format)"
fi

echo ""
echo "5️⃣ Testing CDN endpoint..."
CDN_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='WebComponentCDNUrl'].OutputValue" \
  --output text 2>/dev/null)

if [ -n "$CDN_URL" ] && [ "$CDN_URL" != "None" ]; then
  echo "   CDN URL: $CDN_URL"
  echo ""
  echo "   Testing for CORS headers..."
  curl -I "$CDN_URL" 2>/dev/null | grep -i "access-control" || echo "   ❌ No CORS headers found"
fi

echo ""
echo "=================================="
echo "Summary:"
echo "- If amplify_outputs.json is missing: Check AmplifyDeployProject logs"
echo "- If CORS headers missing: CloudFront cache may need time to propagate"
echo "- If ResponseHeadersPolicyId is None: CloudFormation template needs update"
