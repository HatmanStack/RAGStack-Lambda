# RAGStack-Lambda Project Overview

## Purpose
Serverless document processing pipeline with AI chat on AWS. Documents are uploaded → OCR processed (Textract/Bedrock) → vectorized → stored in Bedrock Knowledge Base → queryable via chat interface.

## Tech Stack
- **Runtime**: Python 3.13+, Node.js 24+
- **Infrastructure**: AWS SAM (single stack)
- **AWS Services**: Lambda, Step Functions, S3, DynamoDB, Bedrock KB, AppSync GraphQL, Cognito, CloudFront
- **Frontend**: React 19 + Vite (Cloudscape Design), reusable `<ragstack-chat>` web component
- **Testing**: pytest (Python), Vitest (TypeScript/React)
- **Linting**: Ruff (Python), ESLint (TypeScript)

## Architecture

### Data Flow
1. **Upload**: User uploads to S3 → EventBridge triggers ProcessDocument Lambda
2. **Processing**: ProcessDocument (OCR) → IngestToKB → Bedrock Knowledge Base
3. **Query**: User queries via AppSync → QueryKB Lambda → Bedrock KB → results with source attribution
4. **Chat**: Web component (`<ragstack-chat>`) → AppSync GraphQL API → QueryKB Lambda

### Repository Structure
```
├── lib/ragstack_common/          # Shared Python library (OCR, embeddings, config, storage)
│   ├── scraper/                  # Web scraping utilities
│   └── text_extractors/          # Document format extractors (docx, xlsx, epub, etc.)
├── src/
│   ├── lambda/                   # Lambda function handlers (30+ functions)
│   │   ├── process_document/     # OCR extraction (Textract/Bedrock)
│   │   ├── ingest_to_kb/         # Ingest embeddings to Bedrock KB
│   │   ├── query_kb/             # Query knowledge base (chat API)
│   │   ├── appsync_resolvers/    # GraphQL resolvers
│   │   └── ...                   # Many more specialized functions
│   ├── ui/                       # React dashboard (Cloudscape Design)
│   ├── ragstack-chat/            # Reusable chat React component + web component
│   ├── api/                      # GraphQL schema
│   └── statemachine/             # Step Functions state machine definition
├── tests/
│   ├── unit/python/              # Python unit tests (pytest)
│   ├── integration/              # Integration tests (@pytest.mark.integration)
│   ├── e2e/                      # End-to-end tests (Playwright)
│   └── events/                   # Lambda test event JSON files
├── template.yaml                 # SAM template (infrastructure as code)
└── publish.py                    # Deployment orchestration script
```

### Key Components
- **lib/ragstack_common/**: Shared library packaged as Lambda layer
- **ProcessDocument Lambda**: Extracts text using Textract or Bedrock vision models
- **IngestToKB Lambda**: Creates embeddings (Nova Multimodal) and syncs to Bedrock KB
- **QueryKB Lambda**: Retrieves documents from KB with source attribution, handles chat with quota management
- **Step Functions**: Orchestrates document processing workflow
- **AppSync**: GraphQL API for UI and chat
