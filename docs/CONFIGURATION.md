# Configuration Guide

## User-Configurable Settings

### Document Processing
- `ocr_backend` - "textract" or "bedrock"
- `bedrock_ocr_model_id` - Claude model for OCR
- `chat_model_id` - Claude model for queries

### Chat Configuration
- `chat_require_auth` - Enable/disable authentication (boolean)
- `chat_primary_model` - Primary chat model ARN
- `chat_fallback_model` - Fallback chat model ARN
- `chat_global_quota_daily` - Daily query limit (all users)
- `chat_per_user_quota_daily` - Daily query limit (per user)
- `chat_allow_document_access` - Enable/disable source document downloads (boolean)

**Hardcoded** (managed by Bedrock KB API):
- Text embeddings: `amazon.titan-embed-text-v2:0`
- Image embeddings: `amazon.titan-embed-image-v1`

## Change Settings

**Via UI (easiest):**
1. WebUI → Settings
2. Change OCR backend or model
3. Save (applies immediately)

**Via CLI:**
```bash
aws dynamodb put-item \
  --table-name RAGStack-<project>-Configuration \
  --item '{
    "Configuration": {"S": "Custom"},
    "ocr_backend": {"S": "bedrock"},
    "chat_model_id": {"S": "anthropic.claude-3-5-sonnet-20241022"}
  }'
```

## Configuration Parameters

| Parameter | Values | Default | Cost Impact |
|-----------|--------|---------|------------|
| `ocr_backend` | textract, bedrock | textract | Textract cheaper (~50%) |
| `bedrock_ocr_model_id` | Claude models | haiku | Haiku cheapest |
| `chat_model_id` | Claude models | haiku | Haiku cheapest |

## Cost Optimization

**OCR (biggest cost):**
- Textract: $1.50 per 1000 pages (default)
- Bedrock: $0.75 per 1000 pages
- Text-native PDFs: Free (no OCR)

**Models:**
- Haiku: ~$0.80 per 1M tokens
- Opus: ~$15 per 1M tokens (20x more expensive)

**Monthly estimate** (1000 docs, 5 pages each):
- Textract + Haiku: ~$7-10
- Bedrock + Haiku: ~$25-30

## Document Access Configuration

### `chat_allow_document_access`

Controls whether users can download original source documents from chat responses.

**Type:** Boolean
**Default:** `false` (disabled)
**Purpose:** Enable/disable "View Document" links in chat source citations

**How it works:**
1. When enabled, chat responses include presigned S3 URLs for original documents
2. URLs expire after 1 hour (security feature)
3. Only read-only access (GetObject), no modification or deletion
4. Users can download PDFs, images, and other source files

**Enable via Admin UI:**
1. Navigate to Configuration page
2. Toggle "Allow Document Access" switch
3. Changes apply immediately (60-second cache delay)

**Enable via CLI:**
```bash
aws dynamodb update-item \
  --table-name {ProjectName}-config-{Suffix} \
  --key '{"Configuration": {"S": "Default"}}' \
  --update-expression "SET chat_allow_document_access = :val" \
  --expression-attribute-values '{":val": {"BOOL": true}}'
```

**Security Implications:**
- URLs are time-limited (1 hour expiry)
- URLs are revocable by disabling the setting
- No bucket listing or write access
- Presigned URLs contain AWS credentials in query params (do not log)

**When to enable:**
- Internal knowledge base (trusted users)
- Public documentation (already public sources)

**When to disable:**
- Sensitive/confidential documents
- Compliance requirements prohibit downloads
- Citation snippets are sufficient

## FAQ

**Q: Why can't I change embedding models?**
- Managed by Bedrock Knowledge Base API automatically
- Changing requires re-creating KB (not recommended)

**Q: Do config changes require redeployment?**
- No. Changes apply immediately

**Q: Can I have different configs per environment?**
- Yes. Deploy separate stacks with different project names
