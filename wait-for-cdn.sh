#!/bin/bash
#
# Wait for CDN to become available
#
# Polls the CDN URL until it returns 200 or times out.
#

CDN_URL="${1:-https://d3w5cdfl4m6ati.cloudfront.net/amplify-chat.js}"
MAX_WAIT=600  # 10 minutes
INTERVAL=10    # Check every 10 seconds

echo "⏳ Waiting for CDN to become available..."
echo "URL: $CDN_URL"
echo "Max wait time: ${MAX_WAIT}s ($(($MAX_WAIT/60)) minutes)"
echo ""

START_TIME=$(date +%s)
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Try to fetch headers
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$CDN_URL" 2>&1)

    if [ "$HTTP_CODE" = "200" ]; then
        echo ""
        echo "✅ CDN is now available! (HTTP 200)"
        echo "Total wait time: ${ELAPSED}s"
        echo ""

        # Get file info
        FILE_SIZE=$(curl -sI "$CDN_URL" | grep -i content-length | awk '{print $2}' | tr -d '\r')
        if [ -n "$FILE_SIZE" ]; then
            SIZE_KB=$((FILE_SIZE / 1024))
            echo "File size: ${SIZE_KB}KB (${FILE_SIZE} bytes)"
        fi

        echo ""
        echo "🧪 Run tests now:"
        echo "   ./test-deployment.sh"
        echo "   OR open test-full-diagnostic.html in browser"
        exit 0
    elif [ "$HTTP_CODE" = "403" ]; then
        echo -ne "\r⏳ Still waiting... (${ELAPSED}s) - HTTP 403 (Access Denied)"
    else
        echo -ne "\r⏳ Still waiting... (${ELAPSED}s) - HTTP $HTTP_CODE"
    fi

    sleep $INTERVAL
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
done

echo ""
echo ""
echo "❌ Timeout after ${MAX_WAIT}s"
echo ""
echo "Possible issues:"
echo "  1. CodeBuild project still running (check AWS Console)"
echo "  2. CloudFront distribution still deploying (can take 15-20 min)"
echo "  3. S3 permissions not configured correctly"
echo "  4. File not uploaded to S3"
echo ""
echo "Check CodeBuild status in AWS Console:"
echo "  Project name should be: cdk-test-1-wc-build-*"
echo ""

exit 1
