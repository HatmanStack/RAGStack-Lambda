#!/bin/bash
#
# Verify web component build status and S3 contents
#

echo "Checking Web Component Build Status"
echo "===================================="
echo ""

# Get project details from check-web-component.sh
BUCKET=$(bash check-web-component.sh 2>/dev/null | grep "S3 Assets Bucket:" | awk '{print $4}')
DISTRIBUTION=$(bash check-web-component.sh 2>/dev/null | grep "CloudFront Distribution ID:" | awk '{print $4}')

if [ -z "$BUCKET" ]; then
    echo "❌ Could not find S3 bucket"
    exit 1
fi

echo "S3 Bucket: $BUCKET"
echo "Distribution: $DISTRIBUTION"
echo ""

# Check files in S3
echo "Files in S3:"
echo "-------------"
aws s3 ls "s3://$BUCKET/" --human-readable || echo "❌ Failed to list S3 bucket"

echo ""
echo "File Details:"
echo "-------------"
aws s3api head-object --bucket "$BUCKET" --key "amplify-chat.js" --query '{Size:ContentLength,LastModified:LastModified,ContentType:ContentType}' --output table 2>/dev/null || echo "❌ amplify-chat.js not found in S3"

echo ""
echo "Recent CodeBuild Runs:"
echo "---------------------"
BUILD_PROJECT=$(aws codebuild list-projects --query "projects[?contains(@, 'wc-build')]" --output text | head -1)

if [ -n "$BUILD_PROJECT" ]; then
    echo "Build Project: $BUILD_PROJECT"
    echo ""
    aws codebuild list-builds-for-project --project-name "$BUILD_PROJECT" --max-items 5 --query 'ids' --output table
else
    echo "❌ Could not find web component build project"
fi

echo ""
echo "To check latest build details:"
echo "  bash check-amplify-build.sh"
echo ""
echo "To invalidate CloudFront cache:"
echo "  bash fix-cdn-cache.sh"
