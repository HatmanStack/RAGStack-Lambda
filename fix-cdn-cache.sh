#!/bin/bash
#
# Fix CloudFront cache by creating invalidation
#

DISTRIBUTION_ID="E1LNC5FLHXX6VF"

echo "Creating CloudFront invalidation for web component..."
echo "Distribution ID: $DISTRIBUTION_ID"
echo ""

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

# Create invalidation
echo "Invalidating /amplify-chat.js and /amplify-chat.esm.js..."
aws cloudfront create-invalidation \
    --distribution-id "$DISTRIBUTION_ID" \
    --paths "/amplify-chat.js" "/amplify-chat.esm.js"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Invalidation created successfully!"
    echo ""
    echo "CloudFront will fetch fresh files from S3 within 1-2 minutes."
    echo ""
    echo "To verify, run: bash check-cdn-version.sh"
else
    echo ""
    echo "❌ Invalidation failed. Check your AWS credentials and permissions."
    exit 1
fi
