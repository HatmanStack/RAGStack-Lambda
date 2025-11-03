# Architecture Overview

## System Design

RAGStack-Lambda is a serverless document processing pipeline on AWS:

```
Document Upload → Process (OCR) → Generate Embeddings → Bedrock KB
                                                          ↓
                         Search Interface (React) ←→ Query Bedrock
```

**Key Principles:**
- **Serverless**: No servers to manage, auto-scaling
- **Cost-optimized**: S3 vectors ($1/mo) vs OpenSearch ($50+/mo)
- **Modular**: Independent, reusable components
- **Production-ready**: Error handling, monitoring, security

## Core Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **ProcessDocument Lambda** | OCR extraction | Textract or Bedrock |
| **GenerateEmbeddings Lambda** | Create embeddings | Bedrock Titan Embed |
| **QueryKB Lambda** | Search documents | Bedrock RetrieveAndGenerate |
| **Step Functions** | Orchestrate workflow | AWS Step Functions |
| **Bedrock KB** | Vector storage & search | Amazon Bedrock |
| **S3** | File storage | AWS S3 |
| **DynamoDB** | Metadata tracking | AWS DynamoDB |
| **AppSync** | GraphQL API | AWS AppSync |
| **React UI** | Web interface | React + Cloudscape |

## Data Flow

### 1. Document Upload
User uploads file → S3 → EventBridge rule triggers → ProcessDocument Lambda

### 2. Processing Pipeline
```
ProcessDocument
  ↓ (extract text via OCR)
GenerateEmbeddings
  ↓ (create vectors)
IngestToKB
  ↓ (index vectors)
Bedrock Knowledge Base
```

### 3. Search
User query → AppSync → QueryKB Lambda → Bedrock KB → Results + Sources

## Architecture Decisions

### ADR-001: Use SAM Instead of Raw CloudFormation
**Decision:** Use AWS SAM for all Lambda deployments

**Rationale:**
- ✅ Simpler Lambda packaging
- ✅ Local testing with `sam local invoke`
- ✅ Better developer experience
- ✅ Built-in best practices

**Trade-off:** Requires SAM CLI installation

---

### ADR-002: S3-Based Vector Storage
**Decision:** Store embeddings in S3 with Bedrock Knowledge Base

**Rationale:**
- ✅ Cost-effective: ~$1/month vs $50+/month for OpenSearch
- ✅ Serverless (no infrastructure)
- ✅ Supports both text and image embeddings
- ✅ Integrates with Bedrock KB

---

### ADR-003: DynamoDB Configuration Management
**Decision:** Runtime configuration stored in DynamoDB (no caching)

**Structure:**
- **Schema**: Parameter definitions (read-only)
- **Default**: System defaults (read-only)
- **Custom**: User overrides (read-write)

**Benefits:**
- ✅ Changes take effect immediately
- ✅ No redeployment needed
- ✅ Audit trail via DynamoDB
- ✅ Supports Settings UI

---

### ADR-004: Shared Library Pattern
**Decision:** All Lambdas import from `lib/ragstack_common/`

**Implementation:**
- Package installed via `pip` during SAM build
- Centralizes OCR, storage, embeddings logic
- Eliminates code duplication

---

### ADR-005: Error Handling Strategy
**Decision:** Three-tier error handling

**Tier 1: Lambda Retry (built-in)**
- Step Functions retries failed invocations
- Exponential backoff: 2s, 4s, 8s
- Max 3 attempts

**Tier 2: Application Retry**
- Bedrock client has built-in retry (max 7 attempts)
- Handles throttling automatically

**Tier 3: Dead Letter Queue**
- Failed executions sent to SQS
- CloudWatch alarms on failures
- Manual review for persistent errors

---

### ADR-006: Local Development
**Decision:** Use SAM local + Docker for offline development

**Workflow:**
1. `sam build` - package functions
2. `sam local invoke` - test Lambdas
3. `npm test` - unit tests (no AWS needed)
4. `python publish.py` - deploy to AWS

---

