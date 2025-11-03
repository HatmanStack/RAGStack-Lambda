# RAGStack-Lambda Architecture

## Overview

RAGStack-Lambda is a serverless document processing pipeline that transforms unstructured documents into searchable knowledge using AWS managed services. The system extracts text via OCR, generates semantic embeddings, and indexes them in an Amazon Bedrock Knowledge Base for natural language search.

### Key Capabilities

- **Multi-format Support**: PDF, images, Office documents, text files, eBooks
- **Dual OCR Backends**: AWS Textract (cost-effective) or Bedrock (multimodal)
- **Intelligent Routing**: Automatic text-native PDF detection to skip unnecessary OCR
- **Multimodal Embeddings**: Both text and image embeddings for comprehensive search
- **Managed Vector Storage**: S3-based vectors with Bedrock Knowledge Base
- **Web Interface**: React UI for document management and search
- **One-Click Deployment**: Automated deployment via AWS SAM

### Design Principles

1. **Serverless-First**: No infrastructure to manage, auto-scaling, pay-per-use
2. **Cost-Optimized**: S3 vectors instead of OpenSearch, text-native PDF detection
3. **Secure by Default**: Encryption at rest/transit, least-privilege IAM, Cognito auth
4. **Developer-Friendly**: SAM for deployment, local testing, clear separation of concerns

## Table of Contents

