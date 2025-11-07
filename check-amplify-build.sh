#!/bin/bash
# Check Amplify CodeBuild deployment status

STACK_NAME="${1:-RAGStack-cdk-test-1}"

# Get Amplify CodeBuild project name
PROJECT=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='AmplifyDeployProjectName'].OutputValue" \
  --output text 2>/dev/null)

if [ -z "$PROJECT" ] || [ "$PROJECT" = "None" ]; then
  echo "❌ Could not find Amplify CodeBuild project"
  exit 1
fi

echo "Amplify Deploy Project: $PROJECT"
echo ""

# Get latest build
LATEST_BUILD=$(aws codebuild list-builds-for-project \
  --project-name "$PROJECT" \
  --max-items 1 \
  --query "ids[0]" \
  --output text 2>/dev/null)

if [ -z "$LATEST_BUILD" ] || [ "$LATEST_BUILD" = "None" ]; then
  echo "❌ No builds found for project"
  exit 1
fi

echo "Latest Build: $LATEST_BUILD"
echo ""

# Get build status
aws codebuild batch-get-builds \
  --ids "$LATEST_BUILD" \
  --query "builds[0].{Phase:currentPhase,Status:buildStatus,StartTime:startTime,EndTime:endTime}" \
  --output table

echo ""
echo "Build Phases:"
aws codebuild batch-get-builds \
  --ids "$LATEST_BUILD" \
  --query "builds[0].phases[*].{Phase:phaseType,Status:phaseStatus,Duration:durationInSeconds}" \
  --output table

echo ""
echo "To view full logs, use:"
echo "  aws logs tail /aws/codebuild/$PROJECT --follow"
echo ""
echo "Or get the log stream for this build:"
LOG_STREAM=$(aws codebuild batch-get-builds --ids "$LATEST_BUILD" --query "builds[0].logs.streamName" --output text)
if [ -n "$LOG_STREAM" ] && [ "$LOG_STREAM" != "None" ]; then
  echo "  aws logs get-log-events --log-group-name /aws/codebuild/$PROJECT --log-stream-name $LOG_STREAM --limit 100"
fi
