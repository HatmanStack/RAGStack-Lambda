#!/bin/bash
#
# Check WebComponentBuildProject status
#

STACK_NAME="${1:-RAGStack-cdk-test-1}"

echo "🔍 Checking Web Component Build Status"
echo "========================================"
echo ""

# Get project name
PROJECT=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='WebComponentBuildProjectName'].OutputValue" \
  --output text 2>/dev/null)

if [ -z "$PROJECT" ] || [ "$PROJECT" = "None" ]; then
  echo "❌ Could not find WebComponentBuildProject"
  exit 1
fi

echo "Project: $PROJECT"
echo ""

# Get latest build
LATEST_BUILD=$(aws codebuild list-builds-for-project \
  --project-name "$PROJECT" \
  --max-items 1 \
  --query "ids[0]" \
  --output text 2>/dev/null)

if [ -z "$LATEST_BUILD" ] || [ "$LATEST_BUILD" = "None" ]; then
  echo "❌ No builds found"
  echo ""
  echo "Run this to trigger a build:"
  echo "  python publish.py --project-name <name> --admin-email <email> --region us-west-2 --chat-only"
  exit 1
fi

echo "Latest Build: $LATEST_BUILD"
echo ""

# Get build details
BUILD_INFO=$(aws codebuild batch-get-builds --ids "$LATEST_BUILD" 2>/dev/null)

STATUS=$(echo "$BUILD_INFO" | jq -r '.builds[0].buildStatus' 2>/dev/null)
PHASE=$(echo "$BUILD_INFO" | jq -r '.builds[0].currentPhase' 2>/dev/null)
START_TIME=$(echo "$BUILD_INFO" | jq -r '.builds[0].startTime' 2>/dev/null)

echo "Status: $STATUS"
echo "Phase: $PHASE"
echo "Start Time: $START_TIME"
echo ""

if [ "$STATUS" = "IN_PROGRESS" ]; then
  echo "⏳ Build is still in progress. Wait for it to complete."
elif [ "$STATUS" = "SUCCEEDED" ]; then
  echo "✅ Build succeeded!"
  echo ""
  echo "Checking if bundle has enhanced logging..."

  if curl -s https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js | grep -q "Bundle loading"; then
    echo "✅ CDN has the new bundle with enhanced logging"
  else
    echo "❌ CDN still has the old bundle"
    echo ""
    echo "CloudFront cache may not have invalidated yet. Wait 2-5 minutes."
    echo "Then hard-refresh browser: Ctrl+Shift+R"
  fi
elif [ "$STATUS" = "FAILED" ]; then
  echo "❌ Build failed!"
fi