## Optional: Amplify Chat Integration

Core system (SAM) provides search. Optional Amplify stack adds chat.

```
                    Bedrock Knowledge Base
                           ↑
                    ┌──────┴──────┐
                    │             │
              ┌─────▼──┐    ┌────▼──┐
              │ SAM    │    │Amplify│
              │(Search)│    │(Chat) │
              └────────┘    └───────┘
```

**Amplify Stack Features:**
- Chat interface with Claude
- Source attribution
- Multi-turn conversations
- Shared Bedrock KB
- Independent deployment/updates

**Setup:**
```bash
# Deploy SAM core first
python publish.py --project-name myapp ...

# Then deploy chat (optional)
cd amplify/
export BEDROCK_KB_ID="<from-SAM-outputs>"
npx amplify publish
```

See [AMPLIFY_CHAT.md](AMPLIFY_CHAT.md) for details.

## Security

| Layer | Implementation |
|-------|----------------|
| **Authentication** | Cognito user pool with MFA optional |
| **Encryption (transit)** | HTTPS/TLS everywhere (AppSync, CloudFront, S3) |
| **Encryption (rest)** | S3 SSE, DynamoDB encryption, RDS encryption |
| **IAM** | Least-privilege policies per Lambda |
| **S3 Access** | Public access blocked, bucket policies |
| **CloudFront** | HTTPS-only, custom error pages |

## Performance

### Latency for 10-Page PDF

| Stage | Duration | Bottleneck |
|-------|----------|-----------|
| Upload to S3 | <5 sec | Network |
| OCR Processing | 2-15 min | OCR service (Textract/Bedrock) |
| Embeddings | 1-5 min | Bedrock API |
| KB Sync | 1-10 min | Knowledge Base indexing |
| **Total** | **5-30 min** | First-time KB sync |

**Optimization Tips:**
- Text-native PDFs: 50% faster (skip OCR)
- Smaller documents: scales linearly
- Subsequent syncs: faster (incremental)

### Scalability Limits

| Resource | Default | Mitigation |
|----------|---------|-----------|
| Lambda concurrency | 1000 | Request quota increase |
| Textract concurrency | 20 | Request quota increase |
| S3 throughput | Unlimited | N/A |
| DynamoDB (on-demand) | Unlimited | N/A |
| Bedrock rate limits | Varies by model | Service Quotas page |

## Cost Optimization

**OCR Choice** (biggest impact):
- Textract: $1.50 per 1000 pages (default, cheaper)
- Bedrock: $0.75 per 1000 pages (multimodal, more expensive upfront)

**Model Choice:**
- Haiku: ~$0.80 per 1M input tokens (cheap, capable)
- Opus: ~$15 per 1M input tokens (expensive, most capable)

**Storage:**
- Delete old extracted text (80% of S3 cost)
- Use S3 lifecycle policies (auto-delete after 7 days)

**Estimated Monthly Cost** (~1000 docs/month):
- Textract + Haiku: **$7-18/month**
- Bedrock OCR + Haiku: **$25-75/month**

See [Configuration](CONFIGURATION.md) and [Optimization](OPTIMIZATION.md) for details.

## Technology Stack

| Layer | Technologies |
|-------|---------------|
| **Infrastructure** | AWS SAM, CloudFormation, Lambda, Step Functions |
| **Storage** | S3, DynamoDB, Bedrock KB |
| **APIs** | AppSync GraphQL, Bedrock API, Textract API |
| **OCR** | Textract or Bedrock Claude |
| **Embeddings** | Amazon Titan Embed |
| **Frontend** | React 19, Vite, AWS Amplify, Cloudscape |
| **IaC** | SAM template.yaml |

## Related Documentation

- [Deployment Guide](DEPLOYMENT.md) - How to deploy
- [Configuration Guide](CONFIGURATION.md) - Runtime settings
- [Development Guide](DEVELOPMENT.md) - Development patterns
- [Testing Guide](TESTING.md) - Test structure
- [User Guide](USER_GUIDE.md) - How to use
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
