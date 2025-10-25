#!/bin/bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Invalidate CloudFront cache after UI deployment

set -e

STACK_NAME=${1:-RAGStack-prod}
REGION=${2:-us-east-1}

echo "Getting CloudFront distribution ID from stack: $STACK_NAME"

DIST_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
  --output text)

if [ -z "$DIST_ID" ]; then
  echo "❌ Error: Could not find CloudFront distribution ID in stack outputs"
  exit 1
fi

echo "Invalidating CloudFront cache for distribution: $DIST_ID"

aws cloudfront create-invalidation \
  --distribution-id "$DIST_ID" \
  --paths "/*" \
  --region "$REGION"

echo "✓ Cache invalidation initiated"
echo "Note: Invalidation may take a few minutes to complete"
