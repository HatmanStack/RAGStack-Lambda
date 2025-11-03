# Configuration Guide

RAGStack-Lambda uses **3 user-configurable settings**. Everything else is hardcoded to production defaults.

## Quick Reference

**User-Configurable Settings**:
- `ocr_backend` - "textract" or "bedrock"
- `bedrock_ocr_model_id` - Claude model for document OCR
- `chat_model_id` - Claude model for Knowledge Base queries

**Hardcoded (Not Changeable)**:
- Text embeddings: `amazon.titan-embed-text-v2:0`
- Image embeddings: `amazon.titan-embed-image-v1`

## Configure at Deployment

Set via `template.yaml` before deploying:

```yaml
Parameters:
  ProjectName:
    Type: String
    Description: "Project identifier (lowercase, 2-32 chars)"

  OcrBackend:
    Type: String
    Default: "textract"
    AllowedValues: ["textract", "bedrock"]
    Description: "OCR service (textract=cheaper, bedrock=multimodal)"

  BedrockOcrModelId:
    Type: String
    Default: "anthropic.claude-3-5-haiku-20241022-v1:0"
    Description: "Claude model for OCR (if using Bedrock)"

  AdminEmail:
    Type: String
    Description: "Admin user email (receives temporary password)"
```

Then deploy:
```bash
python publish.py \
  --project-name myapp \
  --admin-email admin@example.com \
  --region us-east-1
```

## Configure at Runtime

**Via Settings UI** (easiest):
1. Open WebUI → Settings
2. Modify OCR backend or chat model
3. Click Save
4. Changes apply immediately (no cache)

**Via AWS CLI**:
```bash
# View current config
aws dynamodb get-item \
  --table-name RAGStack-<project>-Configuration \
  --key '{"Configuration": {"S": "Custom"}}'

# Update via DynamoDB (manual)
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
| `ocr_backend` | "textract", "bedrock" | textract | Textract: ~$1.50/1000 pages. Bedrock: ~$0.75/1000 pages |
| `bedrock_ocr_model_id` | Claude model IDs | claude-3-5-haiku | Haiku = cheapest, Opus = most capable |
| `chat_model_id` | Claude model IDs | claude-3-5-haiku | Haiku = cheapest, Opus = most capable |

## Lambda Environment Variables

Set in `template.yaml` function properties:

```yaml
ProcessDocument:
  Properties:
    Environment:
      Variables:
        LOG_LEVEL: "INFO"  # DEBUG, INFO, WARNING, ERROR
        CONFIGURATION_TABLE_NAME: !Ref ConfigTable
        OCR_BACKEND: !Ref OcrBackend
```

**Common Variables**:

| Variable | Purpose |
|----------|---------|
| `LOG_LEVEL` | Control logging verbosity (DEBUG = verbose) |
| `CONFIGURATION_TABLE_NAME` | DynamoDB config table |
| `KNOWLEDGE_BASE_ID` | Bedrock KB ID (from SAM outputs) |
| `S3_BUCKET_NAME` | Input bucket for documents |
| `TRACKING_TABLE_NAME` | DynamoDB document tracking table |

## Cost Optimization

### OCR Costs (Biggest Impact)

| Strategy | Savings |
|----------|---------|
| Use Textract (default) | 50% cheaper than Bedrock OCR |
| Use Haiku model for Bedrock | 60% cheaper than Opus |
| Text-native PDFs only | Skip OCR entirely (free) |
| Smaller page limits | Less processing per document |

### Lambda Costs

| Strategy | Savings |
|----------|---------|
| Haiku models for chat | Cheaper per token |
| Optimize memory allocation | Lower execution cost |
| Batch document processing | Fewer Lambda invocations |

### Storage Costs

| Strategy | Savings |
|----------|---------|
| Delete old extracted text | 80% of S3 cost is text files |
| Use S3 lifecycle policies | Auto-delete files after 7 days |
| Compress extracted text | Smaller files = less storage |

### Estimate Monthly Cost

For ~1000 documents/month (5 pages each):

| Config | OCR | Embeddings | Other | Total |
|--------|-----|-----------|-------|-------|
| Textract + Haiku | $5 | $0.15 | $2 | **~$7-10** |
| Bedrock + Haiku | $25 | $0.15 | $2 | **~$27-30** |
| Textract + Opus | $5 | $0.50 | $2 | **~$7-10** |

## Best Practices

**Development/Testing:**
- Use Haiku for cost savings (~1/10th of Opus)
- Use Textract OCR (50% cheaper than Bedrock)
- Keep text-native PDFs only

**Production:**
- Use Haiku unless you need advanced reasoning
- Use Textract for standard documents (images/scans)
- Use Bedrock OCR only for complex multimodal documents
- Monitor costs in AWS Billing console

**Important Notes:**
- ⚠️ Changing embedding models requires re-processing all documents
- Config changes take effect immediately (no cache, no redeployment)
- Default values cannot be changed (schema is read-only)
- Custom values override defaults

## Changing Embedding Models (Advanced)

Embedding models are hardcoded to ensure consistency. If you need different models:

1. **Edit `lib/ragstack_common/models.py`**:
   ```python
   EMBEDDING_MODELS = {
       "text": "your.new.text.model:0",
       "image": "your.new.image.model:1"
   }
   ```

2. **Re-embed all documents**:
   - Documents keep old embeddings
   - New documents use new embeddings
   - Search works with both (performance may vary)
   - Or: delete all documents and re-upload

3. **Test thoroughly before production**

## FAQ

**Q: Why can't I change embedding models in Settings?**
- Because changing them requires re-embedding all documents (expensive operation)
- Hardcoded defaults eliminate risk of accidental breaks

**Q: Do I need to redeploy when I change settings?**
- No. Settings via UI or CLI take effect immediately
- No code change, no redeployment needed

**Q: What if configuration fails to load?**
- Check DynamoDB table exists: `aws dynamodb list-tables`
- Check table name matches `CONFIGURATION_TABLE_NAME` env var
- Verify IAM Lambda role has DynamoDB read permissions

**Q: Can I have different configs per environment?**
- Yes. Deploy separate stacks with different project names
- Each stack has its own configuration

## Related Documentation

- [Deployment Guide](DEPLOYMENT.md) - How to deploy
- [Architecture](ARCHITECTURE.md) - How configuration flows through system
- [User Guide](USER_GUIDE.md) - Using Settings UI
- [Troubleshooting](TROUBLESHOOTING.md) - Configuration issues
