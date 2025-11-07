#!/bin/bash
#
# Check CloudFront CDN version and cache status
#

CDN_URL="https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js"

echo "Checking CloudFront CDN version..."
echo "URL: $CDN_URL"
echo ""

# Get headers with cache info
echo "=== Response Headers ==="
curl -s -I "$CDN_URL" | grep -E "HTTP|content-length|last-modified|etag|x-cache|x-amz-cf-id|age"

echo ""
echo "=== Content Check ==="
echo "Looking for custom element registration code..."

# Check if the file contains the custom element registration
CONTENT=$(curl -s "$CDN_URL")
if echo "$CONTENT" | grep -q "customElements.define.*amplify-chat"; then
    echo "✓ Found: customElements.define() call"
else
    echo "✗ Missing: customElements.define() call"
fi

if echo "$CONTENT" | grep -q "Amplify.configure"; then
    echo "✓ Found: Amplify.configure() call"
else
    echo "✗ Missing: Amplify.configure() call"
fi

# Check file size (should be ~787KB according to your test)
SIZE=$(echo "$CONTENT" | wc -c)
echo ""
echo "File size: $(($SIZE / 1024)) KB"

echo ""
echo "=== Cache Status ==="
X_CACHE=$(curl -s -I "$CDN_URL" | grep -i "x-cache:" | cut -d: -f2 | tr -d ' \r\n')
if [ "$X_CACHE" = "Hit from cloudfront" ]; then
    echo "⚠️  Serving from CloudFront cache (old version may be cached)"
    echo ""
    echo "To invalidate cache, check CloudFront invalidation in deployment logs"
    echo "Or manually invalidate: aws cloudfront create-invalidation --distribution-id E1LNC5FLHXX6VF --paths '/amplify-chat.js'"
elif [ "$X_CACHE" = "Miss from cloudfront" ] || [ "$X_CACHE" = "RefreshHit from cloudfront" ]; then
    echo "✓ Fresh from origin (new version)"
else
    echo "Cache status: $X_CACHE"
fi
