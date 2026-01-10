#!/bin/bash
# cleanup-analyze.sh - Run all static analysis tools and generate reports
# Usage: bash scripts/cleanup-analyze.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
REPORT_DIR="/tmp/cleanup-analysis"

mkdir -p "$REPORT_DIR"

echo "=== Codebase Cleanup Analysis ==="
echo "Output directory: $REPORT_DIR"
echo ""

# Run vulture for Python dead code
echo "--- Python Dead Code (vulture) ---"
cd "$ROOT_DIR"
uvx vulture lib/ src/lambda/ tests/ vulture_whitelist.py --min-confidence 80 > "$REPORT_DIR/vulture.txt" 2>&1 || true
if [ -s "$REPORT_DIR/vulture.txt" ]; then
    cat "$REPORT_DIR/vulture.txt"
    VULTURE_COUNT=$(wc -l < "$REPORT_DIR/vulture.txt")
    echo "Found $VULTURE_COUNT items"
else
    echo "No dead code found"
    VULTURE_COUNT=0
fi
echo ""

# Run knip for UI TypeScript
echo "--- UI TypeScript Dead Code (knip) ---"
cd "$ROOT_DIR/src/ui"
npx knip > "$REPORT_DIR/knip-ui.txt" 2>&1 || true
if [ -s "$REPORT_DIR/knip-ui.txt" ]; then
    cat "$REPORT_DIR/knip-ui.txt"
else
    echo "No issues found"
fi
echo ""

# Run knip for ragstack-chat TypeScript
echo "--- ragstack-chat TypeScript Dead Code (knip) ---"
cd "$ROOT_DIR/src/ragstack-chat"
npx knip > "$REPORT_DIR/knip-chat.txt" 2>&1 || true
if [ -s "$REPORT_DIR/knip-chat.txt" ]; then
    cat "$REPORT_DIR/knip-chat.txt"
else
    echo "No issues found"
fi
echo ""

# Search for console.log statements
echo "--- Console/Print Statements ---"
cd "$ROOT_DIR"
echo "TypeScript console.log:"
grep -r "console\.log\|console\.debug\|console\.warn" src/ui/src src/ragstack-chat/src --include="*.ts" --include="*.tsx" 2>/dev/null | grep -v "\.test\." | grep -v node_modules > "$REPORT_DIR/console-ts.txt" || true
if [ -s "$REPORT_DIR/console-ts.txt" ]; then
    wc -l < "$REPORT_DIR/console-ts.txt" | xargs echo "  Found"
else
    echo "  None found"
fi

echo "Python print():"
grep -r "^[[:space:]]*print(" lib/ src/lambda/ --include="*.py" 2>/dev/null | grep -v "__pycache__" > "$REPORT_DIR/print-py.txt" || true
if [ -s "$REPORT_DIR/print-py.txt" ]; then
    wc -l < "$REPORT_DIR/print-py.txt" | xargs echo "  Found"
else
    echo "  None found"
fi
echo ""

# Summary
echo "=== Analysis Complete ==="
echo "Reports saved to: $REPORT_DIR"
echo "  - vulture.txt (Python dead code)"
echo "  - knip-ui.txt (UI dead code)"
echo "  - knip-chat.txt (Chat dead code)"
echo "  - console-ts.txt (Console statements)"
echo "  - print-py.txt (Print statements)"
