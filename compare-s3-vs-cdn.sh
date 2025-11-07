#!/bin/bash
#
# Check what's in S3 vs CloudFront
#
# This compares the S3 origin file with what CloudFront is serving
# to determine if the issue is caching or if the build never ran.
#

STACK_NAME="${1:-RAGStack-cdk-test-1}"
CDN_URL="https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js"

echo "🔍 Comparing S3 Origin vs CloudFront CDN"
echo "=========================================="
echo ""

# Get bucket name
echo "1️⃣ Finding S3 bucket..."
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='WebComponentAssetsBucket'].OutputValue" \
  --output text 2>/dev/null)

if [ -z "$BUCKET" ] || [ "$BUCKET" = "None" ]; then
  echo "   ❌ Could not find bucket from CloudFormation"
  echo "   Trying alternate method..."
  BUCKET=$(aws s3 ls | grep -E "cdk-test-1.*wc-assets" | awk '{print $3}' | head -1)
fi

if [ -z "$BUCKET" ]; then
  echo "   ❌ Could not find S3 bucket!"
  exit 1
fi

echo "   ✅ Bucket: $BUCKET"
echo ""

# Check if file exists in S3
echo "2️⃣ Checking S3 file..."
if ! aws s3 ls "s3://$BUCKET/amplify-chat.js" >/dev/null 2>&1; then
  echo "   ❌ amplify-chat.js NOT FOUND in S3!"
  echo "   Web component build never ran or failed"
  exit 1
fi

# Get S3 metadata
S3_SIZE=$(aws s3 ls "s3://$BUCKET/amplify-chat.js" | awk '{print $3}')
S3_DATE=$(aws s3 ls "s3://$BUCKET/amplify-chat.js" | awk '{print $1, $2}')
echo "   ✅ File exists in S3"
echo "   Size: $S3_SIZE bytes"
echo "   Last Modified: $S3_DATE"
echo ""

# Download first 1KB from S3
echo "3️⃣ Checking S3 file format..."
aws s3 cp "s3://$BUCKET/amplify-chat.js" - 2>/dev/null | head -c 1000 > /tmp/s3-bundle.txt
S3_START=$(cat /tmp/s3-bundle.txt)

if echo "$S3_START" | grep -q "var AmplifyChat.*function"; then
    echo "   ❌ S3 Format: UMD (old)"
    S3_FORMAT="UMD"
elif echo "$S3_START" | grep -q "!function()\|^(function()"; then
    echo "   ✅ S3 Format: IIFE (new)"
    S3_FORMAT="IIFE"
else
    echo "   ⚠️ S3 Format: Unknown"
    S3_FORMAT="Unknown"
fi
echo ""

# Download first 1KB from CloudFront
echo "4️⃣ Checking CloudFront cache..."
curl -s -r 0-999 "$CDN_URL" > /tmp/cdn-bundle.txt
CDN_START=$(cat /tmp/cdn-bundle.txt)

if echo "$CDN_START" | grep -q "var AmplifyChat.*function"; then
    echo "   ❌ CDN Format: UMD (old)"
    CDN_FORMAT="UMD"
elif echo "$CDN_START" | grep -q "!function()\|^(function()"; then
    echo "   ✅ CDN Format: IIFE (new)"
    CDN_FORMAT="IIFE"
else
    echo "   ⚠️ CDN Format: Unknown"
    CDN_FORMAT="Unknown"
fi
echo ""

# Compare
echo "5️⃣ Comparison:"
echo "   S3 Origin:  $S3_FORMAT"
echo "   CloudFront: $CDN_FORMAT"
echo ""

if [ "$S3_FORMAT" = "$CDN_FORMAT" ]; then
    echo "   ✅ MATCH - CloudFront is serving current version"
    if [ "$S3_FORMAT" = "UMD" ]; then
        echo ""
        echo "   ⚠️ BUT both are UMD format!"
        echo "   This means the web component build never ran with IIFE config."
        echo ""
        echo "   Solution: Trigger a new build with --chat-only"
    fi
else
    echo "   ❌ MISMATCH - CloudFront is serving stale cached version"
    echo ""
    echo "   Solution: Invalidate CloudFront cache"
fi

echo ""
echo "=========================================="
echo ""

# Show first 10 lines of each
echo "📄 First 10 lines from S3:"
echo "----------------------------"
head -10 /tmp/s3-bundle.txt
echo "----------------------------"
echo ""

echo "📄 First 10 lines from CloudFront:"
echo "----------------------------"
head -10 /tmp/cdn-bundle.txt
echo "----------------------------"
echo ""

# Cleanup
rm -f /tmp/s3-bundle.txt /tmp/cdn-bundle.txt

# Show next steps
if [ "$S3_FORMAT" = "UMD" ]; then
    echo "🔧 Next Steps:"
    echo ""
    echo "   The S3 file is UMD format, meaning the CodeBuild project"
    echo "   needs to rebuild with the new IIFE vite config."
    echo ""
    echo "   Run: python publish.py --project-name cdk-test-1 --admin-email <email> --region <region> --chat-only"
    echo ""
elif [ "$S3_FORMAT" = "IIFE" ] && [ "$CDN_FORMAT" = "UMD" ]; then
    echo "🔧 Next Steps:"
    echo ""
    echo "   S3 has IIFE but CloudFront is serving cached UMD version."
    echo ""
    echo "   Invalidate cache:"
    DIST_ID=$(aws cloudformation describe-stacks \
      --stack-name "$STACK_NAME" \
      --query "Stacks[0].Outputs[?OutputKey=='WebComponentDistributionId'].OutputValue" \
      --output text 2>/dev/null)

    if [ -n "$DIST_ID" ] && [ "$DIST_ID" != "None" ]; then
        echo "   aws cloudfront create-invalidation --distribution-id $DIST_ID --paths '/amplify-chat.js'"
    fi
    echo ""
elif [ "$S3_FORMAT" = "IIFE" ] && [ "$CDN_FORMAT" = "IIFE" ]; then
    echo "✅ Both S3 and CloudFront are IIFE format!"
    echo ""
    echo "   If the component still isn't registering, the issue is elsewhere."
    echo "   Check browser console for Amplify.configure() errors."
    echo ""
fi
