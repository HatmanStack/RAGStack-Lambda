# Configuration

All settings are stored in DynamoDB. Changes are read on each Lambda request (no caching), so updates apply immediately without redeployment.

## Settings UI

**Dashboard → Settings** - Change any setting, click Save.

## API Key Management

The API key is for **server-side use only** - MCP servers, backend scripts, and integrations.

**Never expose in frontend code, browser applications, or public repositories.**

**View/Regenerate:** Dashboard → Settings → API Key section

| Action | Description |
|--------|-------------|
| View API Key | Shows current key (click to reveal) |
| Regenerate | Creates new key, invalidates old one immediately |

**Regenerate:** Dashboard → Settings → Regenerate to create a new key (invalidates old key immediately).

**Usage (server-side only):**
```bash
curl -X POST 'YOUR_GRAPHQL_ENDPOINT' \
  -H 'x-api-key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"query": "..."}'
```

## Authentication Methods

| Method | Use Case | Operations |
|--------|----------|------------|
| **IAM (unauth)** | Web component | Query, Search, Subscriptions |
| **API Key** | Server-side integrations | All operations |
| **Cognito** | Admin UI | All operations |

The web component uses IAM authentication via Cognito Identity Pool (no API key needed).

## MCP Server (AI Assistant Integration)

Connect your knowledge base to Claude Desktop, Cursor, VS Code, Amazon Q CLI, and other MCP-compatible AI tools.

**Install:** `pip install ragstack-mcp` or use `uvx` (zero-install)

**Configure:** Add to your AI assistant's MCP config file:

```json
{
  "ragstack-kb": {
    "command": "uvx",
    "args": ["ragstack-mcp"],
    "env": {
      "RAGSTACK_GRAPHQL_ENDPOINT": "YOUR_ENDPOINT",
      "RAGSTACK_API_KEY": "YOUR_API_KEY"
    }
  }
}
```

| Client | Config Location |
|--------|-----------------|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) |
| Amazon Q CLI | `~/.aws/amazonq/mcp.json` |
| Cursor | Settings → MCP Servers |
| VS Code + Cline | `.vscode/cline_mcp_settings.json` |

**Available tools:** `search_knowledge_base`, `chat_with_knowledge_base`, `start_scrape_job`, `get_scrape_job_status`, `list_scrape_jobs`, `upload_document_url`

See [MCP Server README](../src/ragstack-mcp/README.md) for detailed setup per client.

## User Management (Cognito)

Users in the Cognito User Pool can authenticate to both the admin dashboard and the embedded chat widget.

**Add a user via AWS Console:**
1. Go to **Amazon Cognito** → **User pools** → `{ProjectName}-Users`
2. Click **Create user**
3. Enter email address and temporary password
4. User receives email with login instructions

**Add a user via CLI:**
```bash
aws cognito-idp admin-create-user \
  --user-pool-id YOUR_USER_POOL_ID \
  --username user@example.com \
  --user-attributes Name=email,Value=user@example.com Name=email_verified,Value=true \
  --temporary-password TempPass123!
```

**Get User Pool ID:**
```bash
aws cloudformation describe-stacks --stack-name YOUR_STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text
```

**For web component auth:** Pass the user's Cognito JWT token to the `user-token` attribute. See the Chat tab's "Authenticated" embed example.

## Document Processing

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `ocr_backend` | textract, bedrock | textract | Textract is faster and cheaper |
| `bedrock_ocr_model_id` | Claude model ID | haiku | Only used when ocr_backend=bedrock |

## Media Processing (Video/Audio)

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `transcribe_language_code` | See options below | en-US | Language for speech-to-text |
| `speaker_diarization_enabled` | boolean | true | Identify and label speakers |
| `media_segment_duration_seconds` | number | 30 | Chunk duration for embedding |

**Language code options (common):**
- `en-US` - English (US) - default
- `en-GB` - English (UK)
- `en-AU` - English (Australia)
- `es-ES` - Spanish (Spain)
- `es-US` - Spanish (US)
- `fr-FR` - French
- `de-DE` - German
- `it-IT` - Italian
- `pt-BR` - Portuguese (Brazil)
- `ja-JP` - Japanese
- `ko-KR` - Korean
- `zh-CN` - Chinese (Simplified)

For the complete list of supported languages, see [AWS Transcribe Supported Languages](https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html).

