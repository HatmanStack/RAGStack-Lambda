# Configuration Guide

## User-Configurable Settings (3)

- `ocr_backend` - "textract" or "bedrock"
- `bedrock_ocr_model_id` - Claude model for OCR
- `chat_model_id` - Claude model for queries

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

## FAQ

**Q: Why can't I change embedding models?**
- Managed by Bedrock Knowledge Base API automatically
- Changing requires re-creating KB (not recommended)

**Q: Do config changes require redeployment?**
- No. Changes apply immediately

**Q: Can I have different configs per environment?**
- Yes. Deploy separate stacks with different project names
