#!/bin/bash
#
# Download and inspect the CDN bundle to verify config injection
#

CDN_URL="https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js"
BUNDLE_FILE="/tmp/amplify-chat.js"

echo "📦 Downloading bundle from CDN..."
curl -s "$CDN_URL" -o "$BUNDLE_FILE"

if [ ! -f "$BUNDLE_FILE" ]; then
  echo "❌ Failed to download bundle"
  exit 1
fi

FILE_SIZE=$(wc -c < "$BUNDLE_FILE")
echo "✅ Downloaded: $FILE_SIZE bytes"
echo ""

# Check if AMPLIFY_OUTPUTS exists
echo "🔍 Checking for AMPLIFY_OUTPUTS constant..."
if grep -q "AMPLIFY_OUTPUTS" "$BUNDLE_FILE"; then
  echo "✅ AMPLIFY_OUTPUTS found in bundle"
  echo ""

  # Extract the AMPLIFY_OUTPUTS config (first 500 chars after the constant)
  echo "📄 AMPLIFY_OUTPUTS value (first 1000 chars):"
  grep -o "AMPLIFY_OUTPUTS.*" "$BUNDLE_FILE" | head -c 1000
  echo ""
  echo "..."
  echo ""
else
  echo "❌ AMPLIFY_OUTPUTS NOT FOUND in bundle!"
  echo ""
  echo "This means inject-amplify-config.js failed during build."
  echo "The bundle will fail at runtime when trying to import AMPLIFY_OUTPUTS."
fi

# Check for the Amplify.configure call
echo "🔍 Checking for Amplify.configure() call..."
if grep -q "Amplify.configure" "$BUNDLE_FILE"; then
  echo "✅ Amplify.configure() found"
else
  echo "❌ Amplify.configure() NOT FOUND"
fi

# Check for customElements.define
echo "🔍 Checking for customElements.define()..."
if grep -q 'customElements.define.*amplify-chat' "$BUNDLE_FILE"; then
  echo "✅ customElements.define('amplify-chat', ...) found"
else
  echo "❌ customElements.define NOT FOUND for 'amplify-chat'"
fi

echo ""
echo "🔍 Checking for error handling..."
# Look for the console.error statements from wc.ts
if grep -q "Failed to configure Amplify" "$BUNDLE_FILE"; then
  echo "✅ Amplify error handler found"
fi

if grep -q "Failed to register custom element" "$BUNDLE_FILE"; then
  echo "✅ Custom element error handler found"
fi

echo ""
echo "📊 Summary:"
echo "- Bundle size: $FILE_SIZE bytes"
echo "- Run this in browser console to test:"
echo "  fetch('$CDN_URL').then(r => r.text()).then(code => {"
echo "    console.log('Has AMPLIFY_OUTPUTS:', code.includes('AMPLIFY_OUTPUTS'));"
echo "    console.log('Has configure:', code.includes('Amplify.configure'));"
echo "  })"
