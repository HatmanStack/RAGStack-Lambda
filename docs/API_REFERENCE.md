# API Reference

Complete GraphQL API reference for RAGStack-Lambda.

## Authentication Methods

| Method | Use Case | Header | Operations |
|--------|----------|--------|------------|
| **API Key** | Server-side integrations | `x-api-key: YOUR_KEY` | All operations |
| **Cognito** | Admin UI | `Authorization: Bearer TOKEN` | All operations |
| **IAM (unauth)** | Web component | Automatic | Query, Search, Subscriptions |

Get your API key from Dashboard → Settings → API Key.

## Base URL

Your GraphQL endpoint is available in the CloudFormation stack outputs as `GraphQLApiUrl`.

```
https://YOUR_API_ID.appsync-api.REGION.amazonaws.com/graphql
```

---

## Queries

### getDocument

Get document by ID.

**Auth:** API key, Cognito

**GraphQL:**
```graphql
query GetDocument($documentId: ID!) {
  getDocument(documentId: $documentId) {
    documentId
    filename
    inputS3Uri
    outputS3Uri
    status
    fileType
    isTextNative
    totalPages
    errorMessage
    createdAt
    updatedAt
    metadata
    previewUrl
    type
    mediaType
    durationSeconds
  }
}
```

**curl:**
```bash
curl -X POST 'YOUR_GRAPHQL_ENDPOINT' \
  -H 'x-api-key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "query GetDocument($documentId: ID!) { getDocument(documentId: $documentId) { documentId filename status } }",
    "variables": {"documentId": "doc-123"}
  }'
```

---

### listDocuments

List all documents (no pagination).

**Auth:** API key, Cognito

**GraphQL:**
```graphql
query ListDocuments {
  listDocuments {
    items {
      documentId
      filename
      status
      fileType
      totalPages
      createdAt
      updatedAt
      type
    }
    nextToken
  }
}
```

**curl:**
```bash
curl -X POST 'YOUR_GRAPHQL_ENDPOINT' \
  -H 'x-api-key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"query": "query { listDocuments { items { documentId filename status } } }"}'
```

---

### queryKnowledgeBase

Query Knowledge Base with multi-turn chat context.

**Auth:** IAM (unauthenticated web component), API key, Cognito

**GraphQL:**
```graphql
query QueryKnowledgeBase($query: String!, $conversationId: String) {
  queryKnowledgeBase(query: $query, conversationId: $conversationId) {
    answer
    conversationId
    sources {
      documentId
      pageNumber
      s3Uri
      snippet
      documentUrl
      documentAccessAllowed
      score
      filename
      isScraped
      sourceUrl
      isImage
      thumbnailUrl
      caption
      isMedia
      isSegment
      segmentUrl
      mediaType
      contentType
      timestampStart
      timestampEnd
      timestampDisplay
      speaker
      segmentIndex
    }
    filterApplied
  }
}
```

**curl:**
```bash
curl -X POST 'YOUR_GRAPHQL_ENDPOINT' \
  -H 'x-api-key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "query($query: String!, $conversationId: String) { queryKnowledgeBase(query: $query, conversationId: $conversationId) { answer conversationId sources { filename snippet score } } }",
    "variables": {"query": "What is RAGStack?", "conversationId": "session-123"}
  }'
```

---

### searchKnowledgeBase

Raw vector search without chat context.

**Auth:** IAM (unauthenticated), API key, Cognito

**GraphQL:**
```graphql
query SearchKnowledgeBase($query: String!, $maxResults: Int) {
  searchKnowledgeBase(query: $query, maxResults: $maxResults) {
    query
    results {
      content
      source
      score
      documentId
      filename
      documentUrl
      documentAccessAllowed
      isScraped
      sourceUrl
      isImage
      thumbnailUrl
      isMedia
      mediaType
      isSegment
      segmentUrl
      timestampStart
    }
    total
    filterApplied
  }
}
```

**curl:**
```bash
curl -X POST 'YOUR_GRAPHQL_ENDPOINT' \
  -H 'x-api-key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "query($query: String!, $maxResults: Int) { searchKnowledgeBase(query: $query, maxResults: $maxResults) { results { content score } } }",
    "variables": {"query": "serverless architecture", "maxResults": 10}
  }'
```

---

### getConfiguration

Get system configuration (Schema, Default, Custom).

**Auth:** API key, Cognito

**GraphQL:**
```graphql
query GetConfiguration {
  getConfiguration {
    Schema
    Default
    Custom
  }
}
```

---

### getScrapeJob

Get scrape job by ID with pages.

**Auth:** API key, Cognito

