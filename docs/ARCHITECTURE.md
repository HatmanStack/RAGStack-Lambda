# Architecture

## System Design

```
Upload → OCR → Bedrock KB (embeddings + indexing)
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
| GetPageInfo Lambda | Count pages, determine batching strategy |
| EnqueueBatches Lambda | Queue batch jobs to SQS |
| BatchProcessor Lambda | Process 10-page batches (max 10 concurrent) |
| CombinePages Lambda | Merge partial outputs into final document |
| IngestToKB Lambda | Trigger Bedrock KB ingestion (Nova Multimodal embeddings) |
| QueryKB Lambda | Query documents, chat with sources |
| ProcessImage Lambda | Image ingestion with captions |
| Scrape Lambdas | Web scraping pipeline (start/discover/process/status) |
| Step Functions | Orchestrate document/scrape workflows |
| Bedrock KB | Vector storage & retrieval (S3 backend) |
| S3 | File storage (input/, output/, images/) |
| DynamoDB | Document tracking, config, conversations, scrape jobs |
| AppSync | GraphQL API with subscriptions |
| React UI | Web dashboard (Cloudscape) |
| ragstack-chat | AI chat web component |

## Data Flow

### Document Processing

**Small documents (≤20 pages or text-native):**
1. **Upload:** User → S3 input/ → EventBridge → Step Functions
2. **OCR:** ProcessDocument extracts text → S3 output/
3. **Indexing:** IngestToKB → Bedrock KB

**Large documents (>20 pages, requires OCR):**
1. **Upload:** User → S3 input/ → EventBridge → Step Functions
2. **Page Info:** GetPageInfo counts pages, creates 10-page batches
3. **Queue:** EnqueueBatches → SQS batch queue
4. **Process:** BatchProcessor Lambda (max 10 concurrent) → partial files
5. **Combine:** Last batch triggers CombinePages → merged output
6. **Indexing:** IngestToKB → Bedrock KB

**95% threshold:** Ingestion proceeds if ≥95% of pages processed successfully. Failed batches retry 3x before DLQ.

### Web Scraping
1. **Start:** User → AppSync → ScrapeStart Lambda → SQS discovery queue
2. **Discover:** ScrapeDiscover finds links → SQS processing queue
3. **Process:** ScrapeProcess fetches content → S3 input/ (.scraped.md)
4. **Index:** Step Functions → ProcessDocument → IngestToKB

### Image Processing
1. **Upload:** User → S3 images/ → EventBridge → ProcessImage
2. **Indexing:** ProcessImage ingests image + caption to Bedrock KB
3. **Cross-modal:** Both visual and text vectors share image_id

### Chat Query
1. **Query:** User → AppSync → QueryKB Lambda
2. **Quota Check:** Atomic DynamoDB transaction (global + per-user limits)
3. **History:** Load last 5 conversation turns for context
4. **Retrieve:** bedrock_agent.retrieve() → top 5 KB results
5. **Generate:** bedrock_runtime.converse() → answer with citations
6. **Sources:** KB URIs resolved to original files via tracking table
7. **Store:** Save turn to conversation history (14-day TTL)

### Real-time Updates
All state changes publish via GraphQL subscriptions:
- `onDocumentUpdate` - Document processing progress
- `onImageUpdate` - Image processing progress
- `onScrapeUpdate` - Web scraping progress

UI subscribes on load, updates automatically without polling.

## Architecture Decisions

**Why SAM?** Local testing, simpler Lambda packaging

**Why S3 vectors?** ~$1/month vs $50+/month for OpenSearch

**Why DynamoDB config?** Changes apply immediately, no redeployment

**Why shared library?** `lib/ragstack_common/` eliminates duplication

**Error handling:** Lambda retry → Bedrock retry → DLQ

## Security

- HTTPS/TLS everywhere
- S3 SSE, DynamoDB encryption
- Cognito auth + optional MFA
- API key for programmatic access (all operations)
- API key regeneration (manual, via Settings UI)
- Least-privilege IAM
- Public S3 blocked

## API Access

All operations support both API key and Cognito authentication:

| Operation | Endpoint | Auth |
|-----------|----------|------|
| Search KB | `searchKnowledgeBase` | API key / Cognito |
| Chat | `queryKnowledgeBase` | API key / Cognito |
| Upload docs | `createUploadUrl` | API key / Cognito |
| Upload images | `createImageUploadUrl`, `submitImage` | API key / Cognito |
| Scrape | `startScrape`, `getScrapeJob` | API key / Cognito |

**In-app documentation:** Each UI tab includes an expandable section with GraphQL queries and code examples.

## Performance

**10-page PDF:**
- Upload: <5 sec
- OCR: 2-15 min
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
- **Frontend:** React 19, Vite, Cloudscape
- **Chat:** ragstack-chat web component