**How it works:**
1. Video/audio files are detected by content type during upload
2. Files are sent to AWS Transcribe for speech-to-text conversion
3. Transcripts are segmented into 30-second chunks (configurable)
4. Each segment is embedded and indexed for search
5. Speaker labels are preserved when diarization is enabled

**Speaker diarization:**
- When enabled, Transcribe identifies different speakers in the audio
- Up to 10 speakers can be identified
- Each segment tracks the primary speaker
- Useful for interviews, meetings, podcasts

**Segment duration:**
- Controls how transcripts are chunked for embedding
- Shorter segments (15-30s) = more precise search results
- Longer segments (60-120s) = more context per result
- Default 30s balances precision and context

**Supported formats:**
- Video: MP4, WebM
- Audio: MP3, WAV, M4A, OGG, FLAC

**Note:** AWS Transcribe extracts audio from MP4 and WebM video files automatically. MOV files are not natively supported and must be converted to MP4 first.

## Image Processing

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `image_caption_prompt` | string | See below | System prompt for image caption generation |

**Default image caption prompt:**
> You are an image captioning assistant. Generate concise, descriptive captions that are suitable for use as search keywords. Focus on the main subject, setting, and any notable visual elements. Keep captions under 200 characters.

## Metadata Extraction

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `metadata_extraction_enabled` | boolean | true | Enable LLM-based metadata extraction |
| `metadata_extraction_model` | See options below | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Model for metadata extraction |
| `metadata_max_keys` | number | 8 | Maximum metadata fields per document |
| `metadata_extraction_mode` | auto, manual | auto | Auto: LLM decides keys. Manual: use specified keys only |
| `metadata_manual_keys` | string[] | [] | Keys to extract in manual mode |

**Extraction model options:**
- `us.anthropic.claude-haiku-4-5-20251001-v1:0` (default)
- `us.anthropic.claude-3-5-haiku-20241022-v1:0`
- `us.amazon.nova-micro-v1:0`
- `us.amazon.nova-lite-v1:0`

**How it works:**
1. During document ingestion, content is analyzed by an LLM
2. LLM extracts structured metadata fields (e.g., `topic`, `document_type`, `date_range`, `location`)
3. Extracted metadata is stored with the document vectors for filtered retrieval
4. **Auto mode:** LLM decides which keys to extract based on content
5. **Manual mode:** Only extracts keys you specify in `metadata_manual_keys`

**Cost considerations:**
- Each document incurs one additional LLM call (~100 tokens input, ~50 tokens output)
- Using Haiku: ~$0.0001 per document
- Disable if not needed to reduce costs

## Document Management

Manage individual documents from the Dashboard → Documents tab.

### Actions

| Action | Description | Use Case |
|--------|-------------|----------|
| **Reprocess** | Re-run full processing pipeline (OCR/text extraction → metadata → KB ingestion) | Document failed, content changed, or OCR quality issues |
| **Reindex** | Re-extract metadata only (skip OCR), reingest to KB | Changed metadata settings, faster than reprocess |
| **Delete** | Remove from tracking table (does not delete from S3 or KB) | Clean up failed or unwanted documents |

### How to Use

1. Navigate to **Dashboard → Documents** (or Images)
2. Select document(s) using checkboxes
3. Click action button (Reprocess, Reindex, or Delete)
4. For Reprocess/Reindex: monitor progress via status column

### GraphQL API

```graphql
# Reprocess - full pipeline
mutation { reprocessDocument(documentId: "doc-123") { documentId status } }

# Reindex - metadata only (faster)
mutation { reindexDocument(documentId: "doc-123") { documentId status } }

# Delete documents (batch)
mutation { deleteDocuments(documentIds: ["doc-1", "doc-2"]) { deletedCount } }

# Delete image
mutation { deleteImage(imageId: "img-123") }
```

**Note:** Delete removes tracking records only. S3 files and KB vectors remain until the next full reindex or manual cleanup.

## Knowledge Base Reindex

Reindex allows you to regenerate metadata for **all** existing documents using current extraction settings. This is useful when:

- You uploaded documents before enabling metadata extraction
- You changed metadata settings (e.g., switched from auto to manual mode with specific keys)
- You're migrating from an older version with different S3 prefix structures

**Location:** Dashboard → Settings → Metadata Extraction → Reindex All Documents

