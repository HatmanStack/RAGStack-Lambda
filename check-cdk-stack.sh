#!/bin/bash
# Check if CDK backend stack exists

PROJECT_NAME="amplify-test-13"
STACK_NAME="amplify-${PROJECT_NAME}-backend"

echo "Checking for CDK backend stack: $STACK_NAME"
echo "=============================================="
echo ""

# Check if stack exists
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" &>/dev/null; then
  echo "✓ Stack EXISTS"
  echo ""
  echo "Stack Status:"
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].{Status:StackStatus,Created:CreationTime,Updated:LastUpdatedTime}" \
    --output table

  echo ""
  echo "Stack Outputs:"
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}" \
    --output table
else
  echo "✗ Stack DOES NOT EXIST"
  echo ""
  echo "This means the CDK deployment did not run or failed."
  echo ""
  echo "Checking for any Amplify-related stacks:"
  aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE CREATE_FAILED UPDATE_FAILED ROLLBACK_COMPLETE \
    --query "StackSummaries[?contains(StackName, 'amplify')].{Name:StackName,Status:StackStatus,Updated:LastUpdatedTime}" \
    --output table
fi
