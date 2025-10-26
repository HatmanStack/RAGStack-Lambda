#!/bin/bash
# Check RAGStack-Lambda costs

PROJECT_NAME=${1:-RAGStack}
START_DATE=$(date -d "1 month ago" +%Y-%m-%d 2>/dev/null || date -v-1m +%Y-%m-%d)
END_DATE=$(date +%Y-%m-%d)

echo "=== RAGStack-Lambda Cost Report ==="
echo "Period: $START_DATE to $END_DATE"
echo ""

# Get cost by service
echo "Cost by Service:"
aws ce get-cost-and-usage \
  --time-period Start=$START_DATE,End=$END_DATE \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --filter "{\"Tags\":{\"Key\":\"Project\",\"Values\":[\"$PROJECT_NAME\"]}}" \
  --query 'ResultsByTime[0].Groups[*].[Keys[0],Metrics.BlendedCost.Amount]' \
  --output table

echo ""
echo "Top Cost Components:"
echo "1. Bedrock (Claude OCR + Embeddings)"
echo "2. Textract (if using for OCR)"
echo "3. Lambda (execution time)"
echo "4. S3 (storage)"
echo "5. DynamoDB (operations)"
echo ""

# Get monthly forecast
echo "Monthly Forecast:"
FORECAST_END=$(date -d "1 month" +%Y-%m-%d 2>/dev/null || date -v+1m +%Y-%m-%d)
aws ce get-cost-forecast \
  --time-period Start=$END_DATE,End=$FORECAST_END \
  --metric BLENDED_COST \
  --granularity MONTHLY \
  --filter "{\"Tags\":{\"Key\":\"Project\",\"Values\":[\"$PROJECT_NAME\"]}}" \
  --query 'Total.Amount' \
  --output text 2>/dev/null || echo "Forecast unavailable (requires historical data)"

echo ""
echo "=== Optimization Recommendations ==="
echo "1. Lambda: Review memory settings (see docs/OPTIMIZATION.md)"
echo "2. Bedrock: Use Textract for simple OCR (cheaper)"
echo "3. S3: Lifecycle policies configured for auto-cleanup"
echo "4. DynamoDB: Using on-demand billing (cost-effective for variable load)"
echo ""
echo "For detailed optimization guide, see: docs/OPTIMIZATION.md"
