#!/bin/bash
#
# Check if web component is UMD or IIFE format
#

CDN_URL="https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js"

echo "Checking bundle format..."
echo ""

# Download first 1KB to check format (prevents broken pipe)
CONTENT=$(curl -s -r 0-1023 "$CDN_URL")

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
echo "First few lines of bundle:"
echo "$CONTENT" | head -5