**What happens during reindex:**
1. Creates a new Knowledge Base with fresh S3 Vectors storage
2. Iterates through all documents in the tracking table
3. Regenerates metadata using current extraction settings
4. Ingests documents into the new Knowledge Base
5. Deletes the old Knowledge Base after successful migration

**Important notes:**
- Reindex does NOT re-run OCR/text extraction (uses existing extracted text)
- Documents without extracted text (`output_s3_uri`) are skipped
- Queries may return partial results during reindex
- Process time depends on document count (expect several minutes for large KBs)
- Progress is displayed in real-time via the Settings UI

**When NOT to use reindex:**
- To re-extract text from documents (re-upload them instead)
- For minor setting changes that don't affect existing documents

## Query-Time Filtering

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `filter_generation_enabled` | boolean | true | Enable LLM-based filter generation from queries |
| `filter_generation_model` | See options below | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Model for filter generation |
| `multislice_enabled` | boolean | true | Enable parallel filtered/unfiltered queries |
| `multislice_count` | number | 2 | Number of parallel retrieval slices (2-4) |
| `multislice_timeout_ms` | number | 5000 | Timeout per slice in milliseconds |
| `multislice_filtered_boost` | 1.0-2.0 | 1.25 | Score multiplier for filtered results (1.25 = 25% boost) |

**Filter generation model options:**
- `us.anthropic.claude-haiku-4-5-20251001-v1:0` (default)
- `us.anthropic.claude-3-5-haiku-20241022-v1:0`

**Filter examples:** Managed via Settings → Metadata Analysis panel. Run "Analyze Metadata" to generate examples, then enable/disable individual examples to control few-shot learning patterns. See [METADATA_FILTERING.md](./METADATA_FILTERING.md) for details.

**How it works:**
1. User query is analyzed by LLM to detect filter intent
2. If filter intent detected, generates S3 Vectors compatible filter
3. Multi-slice retrieval runs filtered + unfiltered queries in parallel
4. Results are deduplicated and merged by relevance score

**Performance notes:**
- Filter generation adds ~100-200ms latency
- Multi-slice retrieval runs in parallel, not sequential
- Disable for latency-sensitive applications

## Chat Settings

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `chat_primary_model` | See options below | claude-haiku-4-5 | Model for chat responses |
| `chat_fallback_model` | See options below | nova-lite | Used when quota exceeded |
| `chat_global_quota_daily` | number | 10000 | Total queries/day for all users |
| `chat_per_user_quota_daily` | number | 100 | Queries/day per authenticated user |
| `chat_allow_document_access` | boolean | false | Show "View Document" links in sources |
| `chat_system_prompt` | string | See below | System prompt for chat responses |

**Default chat system prompt:**
> You are a helpful assistant that answers questions based on information from a knowledge base. Always base your answers on the provided knowledge base information. If the provided information doesn't contain the answer, clearly state that and provide what relevant information you can. Be concise but thorough.

**Primary model options:**
- `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
- `us.anthropic.claude-haiku-4-5-20251001-v1:0` (default)
- `us.amazon.nova-pro-v1:0`
- `us.amazon.nova-lite-v1:0`

**Fallback model options:**
- `us.anthropic.claude-haiku-4-5-20251001-v1:0`
- `us.amazon.nova-micro-v1:0`
- `us.amazon.nova-lite-v1:0` (default)

## Access Control

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `public_access_chat` | boolean | true | Allow unauthenticated chat queries |
| `public_access_search` | boolean | true | Allow unauthenticated search queries |
| `public_access_upload` | boolean | false | Allow unauthenticated document uploads |
| `public_access_image_upload` | boolean | false | Allow unauthenticated image uploads |
| `public_access_scrape` | boolean | false | Allow unauthenticated web scrape jobs |

## Budget Alerts

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `budget_alert_threshold` | number | 100 | Monthly budget alert threshold (USD) |
| `budget_alert_enabled` | boolean | true | Enable email alerts at 80% and 100% |

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

## Demo Mode

Demo mode restricts functionality for public showcases and trial deployments.

**Restrictions:**
- **Upload limit:** 5 documents per day
- **Chat limit:** 30 queries per day
- **Disabled features:** Reindex, Reprocess, Delete operations

**Use Cases:**
- Public demos (prevent abuse)
- Showcase environments with limited AWS quotas
- Trial deployments before production

**Enable:** `python publish.py --project-name demo --admin-email admin@example.com --demo-mode`

**Disable:** Redeploy without `--demo-mode` flag.