**GraphQL:**
```graphql
query GetScrapeJob($jobId: ID!) {
  getScrapeJob(jobId: $jobId) {
    job {
      jobId
      baseUrl
      title
      status
      config {
        maxPages
        maxDepth
        scope
        includePatterns
        excludePatterns
        scrapeMode
      }
      totalUrls
      processedCount
      failedCount
      createdAt
      updatedAt
    }
    pages {
      url
      title
      status
      documentId
      contentUrl
      error
      depth
    }
  }
}
```

---

### listScrapeJobs

List all scrape jobs (paginated).

**Auth:** API key, Cognito

**GraphQL:**
```graphql
query ListScrapeJobs($limit: Int, $nextToken: String) {
  listScrapeJobs(limit: $limit, nextToken: $nextToken) {
    items {
      jobId
      baseUrl
      title
      status
      totalUrls
      processedCount
      failedCount
      createdAt
      updatedAt
    }
    nextToken
  }
}
```

---

### checkScrapeUrl

Check if a URL has been scraped before.

**Auth:** API key, Cognito

**GraphQL:**
```graphql
query CheckScrapeUrl($url: String!) {
  checkScrapeUrl(url: $url) {
    exists
    lastScrapedAt
    jobId
    title
  }
}
```

---

### getImage

Get image by ID.

**Auth:** API key, Cognito

**GraphQL:**
```graphql
query GetImage($imageId: ID!) {
  getImage(imageId: $imageId) {
    imageId
    filename
    caption
    userCaption
    aiCaption
    status
    s3Uri
    thumbnailUrl
    contentType
    fileSize
    errorMessage
    extractedText
    extractedMetadata
    captionUrl
    createdAt
    updatedAt
  }
}
```

---

### listImages

List all images (paginated).

**Auth:** API key, Cognito

**GraphQL:**
```graphql
query ListImages($limit: Int, $nextToken: String) {
  listImages(limit: $limit, nextToken: $nextToken) {
    items {
      imageId
      filename
      caption
      status
      thumbnailUrl
      createdAt
    }
    nextToken
  }
}
```

---

### getApiKey

Get current API key (admin only).

**Auth:** Cognito only

**GraphQL:**
```graphql
query GetApiKey {
  getApiKey {
    apiKey
    id
    expires
  }
}
```

---

### getMetadataStats

Get metadata key statistics from key library.

**Auth:** API key, Cognito

**GraphQL:**
```graphql
query GetMetadataStats {
  getMetadataStats {
    keys {
      keyName
      dataType
      occurrenceCount
      sampleValues
      lastAnalyzed
      status
    }
    totalKeys
    lastAnalyzed
  }
}
```

---

### getFilterExamples

Get filter examples for metadata filtering.

**Auth:** IAM (unauthenticated), API key, Cognito

**GraphQL:**
```graphql
query GetFilterExamples {
  getFilterExamples {
    examples {
      name
      description
      useCase
      filter
    }
    totalExamples
    lastGenerated
  }
}
```

---

### getKeyLibrary

Get key library for metadata key suggestions.

**Auth:** API key, Cognito

**GraphQL:**
```graphql
query GetKeyLibrary {
  getKeyLibrary {
    keyName
    dataType
    occurrenceCount
    sampleValues
    status
  }
}
```

---

### checkKeySimilarity

Check if a proposed key is similar to existing keys.

**Auth:** API key, Cognito

**GraphQL:**
```graphql
query CheckKeySimilarity($keyName: String!, $threshold: Float) {
  checkKeySimilarity(keyName: $keyName, threshold: $threshold) {
    proposedKey
    similarKeys {
      keyName
      similarity
      occurrenceCount
    }
    hasSimilar
  }
}
```

---

## Mutations

### createUploadUrl

Create presigned URL for document upload.

**Auth:** IAM (unauthenticated), API key, Cognito

**GraphQL:**
```graphql
mutation CreateUploadUrl($filename: String!) {
  createUploadUrl(filename: $filename) {
    uploadUrl
    documentId
    fields
  }
}
```

**curl:**
```bash
curl -X POST 'YOUR_GRAPHQL_ENDPOINT' \
  -H 'x-api-key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "mutation($filename: String!) { createUploadUrl(filename: $filename) { uploadUrl documentId fields } }",
    "variables": {"filename": "document.pdf"}
  }'
```

---

### processDocument

Manually trigger processing (if needed).

**Auth:** API key, Cognito

**GraphQL:**
```graphql
mutation ProcessDocument($documentId: ID!) {
  processDocument(documentId: $documentId) {
    documentId
    status
  }
}
```

---

### updateConfiguration

