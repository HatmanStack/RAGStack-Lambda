#!/bin/bash
# Check amplify_outputs.json in S3 artifact bucket

STACK_NAME="${1:-RAGStack-cdk-test-1}"

# Get artifact bucket name
ARTIFACT_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='UISourceBucketName'].OutputValue" \
  --output text 2>/dev/null)

if [ -z "$ARTIFACT_BUCKET" ] || [ "$ARTIFACT_BUCKET" = "None" ]; then
  echo "❌ Could not find artifact bucket"
  exit 1
fi

echo "Artifact Bucket: $ARTIFACT_BUCKET"
echo ""
echo "Contents of amplify_outputs.json:"
echo "================================="
aws s3 cp s3://$ARTIFACT_BUCKET/amplify_outputs.json - 2>/dev/null | jq . || echo "❌ File not found or invalid JSON"
