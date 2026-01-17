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
- Error handling (DLQ, 3x retry), CloudWatch metrics

## Components

| Component | Purpose |
|-----------|---------|
| DetectFileType Lambda | Detect file type, count pages, and route to appropriate processor |
| ProcessDocument Lambda | OCR extraction (Textract/Bedrock) for PDF/images |
| ProcessMedia Lambda | Video/audio transcription via AWS Transcribe, 30s segmentation |
| ProcessText Lambda | Text extraction for HTML, CSV, JSON, XML, EML, EPUB, DOCX, XLSX |
| EnqueueBatches Lambda | Queue batch jobs to SQS |
| BatchProcessor Lambda | Process 10-page batches (max 10 concurrent) |
| CombinePages Lambda | Merge partial outputs into final document |
| IngestToKB Lambda | Trigger Bedrock KB ingestion (Nova Multimodal embeddings) |
| IngestMedia Lambda | Ingest transcribed media segments to KB |
| QueryKB Lambda | Query documents, chat with sources |
| SearchKB Lambda | Direct KB search (no chat context) |
| ProcessImage Lambda | Image ingestion with captions |
| Scrape Lambdas | Web scraping pipeline (start/discover/process/status) |
| ReindexKB Lambda | Orchestrate KB reindexing with new metadata settings |
| MetadataAnalyzer Lambda | Sample KB vectors and generate filter examples |
| SyncCoordinator Lambda | Coordinate KB sync operations |
| SyncStatusChecker Lambda | Check KB sync completion status |
| ConfigurationResolver Lambda | Resolve DynamoDB configuration |
| AppSyncResolvers Lambda | GraphQL resolver implementations |
| ApiKeyResolver Lambda | API key validation and management |
| Step Functions | Orchestrate document/scrape/reindex workflows |
| Bedrock KB | Vector storage & retrieval (S3 backend) |
| S3 | File storage (input/, output/, images/) |
| DynamoDB | Document tracking, config, conversations, scrape jobs |
| AppSync | GraphQL API with subscriptions |
| React UI | Web dashboard (Cloudscape) |
| ragstack-chat | AI chat web component |

## Data Flow

### Document Processing

Documents are automatically routed to the appropriate processor based on file type detection:

```
Upload → DetectFileType → Route by Type:
         │
         ├── Text files (HTML, TXT, CSV, JSON, XML, EML, EPUB, DOCX, XLSX)
         │   └── ProcessText → IngestToKB → Bedrock KB
         │
         ├── OCR files (PDF, images)
         │   └── ProcessDocument → IngestToKB → Bedrock KB
         │
         ├── Media files (MP4, WebM, MP3, WAV, M4A, OGG, FLAC)
         │   └── ProcessMedia → AWS Transcribe → 30s segments → IngestToKB → Bedrock KB
         │
         └── Passthrough (Markdown)
             └── ProcessDocument → IngestToKB → Bedrock KB
```

**Supported File Types:**

| Category | Types | Processing |
|----------|-------|------------|
| **Text** | HTML, TXT, CSV, JSON, XML, EML, EPUB, DOCX, XLSX | Direct text extraction with smart analysis |
| **OCR** | PDF, JPG, PNG, TIFF, GIF, BMP, WebP, AVIF | Textract or Bedrock vision OCR (WebP/AVIF require Bedrock) |
| **Media** | MP4, WebM, MP3, WAV, M4A, OGG, FLAC | AWS Transcribe speech-to-text, 30s segments with timestamps |
| **Passthrough** | Markdown (.md) | Copy directly to output |

**Text Processing:** Content sniffing detects actual file type regardless of extension. Structured formats (CSV, JSON, XML) get smart extraction with schema analysis.

**Large PDFs (>20 pages):**
1. **Upload:** User → S3 input/ → EventBridge → Step Functions
2. **Page Info:** DetectFileType counts pages, creates 10-page batches
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

### Media Processing (Video/Audio)
1. **Upload:** User → S3 input/ → EventBridge → DetectFileType
2. **Transcribe:** ProcessMedia → AWS Transcribe batch job → transcript with timestamps
3. **Segment:** Transcript split into 30-second chunks
4. **Metadata:** Each segment tagged with `timestamp_start`, `timestamp_end`, `speaker` (if diarization enabled)
5. **Indexing:** Segments ingested to Bedrock KB with timestamp metadata
6. **Query:** Sources include timestamp ranges, URLs with `#t=start,end` fragment for HTML5 playback

**Speaker diarization:** When enabled, Transcribe identifies up to 10 speakers. Each segment tracks the primary speaker for filtering.

**Source format:** Chat responses show timestamps like "1:30-2:00" with clickable links that open the media at that position.

### Knowledge Base Reindex
1. **Trigger:** User → AppSync → startReindex mutation → Step Functions
2. **Init:** Create new S3 Vectors bucket + Knowledge Base
3. **Process:** Map state iterates documents, regenerates metadata, ingests to new KB
4. **Finalize:** Update SSM parameter to new KB ID
5. **Cleanup:** Delete old KB and S3 Vectors bucket

**Note:** Reindex regenerates metadata only - does NOT re-run OCR/text extraction.

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
- `onReindexUpdate` - Knowledge Base reindex progress

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
- Textract + Haiku: **$7-10/month**
- Bedrock OCR + Haiku: **$25-75/month**

See [Configuration](CONFIGURATION.md)

## Stack

- **Infrastructure:** SAM, Lambda, Step Functions
- **Storage:** S3, DynamoDB, Bedrock KB
- **APIs:** AppSync, Bedrock, Textract, Transcribe
- **Frontend:** React 19, Vite, Cloudscape
- **Chat:** ragstack-chat web component
