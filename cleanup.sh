#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="$SCRIPT_DIR/.cleanup-reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$REPORT_DIR"

phase_analyze() {
    echo "=== Phase 1: Analysis ==="

    echo "Running vulture (Python dead code)..."
    uvx vulture lib/ src/lambda/ --min-confidence 80 > "$REPORT_DIR/vulture_$TIMESTAMP.txt" 2>&1 || true

    echo "Running ruff (unused imports)..."
    uv run ruff check . --select=F401,F841 --output-format=concise > "$REPORT_DIR/unused_$TIMESTAMP.txt" 2>&1 || true

    echo "Running knip (JS/TS unused exports)..."
    (cd "$SCRIPT_DIR/src/ui" && npx knip > "$REPORT_DIR/knip_ui_$TIMESTAMP.txt" 2>&1) || true
    (cd "$SCRIPT_DIR/src/ragstack-chat" && npx knip > "$REPORT_DIR/knip_chat_$TIMESTAMP.txt" 2>&1) || true

    echo "Analysis complete. Reports in $REPORT_DIR"
}

phase_fix() {
    echo "=== Phase 2: Auto-fix ==="

    echo "Fixing Python unused imports..."
    uv run ruff check . --fix --select=F401,F841 || true

    echo "Formatting Python code..."
    uv run ruff format .

    echo "Auto-fix complete."
}

phase_validate() {
    echo "=== Phase 3: Validation ==="

    echo "Running Python linting..."
    uv run ruff check .
    uv run ruff format . --check

    echo "Running vulture..."
    uvx vulture lib/ src/lambda/ --min-confidence 90

    echo "Running frontend linting..."
    (cd "$SCRIPT_DIR/src/ui" && npm run lint -- --max-warnings 0)
    (cd "$SCRIPT_DIR/src/ragstack-chat" && npm run lint -- --max-warnings 0)

    echo "Running tests..."
    npm run test

    echo "Validation complete."
}

generate_report() {
    echo "=== Generating Audit Report ==="

    cat > "$REPORT_DIR/audit_$TIMESTAMP.md" <<EOF
# Codebase Cleanup Audit Report
Generated: $(date)

## Analysis Results

### Python Dead Code (vulture)
\`\`\`
$(cat "$REPORT_DIR/vulture_$TIMESTAMP.txt" 2>/dev/null || echo "No issues found")
\`\`\`

### Unused Imports (ruff)
\`\`\`
$(cat "$REPORT_DIR/unused_$TIMESTAMP.txt" 2>/dev/null || echo "No issues found")
\`\`\`

### JS/TS Unused Exports (knip - UI)
\`\`\`
$(cat "$REPORT_DIR/knip_ui_$TIMESTAMP.txt" 2>/dev/null || echo "No issues found")
\`\`\`

### JS/TS Unused Exports (knip - Chat)
\`\`\`
$(cat "$REPORT_DIR/knip_chat_$TIMESTAMP.txt" 2>/dev/null || echo "No issues found")
\`\`\`

## Validation Status
Run \`./cleanup.sh validate\` to check current status.
EOF

    echo "Report generated: $REPORT_DIR/audit_$TIMESTAMP.md"
}

case "${1:-all}" in
    analyze) phase_analyze ;;
    fix) phase_fix ;;
    validate) phase_validate ;;
    report) generate_report ;;
    all)
        phase_analyze
        phase_fix
        phase_validate
        generate_report
        ;;
    *)
        echo "Usage: $0 {analyze|fix|validate|report|all}"
        exit 1
        ;;
esac
