# RAGStack-Lambda Architecture

## Overview

RAGStack-Lambda is a serverless document processing pipeline that extracts text from documents using OCR, generates embeddings, and indexes them in a Bedrock Knowledge Base for semantic search.

## Architecture Decision Records (ADRs)

### ADR-001: Use SAM Instead of Raw CloudFormation

**Status:** Accepted

**Context:**
- Need to deploy Lambda functions with dependencies
- Want local testing capability
- Original plan mixed SAM and CloudFormation

**Decision:**
Use AWS SAM for entire deployment (not raw CloudFormation).

**Consequences:**
- Simpler Lambda packaging
- Built-in local testing with `sam local`
- Better developer experience
- Must use `sam deploy` instead of `aws cloudformation deploy`

**Implementation:**
- Use `AWS::Serverless::Function` for all Lambdas
- Use `sam build` to package dependencies
- Use `sam local invoke` for testing

---

### ADR-002: Bedrock Knowledge Base with S3 Vectors (Simplified)

**Status:** Accepted with Modifications

**Context:**
- Parent project has 1,108-line KB template
- Supports both OpenSearch Serverless and S3 Vectors
- Has web crawler, sync scheduling, encryption
- RAGStack-Lambda needs simpler version

**Decision:**
Use **manual Knowledge Base creation** for MVP, not custom resource.

**Rationale:**
1. **Complexity:** Parent project's custom resource is 300+ lines
2. **S3 Vectors API:** Requires special `s3vectors:*` permissions not in standard IAM
3. **Bedrock Agent Limitations:** KB creation via CloudFormation is limited
4. **Time-to-value:** Manual setup faster for MVP

**Implementation Plan:**

**Option A: Manual KB Setup (RECOMMENDED FOR MVP)**
1. Deploy stack WITHOUT Knowledge Base resource
2. Manually create KB via AWS Console:
   - Go to Bedrock > Knowledge Bases > Create
   - Choose S3 as data source
   - Point to vector bucket
   - Configure chunking (300 tokens, 15% overlap)
3. Store KB ID in Parameter Store
4. Update Lambda environment variables with KB ID

**Option B: CloudFormation Custom Resource (Production)**
- Use parent project's approach (copy from options/bedrockkb/)
- Requires 300-500 additional lines of code
- Implement in Phase 3.4 (expanded)

**For MVP, use Option A.**

---

### ADR-003: Embedding Generation Strategy

**Status:** Accepted

**Context:**
- Lambda has 15-minute timeout
- Large documents (100+ pages) may exceed timeout
- Bedrock has rate limits (varies by model)

**Decision:**
Implement **batch processing with pagination** for embedding generation.

**Implementation:**
1. If document has >20 pages, split into batches
2. Process batches sequentially with delay between
3. Use Step Functions to orchestrate batches
4. Store partial results in DynamoDB

**Code Pattern:**
```python
def generate_embeddings(pages):
    BATCH_SIZE = 20

    for i in range(0, len(pages), BATCH_SIZE):
        batch = pages[i:i+BATCH_SIZE]
        process_batch(batch)
        time.sleep(2)  # Rate limit protection
```

---

### ADR-004: Knowledge Base Data Ingestion Flow

**Status:** Accepted

**Context:**
Original plan unclear on how KB syncs new data.

**Decision:**
Use **EventBridge + Lambda** to trigger KB sync after embeddings are uploaded.

**Flow:**
1. GenerateEmbeddings Lambda writes embeddings to S3 vector bucket
2. S3 event triggers EventBridge rule
3. EventBridge invokes SyncKB Lambda
4. SyncKB Lambda calls Bedrock Agent API to sync data source
5. KB re-indexes automatically

**Implementation:**
Add new Lambda: `SyncKBFunction`
```python
import boto3
bedrock_agent = boto3.client('bedrock-agent')

def lambda_handler(event, context):
    kb_id = os.environ['KNOWLEDGE_BASE_ID']
    data_source_id = os.environ['DATA_SOURCE_ID']

    response = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=data_source_id
    )

    return {'jobId': response['ingestionJob']['ingestionJobId']}
```

---

### ADR-005: IAM Permissions Strategy

**Status:** Accepted

**Context:**
Original plan didn't specify all Lambda permissions.

**Decision:**
Use **least-privilege IAM policies** with specific resource ARNs.

