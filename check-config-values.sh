#!/bin/bash
#
# Check if actual Amplify config values are embedded in the bundle
#

CDN_URL="https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js"

echo "🔍 Checking if Amplify configuration values are in the bundle..."
echo ""

# Download bundle
BUNDLE=$(curl -s "$CDN_URL")

# Check for API endpoint from amplify_outputs.json
echo "1️⃣ Checking for API endpoint (smjbvtec3nbvza6fjnwrw3b7wm.appsync-api.us-west-2.amazonaws.com)..."
if echo "$BUNDLE" | grep -q "smjbvtec3nbvza6fjnwrw3b7wm"; then
  echo "   ✅ API endpoint FOUND in bundle"
else
  echo "   ❌ API endpoint NOT FOUND in bundle!"
  echo "   This means AMPLIFY_OUTPUTS was not properly injected during build."
fi

# Check for User Pool ID
echo ""
echo "2️⃣ Checking for User Pool ID (us-west-2_DwMyWAlBQ)..."
if echo "$BUNDLE" | grep -q "us-west-2_DwMyWAlBQ"; then
  echo "   ✅ User Pool ID FOUND in bundle"
else
  echo "   ❌ User Pool ID NOT FOUND in bundle!"
fi

# Check for User Pool Client ID
echo ""
echo "3️⃣ Checking for User Pool Client ID (2noq9v1p9a7cquhdbp81orbqtc)..."
if echo "$BUNDLE" | grep -q "2noq9v1p9a7cquhdbp81orbqtc"; then
  echo "   ✅ User Pool Client ID FOUND in bundle"
else
  echo "   ❌ User Pool Client ID NOT FOUND in bundle!"
fi

echo ""
echo "=================================="
echo "Summary:"
echo "If any values are missing, the inject-amplify-config.js script"
echo "failed during CodeBuild, and the bundle has a broken import."
echo ""
echo "Next step: Check WebComponentBuildProject logs for errors during build phase."
