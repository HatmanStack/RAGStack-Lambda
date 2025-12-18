# Architecture

## System Design

```
Upload → OCR → Embeddings → Bedrock KB
                                ↓
        UI/Chat ←→ Query Bedrock KB
```

**Principles:**
- Serverless (auto-scaling, no servers)
- Cost-optimized (S3 vectors ~$1/mo vs OpenSearch $50+/mo)
- Production-ready (error handling, monitoring)

## Components

| Component | Purpose |
|-----------|---------|
| ProcessDocument Lambda | OCR extraction (Textract/Bedrock) |
| GenerateEmbeddings Lambda | Create embeddings (Titan) |
| QueryKB Lambda | Query documents (used by chat) |
| Step Functions | Orchestrate workflow |
| Bedrock KB | Vector storage & retrieval |
| S3 | File storage |
| DynamoDB | Metadata & config |
| AppSync | GraphQL API |
| React UI | Web interface |
| Amplify Chat | AI chat (optional) |

## Data Flow

1. **Upload:** User → S3 → EventBridge → ProcessDocument
2. **Processing:** ProcessDocument → GenerateEmbeddings → IngestToKB → Bedrock KB
3. **Chat:** User → AppSync → QueryKB → Bedrock KB → Results

## Architecture Decisions

**Why SAM?** Local testing, simpler Lambda packaging

**Why S3 vectors?** ~$1/month vs $50+/month for OpenSearch

**Why DynamoDB config?** Changes apply immediately, no redeployment

**Why shared library?** `lib/ragstack_common/` eliminates duplication

**Error handling:** 3-tier (Lambda retry → Bedrock retry → DLQ)

## Optional: Amplify Chat

Core (SAM) provides document processing. Optional Amplify adds chat interface.

```
        Bedrock KB
            ↑
     ┌──────┴──────┐
     │             │
  SAM(Core)  Amplify(Chat)
```

Deploy:
```bash
python publish.py --project-name myapp --admin-email admin@example.com
```

See [RAGSTACK_CHAT.md](RAGSTACK_CHAT.md)

## Security

- HTTPS/TLS everywhere
- S3 SSE, DynamoDB encryption
- Cognito auth + optional MFA
- Lambda Authorizer validates JWT tokens for chat API
- Least-privilege IAM
- Public S3 blocked

## Performance

**10-page PDF:**
- Upload: <5 sec
- OCR: 2-15 min
- Embeddings: 1-5 min
- KB Sync: 1-10 min

**Optimization:**
- Text-native PDFs: 50% faster (skip OCR)
- Smaller docs: scales linearly

## Cost

1000 docs/month (5 pages each):
- Textract + Haiku: **$7-18/month**
- Bedrock OCR + Haiku: **$25-75/month**

See [Configuration](CONFIGURATION.md)

## Stack

- **Infrastructure:** SAM, Lambda, Step Functions
- **Storage:** S3, DynamoDB, Bedrock KB
- **APIs:** AppSync, Bedrock, Textract
- **Frontend:** React 19, Vite, Amplify, Cloudscape
