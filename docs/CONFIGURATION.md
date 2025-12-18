# Configuration

All settings are stored in DynamoDB and apply immediately without redeployment.

## Settings UI

**Dashboard → Settings** - Change any setting, click Save.

## Document Processing

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `ocr_backend` | textract, bedrock | textract | Textract is faster and cheaper |
| `bedrock_ocr_model_id` | Claude model ID | haiku | Only used when ocr_backend=bedrock |

## Chat Settings

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `chat_require_auth` | boolean | false | Require authentication for chat |
| `chat_primary_model` | Model ARN | claude-haiku | Model for chat responses |
| `chat_fallback_model` | Model ARN | nova-micro | Used when quota exceeded |
| `chat_global_quota_daily` | number | 10000 | Total queries/day for all users |
| `chat_per_user_quota_daily` | number | 100 | Queries/day per authenticated user |
| `chat_allow_document_access` | boolean | false | Show "View Document" links in sources |

## Quota System

Quotas prevent runaway costs. When exceeded, chat switches to the fallback model (cheaper, less capable).

**How it works:**
1. Each query checks global + per-user quota atomically
2. If under limit → use primary model, increment counter
3. If over limit → use fallback model (still works, just different model)
4. Counters reset at midnight UTC
5. Unauthenticated users share the global quota only

**Atomic enforcement:** Uses DynamoDB transactions to prevent race conditions under high concurrency.

## Document Access

When `chat_allow_document_access` is enabled:
- Chat sources include "View Document" links
- Links are presigned S3 URLs (1-hour expiry)
- Read-only access to original files

**Enable for:** Internal KB, public docs
**Disable for:** Sensitive documents, compliance requirements

## CLI Configuration

```bash
# View current config
aws dynamodb get-item \
  --table-name RAGStack-<project>-config-<suffix> \
  --key '{"Configuration": {"S": "Custom"}}'

# Update setting
aws dynamodb update-item \
  --table-name RAGStack-<project>-config-<suffix> \
  --key '{"Configuration": {"S": "Custom"}}' \
  --update-expression "SET chat_per_user_quota_daily = :val" \
  --expression-attribute-values '{":val": {"N": "200"}}'
```

## Cost Impact

| Choice | Monthly Cost (1000 docs) |
|--------|-------------------------|
| Textract + Haiku | $7-10 |
| Bedrock OCR + Haiku | $25-30 |
| Sonnet instead of Haiku | +$5-15 |

**Tips:**
- Text-native PDFs skip OCR entirely (free)
- Haiku is 20x cheaper than Opus
- Set conservative quotas, increase as needed
