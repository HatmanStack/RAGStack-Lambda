# Troubleshooting Guide

Quick reference for common issues and solutions.

## Recommended Workflow: Better Search Results

For the best search quality, use manual metadata keys. This gives you control over what metadata is extracted and ensures consistent filtering across your documents.

**Steps:**

1. **Initial upload**: Process a representative sample of documents with default settings (Haiku extraction, auto mode)
2. **Review extracted keys**: Go to Settings → Metadata Key Statistics to see what keys were discovered
3. **Select manual keys**: Switch to "Manual" extraction mode and select only the keys relevant to your use case (e.g., `surnames`, `topic`, `year`, `location`)
4. **Run full reindex**: Click "Reindex Knowledge Base" — this re-extracts metadata using only your selected keys and rebuilds the KB with consistent metadata
5. **Create filter examples**: After reindex, run "Analyze Metadata" to generate few-shot examples for query-time filter generation

**Why this works:** Auto mode creates inconsistent metadata across documents. Manual mode enforces a consistent schema for better filtering.

---

## Best Practices

Tips from production usage to help you get the most out of RAGStack.

### Model Selection

| Use Case | Recommended | Also Good | Avoid | Why |
|----------|-------------|-----------|-------|-----|
| Chat primary | Claude Haiku 4.5 / Sonnet 4.6 | Nova 2 Lite, Nova Pro | Nova Micro | Quality and multimodal support matter for chat |
| Chat fallback | Nova Lite | Nova 2 Lite | Nova Micro | Good balance of cost and quality for fallback |
| Metadata extraction | Claude Haiku 4.5 | Nova 2 Lite (with manual keys) | Nova Lite | Nova Lite hallucinates fields; Nova 2 Lite has better reasoning |
| Filter generation | Claude Haiku 4.5 | Nova 2 Lite | Nova Lite | Needs accurate query intent understanding |
| OCR (Bedrock backend) | Claude Haiku 4.5 | Nova 2 Lite, Nova Pro | - | Vision-capable models required |

### Document Processing

- **Large PDFs (100+ pages)**: Processing is automatic via batch queue. Monitor status in dashboard.
- **Image-heavy documents**: Consider switching `ocr_backend` to `bedrock` for better accuracy.
- **Mixed content**: RAGStack handles text, images, and media differently - each optimized for its type.

### Query Quality

- **Multi-slice retrieval**: Keep enabled (default) - runs filtered and unfiltered queries in parallel for better recall.
- **Metadata filtering**: Works best when documents have consistent metadata. Use manual extraction mode if you need specific keys.

### Filter Generation

- **Filters require initialization**: Filter examples aren't created until you run "Analyze Metadata" in the Settings tab at least once. Without this, query-time filter generation won't have few-shot examples.
- **Refreshing filter examples**: Filter examples are few-shot prompts that guide the model. If your queries aren't generating good filters, disable the problematic examples and run "Analyze Metadata" again - disabled filters will be replaced with new ones based on current active keys.
- **Active keys**: A metadata key is "active" if it has an occurrence count > 0 (i.e., at least one document has that key). Only active keys are used for filter generation. After a full reindex, check that your expected keys are active.

### Cost Optimization

Once you've set up manual keys (see "Recommended Workflow" above), you can reduce costs:

1. **Downgrade extraction model**: Switch to Nova Lite for metadata extraction — manual mode constrains its output so quality remains good
2. **Keep Haiku for filters**: Leave filter generation on Haiku — it needs better reasoning to translate queries into filters accurately

This uses Haiku's quality for discovery and filter generation, while using Nova Lite's lower cost for bulk extraction.

### Filtered Results Ranking

- **Increase boost ceiling:** Raise `multislice_filtered_boost` (1.3-1.5) if filtered results still buried by visual similarity
- **Disable boost:** Set to 1.0 if filtered results dominate too aggressively
- **Default is balanced:** 1.25 ceiling works well for most use cases

---

## Bedrock Model Access Issues

Anthropic and some other third-party models on Bedrock are offered through AWS Marketplace and require a **one-time agreement acceptance** per model. Once an admin accepts the agreement, all IAM roles in the account can invoke that model without needing Marketplace permissions.

| Problem | Cause | Solution |
|---------|-------|----------|
| `Model access is denied due to IAM user or service role is not authorized to perform the required AWS Marketplace actions` | The Marketplace agreement for this model hasn't been accepted yet. New models (e.g., Claude Sonnet 4.6) need a one-time acceptance even though the old model catalog is retired. | An admin with `aws-marketplace:Subscribe` permissions must invoke the model once (via console playground or CLI) to accept the agreement. After that, all Lambda roles can use it. |
| Error after upgrading models in config | New model added but Marketplace agreement not accepted | Check Lambda logs to identify which model (`aws logs filter-log-events --log-group-name /aws/lambda/<stack>-query --filter-pattern "ERROR"`). Then accept the agreement — see diagnostic below. |
| Error only on chat, not other features | `chat_primary_model` points to a model without accepted agreement | Either accept the agreement for the model, or change `chat_primary_model` in Settings to a model that already works. |