Update custom configuration.

**Auth:** Cognito only

**GraphQL:**
```graphql
mutation UpdateConfiguration($customConfig: AWSJSON!) {
  updateConfiguration(customConfig: $customConfig)
}
```

---

### startScrape

Start a new web scraping job.

**Auth:** IAM (unauthenticated), API key, Cognito

**GraphQL:**
```graphql
mutation StartScrape($input: StartScrapeInput!) {
  startScrape(input: $input) {
    jobId
    baseUrl
    status
    config {
      maxPages
      maxDepth
      scope
    }
    totalUrls
    processedCount
    failedCount
    createdAt
  }
}
```

**Variables:**
```json
{
  "input": {
    "url": "https://docs.example.com",
    "maxPages": 100,
    "maxDepth": 3,
    "scope": "HOSTNAME",
    "includePatterns": ["/docs/*"],
    "excludePatterns": ["/blog/*"],
    "scrapeMode": "AUTO",
    "forceRescrape": false
  }
}
```

---

### cancelScrape

Cancel an in-progress scrape job.

**Auth:** IAM (unauthenticated), API key, Cognito

**GraphQL:**
```graphql
mutation CancelScrape($jobId: ID!) {
  cancelScrape(jobId: $jobId) {
    jobId
    status
  }
}
```

---

### createImageUploadUrl

Create presigned URL for image upload.

**Auth:** IAM (unauthenticated), API key, Cognito

**GraphQL:**
```graphql
mutation CreateImageUploadUrl($filename: String!, $autoProcess: Boolean, $userCaption: String) {
  createImageUploadUrl(filename: $filename, autoProcess: $autoProcess, userCaption: $userCaption) {
    uploadUrl
    imageId
    s3Uri
    fields
  }
}
```

---

### generateCaption

Generate AI caption for an image using vision model.

**Auth:** IAM (unauthenticated), API key, Cognito

**GraphQL:**
```graphql
mutation GenerateCaption($imageS3Uri: String!) {
  generateCaption(imageS3Uri: $imageS3Uri) {
    caption
    error
  }
}
```

---

### submitImage

Submit image with caption to finalize upload and trigger processing.

**Auth:** IAM (unauthenticated), API key, Cognito

**GraphQL:**
```graphql
mutation SubmitImage($input: SubmitImageInput!) {
  submitImage(input: $input) {
    imageId
    filename
    status
    caption
  }
}
```

**Variables:**
```json
{
  "input": {
    "imageId": "img-123",
    "caption": "Combined caption text",
    "userCaption": "User description",
    "aiCaption": "AI-generated description",
    "extractText": false
  }
}
```

---

### deleteImage

Delete an image from S3, DynamoDB, and Knowledge Base.

**Auth:** API key, Cognito

**GraphQL:**
```graphql
mutation DeleteImage($imageId: ID!) {
  deleteImage(imageId: $imageId)
}
```

---

### deleteDocuments

Delete documents from DynamoDB tracking table (batch delete).

**Auth:** API key, Cognito

**Note:** Does not delete from S3 or Knowledge Base - those are cleaned up separately.

**GraphQL:**
```graphql
mutation DeleteDocuments($documentIds: [ID!]!) {
  deleteDocuments(documentIds: $documentIds) {
    deletedCount
    failedIds
    errors
  }
}
```

---

### reprocessDocument

Reprocess a document by triggering the appropriate pipeline.

**Auth:** API key, Cognito

**GraphQL:**
```graphql
mutation ReprocessDocument($documentId: ID!) {
  reprocessDocument(documentId: $documentId) {
    documentId
    type
    status
    executionArn
    error
  }
}
```

---

### reindexDocument

Reindex a document - re-extract metadata from existing text and reingest to KB.

**Auth:** API key, Cognito

**Note:** Faster than reprocess since it skips OCR extraction.

**GraphQL:**
```graphql
mutation ReindexDocument($documentId: ID!) {
  reindexDocument(documentId: $documentId) {
    documentId
    type
    status
    executionArn
    error
  }
}
```

---

### createZipUploadUrl

Create presigned URL for ZIP archive upload (batch image upload).

**Auth:** IAM (unauthenticated), API key, Cognito

**GraphQL:**
```graphql
mutation CreateZipUploadUrl($generateCaptions: Boolean) {
  createZipUploadUrl(generateCaptions: $generateCaptions) {
    uploadUrl
    uploadId
    fields
  }
}
```

---

### regenerateApiKey

Regenerate API key (admin only) - creates new key and deletes old ones.

**Auth:** Cognito only

