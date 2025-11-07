#!/bin/bash
#
# Verify web component build status and S3 contents
#

echo "Checking Web Component Build Status"
echo "===================================="
echo ""

# Try to find bucket and distribution from CloudFormation stack
PROJECT_NAME="${PROJECT_NAME:-amplify-test-13}"
STACK_NAME="RAGStack-${PROJECT_NAME}"

echo "Looking for stack: $STACK_NAME"
echo ""

# Get bucket name from CloudFormation
BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='WebComponentBucket'].OutputValue" --output text 2>/dev/null)
DISTRIBUTION=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='WebComponentDistribution'].OutputValue" --output text 2>/dev/null)

if [ -z "$BUCKET" ] || [ "$BUCKET" = "None" ]; then
    echo "❌ Could not find S3 bucket from CloudFormation"
    echo "   Trying alternate method..."

    # Try to find bucket by naming pattern
    BUCKET=$(aws s3 ls | grep -E "${PROJECT_NAME}.*wc-assets" | awk '{print $3}' | head -1)
fi

if [ -z "$BUCKET" ]; then
    echo "❌ Could not find S3 bucket"
    echo ""
    echo "Please provide bucket name manually:"
    echo "  BUCKET_NAME=your-bucket-name bash $0"
    exit 1
fi

echo "S3 Bucket: $BUCKET"
echo "Distribution: $DISTRIBUTION"
echo ""

# Check files in S3
echo "Files in S3:"
echo "-------------"
aws s3 ls "s3://$BUCKET/" --human-readable --recursive || echo "❌ Failed to list S3 bucket"

echo ""
echo "amplify-chat.js Details:"
echo "------------------------"
aws s3api head-object --bucket "$BUCKET" --key "amplify-chat.js" 2>/dev/null | jq '{Size: .ContentLength, LastModified: .LastModified, ContentType: .ContentType, ETag: .ETag}' || echo "❌ amplify-chat.js not found in S3"

echo ""
echo "Download first 500 bytes to check format:"
echo "-----------------------------------------"
aws s3 cp "s3://$BUCKET/amplify-chat.js" - 2>/dev/null | head -c 500

echo ""
echo ""
echo "==================================="
echo ""

# Check for UMD vs IIFE pattern
FIRST_LINE=$(aws s3 cp "s3://$BUCKET/amplify-chat.js" - 2>/dev/null | head -c 200)

if echo "$FIRST_LINE" | grep -q "var AmplifyChat=function"; then
    echo "❌ S3 file format: UMD (old)"
    echo "   The IIFE build didn't upload to S3!"
elif echo "$FIRST_LINE" | grep -q "!function()" || echo "$FIRST_LINE" | grep -q "(function()"; then
    echo "✅ S3 file format: IIFE (new)"
else
    echo "⚠️  S3 file format: Unknown"
fi

echo ""
echo "To check build logs:"
echo "  aws codebuild list-builds-for-project --project-name ${PROJECT_NAME}-wc-build-* --max-items 1"
