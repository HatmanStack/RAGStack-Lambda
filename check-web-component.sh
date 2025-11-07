#!/bin/bash
# Script to check web component deployment status

# Get stack name from argument or use default
STACK_NAME="${1:-RAGStack-cdk-test-1}"

echo "Checking Web Component Deployment Status"
echo "========================================="
echo ""

# Get CloudFront distribution ID
DIST_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='WebComponentDistributionId'].OutputValue" --output text 2>/dev/null)

if [ -z "$DIST_ID" ] || [ "$DIST_ID" = "None" ]; then
  echo "❌ Could not find CloudFront distribution ID in stack outputs"
  exit 1
fi

echo "✓ CloudFront Distribution ID: $DIST_ID"

# Get S3 bucket name
BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='WebComponentAssetsBucketName'].OutputValue" --output text 2>/dev/null)

if [ -z "$BUCKET" ] || [ "$BUCKET" = "None" ]; then
  echo "❌ Could not find S3 bucket name in stack outputs"
  exit 1
fi

echo "✓ S3 Assets Bucket: $BUCKET"
echo ""

# Check files in S3 bucket
echo "Files in S3 bucket:"
aws s3 ls s3://$BUCKET/ --human-readable --summarize

echo ""
echo "Checking if amplify-chat.js exists:"
if aws s3 ls s3://$BUCKET/amplify-chat.js > /dev/null 2>&1; then
  echo "✓ amplify-chat.js exists in S3"
  aws s3 ls s3://$BUCKET/amplify-chat.js --human-readable
else
  echo "❌ amplify-chat.js NOT FOUND in S3"
  echo ""
  echo "To fix this, run the web component build:"
  echo "  python publish.py --project-name amplify-test-13 --admin-email your@email.com --region us-west-2 --chat-only"
fi

echo ""
echo "CloudFront Distribution Status:"
aws cloudfront get-distribution --id $DIST_ID --query "Distribution.{Status:Status,DomainName:DomainName,Enabled:DistributionConfig.Enabled}" --output table

echo ""
echo "CloudFront CDN URL:"
aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='WebComponentCDNUrl'].OutputValue" --output text
