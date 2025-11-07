#!/bin/bash
#
# Deploy Amplify chat from the correct branch with our fixes
#

set -e  # Exit on any error

echo "Verifying correct branch..."
CURRENT_BRANCH=$(git branch --show-current)
EXPECTED_BRANCH="claude/amplify-ts-documentation-011CUqVzG1sGFFSTKHhvBrV5"

if [ "$CURRENT_BRANCH" != "$EXPECTED_BRANCH" ]; then
    echo "ERROR: Wrong branch! Currently on '$CURRENT_BRANCH'"
    echo "       Expected: '$EXPECTED_BRANCH'"
    echo ""
    echo "Switching to correct branch..."
    git checkout "$EXPECTED_BRANCH"
fi

echo "✓ On correct branch: $EXPECTED_BRANCH"
echo ""

# Verify we have the latest code
if [ ! -f "amplify/lib/backend-stack.ts" ]; then
    echo "ERROR: amplify/lib/backend-stack.ts not found!"
    echo "This file is required for the CDK deployment."
    exit 1
fi

echo "✓ Required files present"
echo ""

# Check latest commit
LATEST_COMMIT=$(git log -1 --oneline)
echo "Latest commit: $LATEST_COMMIT"
echo ""

# Get deployment parameters
read -p "Project name (default: amplify-test-13): " PROJECT_NAME
PROJECT_NAME=${PROJECT_NAME:-amplify-test-13}

read -p "Admin email: " ADMIN_EMAIL
if [ -z "$ADMIN_EMAIL" ]; then
    echo "ERROR: Admin email is required"
    exit 1
fi

read -p "AWS Region (default: us-west-2): " AWS_REGION
AWS_REGION=${AWS_REGION:-us-west-2}

echo ""
echo "==================================="
echo "Deployment Configuration"
echo "==================================="
echo "Branch:       $EXPECTED_BRANCH"
echo "Project:      $PROJECT_NAME"
echo "Admin Email:  $ADMIN_EMAIL"
echo "Region:       $AWS_REGION"
echo "==================================="
echo ""

read -p "Proceed with deployment? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    echo "Deployment cancelled"
    exit 0
fi

echo ""
echo "Starting deployment..."
echo ""

# Run publish.py with chat-only flag (faster, just tests Amplify stack)
python publish.py \
    --project-name "$PROJECT_NAME" \
    --admin-email "$ADMIN_EMAIL" \
    --region "$AWS_REGION" \
    --chat-only

echo ""
echo "✓ Deployment complete!"
echo ""
echo "Verify the deployment:"
echo "  ./check-cdk-stack.sh"
echo "  ./check-amplify-outputs.sh"