- [Overview](#overview)
- [Architecture Decision Records (ADRs)](#architecture-decision-records-adrs)
- [Architecture Diagram](#architecture-diagram)
- [Components](#components)
- [Runtime Configuration System](#runtime-configuration-system)
- [Data Flow](#data-flow)
- [Security](#security)
- [Scalability](#scalability)
- [Monitoring](#monitoring)
- [Cost Optimization](#cost-optimization)

---

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
python publish.py --project-name <project-name> --admin-email <email> --region <region>

# 5. Run integration tests
pytest tests/integration/ --stack-name RAGStack-<project-name>

# 6. Deploy to production
python publish.py --project-name <project-name> --admin-email <email> --region <region>
```

**Environment Configuration:**
`samconfig.toml` contains dev and prod environment configurations with stack names, regions, and parameter overrides.

---

### ADR-008: Hardcode Embedding Models

**Status:** Accepted

**Context:**
The system originally allowed runtime configuration of embedding models through the Settings UI. When users changed embedding models, the system had to re-process all documents to generate new embeddings. This required:
- Complex change detection logic
- Re-embedding job tracking in DynamoDB
- GraphQL mutations for triggering re-embedding
- UI components for warning users and showing progress
- Document count queries
- Step Functions orchestration for bulk re-processing

**Decision:**
Remove embedding model configuration entirely. Hardcode embedding models in the `generate_embeddings` Lambda function:
- Text embeddings: `amazon.titan-embed-text-v2:0`
- Image embeddings: `amazon.titan-embed-image-v1`

Remove all re-embedding infrastructure, including:
- `getDocumentCount`, `reEmbedAllDocuments`, `getReEmbedJobStatus` GraphQL operations
- Re-embedding job tracking in DynamoDB
- Embedding change detection in Settings UI
- Re-embedding progress indicators

**Consequences:**
- ✅ Simpler configuration system (3 fields instead of 5)
- ✅ No risk of accidental embedding changes
- ✅ ~500 lines of code removed
- ✅ No re-embedding infrastructure needed
- ✅ Clearer user experience
- ⚠️ Users cannot experiment with different embedding models through UI
- ⚠️ Changing models requires code changes and redeployment

**Rationale:**
Default Titan models are production-ready for 95% of use cases. The complexity cost of runtime configurability outweighs the flexibility benefit.

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

| Function | Purpose | Timeout | Memory | Triggers |
|----------|---------|---------|--------|----------|
| ProcessDocument | OCR, format conversion, text extraction | 15 min | 3008 MB | Step Functions |
| GenerateEmbeddings | Generate text/image embeddings | 15 min | 2048 MB | Step Functions |
| QueryKB | Query Knowledge Base | 60 sec | 512 MB | AppSync GraphQL |
| AppSyncResolvers | Handle GraphQL queries/mutations | 30 sec | 512 MB | AppSync GraphQL |
| KBCustomResource | One-time KB setup (CloudFormation) | 15 min | 512 MB | CloudFormation |

**ProcessDocument Details:**
- Detects document format (PDF, image, Office, text)
- Converts Office docs to PDF using LibreOffice
- Checks if PDF is text-native (extractable text)
- Routes to direct text extraction or OCR based on content
- Extracts embedded images from PDFs
- Saves processed results to S3 Output bucket
- Updates DynamoDB tracking with progress

**GenerateEmbeddings Details:**
- Reads extracted text from S3
- Batches text into chunks (300 tokens, 15% overlap)
- Generates text embeddings via Titan Embed Text V2
- Generates image embeddings via Titan Embed Image
- Implements batch processing for >20 pages
- Rate limiting (2s delay between batches)
- Saves embeddings to S3 Vectors bucket

**QueryKB Details:**
- Receives natural language query from UI
- Invokes Bedrock Knowledge Base retrieve API
- Returns top-k results with source references
- Includes relevance scores and document metadata

**AppSyncResolvers Details:**
- `getDocument`: Fetch document details from DynamoDB
- `listDocuments`: List all documents with pagination
- `createUploadUrl`: Generate S3 presigned URL for uploads
- `queryKnowledgeBase`: Proxy to QueryKB function
- All resolvers enforce Cognito authentication

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

---

## Runtime Configuration System

The runtime configuration system allows users to modify operational parameters (OCR backends, embedding models, response models) through a WebUI Settings page without redeploying the CloudFormation stack.

### Overview

Traditional AWS deployments require stack updates (via `sam deploy` or CloudFormation) to change Lambda environment variables. This process takes 10-15 minutes and disrupts experimentation. The runtime configuration system stores configuration in DynamoDB, allowing Lambda functions to read parameters at invocation time for immediate changes.

### Components

#### ConfigurationTable (DynamoDB)

**Design**: Single-table design with partition key `Configuration`

**Three Item Types**:

| Type | Purpose | Writable | Seeded By |
|------|---------|----------|-----------|
| **Schema** | Defines available parameters, validation rules, UI metadata | Read-only | CloudFormation → publish.py |
| **Default** | System default values | Read-only | publish.py during deployment |
| **Custom** | User-overridden values | Read-write | Settings UI via GraphQL |

**Schema Format** (JSON Schema with UI extensions):
```json
{
  "properties": {
    "ocr_backend": {
      "type": "string",
      "enum": ["textract", "bedrock"],
      "description": "OCR Backend",
      "order": 1
    },
    "bedrock_ocr_model_id": {
      "type": "string",
      "enum": ["claude-3-5-haiku", "claude-3-5-sonnet", "claude-3-opus"],
      "description": "Bedrock OCR Model",
      "order": 2,
      "dependsOn": {
        "field": "ocr_backend",
        "value": "bedrock"
      }
    }
  }
}
```

**Effective Configuration**: Custom values override Default values (merge semantics)

#### ConfigurationManager (Python Library)

**Location**: `lib/ragstack_common/config.py`

**Key Methods**:
- `get_effective_config()` - Merges Custom → Default, returns effective configuration
- `get_parameter(param_name)` - Convenience method to get a single parameter
- `update_custom_config(custom_config)` - Updates Custom configuration (used by resolver)
- `get_schema()` - Returns Schema configuration

**Design Decision - No Caching**:
```python
def get_effective_config(self):
    """NO CACHING: Reads from DynamoDB on every call"""
    default_config = self.get_configuration_item('Default')
    custom_config = self.get_configuration_item('Custom')
    return {**default_config, **custom_config}
```

**Rationale**:
- Changes take effect immediately (within milliseconds)
- DynamoDB read latency ~0.25ms (negligible vs. 1-15 minute Lambda execution)
- Eliminates cache invalidation complexity
- Predictable behavior (no stale values)

**Cost Impact**: ~$0.25 per million reads (minimal)

#### ConfigurationResolver Lambda

**Location**: `src/lambda/configuration_resolver/index.py`

**Purpose**: GraphQL resolver for configuration operations

**Operations**:

| Operation | Type | Description | Returns |
|-----------|------|-------------|---------|
| `getConfiguration` | Query | Returns Schema, Default, Custom configs | `ConfigurationResponse` |
| `updateConfiguration` | Mutation | Updates Custom configuration | `Boolean` |

**Permissions**:
- DynamoDB: GetItem, PutItem, UpdateItem on ConfigurationTable

#### Settings UI Component

**Location**: `src/ui/src/components/Settings/index.jsx`

**Features**:
1. **Dynamic Form Rendering**: Reads Schema and generates form fields (3 configurable fields)
2. **Conditional Fields**: `dependsOn` pattern hides/shows fields based on other field values
3. **Validation Indicators**: Shows which fields are customized from defaults

**Configurable Fields**:
- `ocr_backend`: OCR engine selection (Textract or Bedrock)
- `bedrock_ocr_model_id`: Claude model for Bedrock OCR (conditional on OCR backend)
- `chat_model_id`: Model for Knowledge Base query responses

**State Management**:
```javascript
const [schema, setSchema] = useState({});           // Schema from DynamoDB
const [defaultConfig, setDefaultConfig] = useState({}); // Default values
const [customConfig, setCustomConfig] = useState({});   // Custom overrides
const [formValues, setFormValues] = useState({});       // Current form state
```

**Dynamic Rendering Example**:
```javascript
// Conditional field visibility
if (property.dependsOn) {
  const depField = property.dependsOn.field;
  const depValue = property.dependsOn.value;
  if (formValues[depField] !== depValue) {
    return null; // Hide this field
  }
}
```

### Data Flow

#### Configuration Read (Lambda Invocation)

```
┌──────────────┐
│   Lambda     │
│  Invoked     │
└──────┬───────┘
       │
       │ 1. Import ConfigurationManager
       ▼
┌──────────────────────┐
│ ConfigurationManager │
│ .get_parameter()     │
└──────┬───────────────┘
       │
       │ 2. Read from DynamoDB (no cache)
       ▼
┌─────────────────────┐      ┌─────────────────────┐
│ Get "Default" item  │      │ Get "Custom" item   │
│ from DynamoDB       │      │ from DynamoDB       │
└──────┬──────────────┘      └──────┬──────────────┘
       │                            │
       │ 3. Merge Custom → Default
       └─────────────┬──────────────┘
                     ▼
            ┌────────────────┐
            │ Return merged  │
            │ configuration  │
            └────────────────┘
```

**Latency**: ~0.5ms DynamoDB read + ~0.1ms merge = **~0.6ms overhead**

#### Configuration Write (Settings UI)

```
┌──────────────┐
│   User       │
│ Changes OCR  │
│ Backend      │
└──────┬───────┘
       │
       │ 1. Click "Save changes"
       ▼
┌──────────────────────┐
│ Settings UI          │
│ .handleSave()        │
└──────┬───────────────┘
       │
       │ 2. GraphQL mutation
       ▼
┌──────────────────────┐
│ updateConfiguration  │
│ mutation             │
└──────┬───────────────┘
       │
       │ 3. Call ConfigurationResolver Lambda
       ▼
┌──────────────────────┐
│ ConfigurationResolver│
│ .handle_update()     │
└──────┬───────────────┘
       │
       │ 4. Write Custom config to DynamoDB
       ▼
┌──────────────────────┐
│ DynamoDB PutItem     │
│ Configuration=Custom │
└──────────────────────┘
```


### Design Decisions

#### ADR: No Configuration Caching

**Decision**: Lambda functions read configuration from DynamoDB on every invocation, with no caching.

**Rationale**:
- **Immediate Consistency**: Changes take effect on next invocation (~milliseconds)
- **Simplicity**: No cache invalidation logic
- **Low Overhead**: DynamoDB reads ~0.25ms, negligible vs. OCR/embedding operations
- **Predictability**: No stale cached values

**Trade-offs**:
- Additional DynamoDB read cost (~$1.25 per million reads)
- +0.6ms latency per invocation
- No cache warming needed

#### ADR: Backend-Only Validation

**Decision**: Settings UI does NOT validate configuration values; only ConfigurationResolver Lambda enforces validation.

**Rationale**:
- **Single Source of Truth**: Validation logic in one place
- **Security**: UI can be bypassed via direct GraphQL calls
- **Simplicity**: No duplicated validation in JavaScript
- **Flexibility**: Schema changes only require backend updates

**Trade-offs**:
- User sees validation errors after submission (round-trip)
- Poorer UX compared to client-side validation
- Acceptable trade-off for security and maintainability

**Mitigation**: UI uses Schema enums for dropdowns (better UX, prevents common errors)

#### ADR: Schema in CloudFormation

**Decision**: Schema is defined in template.yaml and seeded via publish.py, not editable via UI.

**Rationale**:
- **Infrastructure as Code**: Schema version-controlled with infrastructure
- **Deployment Safety**: Schema changes require review and deployment
- **Consistency**: Ensures Schema matches deployed Lambda expectations

**Trade-offs**:
- Adding new models requires template update + redeploy
- Less flexible than editable Schema
- Acceptable for infrequent Schema changes

#### ADR: No Admin Restrictions

**Decision**: All authenticated users can read and write configuration (no RBAC).

**Rationale**:
- **Simplicity**: No role-based access control implementation
- **MVP Scope**: Admin-only restrictions can be added post-MVP
- **Trust Model**: Assumes authorized users are trusted
- **Single-Team Use Case**: Suitable for single-team deployments

**Trade-offs**:
- Not suitable for multi-tenant environments
- Could add Cognito Groups-based RBAC later if needed

### Performance Characteristics

**Configuration Read Latency** (per Lambda invocation):
- DynamoDB GetItem (Default): ~0.25ms
- DynamoDB GetItem (Custom): ~0.25ms
- Python merge operation: ~0.1ms
- **Total overhead**: ~0.6ms

**Configuration Write Latency** (Settings UI save):
- GraphQL mutation: ~50ms (including auth)
- Lambda cold start: ~500ms (first time)
- Lambda warm: ~100ms
- DynamoDB PutItem: ~10ms
- **Total**: ~160ms (warm), ~560ms (cold)

**Re-embedding Job**:
- Document query (StatusIndex GSI): ~50-200ms (depends on document count)
- Step Functions trigger loop: ~100ms per document (synchronous)
- **Limit**: 500 documents per job (to prevent Lambda timeout)
- **Scalability Note**: For >500 documents, use SQS + Lambda consumer pattern

### Failure Modes

#### ConfigurationTable Unavailable

**Symptom**: Lambda functions fail immediately

**Behavior**:
- `ConfigurationManager.__init__()` raises `ValueError` if table name not set
- Lambdas fail with clear error: "Configuration table name not provided"
- No fallback to environment variables (by design)

**Recovery**: Fix CloudFormation environment variables, redeploy

#### ConfigurationTable Empty

**Symptom**: Lambdas fail with missing configuration

**Behavior**:
- `get_effective_config()` returns empty dict
- Lambda code expects specific keys (e.g., `ocr_backend`)
- KeyError raised when accessing missing config

**Recovery**: Run `publish.py` to seed Default configuration

#### Re-embedding Job Stuck

**Symptom**: Job shows IN_PROGRESS indefinitely

**Causes**:
- Step Functions executions failed
- GenerateEmbeddings Lambda errors
- Job progress update failed

**Recovery**:
1. Check Step Functions console for failed executions
2. Review CloudWatch logs for GenerateEmbeddings errors
3. Manually update job status:
   ```bash
   aws dynamodb update-item \
     --table-name RAGStack-<project>-Configuration \
     --key '{"Configuration": {"S": "ReEmbedJob#<job-id>"}}' \
     --update-expression "SET #status = :status" \
     --expression-attribute-names '{"#status": "status"}' \
     --expression-attribute-values '{":status": {"S": "COMPLETED"}}'
   ```

---

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
2. **S3 Vectors** - Cheaper than OpenSearch Serverless ($0.023/GB vs $0.24/GB)
3. **S3 lifecycle policies** - Auto-delete old files after 7 days
4. **DynamoDB on-demand** - Pay per request, no idle costs
5. **CloudFront** - Reduce origin requests, lower data transfer costs
6. **Textract vs Bedrock** - Use Textract for most documents ($1.50 vs $25-75 per 1000 pages)
7. **Lambda memory optimization** - Right-size memory for cost/performance balance

See [Configuration Guide](CONFIGURATION.md) for cost optimization settings.

---

## Technology Stack

### AWS Services Used

| Service | Purpose | Why Chosen |
|---------|---------|------------|
| **AWS SAM** | Infrastructure as Code | Simpler than raw CloudFormation, local testing |
| **Lambda** | Serverless compute | Auto-scaling, pay-per-use, no servers to manage |
| **Step Functions** | Workflow orchestration | Visual workflows, error handling, retries |
| **S3** | Object storage | Unlimited scale, low cost, durable |
| **DynamoDB** | NoSQL database | Serverless, on-demand pricing, fast |
| **Textract** | OCR service | Purpose-built for documents, cost-effective |
| **Bedrock** | LLM and embeddings | Latest models, no infrastructure, pay-per-use |
| **AppSync** | GraphQL API | Real-time updates, Cognito integration |
| **Cognito** | Authentication | Managed user pools, MFA, password policies |
| **CloudFront** | CDN | HTTPS, global distribution, low latency |
| **EventBridge** | Event routing | Serverless pub/sub, loose coupling |
| **CloudWatch** | Monitoring & logs | Centralized logging, metrics, alarms |

### Third-Party Libraries

| Library | Purpose | Used In |
|---------|---------|---------|
| **PyMuPDF** | PDF text extraction | ProcessDocument Lambda |
| **Pillow** | Image processing | ProcessDocument Lambda |
| **boto3** | AWS SDK for Python | All Lambda functions |
| **React** | UI framework | Web interface |
| **CloudScape** | UI components | Web interface |
| **Amplify** | AWS integration | Web interface |

---

## Performance Characteristics

### Throughput

- **Upload rate**: Limited by Cognito (10k requests/second)
- **Processing rate**: Limited by Lambda concurrency (default: 1000)
- **Textract concurrency**: Default 20, can request increase
- **Bedrock rate limits**: Varies by model (check quotas)
- **DynamoDB**: Unlimited (on-demand mode)
- **S3**: Unlimited

### Latency

Typical processing times for a 10-page PDF document:

| Stage | Duration | Bottleneck |
|-------|----------|------------|
| Upload to S3 | <5 seconds | Network bandwidth |
| ProcessDocument | 20-40 seconds | OCR processing |
| GenerateEmbeddings | 10-20 seconds | Bedrock API calls |
| KB Sync | 2-10 minutes | Knowledge Base indexing |
| **Total** | **3-12 minutes** | First-time KB sync |

**Optimization tips:**
- Text-native PDFs: 50% faster (skip OCR)
- Smaller documents: Linear scaling
- Subsequent syncs: Faster (incremental indexing)

### Scalability Limits

| Resource | Limit | Mitigation |
|----------|-------|------------|
| Lambda concurrency | 1000 (default) | Request quota increase |
| Textract concurrency | 20 (default) | Request quota increase |
| S3 bucket count | 100 (soft limit) | Use lifecycle policies |
| DynamoDB tables | 256 per region | Adequate for this solution |
| Cognito users | 40M per pool | Adequate for most use cases |

---

## Related Documentation

For more information about specific aspects of the system:

- **[Deployment Guide](DEPLOYMENT.md)** - How to deploy and configure the system
- **[Configuration Guide](CONFIGURATION.md)** - Available configuration options and optimization
- **[User Guide](USER_GUIDE.md)** - How to use the web interface
- **[Testing Guide](TESTING.md)** - How to test the system end-to-end
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions

For implementation details:

- **`template.yaml`** - CloudFormation infrastructure definition
- **`lib/ragstack_common/`** - Shared libraries (OCR, storage, embeddings)
- **`src/lambda/`** - Lambda function implementations
- **`src/ui/`** - React web interface source code
