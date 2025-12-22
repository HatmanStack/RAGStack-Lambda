#!/bin/bash
#
# Test API authentication for all endpoints
# Tests: valid key, no key, wrong key
#
# Usage: ./tests/test-api-auth.sh [endpoint] [api_key]
#   endpoint: GraphQL endpoint URL (or uses RAGSTACK_GRAPHQL_ENDPOINT env var)
#   api_key:  Valid API key (or uses RAGSTACK_API_KEY env var)

# Don't use set -e as arithmetic operations can return non-zero

ENDPOINT="${1:-${RAGSTACK_GRAPHQL_ENDPOINT}}"
VALID_KEY="${2:-${RAGSTACK_API_KEY}}"
WRONG_KEY="da2-wrongkey12345"

if [ -z "$ENDPOINT" ]; then
  echo "Error: No endpoint provided. Set RAGSTACK_GRAPHQL_ENDPOINT or pass as first argument."
  exit 1
fi

if [ -z "$VALID_KEY" ]; then
  echo "Error: No API key provided. Set RAGSTACK_API_KEY or pass as second argument."
  exit 1
fi

PASS=0
FAIL=0

test_endpoint() {
  local name="$1"
  local query="$2"
  local key="$3"
  local key_desc="$4"
  local expect_success="$5"

  if [ -z "$key" ]; then
    result=$(curl -s -m 10 -w "\n%{http_code}" -X POST "$ENDPOINT" \
      -H "Content-Type: application/json" \
      -d "$query" 2>/dev/null)
  else
    result=$(curl -s -m 10 -w "\n%{http_code}" -X POST "$ENDPOINT" \
      -H "Content-Type: application/json" \
      -H "x-api-key: $key" \
      -d "$query" 2>/dev/null)
  fi

  http_code=$(echo "$result" | tail -1)
  body=$(echo "$result" | sed '$d')

  has_data=$(echo "$body" | grep -c '"data"' || true)
  has_error=$(echo "$body" | grep -c '"errors"' || true)

  if [ "$expect_success" = "true" ]; then
    if [ "$http_code" = "200" ] && [ "$has_data" -gt 0 ]; then
      echo "  ✅ [$key_desc] OK"
      PASS=$((PASS + 1))
    else
      echo "  ❌ [$key_desc] FAILED - Expected success, got HTTP $http_code"
      if [ "$has_error" -gt 0 ]; then
        echo "     $(echo "$body" | grep -o '"message":"[^"]*"' | head -1)"
      fi
      FAIL=$((FAIL + 1))
    fi
  else
    if [ "$http_code" = "401" ] || [ "$has_error" -gt 0 ]; then
      echo "  ✅ [$key_desc] DENIED (expected)"
      PASS=$((PASS + 1))
    else
      echo "  ❌ [$key_desc] FAILED - Expected denial, got HTTP $http_code with data"
      FAIL=$((FAIL + 1))
    fi
  fi
}

echo "Testing API Authentication"
echo "Endpoint: $ENDPOINT"
echo ""

echo "=== CHAT (queryKnowledgeBase) ==="
CHAT='{"query":"query { queryKnowledgeBase(query: \"test\") { answer } }"}'
test_endpoint "chat" "$CHAT" "$VALID_KEY" "valid key" "true"
test_endpoint "chat" "$CHAT" "" "no key" "false"
test_endpoint "chat" "$CHAT" "$WRONG_KEY" "wrong key" "false"

echo ""
echo "=== SEARCH (searchKnowledgeBase) ==="
SEARCH='{"query":"query { searchKnowledgeBase(query: \"test\") { total } }"}'
test_endpoint "search" "$SEARCH" "$VALID_KEY" "valid key" "true"
test_endpoint "search" "$SEARCH" "" "no key" "false"
test_endpoint "search" "$SEARCH" "$WRONG_KEY" "wrong key" "false"

echo ""
echo "=== DOCUMENT UPLOAD (createUploadUrl) ==="
DOC='{"query":"mutation { createUploadUrl(filename: \"test.pdf\") { uploadUrl documentId } }"}'
test_endpoint "doc" "$DOC" "$VALID_KEY" "valid key" "true"
test_endpoint "doc" "$DOC" "" "no key" "false"
test_endpoint "doc" "$DOC" "$WRONG_KEY" "wrong key" "false"

echo ""
echo "=== IMAGE UPLOAD (createImageUploadUrl) ==="
IMG='{"query":"mutation { createImageUploadUrl(filename: \"test.jpg\") { uploadUrl imageId } }"}'
test_endpoint "img" "$IMG" "$VALID_KEY" "valid key" "true"
test_endpoint "img" "$IMG" "" "no key" "false"
test_endpoint "img" "$IMG" "$WRONG_KEY" "wrong key" "false"

echo ""
echo "=== WEB SCRAPING (startScrape) ==="
SCRAPE='{"query":"mutation { startScrape(input: {url: \"https://example.com\", maxPages: 1}) { jobId status } }"}'
test_endpoint "scrape" "$SCRAPE" "$VALID_KEY" "valid key" "true"
test_endpoint "scrape" "$SCRAPE" "" "no key" "false"
test_endpoint "scrape" "$SCRAPE" "$WRONG_KEY" "wrong key" "false"

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
