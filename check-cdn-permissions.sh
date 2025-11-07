#!/bin/bash
#
# Check CloudFront and S3 Permissions
#
# This script checks if the web component file exists in S3 and if CloudFront has access.
#

set -e

echo "🔍 Checking CloudFront and S3 Configuration"
echo "==========================================="
echo ""

# Get stack outputs
STACK_NAME="${1:-cdk-test-1}"
REGION="${2:-us-east-1}"

echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo ""

# Get CloudFront distribution ID
echo "1️⃣ Getting CloudFront distribution..."
DIST_ID=$(aws cloudformation describe-stacks \
    --stack-name "RAGStack-${STACK_NAME}" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`WebComponentCDNUrl`].OutputValue' \
    --output text 2>/dev/null | grep -oP 'https://\K[^/]+' | head -1 || echo "")

if [ -z "$DIST_ID" ]; then
    echo "   ⚠️ Could not find WebComponentCDNUrl in stack outputs"
    echo "   Trying to get distribution ID directly..."
    DIST_ID=$(aws cloudformation describe-stacks \
        --stack-name "RAGStack-${STACK_NAME}" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`WebComponentDistributionId`].OutputValue' \
        --output text 2>/dev/null || echo "")
fi

echo "   Distribution: $DIST_ID"

# Get S3 bucket name
echo ""
echo "2️⃣ Getting S3 bucket..."
BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "RAGStack-${STACK_NAME}" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`WebComponentAssetsBucket`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -z "$BUCKET" ]; then
    echo "   ⚠️ Could not find WebComponentAssetsBucket in stack outputs"
    echo "   Trying alternative name..."
    BUCKET=$(aws s3 ls | grep -i "wc-assets" | awk '{print $3}' | head -1 || echo "")
fi

echo "   Bucket: $BUCKET"

# Check if file exists in S3
echo ""
echo "3️⃣ Checking S3 bucket contents..."
if [ -n "$BUCKET" ]; then
    echo "   Files in bucket:"
    aws s3 ls "s3://$BUCKET/" --region "$REGION" 2>/dev/null || echo "   ⚠️ Cannot access bucket"

    if aws s3 ls "s3://$BUCKET/amplify-chat.js" --region "$REGION" 2>/dev/null; then
        echo "   ✓ amplify-chat.js exists in S3"
        SIZE=$(aws s3 ls "s3://$BUCKET/amplify-chat.js" --region "$REGION" | awk '{print $3}')
        echo "   Size: $SIZE bytes"
    else
        echo "   ✗ amplify-chat.js NOT found in S3!"
    fi
else
    echo "   ⚠️ Bucket name not found"
fi

# Check CloudFront configuration
echo ""
echo "4️⃣ Checking CloudFront configuration..."
if [ -n "$DIST_ID" ] && [[ "$DIST_ID" =~ ^[A-Z0-9]+ ]]; then
    DIST_CONFIG=$(aws cloudfront get-distribution --id "$DIST_ID" --query 'Distribution' 2>/dev/null || echo "")

    if [ -n "$DIST_CONFIG" ]; then
        echo "   ✓ Distribution found"
        STATUS=$(echo "$DIST_CONFIG" | jq -r '.Status')
        echo "   Status: $STATUS"

        ORIGIN=$(echo "$DIST_CONFIG" | jq -r '.DistributionConfig.Origins.Items[0].DomainName')
        echo "   Origin: $ORIGIN"

        OAI=$(echo "$DIST_CONFIG" | jq -r '.DistributionConfig.Origins.Items[0].S3OriginConfig.OriginAccessIdentity')
        echo "   OAI: $OAI"
    else
        echo "   ✗ Could not get distribution config"
    fi
else
    echo "   ⚠️ Invalid or missing distribution ID"
fi

# Check S3 bucket policy
echo ""
echo "5️⃣ Checking S3 bucket policy..."
if [ -n "$BUCKET" ]; then
    POLICY=$(aws s3api get-bucket-policy --bucket "$BUCKET" --region "$REGION" --query 'Policy' --output text 2>/dev/null || echo "")

    if [ -n "$POLICY" ]; then
        echo "   ✓ Bucket policy exists"
        if echo "$POLICY" | jq -r '.Statement[].Principal.CanonicalUser' | grep -q "^[0-9a-f]"; then
            echo "   ✓ Policy grants access to CanonicalUser (CloudFront OAI)"
        else
            echo "   ⚠️ Policy may not include CloudFront OAI"
        fi
    else
        echo "   ⚠️ No bucket policy found"
    fi
else
    echo "   ⚠️ Bucket name not known"
fi

echo ""
echo "==========================================="
echo ""
echo "💡 Next steps:"
echo "   - If file is missing: Check CodeBuild project build status"
echo "   - If OAI not configured: Check template.yaml WebComponentBucketPolicy"
echo "   - If distribution is 'InProgress': Wait for CloudFront deployment"
echo ""