**Example for ProcessDocument Lambda:**
```yaml
Policies:
  - S3ReadPolicy:
      BucketName: !Ref InputBucket
  - S3CrudPolicy:
      BucketName: !Ref OutputBucket
  - S3CrudPolicy:
      BucketName: !Ref WorkingBucket
  - DynamoDBCrudPolicy:
      TableName: !Ref TrackingTable
  - Statement:
      - Effect: Allow
        Action:
          - textract:DetectDocumentText
          - textract:AnalyzeDocument
        Resource: '*'  # Textract doesn't support resource-level permissions
      - Effect: Allow
        Action:
          - bedrock:InvokeModel
        Resource:
          - !Sub 'arn:aws:bedrock:${AWS::Region}::foundation-model/anthropic.claude-*'
          - !Sub 'arn:aws:bedrock:${AWS::Region}::foundation-model/amazon.titan-*'
      - Effect: Allow
        Action:
          - kms:Decrypt
          - kms:GenerateDataKey
        Resource: !Ref EncryptionKeyArn  # If using encryption
```

**All Lambda permissions detailed in Phase 3.**

---

### ADR-006: Error Handling Strategy

**Status:** Accepted

**Context:**
Need resilient processing with retries and error tracking.

**Decision:**
Implement **three-tier error handling:**

**Tier 1: Lambda Retry (Built-in)**
- Step Functions automatically retries failed Lambda invocations
- Exponential backoff: 2s, 4s, 8s
- Max 3 attempts

**Tier 2: Application Retry (Bedrock client)**
- BedrockClient has built-in retry with exponential backoff
- Max 7 attempts
- Handles throttling automatically

**Tier 3: Dead Letter Queue**
- Failed executions sent to SQS DLQ
- Manual review queue for persistent failures
- CloudWatch alarm on DLQ depth > 0

**Implementation:**
```yaml
ProcessDocumentFunction:
  Properties:
    DeadLetterQueue:
      Type: SQS
      TargetArn: !GetAtt ProcessingDLQ.Arn

ProcessingDLQ:
  Type: AWS::SQS::Queue
  Properties:
    MessageRetentionPeriod: 1209600  # 14 days

DLQAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    MetricName: ApproximateNumberOfMessagesVisible
    Namespace: AWS/SQS
    Statistic: Sum
    Period: 300
    EvaluationPeriods: 1
    Threshold: 1
    ComparisonOperator: GreaterThanThreshold
    Dimensions:
      - Name: QueueName
        Value: !GetAtt ProcessingDLQ.QueueName
```

---

### ADR-007: Development Workflow

**Status:** Accepted

**Context:**
Need local development and testing before AWS deployment.

**Decision:**
Use **SAM local with Docker** for development.

**Workflow:**
```bash
# 1. Local development
cd ~/RAGStack-Lambda
sam build

# 2. Test Lambda locally
sam local invoke ProcessDocumentFunction -e tests/events/process_document.json

# 3. Start local API
sam local start-api

# 4. Deploy to dev environment
./publish.sh --env dev

# 5. Run integration tests
pytest tests/integration/ --env dev

# 6. Deploy to production
./publish.sh --env prod
```

**Environment Configuration:**
`samconfig.toml` contains dev and prod environment configurations with stack names, regions, and parameter overrides.

---

## Architecture Diagram

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │ HTTPS
       ↓
┌─────────────────┐
│  CloudFront     │ (CDN + HTTPS)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   React UI      │ (S3 Static Hosting)
└────────┬────────┘
         │ GraphQL
         ↓
┌─────────────────┐
│  AppSync API    │ (GraphQL + Cognito Auth)
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────────────────────┐
│              Lambda Functions                    │
│  • ProcessDocument                               │
│  • GenerateEmbeddings                            │
│  • QueryKB                                       │
│  • AppSync Resolvers                             │
└─────┬──────────────┬─────────────┬──────────────┘
      │              │             │
      ↓              ↓             ↓
