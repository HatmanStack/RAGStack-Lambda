# Sync Coordinator Implementation Plan (IMPLEMENTED)

## Problem
`process-image` Lambda calls `start_ingestion_with_retry()` after writing metadata to S3. When multiple images are uploaded quickly, concurrent sync attempts cause `ConflictException` errors because Bedrock KB only allows one sync job at a time per data source.

## Solution: SQS FIFO Queue + Single-Concurrency Sync Coordinator

### Architecture
```text
process-image → SQS FIFO Queue → sync-coordinator Lambda (concurrency=1)
     │              │                      │
 writes S3    dedup window           Wait for running sync
 metadata     (5 min default)        Then start new sync
```

### Why This Works
1. **FIFO queue with deduplication**: Multiple sync requests within dedup window become one message
2. **Reserved concurrency = 1**: Only one sync-coordinator runs at a time, no race conditions
3. **Wait-then-sync pattern**: Coordinator polls for running jobs, waits, then starts fresh sync

---

## Implementation Steps

### Step 1: Create SQS FIFO Queue (template.yaml)

```yaml
SyncRequestQueue:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub '${AWS::StackName}-sync-requests.fifo'
    FifoQueue: true
    ContentBasedDeduplication: true
    # 5-minute dedup window (default)
    VisibilityTimeout: 300  # 5 min - enough for sync to complete
    MessageRetentionPeriod: 3600  # 1 hour
```

### Step 2: Create sync-coordinator Lambda

**Location:** `src/lambda/sync_coordinator/index.py`

**Logic:**
1. Receive SQS message (contains kb_id, ds_id)
2. Poll `list_ingestion_jobs` for IN_PROGRESS jobs
3. If running: wait with exponential backoff (max 5 min)
4. Start new ingestion job
5. Log success/failure

**Key code:**
```python
def lambda_handler(event, context):
    """Process sync request from SQS FIFO queue."""
    for record in event["Records"]:
        body = json.loads(record["body"])
        kb_id = body["kb_id"]
        ds_id = body["ds_id"]
        
        # Wait for any running sync to complete
        wait_for_sync_completion(kb_id, ds_id, max_wait=300)
        
        # Start new sync
        bedrock_agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
        )
```

**template.yaml addition:**
```yaml
SyncCoordinatorFunction:
  Type: AWS::Serverless::Function
  Properties:
    FunctionName: !Sub '${AWS::StackName}-sync-coordinator'
    CodeUri: src/lambda/sync_coordinator/
    Handler: index.lambda_handler
    Runtime: python3.13
    Timeout: 600  # 10 min - allows waiting for long syncs
    MemorySize: 256
    ReservedConcurrentExecutions: 1  # CRITICAL: prevents race conditions
    Environment:
      Variables:
        LOG_LEVEL: INFO
    Events:
      SQSEvent:
        Type: SQS
        Properties:
          Queue: !GetAtt SyncRequestQueue.Arn
          BatchSize: 1  # Process one at a time
    Policies:
      - Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Action:
              - bedrock:StartIngestionJob
              - bedrock:ListIngestionJobs
              - bedrock:GetIngestionJob
            Resource: '*'
```

### Step 3: Update process-image Lambda

**Change:** Replace `start_ingestion_with_retry()` call with SQS message send.

**Before:**
```python
ingestion_response = start_ingestion_with_retry(kb_id, ds_id)
```

**After:**
```python
sqs.send_message(
    QueueUrl=os.environ["SYNC_REQUEST_QUEUE_URL"],
    MessageBody=json.dumps({"kb_id": kb_id, "ds_id": ds_id}),
    MessageGroupId="sync-requests",  # All sync requests in same group
)
```

**template.yaml changes:**
- Add `SYNC_REQUEST_QUEUE_URL` env var to ProcessImageFunction
- Add SQS SendMessage policy

### Step 4: Consider other Lambdas that start syncs

Review these Lambdas that also call `start_ingestion_with_retry`:
- `ingest_to_kb` - document ingestion
- `ingest_media` - media ingestion

Options:
1. Update all to use SQS queue (consistent)
2. Keep as-is since they're less concurrent (documents processed serially)

**Recommendation:** Start with process-image only, expand if needed.

---

## Files to Create/Modify

### New Files
- `src/lambda/sync_coordinator/index.py` (~100 lines)

### Modified Files
- `template.yaml`: Add queue + Lambda + env vars + policies
- `src/lambda/process_image/index.py`: Replace sync call with SQS send

---

## Testing Plan

1. Deploy stack
2. Upload 5 images rapidly via API
3. Verify:
   - All images get metadata written to S3
   - Only 1-2 sync jobs run (not 5)
   - All images searchable after sync completes
4. Check CloudWatch logs for sync-coordinator

---

## Rollback Plan

If issues arise:
1. Revert process-image to call `start_ingestion_with_retry` directly
2. Delete SyncCoordinatorFunction and SyncRequestQueue from template
3. Redeploy

The old behavior (with occasional ConflictException) is still functional - just requires manual sync trigger.
