#!/bin/bash
#
# Check if web component is UMD or IIFE format
#

CDN_URL="https://d2m6vpu87luaxh.cloudfront.net/amplify-chat.js"

echo "Checking bundle format..."
echo ""

CONTENT=$(curl -s "$CDN_URL" | head -100)

# Check for UMD pattern
if echo "$CONTENT" | grep -q "function(module,exports)"; then
    echo "❌ Format: UMD (old - won't auto-register)"
elif echo "$CONTENT" | grep -q "typeof exports"; then
    echo "❌ Format: UMD (old - won't auto-register)"
elif echo "$CONTENT" | grep -q "!function()" || echo "$CONTENT" | grep -q "(function()"; then
    echo "✅ Format: IIFE (new - will auto-register!)"
else
    echo "⚠️  Format: Unknown (check manually)"
fi

echo ""
echo "First 5 lines of bundle:"
echo "$CONTENT" | head -5