┌──────────┐  ┌─────────────┐  ┌────────────┐
│   S3     │  │ DynamoDB    │  │  Bedrock   │
│ Buckets  │  │  Tables     │  │            │
│          │  │             │  │ • OCR      │
│ • Input  │  │ • Tracking  │  │ • Embed    │
│ • Output │  │ • Metering  │  │ • KB       │
│ • Vectors│  │             │  │            │
│ • Working│  │             │  │            │
└──────────┘  └─────────────┘  └────────────┘
```

## Components

### Frontend

**React UI (CloudScape)**
- User authentication (Cognito)
- Document upload with drag-drop
- Processing status dashboard
- Knowledge Base search interface
- Built with CloudScape Design System
- Served via CloudFront for HTTPS

### API Layer

**AppSync GraphQL API**
- Authenticated via Cognito User Pool
- Resolvers implemented as Lambda functions
- Queries: getDocument, listDocuments, queryKnowledgeBase
- Mutations: createUploadUrl

### Processing Pipeline

**Step Functions State Machine**
Orchestrates document processing:

1. **ProcessDocument** → OCR and text extraction
2. **GenerateEmbeddings** → Text and image embeddings
3. **Mark as Indexed** → Final status update

**Lambda Functions:**

| Function | Purpose | Timeout | Memory |
|----------|---------|---------|--------|
| ProcessDocument | OCR, format conversion, text extraction | 15 min | 3008 MB |
| GenerateEmbeddings | Generate text/image embeddings | 15 min | 2048 MB |
| QueryKB | Query Knowledge Base | 60 sec | 512 MB |
| AppSyncResolvers | Handle GraphQL queries | 30 sec | 512 MB |

### Storage

**S3 Buckets:**
- **Input** - User uploads, triggers processing
- **Output** - Extracted text and images
- **Vectors** - Embeddings for Knowledge Base
- **Working** - Temporary files (auto-cleanup after 7 days)
- **UI** - Static website assets

**DynamoDB Tables:**
- **Tracking** - Document processing status
- **Metering** - Token usage and cost tracking

### Knowledge Base

**Amazon Bedrock Knowledge Base**
- Vector store: S3 Vectors (cost-optimized)
- Embedding model: Titan Embed Text V2
- Image embeddings: Titan Embed Image
- Chunking: Fixed-size, 300 tokens, 15% overlap

### Authentication

**Cognito:**
- User Pool for authentication
- Identity Pool for AWS credentials
- MFA optional
- Password policies enforced

## Data Flow

### Document Upload Flow

```
1. User drags PDF to UI
2. UI requests presigned URL from AppSync
3. AppSync Lambda creates tracking record
4. UI uploads directly to S3 input bucket
5. S3 event → EventBridge → Step Functions
6. Step Functions starts processing
```

### Processing Flow

```
1. ProcessDocument Lambda:
   - Download from S3 input bucket
   - Detect document type (PDF vs image vs Office)
   - Convert if needed (Office → PDF)
   - Check if PDF is text-native
   - If text-native: extract text directly (PyMuPDF)
   - If scanned: run OCR (Textract or Bedrock)
   - Extract embedded images
   - Save text + images to S3 output bucket
   - Update DynamoDB tracking

2. GenerateEmbeddings Lambda:
   - Read text from S3 output bucket
   - Generate text embedding (Titan Embed Text V2)
   - For each image:
     - Read image bytes
     - Generate image embedding (Titan Embed Image)
   - Save embeddings to S3 vector bucket
   - Update DynamoDB tracking

3. Knowledge Base Auto-Sync:
   - S3 vector bucket monitors for new files
   - Bedrock KB automatically indexes new embeddings
   - Document becomes searchable
```

### Search Flow

```
1. User enters query in UI
2. UI sends GraphQL query to AppSync
3. QueryKB Lambda invokes Bedrock Knowledge Base
4. KB performs vector similarity search
5. Returns top-k results with source references
6. UI displays results with relevance scores
```

## Security

- **Encryption at rest**: S3 SSE, DynamoDB encryption
- **Encryption in transit**: HTTPS/TLS everywhere
- **IAM**: Least-privilege policies for all resources
- **Cognito**: MFA optional, password policies enforced
- **S3**: Public access blocked
- **CloudFront**: HTTPS-only, OAI for S3 access
- **VPC**: Not required (all services are AWS-managed)

## Scalability

- **Concurrent uploads**: Limited by Cognito (default: 10k RPS)
- **Processing**: Limited by Lambda concurrency (default: 1000)
- **Textract**: Default 20 concurrent requests (can increase)
- **Bedrock**: Rate limits vary by model (see quotas)
- **DynamoDB**: On-demand scaling (no limits)
- **S3**: Unlimited scalability

## Monitoring

- **CloudWatch Logs**: All Lambda function logs
- **DynamoDB**: Document tracking and status
- **Metering**: Token usage tracked in DynamoDB
- **X-Ray**: Optional distributed tracing

Refer to Phase 7 for comprehensive monitoring setup with CloudWatch dashboards and alarms.

## Cost Optimization

1. **Text-native PDF detection** - Skip OCR when possible
2. **S3 Vectors** - Cheaper than OpenSearch Serverless
3. **S3 lifecycle policies** - Auto-delete old files
4. **DynamoDB on-demand** - Pay per request
5. **CloudFront** - Reduce origin requests
