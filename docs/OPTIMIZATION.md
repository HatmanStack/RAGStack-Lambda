# RAGStack-Lambda Optimization Guide

## Overview

This guide provides strategies to optimize performance and reduce costs for the RAGStack-Lambda document processing pipeline.

---

## Lambda Memory Optimization

Lambda functions are billed based on memory allocation and execution time (GB-seconds). Right-sizing memory can significantly reduce costs while maintaining performance.

### Current Settings

From the CloudFormation template:

- **ProcessDocumentFunction**: 3008 MB (max memory for OCR processing)
- **GenerateEmbeddingsFunction**: 2048 MB
- **QueryKBFunction**: 512 MB
- **AppSyncResolverFunction**: 256 MB (via Globals)
- **KBCustomResourceFunction**: 512 MB

### How to Optimize Memory Allocation

#### 1. Analyze Actual Memory Usage

Use CloudWatch Logs Insights to query Lambda memory usage:

```bash
# Query for ProcessDocument memory usage
aws logs start-query \
  --log-group-name /aws/lambda/RAGStack-ProcessDocument \
  --start-time $(date -d '7 days ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @maxMemoryUsed, @memorySize
    | filter @type = "REPORT"
    | stats avg(@maxMemoryUsed/1024/1024) as AvgMemoryUsedMB,
            max(@maxMemoryUsed/1024/1024) as MaxMemoryUsedMB,
            avg(@memorySize/1024/1024) as AllocatedMB
    | limit 1'
```

#### 2. Calculate Utilization

**Target utilization: 70-85%** of allocated memory

- **Under-allocated** (>90% usage): Risk of out-of-memory errors
- **Over-allocated** (<50% usage): Wasting money on unused capacity
- **Optimal** (70-85% usage): Cost-effective with headroom for spikes

#### 3. Adjust Memory Settings

If utilization is outside optimal range, update `template.yaml`:

```yaml
ProcessDocumentFunction:
  Properties:
    MemorySize: 2048  # Reduced from 3008 if usage shows ~1500MB avg
```

#### 4. Monitor Impact on Duration

**Important:** Memory and CPU are proportional in Lambda. Lower memory = slower CPU.

After reducing memory allocation:
- Monitor execution duration
- If duration increases significantly, consider increasing memory back
- Sometimes **increasing** memory reduces total cost (faster execution)

### Cost Comparison by Memory Size

| Memory (MB) | Price per ms | Duration (example) | Cost per invocation |
|-------------|--------------|-------------------|---------------------|
| 512         | $0.0000000083 | 5000ms           | $0.0415             |
| 1024        | $0.0000000167 | 3000ms           | $0.0501             |
| 2048        | $0.0000000333 | 1800ms           | $0.0599             |
| 3008        | $0.0000000490 | 1500ms           | $0.0735             |

**Key insight:** The sweet spot varies by workload. Test different configurations.

### Optimization Workflow

```bash
# 1. Analyze current usage
./scripts/analyze_lambda_memory.sh ProcessDocument

# 2. Update memory in template.yaml
vim template.yaml

# 3. Deploy changes
sam build && sam deploy

# 4. Monitor for 24-48 hours
# 5. Check CloudWatch metrics for errors and duration
# 6. Repeat if needed
```

---

## Bedrock Cost Optimization

Bedrock charges vary significantly by model and operation type.

### OCR Backend Selection

The system supports two OCR backends:

| Backend | Cost per 1000 pages | Best for | Accuracy |
|---------|---------------------|----------|----------|
| **Textract** | $1.50 | Simple text documents, forms, tables | Good |
| **Bedrock Claude** | ~$0.75-5.00 | Complex layouts, handwriting, mixed content | Excellent |

#### When to Use Textract

- Printed text documents
- Standard forms and invoices
- High-volume, batch processing
- Cost-sensitive applications

#### When to Use Bedrock OCR

- Handwritten documents
- Complex layouts with mixed content
- Documents requiring contextual understanding
- Quality over cost priority

#### Configure OCR Backend

Update in `template.yaml` parameters:

```yaml
Parameters:
  OcrBackend:
    Type: String
    Default: textract  # Use textract by default for cost savings
    AllowedValues:
      - textract
      - bedrock
```

Or override during deployment:

```bash
sam deploy --parameter-overrides OcrBackend=textract
```

### Embedding Model Selection

Current configuration uses cost-effective models:

- **Text embeddings**: `amazon.titan-embed-text-v2:0` - $0.0001 per 1000 tokens
- **Image embeddings**: `amazon.titan-embed-image-v1` - $0.06 per 1000 images