**Quick diagnostic — accept agreement and test access:**
```bash
# Test from CLI (your IAM user likely has marketplace permissions).
# If this succeeds, the agreement is accepted for the account and Lambda roles will work too.
echo '{"anthropic_version":"bedrock-2023-05-31","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}' \
  | aws bedrock-runtime invoke-model \
    --model-id "us.anthropic.claude-sonnet-4-6" \
    --region us-east-1 \
    --body fileb:///dev/stdin \
    --content-type "application/json" /dev/null

# If this also fails with AccessDeniedException, your IAM user needs:
#   aws-marketplace:ViewSubscriptions
#   aws-marketplace:Subscribe
# Or use the Bedrock console playground to invoke the model (triggers agreement acceptance).
```

---

## Deployment Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| Stack creation fails with `ROLLBACK_COMPLETE` | Bedrock model agreement not accepted | Accept Marketplace agreements for required models (Anthropic Claude, etc.) by invoking them once from the CLI or Bedrock console playground. See "Bedrock Model Access Issues" above. |
| `Invalid email address` error | Bad email format | Use valid email: `python publish.py --admin-email valid@example.com` |
| `User is not authorized` | Insufficient IAM permissions | Need: `iam:*`, `cloudformation:*`, `lambda:*`, `s3:*` |
| S3 bucket name exists | Bucket name collision | Change project name: `python publish.py --project-name <unique-name>` |
| `sam build` fails | Python version mismatch | Check: `python3.13 --version`. Install Python 3.13+ if needed. |
| Docker connection error | Docker not running | Start Docker: macOS (open Docker Desktop), Linux (`sudo systemctl start docker`) |
| SAM build timeout | Network or resource issue | `sam build --use-container` |

## Document Processing Issues

| Problem | Symptoms | Solution |
|---------|----------|----------|
| Documents stuck in UPLOADED | Not processing | Verify EventBridge rule: `aws events list-rules --name-prefix RAGStack-<project>`. Check Lambda logs: `aws logs tail /aws/lambda/RAGStack-<project>-ProcessDocument --follow` |
| Documents stuck in PROCESSING | Still processing after hours | Lambda timeout (15 min limit). Split document or increase memory. Check Textract concurrency quota. |
| Documents fail with ERROR | Error in dashboard | Check Lambda logs: `aws logs tail /aws/lambda/RAGStack-<project>-ProcessDocument --follow`. Image-heavy PDFs may need Bedrock OCR (set `ocr_backend` to `bedrock`). |
| Slow processing | Takes >30 minutes | Text-native PDFs should be faster (~2-5 min). Image-heavy docs slower. Check CloudWatch for bottlenecks. |

## Media Processing Issues (Video/Audio)

| Problem | Cause | Solution |
|---------|-------|----------|
| Media stuck in PROCESSING | Transcribe job still running | Check Transcribe console for job status. Large files (>1hr) take longer. Wait up to 30 minutes for long media. |
| No transcript generated | Unsupported format or no audio | Verify file has audio track. MOV files not supported - convert to MP4. Check file isn't corrupted. |
| Wrong language detected | Incorrect language setting | Set `transcribe_language_code` in Settings to match audio language. Default is `en-US`. |
| Missing speaker labels | Diarization disabled | Enable `speaker_diarization_enabled` in Settings. Only works with supported languages. |
| Timestamp links not working | Browser doesn't support media fragments | Try Chrome/Firefox (best support). Safari has limited `#t=` fragment support. Check presigned URL hasn't expired. |
| Media player won't load | CORS or expired URL | Presigned URLs expire after 1 hour. Refresh chat to get new URLs. Check browser console for CORS errors. |
| Transcribe access denied | Missing IAM permissions | Verify Lambda has `transcribe:StartTranscriptionJob` and `transcribe:GetTranscriptionJob` permissions. |

**Debugging media processing:**
```bash
# Check Transcribe job status
aws transcribe list-transcription-jobs --status IN_PROGRESS

# View ProcessMedia Lambda logs
aws logs tail /aws/lambda/RAGStack-<project>-ProcessMedia --follow

# Check document status in DynamoDB
aws dynamodb get-item --table-name RAGStack-<project>-Documents \
  --key '{"document_id": {"S": "<document-id>"}}'
```

