#!/bin/bash
#
# Check CodeBuild logs for web component build
#

STACK_NAME="${1:-RAGStack-cdk-test-1}"
PROJECT_NAME="${2:-cdk-test-1-wc-build-73ttw}"

echo "🔍 Checking CodeBuild Logs for Web Component Build"
echo "=================================================="
echo ""
echo "Stack: $STACK_NAME"
echo "Project: $PROJECT_NAME"
echo ""

# Get the latest build ID
echo "1️⃣ Getting latest build..."
BUILD_ID=$(aws codebuild list-builds-for-project \
  --project-name "$PROJECT_NAME" \
  --sort-order DESCENDING \
  --max-items 1 \
  --query 'ids[0]' \
  --output text 2>/dev/null)

if [ -z "$BUILD_ID" ] || [ "$BUILD_ID" = "None" ]; then
  echo "   ❌ No builds found for project $PROJECT_NAME"
  exit 1
fi

echo "   Latest Build: $BUILD_ID"

# Get build details
echo ""
echo "2️⃣ Getting build status..."
BUILD_STATUS=$(aws codebuild batch-get-builds \
  --ids "$BUILD_ID" \
  --query 'builds[0].buildStatus' \
  --output text 2>/dev/null)

echo "   Status: $BUILD_STATUS"

# Get log stream
echo ""
echo "3️⃣ Getting build logs..."
LOG_GROUP=$(aws codebuild batch-get-builds \
  --ids "$BUILD_ID" \
  --query 'builds[0].logs.groupName' \
  --output text 2>/dev/null)

LOG_STREAM=$(aws codebuild batch-get-builds \
  --ids "$BUILD_ID" \
  --query 'builds[0].logs.streamName' \
  --output text 2>/dev/null)

echo "   Log Group: $LOG_GROUP"
echo "   Log Stream: $LOG_STREAM"

# Get the actual logs
echo ""
echo "4️⃣ Fetching logs (last 100 lines)..."
echo "=================================================="
aws logs get-log-events \
  --log-group-name "$LOG_GROUP" \
  --log-stream-name "$LOG_STREAM" \
  --limit 100 \
  --query 'events[*].message' \
  --output text 2>/dev/null | tail -50

echo "=================================================="
echo ""
echo "To see full logs, visit:"
echo "https://console.aws.amazon.com/codesuite/codebuild/projects/$PROJECT_NAME/build/$BUILD_ID"
echo ""
