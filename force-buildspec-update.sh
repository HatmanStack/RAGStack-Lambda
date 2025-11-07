#!/bin/bash
#
# Force CodeBuild BuildSpec Update
#
# This script forces CloudFormation to update the CodeBuild project's buildspec
# by adding a comment to trigger a change detection.
#

set -e

echo "🔧 Forcing BuildSpec update..."

# Check if template.yaml has --ignore-scripts
if grep -q "npm install esbuild@0.25.12 --ignore-scripts" template.yaml; then
    echo "✓ Template has --ignore-scripts flag"
else
    echo "✗ Template does NOT have --ignore-scripts flag!"
    echo "  Expected: npm install esbuild@0.25.12 --ignore-scripts"
    exit 1
fi

# Get stack name from argument or default
STACK_NAME=${1:-$(grep "stack_name = " publish.py | head -1 | cut -d'"' -f2 2>/dev/null || echo "RAGStack")}

echo ""
echo "To update the CodeBuild project buildspec:"
echo ""
echo "1. Run a full SAM deployment:"
echo "   python publish.py --project-name <your-project> --admin-email <your-email> --region <your-region>"
echo ""
echo "2. Or update just the stack (if already deployed):"
echo "   sam build && sam deploy --stack-name ${STACK_NAME} --region <your-region> --no-confirm-changeset"
echo ""
echo "3. Or use AWS CLI to force update the CodeBuild project:"
echo "   aws codebuild update-project --name <project-name> --region <your-region> \\"
echo "     --source '{\"type\": \"S3\", \"location\": \"<bucket>/amplify-placeholder.zip\", \"buildspec\": \"<buildspec-yaml>\"}'"
echo ""