**GraphQL:**
```graphql
mutation RegenerateApiKey {
  regenerateApiKey {
    apiKey
    id
    expires
  }
}
```

---

### analyzeMetadata

Analyze metadata in Knowledge Base vectors.

**Auth:** API key, Cognito

**Note:** Samples vectors, analyzes field occurrences, and updates key library statistics.

**GraphQL:**
```graphql
mutation AnalyzeMetadata {
  analyzeMetadata {
    success
    vectorsSampled
    keysAnalyzed
    examplesGenerated
    executionTimeMs
    error
  }
}
```

---

### regenerateFilterExamples

Regenerate filter examples using only the configured filter keys.

**Auth:** API key, Cognito

**GraphQL:**
```graphql
mutation RegenerateFilterExamples {
  regenerateFilterExamples {
    success
    examplesGenerated
    executionTimeMs
    error
  }
}
```

---

### deleteMetadataKey

Delete a metadata key from the key library.

**Auth:** API key, Cognito

**GraphQL:**
```graphql
mutation DeleteMetadataKey($keyName: String!) {
  deleteMetadataKey(keyName: $keyName) {
    success
    keyName
    error
  }
}
```

---

### startReindex

Start Knowledge Base reindex operation (admin only).

**Auth:** Cognito only

**Note:** Creates new KB, regenerates metadata for all documents, migrates content, deletes old KB.

**GraphQL:**
```graphql
mutation StartReindex {
  startReindex {
    executionArn
    status
    startedAt
  }
}
```

---

## Subscriptions

### onDocumentUpdate

Subscribe to document status updates.

**Auth:** Cognito only

**GraphQL:**
```graphql
subscription OnDocumentUpdate {
  onDocumentUpdate {
    documentId
    filename
    status
    totalPages
    errorMessage
    updatedAt
  }
}
```

---

### onScrapeUpdate

Subscribe to scrape job status updates.

**Auth:** Cognito only

**GraphQL:**
```graphql
subscription OnScrapeUpdate {
  onScrapeUpdate {
    jobId
    baseUrl
    title
    status
    totalUrls
    processedCount
    failedCount
    updatedAt
  }
}
```

---

### onImageUpdate

Subscribe to image status updates.

**Auth:** Cognito only

**GraphQL:**
```graphql
subscription OnImageUpdate {
  onImageUpdate {
    imageId
    filename
    status
    caption
    errorMessage
    updatedAt
  }
}
```

---

### onReindexUpdate

Subscribe to reindex progress updates.

**Auth:** Cognito only

**GraphQL:**
```graphql
subscription OnReindexUpdate {
  onReindexUpdate {
    status
    totalDocuments
    processedCount
    currentDocument
    errorCount
    errorMessages
    newKnowledgeBaseId
    updatedAt
  }
}
```

---

## Enums

### DocumentStatus
`PENDING`, `UPLOADED`, `PROCESSING`, `OCR_COMPLETE`, `EMBEDDING_COMPLETE`, `TRANSCRIBING`, `TRANSCRIBED`, `SYNC_QUEUED`, `INDEXED`, `FAILED`, `INGESTION_FAILED`

### ImageStatus
`PENDING`, `PROCESSING`, `SYNC_QUEUED`, `INDEXED`, `FAILED`, `INGESTION_FAILED`

### ScrapeStatus
`PENDING`, `DISCOVERING`, `PROCESSING`, `COMPLETED`, `COMPLETED_WITH_ERRORS`, `FAILED`, `CANCELLED`

### ScrapeScope
`SUBPAGES`, `HOSTNAME`, `DOMAIN`

### ScrapeMode
`FAST`, `FULL`, `AUTO`

### ReindexStatus
`PENDING`, `CREATING_KB`, `PROCESSING`, `UPDATING_LAMBDAS`, `DELETING_OLD_KB`, `COMPLETED`, `FAILED`

---

## Error Handling

GraphQL errors follow the standard format:

```json
{
  "errors": [
    {
      "message": "Error description",
      "path": ["queryKnowledgeBase"],
      "extensions": {
        "errorType": "RuntimeException"
      }
    }
  ]
}
```

Common errors:
- `401 Unauthorized` - Invalid or missing API key/token
- `403 Forbidden` - Insufficient permissions
- `400 Bad Request` - Invalid input parameters
- `500 Internal Server Error` - Lambda execution failure

---

## Rate Limits

Rate limits are configured per deployment. Defaults:
- **Global quota:** 10,000 queries/day
- **Per-user quota:** 100 queries/day

When exceeded, chat switches to fallback model (cheaper, less capable).

See [CONFIGURATION.md](./CONFIGURATION.md) for quota settings.
