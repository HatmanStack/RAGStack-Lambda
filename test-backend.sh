#!/bin/bash

# Test the Amplify backend locally
echo "Testing Amplify backend..."

# Check if sandbox is running
if ! curl -s http://localhost:3001/graphql >/dev/null 2>&1; then
  echo "❌ Sandbox not running"
  echo "Start it with: npx ampx sandbox"
  exit 1
fi

echo "✅ Backend is running"
echo "✅ GraphQL endpoint available at http://localhost:3001/graphql"
echo ""
echo "Next steps:"
echo "1. Start frontend: cd src/ui && npm run dev"
echo "2. Log in with your test user"
echo "3. Send a message to test chat"