**Already optimized** - these are the most cost-effective embedding models available.

### Batch Processing Optimization

The `GenerateEmbeddingsFunction` processes embeddings in batches to avoid rate limits:

```python
# Current configuration in generate_embeddings Lambda
BATCH_SIZE = 20  # Process 20 pages at a time
DELAY_BETWEEN_BATCHES = 2  # seconds
```

**Optimization tips:**
- Increase batch size if not hitting rate limits
- Reduce delay between batches (monitor for throttling)
- Use CloudWatch metrics to find optimal settings

---

## S3 Lifecycle Optimization

Lifecycle policies automatically transition or delete objects to reduce storage costs.

### Current Configuration

| Bucket | Lifecycle Policy | Rationale |
|--------|------------------|-----------|
| **InputBucket** | No expiration (Phase 7 config) | Keep source documents indefinitely |
| **OutputBucket** | No expiration (Phase 7 config) | Keep processed results indefinitely |
| **WorkingBucket** | Delete after 7 days | Temporary files only |
| **VectorBucket** | No expiration | Vector embeddings for KB |
| **CloudTrailBucket** | Delete after 90 days | Audit logs retention |

### Customizing Retention Periods

Edit `template.yaml` to adjust retention based on your requirements:

```yaml
InputBucket:
  Properties:
    LifecycleConfiguration:
      Rules:
        - Id: TransitionToIA
          Status: Enabled
          Transitions:
            - StorageClass: STANDARD_IA
              TransitionInDays: 30  # Move to Infrequent Access after 30 days
        - Id: DeleteOldDocuments
          Status: Enabled
          ExpirationInDays: 365  # Delete after 1 year
```

### Storage Class Comparison

| Class | Cost per GB/month | Retrieval Cost | Use Case |
|-------|-------------------|----------------|----------|
| **STANDARD** | $0.023 | None | Frequently accessed |
| **STANDARD_IA** | $0.0125 | $0.01/GB | Monthly access |
| **GLACIER** | $0.004 | $0.02/GB + hours delay | Archive |

**Recommendation:**
- Documents accessed monthly → STANDARD_IA after 30 days
- Documents accessed rarely → GLACIER after 90 days
- Active processing data → STANDARD

---

## DynamoDB Optimization

RAGStack-Lambda uses **on-demand billing** for DynamoDB, which is optimal for variable workloads.

### Current Configuration

- **TrackingTable**: On-demand billing
- **MeteringTable**: On-demand billing with TTL

### When to Switch to Provisioned Capacity

Consider provisioned capacity if:

1. **Consistent traffic**: >1000 documents per day with predictable patterns
2. **Cost threshold**: On-demand costs exceed $25/month
3. **Predictable load**: Can accurately forecast read/write capacity

### Cost Comparison

| Mode | Pricing | Best For |
|------|---------|----------|
| **On-Demand** | $1.25 per million writes<br>$0.25 per million reads | Variable workloads<br>Unpredictable traffic |
| **Provisioned** | $0.00065 per WCU-hour<br>$0.00013 per RCU-hour | Consistent traffic<br>Predictable patterns |

**Current setup is optimal for most use cases.**

### TTL Optimization

The `MeteringTable` uses Time-to-Live (TTL) to automatically delete old metering records:

```python
# Metering records expire after 90 days
ttl = int((datetime.now() + timedelta(days=90)).timestamp())
```

**Adjust TTL** in `lib/ragstack_common/storage.py` if you need longer retention.

---

## Step Functions Optimization

Step Functions charges per state transition ($0.025 per 1000 transitions).

### Current Pipeline

The `ProcessingPipeline` state machine has:
- 2 Lambda task states (ProcessDocument, GenerateEmbeddings)
- Error handling with retry logic
- Minimal state transitions

**Already optimized** - Using direct Lambda integrations without intermediate states.

### Optimization Tips

1. **Avoid unnecessary states**: Combine logic in Lambda when possible
2. **Use Express Workflows** for high-volume, short-duration workflows (not applicable here)
3. **Batch processing**: Process multiple documents in one execution if feasible

---

## CloudWatch Costs

CloudWatch charges for:
- Log ingestion: $0.50 per GB
- Log storage: $0.03 per GB/month
- Metrics: First 10,000 free, then $0.30 per metric
- Dashboards: $3 per dashboard per month

### Current Configuration