## Knowledge Base Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| Chat returns no results | KB not created/synced | Verify KB: `aws bedrock-agent list-knowledge-bases --query "knowledgeBaseSummaries[?contains(name,'<project>')]"`. Check sync: `aws bedrock-agent list-ingestion-jobs --knowledge-base-id <KB-ID> --data-source-id <DS-ID>`. Verify documents show INDEXED in DynamoDB. |
| Chat results irrelevant | Query too vague | Try rephrasing query (be more specific). Ensure documents are fully processed. |
| "Knowledge Base not found" error | KB ID incorrect or missing | Check SAM outputs for Knowledge Base ID. Set in environment variables. Verify KB in Bedrock console. |

## UI Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| UI not loading | CloudFront cache stale | Invalidate: `aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"` |
| Blank page after login | Cognito not configured | Check `.env.local` has correct Cognito IDs from SAM outputs. |
| Upload fails | S3 permissions or bucket missing | Verify input bucket exists. Check Cognito user has S3 put permissions. |
| API errors in console | GraphQL endpoint wrong | Check `VITE_GRAPHQL_URL` in `.env.local` matches SAM outputs. |
| Dark mode not working | System preference not detected | Set dark mode in OS settings. Test in browser DevTools. |

## Authentication Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| Login fails | Wrong credentials | Check temporary password email. Use correct format (email not username). |
| "User does not exist" | Account not created | Sign up first, verify email. Check correct user pool selected. |
| MFA errors | MFA configured but not set up | Admin sets up MFA in Cognito console or disable if not needed. |
| Session expires quickly | Token refresh issue | Clear browser cache. Check system clock (must be synchronized). Ensure HTTPS. |

## Performance Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| Lambda timeout (15 min limit) | Document too large or slow OCR | Use Textract (faster than Bedrock). Split large documents. Increase Lambda memory. |
| High costs | Bedrock tokens expensive | Use Textract OCR instead of Bedrock. Text-native PDFs skip OCR entirely. |
| Slow embeddings generation | Rate limiting or large batch | Reduce batch size. Add delay between batches. Check Bedrock quota in Service Quotas. |
| DynamoDB throttling | High write rate | Change to on-demand billing mode. Increase provisioned capacity. |

## Chat Performance

| Problem | Cause | Solution |
|---------|-------|----------|
| First chat response slow (500ms-2s) | Lambda cold start | **Expected behavior** for serverless. Subsequent requests ~200-500ms. |
| Quota limits not enforced immediately | Race condition on high concurrency | Atomic quota checking prevents most races. Some overflow (<1%) possible under extreme load. |
| Chat responses timeout | Bedrock query taking too long | Check Knowledge Base has indexed documents. Verify network connectivity to Bedrock. |
| Config changes not applied | Config cached | Wait for cache refresh or redeploy to force. |

## Runtime Configuration Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| Config values not updating | Cached in Lambda | Config cached 60s (Amplify chat). Wait or force cold start. Check DynamoDB table has correct entries. |
| "Configuration table not found" | Table name wrong | Verify `CONFIGURATION_TABLE_NAME` environment variable. Check table exists in DynamoDB. |
| Invalid config value | Schema validation failed | Check format matches schema (docs/CONFIGURATION.md). Validate regex patterns. |

## Testing Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| Unit tests fail with imports | Library not installed | `npm install` in project root. `npm run test:backend` to verify. |
| Integration tests fail | Stack not deployed or missing env vars | Export `STACK_NAME`, `DATA_BUCKET`, `TRACKING_TABLE`. Verify stack exists. |
| Sample documents missing | Not generated | `cd tests/sample-documents && python3 generate_samples.py` |

## Debugging Tips

**View Lambda Logs**
```bash
# Stream live logs
aws logs tail /aws/lambda/RAGStack-<project-name>-<function-name> --follow

# View specific execution
aws logs get-log-events --log-group-name /aws/lambda/RAGStack-<project> \
  --log-stream-name <stream-name>
```

**Check Step Functions Execution**
```bash
# List executions
aws stepfunctions list-executions --state-machine-arn <ARN>

# View execution details
aws stepfunctions describe-execution --execution-arn <ARN>

# Get full history
aws stepfunctions get-execution-history --execution-arn <ARN>
```

**Check DynamoDB Data**
```bash
# View document status
aws dynamodb scan --table-name RAGStack-<project>-Documents

# Check configuration
aws dynamodb get-item --table-name RAGStack-<project>-Configuration \
  --key '{"PK": {"S": "Schema"}}'
```

**Check Bedrock Knowledge Base**
```bash
# List knowledge bases
aws bedrock-agent list-knowledge-bases

# Get KB details
aws bedrock-agent get-knowledge-base --knowledge-base-id <KB-ID>

# Check data source sync status
aws bedrock-agent list-data-sources --knowledge-base-id <KB-ID>
```

