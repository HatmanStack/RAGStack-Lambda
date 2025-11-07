#!/bin/bash
#
# Comprehensive diagnostic for web component issue
#

CDN_URL="https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js"

echo "🔍 Web Component Diagnostic Report"
echo "===================================="
echo ""
echo "CDN URL: $CDN_URL"
echo "Date: $(date)"
echo ""

# 1. Check accessibility
echo "1️⃣ Checking CDN accessibility..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$CDN_URL")
echo "   HTTP Status: $HTTP_CODE"

if [ "$HTTP_CODE" != "200" ]; then
    echo "   ❌ CDN not accessible! Stopping diagnostics."
    exit 1
fi
echo "   ✅ CDN is accessible"
echo ""

# 2. Check file size
echo "2️⃣ Checking file size..."
SIZE=$(curl -sI "$CDN_URL" | grep -i content-length | awk '{print $2}' | tr -d '\r')
if [ -n "$SIZE" ]; then
    SIZE_KB=$((SIZE / 1024))
    echo "   File size: ${SIZE_KB}KB (${SIZE} bytes)"
    if [ "$SIZE" -lt 10000 ]; then
        echo "   ⚠️ Warning: File seems too small (< 10KB)"
    fi
else
    echo "   ⚠️ Could not determine size"
fi
echo ""

# 3. Check bundle format
echo "3️⃣ Checking bundle format (first 1000 bytes)..."
FIRST_KB=$(curl -s -r 0-999 "$CDN_URL")

if echo "$FIRST_KB" | grep -q "var AmplifyChat.*function"; then
    echo "   ❌ Format: UMD (won't auto-register!)"
elif echo "$FIRST_KB" | grep -q "!function()\|^(function()"; then
    echo "   ✅ Format: IIFE (should auto-register)"
elif echo "$FIRST_KB" | grep -q "typeof exports"; then
    echo "   ❌ Format: CommonJS/UMD"
else
    echo "   ⚠️ Format: Unknown"
fi
echo ""

# 4. Show first 30 lines
echo "4️⃣ First 30 lines of bundle:"
echo "----------------------------"
curl -s "$CDN_URL" | head -30
echo "----------------------------"
echo ""

# 5. Check for key functions
echo "5️⃣ Checking for key code patterns..."

if curl -s "$CDN_URL" | grep -q "customElements.define"; then
    echo "   ✅ Found: customElements.define()"
else
    echo "   ❌ Missing: customElements.define()"
fi

if curl -s "$CDN_URL" | grep -q "Amplify.configure"; then
    echo "   ✅ Found: Amplify.configure()"
else
    echo "   ❌ Missing: Amplify.configure()"
fi

if curl -s "$CDN_URL" | grep -q "AMPLIFY_OUTPUTS"; then
    echo "   ✅ Found: AMPLIFY_OUTPUTS (embedded config)"

    # Try to extract the config
    echo ""
    echo "   Extracting AMPLIFY_OUTPUTS..."
    curl -s "$CDN_URL" | grep -A 30 "AMPLIFY_OUTPUTS" | head -35
else
    echo "   ❌ Missing: AMPLIFY_OUTPUTS (config not embedded!)"
fi
echo ""

# 6. Check for React
echo "6️⃣ Checking for bundled dependencies..."
if curl -s "$CDN_URL" | grep -q "createElement"; then
    echo "   ✅ React appears to be bundled"
else
    echo "   ⚠️ React might not be bundled"
fi
echo ""

# 7. Cache status
echo "7️⃣ CloudFront cache status..."
X_CACHE=$(curl -sI "$CDN_URL" | grep -i x-cache | cut -d: -f2 | tr -d ' \r\n')
echo "   X-Cache: $X_CACHE"
if echo "$X_CACHE" | grep -q "Hit"; then
    echo "   ⚠️ Serving from cache (might be old version)"
else
    echo "   ✅ Fresh from origin"
fi
echo ""

echo "===================================="
echo "✓ Diagnostic complete!"
echo ""
echo "📋 Next steps:"
echo "   1. If format is UMD: Web component build didn't run or failed"
echo "   2. If AMPLIFY_OUTPUTS missing: Config injection failed"
echo "   3. Share this output for further troubleshooting"
echo ""
