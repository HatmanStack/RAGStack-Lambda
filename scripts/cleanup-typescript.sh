#!/bin/bash
# cleanup-typescript.sh - TypeScript dead code cleanup
# Usage: bash scripts/cleanup-typescript.sh [--dry-run|--execute]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
MODE="${1:---dry-run}"

echo "=== TypeScript Cleanup ==="
echo "Mode: $MODE"
echo ""

# Analyze UI
echo "--- Analyzing src/ui with knip ---"
cd "$ROOT_DIR/src/ui"
KNIP_UI=$(npx knip 2>&1 || true)
if [ -n "$KNIP_UI" ]; then
    echo "$KNIP_UI"
else
    echo "No issues found"
fi
echo ""

# Analyze ragstack-chat
echo "--- Analyzing src/ragstack-chat with knip ---"
cd "$ROOT_DIR/src/ragstack-chat"
KNIP_CHAT=$(npx knip 2>&1 || true)
if [ -n "$KNIP_CHAT" ]; then
    echo "$KNIP_CHAT"
else
    echo "No issues found"
fi
echo ""

# Find console.log statements
echo "--- Finding console.log statements ---"
cd "$ROOT_DIR"
CONSOLE_FILES=$(grep -rl "console\.log\|console\.debug\|console\.warn" src/ui/src src/ragstack-chat/src --include="*.ts" --include="*.tsx" 2>/dev/null | grep -v "\.test\." | grep -v node_modules || true)

if [ -z "$CONSOLE_FILES" ]; then
    echo "No console.log statements found in production code"
else
    echo "Files with console statements:"
    for f in $CONSOLE_FILES; do
        COUNT=$(grep -c "console\.log\|console\.debug\|console\.warn" "$f" 2>/dev/null || echo "0")
        echo "  $f: $COUNT occurrences"
    done
fi
echo ""

if [ "$MODE" == "--execute" ]; then
    echo "--- Executing cleanup ---"

    # Remove console.log statements (preserving console.error)
    if [ -n "$CONSOLE_FILES" ]; then
        echo "Removing console.log/debug/warn statements..."
        for f in $CONSOLE_FILES; do
            # Remove lines that are just console.log/debug/warn statements
            sed -i '/^[[:space:]]*console\.log(/d' "$f"
            sed -i '/^[[:space:]]*console\.debug(/d' "$f"
            sed -i '/^[[:space:]]*console\.warn(/d' "$f"
            echo "  Cleaned: $f"
        done
    fi

    # Run ESLint fix
    echo "Running ESLint to fix imports..."
    cd "$ROOT_DIR/src/ui"
    npm run lint -- --fix 2>/dev/null || true

    cd "$ROOT_DIR/src/ragstack-chat"
    npm run lint -- --fix 2>/dev/null || true

    echo ""
    echo "Cleanup complete. Run tests to verify: npm run test:frontend"
else
    echo "--- Dry run complete ---"
    echo "To execute cleanup, run: bash scripts/cleanup-typescript.sh --execute"
fi
