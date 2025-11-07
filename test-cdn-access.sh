#!/bin/bash
#
# Test if CloudFront CDN is accessible
#

CDN_URL="https://d2m6vpu87luaxh.cloudfront.net/amplify-chat.js"

echo "Testing CloudFront CDN access..."
echo "URL: $CDN_URL"
echo ""

# Test with curl
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$CDN_URL")

if [ "$RESPONSE" = "200" ]; then
    echo "✅ SUCCESS: CDN is accessible (HTTP $RESPONSE)"
    echo ""
    echo "File size:"
    curl -s -I "$CDN_URL" | grep -i content-length
elif [ "$RESPONSE" = "403" ]; then
    echo "❌ BLOCKED: Getting HTTP 403 Forbidden"
    echo ""
    echo "This means the S3 bucket policy hasn't been updated yet."
    echo "You need to redeploy to apply the fix:"
    echo ""
    echo "  python publish.py \\"
    echo "    --project-name amplify-test-13 \\"
    echo "    --admin-email your@email.com \\"
    echo "    --region us-west-2 \\"
    echo "    --skip-ui"
else
    echo "❌ ERROR: Got HTTP $RESPONSE"
fi

echo ""
echo "Full headers:"
curl -s -I "$CDN_URL"
