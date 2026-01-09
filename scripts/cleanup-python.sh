#!/bin/bash
# cleanup-python.sh - Python dead code cleanup
# Usage: bash scripts/cleanup-python.sh [--dry-run|--execute]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
MODE="${1:---dry-run}"

echo "=== Python Cleanup ==="
echo "Mode: $MODE"
echo ""

cd "$ROOT_DIR"

# Run vulture to find dead code
echo "--- Analyzing with vulture ---"
VULTURE_OUTPUT=$(uvx vulture lib/ src/lambda/ tests/ vulture_whitelist.py --min-confidence 80 2>&1 || true)

if [ -z "$VULTURE_OUTPUT" ]; then
    echo "No dead code found by vulture"
    echo ""
else
    echo "Vulture findings:"
    echo "$VULTURE_OUTPUT"
    echo ""
fi

# Find print statements (excluding tests and __pycache__)
echo "--- Finding print() statements ---"
PRINT_FILES=$(grep -rl "^[[:space:]]*print(" lib/ src/lambda/ --include="*.py" 2>/dev/null | grep -v "__pycache__" || true)

if [ -z "$PRINT_FILES" ]; then
    echo "No print() statements found in production code"
else
    echo "Files with print() statements:"
    for f in $PRINT_FILES; do
        COUNT=$(grep -c "^[[:space:]]*print(" "$f" 2>/dev/null || echo "0")
        echo "  $f: $COUNT occurrences"
    done
fi
echo ""

if [ "$MODE" == "--execute" ]; then
    echo "--- Executing cleanup ---"

    # Remove print statements (simple cases only)
    if [ -n "$PRINT_FILES" ]; then
        echo "Removing print() statements..."
        for f in $PRINT_FILES; do
            # Remove lines that are just print statements (preserving indentation structure)
            sed -i '/^[[:space:]]*print(/d' "$f"
            echo "  Cleaned: $f"
        done
    fi

    # Run ruff to fix any import issues
    echo "Running ruff to fix imports..."
    uv run ruff check lib/ src/lambda/ --fix --select F401 2>/dev/null || true
    uv run ruff format lib/ src/lambda/ 2>/dev/null || true

    echo ""
    echo "Cleanup complete. Run tests to verify: npm run test:backend"
else
    echo "--- Dry run complete ---"
    echo "To execute cleanup, run: bash scripts/cleanup-python.sh --execute"
fi
