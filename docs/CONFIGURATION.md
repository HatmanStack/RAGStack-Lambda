# Configuration

All settings are stored in DynamoDB and apply immediately without redeployment.

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

## Metadata Extraction

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `metadata_extraction_enabled` | boolean | true | Enable LLM-based metadata extraction |
| `metadata_extraction_model` | Model ARN | claude-3-5-haiku | Model for metadata extraction |
| `metadata_max_keys` | number | 8 | Maximum metadata fields to extract per document |

**How it works:**
1. Documents are analyzed by an LLM to extract structured metadata
2. Extracted fields like `topic`, `document_type`, `date_range`, `location` are stored
3. Base metadata (document_id, filename, file_type) is always included
4. Metadata enables filtered searches and better organization

**Cost considerations:**
- Each document incurs one additional LLM call (~100 tokens input, ~50 tokens output)
- Using Haiku: ~$0.0001 per document
- Disable if not needed to reduce costs

## Chat Settings

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `chat_primary_model` | Model ARN | claude-haiku | Model for chat responses |
| `chat_fallback_model` | Model ARN | nova-micro | Used when quota exceeded |
| `chat_global_quota_daily` | number | 10000 | Total queries/day for all users |
| `chat_per_user_quota_daily` | number | 100 | Queries/day per authenticated user |
| `chat_allow_document_access` | boolean | false | Show "View Document" links in sources |

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