Phase 7 added:
- 1 CloudWatch Dashboard ($3/month)
- 5 CloudWatch Alarms (free within limits)
- CloudTrail logs with 90-day retention

### Log Retention Optimization

Current retention for Lambda logs:

```yaml
StateMachineLogGroup:
  Properties:
    RetentionInDays: 30  # Adjust based on debugging needs
```

**Optimization options:**
- **Development**: 7 days retention
- **Production**: 30 days retention
- **Compliance**: 90+ days retention

Reduce retention to save storage costs:

```bash
aws logs put-retention-policy \
  --log-group-name /aws/lambda/RAGStack-ProcessDocument \
  --retention-in-days 7
```

---

## Monitoring Costs

### Using the Cost Check Script

Run monthly to review costs:

```bash
./scripts/check_costs.sh RAGStack
```

### AWS Cost Explorer

1. Go to AWS Console → Cost Explorer
2. Filter by tag: `Project=RAGStack`
3. Group by: Service
4. Set date range: Last 30 days

### Budget Alerts

Phase 7 configured a budget with:
- **Limit**: $100/month (placeholder)
- **Alert at**: 80% ($80)
- **Forecast alert**: 100% ($100)

**Update budget** to your actual expected costs:

```yaml
MonthlyBudget:
  Properties:
    Budget:
      BudgetLimit:
        Amount: 50  # Adjust to your expected monthly cost
```

---

## Cost Optimization Checklist

### Monthly Review

- [ ] Run `./scripts/check_costs.sh` to check current spending
- [ ] Review CloudWatch dashboard for usage patterns
- [ ] Check Lambda memory utilization (target 70-85%)
- [ ] Verify S3 lifecycle policies are deleting old objects
- [ ] Review Bedrock OCR vs Textract usage mix

### Quarterly Review

- [ ] Analyze CloudWatch Logs Insights for Lambda optimization opportunities
- [ ] Review DynamoDB usage patterns (consider provisioned if consistent)
- [ ] Check if any resources can be rightsized
- [ ] Review budget alerts and adjust thresholds

### Cost Reduction Quick Wins

1. **Switch to Textract for simple documents** (can save 70% on OCR)
2. **Reduce Lambda memory** if utilization <50% (can save 20-30%)
3. **Enable S3 lifecycle transitions** to IA storage (can save 45% on storage)
4. **Reduce CloudWatch log retention** to 7 days (can save on log storage)

---

## Example Monthly Cost Breakdown

Assuming 1000 documents/month, 5 pages average:

| Service | Usage | Cost |
|---------|-------|------|
| **Textract** | 5000 pages × $0.0015 | $7.50 |
| **Bedrock Embeddings** | 10,000 tokens × $0.0001/1000 | $1.00 |
| **Lambda** | 2000 invocations, 512MB avg, 5s avg | $0.40 |
| **S3** | 5 buckets, 10GB storage | $0.23 |
| **DynamoDB** | 2000 writes, 5000 reads | $2.63 |
| **Step Functions** | 1000 executions, 2 transitions | $0.05 |
| **CloudWatch** | 1 dashboard, 1GB logs | $3.50 |
| **CloudTrail** | 1GB logs | $0.50 |
| **Total** | | **~$15.81/month** |

**With Bedrock OCR instead of Textract:**
- Bedrock OCR: 5000 pages × $0.005 = $25.00
- **Total**: ~$33.31/month

---

## Advanced Optimization

### Lambda Power Tuning

Use [AWS Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning) to automatically find optimal memory settings:

```bash
# Install SAR application
aws serverlessrepo create-cloud-formation-change-set \
  --application-id arn:aws:serverlessrepo:us-east-1:451282441545:applications/aws-lambda-power-tuning \
  --stack-name lambda-power-tuning

# Run power tuning for ProcessDocument
# Follow tool documentation for execution
```

### Reserved Capacity

For predictable, high-volume workloads:
- **Lambda**: Reserved concurrency (not applicable for variable load)
- **DynamoDB**: Reserved capacity (only if >$25/month on-demand)
- **S3**: Commitments for >500TB storage

**Not recommended for RAGStack-Lambda** unless running at very high scale (>10,000 docs/day).

---

## Questions or Issues?

- **CloudWatch Dashboard**: Check metrics at AWS Console → CloudWatch → Dashboards → RAGStack-Monitor
- **Cost anomalies**: Review AWS Cost Explorer for unexpected spikes
- **Performance issues**: See `docs/TESTING.md` for troubleshooting

For architectural optimization, see `docs/ARCHITECTURE.md`.
