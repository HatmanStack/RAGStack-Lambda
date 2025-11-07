#!/bin/bash
#
# Test Web Component Deployment
#
# This script tests the deployed web component to verify it's working correctly.
#

set -e

CDN_URL="https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js"

echo "🧪 Testing Web Component Deployment"
echo "=================================="
echo ""

# Test 1: Check if CDN URL is accessible
echo "1️⃣ Testing CDN accessibility..."
if curl -s -I "$CDN_URL" | grep -q "HTTP/2 200"; then
    echo "   ✓ CDN is accessible (HTTP 200)"
else
    echo "   ✗ CDN returned non-200 response"
    curl -I "$CDN_URL"
    exit 1
fi

# Test 2: Check file size
echo ""
echo "2️⃣ Checking file size..."
FILE_SIZE=$(curl -sI "$CDN_URL" | grep -i content-length | awk '{print $2}' | tr -d '\r')
if [ -n "$FILE_SIZE" ]; then
    SIZE_KB=$((FILE_SIZE / 1024))
    echo "   ✓ File size: ${SIZE_KB}KB (${FILE_SIZE} bytes)"
    if [ "$FILE_SIZE" -lt 10000 ]; then
        echo "   ⚠️ Warning: File seems too small (< 10KB)"
    fi
else
    echo "   ✗ Could not determine file size"
fi

# Test 3: Check if it's JavaScript
echo ""
echo "3️⃣ Checking content type..."
CONTENT_TYPE=$(curl -sI "$CDN_URL" | grep -i content-type | awk '{print $2}' | tr -d '\r')
if echo "$CONTENT_TYPE" | grep -q "javascript"; then
    echo "   ✓ Content-Type: $CONTENT_TYPE"
else
    echo "   ⚠️ Unexpected Content-Type: $CONTENT_TYPE"
fi

# Test 4: Check for IIFE format
echo ""
echo "4️⃣ Checking bundle format..."
BUNDLE=$(curl -s "$CDN_URL" | head -20)
if echo "$BUNDLE" | grep -q "(function()" || echo "$BUNDLE" | grep -q "var AmplifyChat"; then
    echo "   ✓ Appears to be IIFE/UMD format (immediate execution)"
else
    echo "   ⚠️ Cannot determine format from first 20 lines"
fi

# Test 5: Check for Amplify configuration
echo ""
echo "5️⃣ Checking for embedded Amplify config..."
if curl -s "$CDN_URL" | grep -q "AMPLIFY_OUTPUTS"; then
    echo "   ✓ AMPLIFY_OUTPUTS found in bundle"
else
    echo "   ⚠️ AMPLIFY_OUTPUTS not found in bundle"
fi

# Test 6: Check for custom element registration
echo ""
echo "6️⃣ Checking for customElements.define..."
if curl -s "$CDN_URL" | grep -q "customElements.define"; then
    echo "   ✓ customElements.define found in bundle"
else
    echo "   ✗ customElements.define NOT found in bundle"
fi

# Test 7: Check cache status
echo ""
echo "7️⃣ Checking CloudFront cache status..."
X_CACHE=$(curl -sI "$CDN_URL" | grep -i x-cache | awk '{print $2}' | tr -d '\r')
if [ -n "$X_CACHE" ]; then
    echo "   Cache Status: $X_CACHE"
    if echo "$X_CACHE" | grep -q "Hit"; then
        echo "   ℹ️ Serving from cache (may be stale)"
    else
        echo "   ✓ Fresh from origin"
    fi
fi

echo ""
echo "=================================="
echo "✓ Basic tests complete!"
echo ""
echo "📋 Next Steps:"
echo "   1. Open test-full-diagnostic.html in a browser"
echo "   2. Open browser DevTools (F12) and check Console"
echo "   3. Look for [AmplifyChat] log messages"
echo "   4. Verify custom element registration status"
echo ""
echo "🌐 Test page location:"
echo "   file://$(pwd)/test-full-diagnostic.html"
echo ""
