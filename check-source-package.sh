#!/bin/bash
#
# Check what source was actually packaged and uploaded for the web component build
#

STACK_NAME="${1:-RAGStack-cdk-test-1}"

echo "🔍 Checking Web Component Source Package"
echo "=========================================="
echo ""

# Get artifact bucket and key
echo "1️⃣ Finding source package..."
ARTIFACT_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" \
  --output text 2>/dev/null)

# If not found via output, try to find by pattern
if [ -z "$ARTIFACT_BUCKET" ] || [ "$ARTIFACT_BUCKET" = "None" ]; then
  echo "   ⚠️ ArtifactBucketName output not found, trying alternate method..."
  PROJECT_NAME=$(echo "$STACK_NAME" | sed 's/RAGStack-//')
  ARTIFACT_BUCKET=$(aws s3 ls | grep -E "${PROJECT_NAME}.*artifacts" | awk '{print $3}' | head -1)
fi

if [ -z "$ARTIFACT_BUCKET" ]; then
  echo "   ❌ Could not find artifact bucket"
  echo "   Tried:"
  echo "     - CloudFormation output: ArtifactBucketName"
  echo "     - S3 bucket pattern: ${PROJECT_NAME}.*artifacts"
  echo ""
  echo "   Available S3 buckets:"
  aws s3 ls | grep -i "${PROJECT_NAME:-cdk-test}" | head -10
  exit 1
fi

echo "   Artifact Bucket: $ARTIFACT_BUCKET"

# List UI source files
echo ""
echo "2️⃣ Listing source packages in S3..."
aws s3 ls "s3://$ARTIFACT_BUCKET/" | grep -E "ui-source|web-component-source" | tail -5

# Download and inspect the latest package
echo ""
echo "3️⃣ Downloading latest web component source package..."
# Look for web-component-source
LATEST_SOURCE=$(aws s3 ls "s3://$ARTIFACT_BUCKET/" | grep "web-component-source" | sort | tail -1 | awk '{print $4}')

if [ -z "$LATEST_SOURCE" ]; then
  echo "   ❌ No web-component-source found!"
  echo "   This means the web component source was never packaged."
  exit 1
fi

echo "   Latest: $LATEST_SOURCE"
aws s3 cp "s3://$ARTIFACT_BUCKET/$LATEST_SOURCE" /tmp/amplify-chat-source.zip

# Extract and check vite config
echo ""
echo "4️⃣ Extracting and checking vite.wc.config.ts..."
unzip -q /tmp/amplify-chat-source.zip -d /tmp/amplify-chat-extracted

if [ -f /tmp/amplify-chat-extracted/src/amplify-chat/vite.wc.config.ts ]; then
  echo "   ✅ vite.wc.config.ts found in package"
  echo ""
  echo "   Checking format configuration..."
  grep -A 2 "formats:" /tmp/amplify-chat-extracted/src/amplify-chat/vite.wc.config.ts
else
  echo "   ❌ vite.wc.config.ts NOT found in package!"
fi

# Cleanup
rm -rf /tmp/amplify-chat-source.zip /tmp/amplify-chat-extracted

echo ""
echo "=========================================="
echo ""
echo "If the package shows ['umd', 'es'], then the source was packaged"
echo "before the IIFE change was committed."
echo ""
echo "If it shows ['iife', 'es'], then the build should produce IIFE"
echo "but something is wrong with the CodeBuild execution."
echo ""
