# RAGStack-Lambda Configuration Guide

This guide covers how to configure and customize RAGStack-Lambda for your use case.

## Table of Contents

- [Configuration Overview](#configuration-overview)
- [Runtime Configuration Management](#runtime-configuration-management)
- [SAM Configuration](#sam-configuration)
- [CloudFormation Parameters](#cloudformation-parameters)
- [Environment-Specific Configuration](#environment-specific-configuration)
- [Lambda Configuration](#lambda-configuration)
- [OCR Configuration](#ocr-configuration)
- [Embedding Models](#embedding-models)
- [UI Configuration](#ui-configuration)
- [Cost Optimization](#cost-optimization)

---

## Configuration Overview

RAGStack-Lambda uses multiple configuration layers:

1. **CLI Parameters** - Deployment-time configuration via `publish.py` arguments
2. **CloudFormation Parameters** (`template.yaml`) - Infrastructure parameters
3. **Lambda Environment Variables** - Runtime configuration
4. **UI Configuration** (generated during deployment) - Frontend settings
5. **Runtime Configuration** (DynamoDB) - User-modifiable settings via Settings UI

---

## Runtime Configuration Management

Starting with the runtime configuration feature, you can modify operational parameters through the Settings UI without redeploying the stack. This includes OCR backends, embedding models, and response models.

### Overview

Runtime configuration is stored in a DynamoDB table (`RAGStack-<project>-Configuration`) with three types of items:

| Type | Purpose | Editable | Modified By |
|------|---------|----------|-------------|
| **Schema** | Defines available parameters and validation rules | No | CloudFormation deployment |
| **Default** | System default values | No | `publish.py` script during deployment |
| **Custom** | User overrides | Yes | Settings UI in WebUI |

**Effective Configuration**: Lambda functions merge Custom → Default to get the effective configuration. Custom values override Default values.

### Accessing Runtime Configuration

#### Via Settings UI (Recommended)

1. Open WebUI and navigate to **Settings** page
2. Modify any configuration parameters
3. Click **Save changes**
4. Changes take effect **immediately** on next Lambda invocation (no cache)

See [USER_GUIDE.md - Managing Settings](USER_GUIDE.md#managing-settings) for detailed instructions.

#### Via AWS CLI

**View Current Configuration**:

```bash
# Get Default configuration
aws dynamodb get-item \
  --table-name RAGStack-<project>-Configuration \
  --key '{"Configuration": {"S": "Default"}}'

# Get Custom overrides
aws dynamodb get-item \
  --table-name RAGStack-<project>-Configuration \
  --key '{"Configuration": {"S": "Custom"}}'

# Get Schema (available parameters)
aws dynamodb get-item \
  --table-name RAGStack-<project>-Configuration \
  --key '{"Configuration": {"S": "Schema"}}'
```

**Modify Configuration Programmatically**:

```python
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('RAGStack-<project>-Configuration')

# Update custom configuration
table.put_item(
    Item={
        'Configuration': 'Custom',
        'ocr_backend': 'bedrock',
        'bedrock_ocr_model_id': 'anthropic.claude-3-5-sonnet-20241022-v2:0',
        'text_embed_model_id': 'cohere.embed-english-v3'
    }
)
```

**Reset to Defaults**:

```bash
# Remove all custom overrides (revert to defaults)
aws dynamodb put-item \
  --table-name RAGStack-<project>-Configuration \
  --item '{"Configuration": {"S": "Custom"}}'
```

### Seeding Configuration

Configuration is automatically seeded during deployment by `publish.py`. To manually re-seed:

```bash
# Re-run publish.py (includes configuration seeding)
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region>
```

**Manual Seeding Script** (if needed):

```python
import boto3
import json

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('RAGStack-<project>-Configuration')

# Seed Schema
schema = {
    "properties": {
        "ocr_backend": {
            "type": "string",
            "enum": ["textract", "bedrock"],
            "description": "OCR Backend",
            "order": 1
        },
        "bedrock_ocr_model_id": {
            "type": "string",
            "enum": [
                "anthropic.claude-3-5-haiku-20241022-v1:0",
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "anthropic.claude-3-opus-20240229-v1:0"
            ],
            "description": "Bedrock OCR Model",
            "order": 2,
            "dependsOn": {
                "field": "ocr_backend",
                "value": "bedrock"
            }
        },
        "text_embed_model_id": {
            "type": "string",
            "enum": [
                "amazon.titan-embed-text-v1",
                "amazon.titan-embed-text-v2:0",
                "cohere.embed-english-v3",
                "cohere.embed-multilingual-v3"
            ],
            "description": "Text Embedding Model",
            "order": 3
        },
        "image_embed_model_id": {
            "type": "string",
            "enum": ["amazon.titan-embed-image-v1"],
            "description": "Image Embedding Model",
            "order": 4
        },
        "response_model_id": {
            "type": "string",
            "enum": [
                "anthropic.claude-3-5-haiku-20241022-v1:0",
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "anthropic.claude-3-opus-20240229-v1:0"
            ],
            "description": "Response Model",
            "order": 5
        }
    },
    "required": ["ocr_backend", "text_embed_model_id", "image_embed_model_id", "response_model_id"]
}

table.put_item(
    Item={
        'Configuration': 'Schema',
        'Schema': schema
    }
)

# Seed Default configuration
default_config = {
    'Configuration': 'Default',
    'ocr_backend': 'textract',
    'bedrock_ocr_model_id': 'anthropic.claude-3-5-haiku-20241022-v1:0',
    'text_embed_model_id': 'amazon.titan-embed-text-v2:0',
    'image_embed_model_id': 'amazon.titan-embed-image-v1',
    'response_model_id': 'anthropic.claude-3-5-haiku-20241022-v1:0'
}

table.put_item(Item=default_config)

print("Configuration seeded successfully")
```

### Configurable Parameters

#### ocr_backend
- **Type**: String
- **Options**: `textract`, `bedrock`
- **Default**: `textract`
- **Purpose**: Choose OCR engine for document text extraction
- **When to change**: Use Bedrock for complex layouts, multilingual documents

#### bedrock_ocr_model_id
- **Type**: String
- **Options**: `claude-3-5-haiku`, `claude-3-5-sonnet`, `claude-3-opus`
- **Default**: `claude-3-5-haiku`
- **Visibility**: Only when `ocr_backend = bedrock`
- **Purpose**: Select Claude model for Bedrock OCR
- **When to change**: Use Sonnet/Opus for higher accuracy on complex documents

#### text_embed_model_id
- **Type**: String
- **Options**: `amazon.titan-embed-text-v1`, `amazon.titan-embed-text-v2:0`, `cohere.embed-english-v3`, `cohere.embed-multilingual-v3`
- **Default**: `amazon.titan-embed-text-v2:0`
- **Purpose**: Model for generating text embeddings
- **When to change**:
  - Use Cohere Multilingual for non-English documents
  - Stay within same model family when changing (see KB compatibility notes)

#### image_embed_model_id
- **Type**: String
- **Options**: `amazon.titan-embed-image-v1`
- **Default**: `amazon.titan-embed-image-v1`
- **Purpose**: Model for generating image embeddings

#### response_model_id
- **Type**: String
- **Options**: `claude-3-5-haiku`, `claude-3-5-sonnet`, `claude-3-opus`
- **Default**: `claude-3-5-haiku`
- **Purpose**: Model for Knowledge Base query responses
- **When to change**: Use Sonnet/Opus for more detailed, nuanced answers

### Adding New Models to Schema

To add new models (e.g., a new Bedrock embedding model):

1. **Update Schema in `template.yaml`**:

   Locate the Schema definition in template.yaml and add the new model to the appropriate enum:

   ```yaml
   # Example: Adding a new text embedding model
   text_embed_model_id:
     type: string
     enum:
       - amazon.titan-embed-text-v1
       - amazon.titan-embed-text-v2:0
       - cohere.embed-english-v3
       - cohere.embed-multilingual-v3
       - amazon.titan-embed-text-v3  # NEW MODEL
     description: Text Embedding Model
     order: 3
   ```

2. **Redeploy the stack**:

   ```bash
   python publish.py \
     --project-name <project-name> \
     --admin-email <email> \
     --region <region>
   ```

3. **Verify in Settings UI**:
   - Open Settings page
   - New model should appear in dropdown
   - Test by selecting and saving

### Configuration Best Practices

#### For Development/Testing
- Use **Textract** for OCR (faster, cheaper)
- Use **Haiku** models for responses (faster)
- Change configurations frequently via Settings UI to experiment

#### For Production
- Use **Textract** for standard documents
- Use **Bedrock Sonnet OCR** for complex/multilingual documents
- Use **Titan Text v2** or **Cohere English v3** for embeddings
- Use **Sonnet** for response model (good balance of speed and quality)
- Always **re-embed** when changing embedding models

#### Cost Optimization
- **OCR**: Textract ($1.50/1000 pages) vs. Bedrock ($25-75/1000 pages)
- **Embeddings**: Minimal cost difference between models
- **Responses**: Haiku is 10x cheaper than Opus

#### Knowledge Base Compatibility
- **Stay within model families** when changing embedding models
- **Safe**: titan-v1 → titan-v2, cohere-english → cohere-multilingual
- **Unsafe**: titan → cohere (requires KB recreation)
- See [USER_GUIDE.md - Knowledge Base Compatibility](USER_GUIDE.md#knowledge-base-compatibility)

### Troubleshooting Configuration

#### Configuration Not Loading

**Problem**: Lambda logs show "Configuration table name not provided"

**Solution**: Ensure `CONFIGURATION_TABLE_NAME` environment variable is set on Lambda:

```bash
aws lambda update-function-configuration \
  --function-name RAGStack-<project>-ProcessDocument \
  --environment Variables={CONFIGURATION_TABLE_NAME=RAGStack-<project>-Configuration}
```

#### Changes Not Taking Effect

**Problem**: Changed configuration in UI but Lambdas still use old values

**Solution**:
1. Verify Custom configuration was saved:
   ```bash
   aws dynamodb get-item \
     --table-name RAGStack-<project>-Configuration \
     --key '{"Configuration": {"S": "Custom"}}'
   ```
2. Check Lambda logs for "Effective configuration" log line
3. Configuration is NOT cached - changes should be immediate

#### Default Configuration Missing

**Problem**: Settings UI shows empty or errors on load

**Solution**: Re-seed configuration:
```bash
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region>
```

---

## Deployment Configuration

All deployment configuration is provided via CLI parameters to `publish.py`:

```bash
python publish.py \
  --project-name <project-name> \    # Required: Identifies this deployment
  --admin-email <email> \             # Required: Admin user email
  --region <region>                   # Required: AWS region
```

**Project Name Rules:**
- Lowercase letters, numbers, and hyphens only
- Must start with a lowercase letter
- Length: 2-32 characters
- Valid examples: `customer-docs`, `legal-archive`, `hr-system`
- Invalid examples: `Customer-Docs`, `_private`, `test docs`, `a`

---

## SAM Configuration

The `samconfig.toml` file contains minimal build settings only. All deployment parameters are provided via CLI:

### File Structure

```toml
version = 0.1

[default]
[default.global.parameters]
# Build settings only - no deployment configuration

[default.build.parameters]
cached = true
parallel = true
```

**Note:** Unlike previous versions, `samconfig.toml` no longer contains environment-specific configurations. All deployment parameters must be provided on the command line

---

## CloudFormation Parameters

These parameters are defined in `template.yaml` and can be overridden during deployment.

### ProjectName

- **Type**: String
- **Default**: `RAGStack`
- **Description**: Prefix for all AWS resource names
- **Constraints**:
  - Must start with a letter
  - 2-33 characters
  - Only alphanumeric and hyphens

**Example**:

```bash
python publish.py --project-name <project-name> --admin-email <email> --region <region> --admin-email admin@example.com
# Creates resources like: RAGStack-<project-name>-InputBucket, RAGStack-<project-name>-ProcessDocument, etc.
```

### OcrBackend

- **Type**: String
- **Default**: `textract`
- **Allowed Values**: `textract`, `bedrock`
- **Description**: OCR engine to use

**Textract** (Recommended):
- Lower cost ($1.50 per 1000 pages)
- Faster processing
- Better table extraction
- Dedicated OCR service

**Bedrock** (Alternative):
- Higher cost (~$25-75 per 1000 pages)
- Multimodal understanding
- Better for complex layouts
- Uses Claude models

**Configure**:

```toml
# In samconfig.toml
parameter_overrides = [
  "OcrBackend=bedrock"
]
```

### BedrockOcrModelId

- **Type**: String
- **Default**: `anthropic.claude-3-5-haiku-20241022-v1:0`
- **Description**: Bedrock model for OCR (only used if `OcrBackend=bedrock`)
- **Allowed Values**:
  - `anthropic.claude-3-5-haiku-20241022-v1:0` (recommended - fast, cost-effective)
  - `anthropic.claude-3-5-sonnet-20241022-v2:0` (higher quality, slower)
  - `anthropic.claude-3-haiku-20240307-v1:0` (legacy)
  - `anthropic.claude-3-sonnet-20240229-v1:0` (legacy)

**Cost Comparison** (per 1M input tokens):

| Model | Cost | Use Case |
|-------|------|----------|
| Claude 3.5 Haiku | $0.80 | Fast OCR, simple docs |
| Claude 3.5 Sonnet | $3.00 | Complex layouts, higher accuracy |

**Configure**:

```toml
parameter_overrides = [
  "OcrBackend=bedrock",
  "BedrockOcrModelId=anthropic.claude-3-5-sonnet-20241022-v2:0"
]
```

### TextEmbedModelId

- **Type**: String
- **Default**: `amazon.titan-embed-text-v2:0`
- **Description**: Model for text embeddings
- **Allowed Values**:
  - `amazon.titan-embed-text-v2:0` (recommended - 1024 dimensions)
  - `amazon.titan-embed-text-v1` (legacy - 512 dimensions)

**Titan v2 advantages**:
- Higher quality embeddings
- Better semantic search
- Support for longer texts (8K tokens vs 512 tokens)
- Same cost as v1

**Configure**:

```toml
parameter_overrides = [
  "TextEmbedModelId=amazon.titan-embed-text-v2:0"
]
```

### ImageEmbedModelId

- **Type**: String
- **Default**: `amazon.titan-embed-image-v1`
- **Description**: Model for image embeddings
- **Allowed Values**:
  - `amazon.titan-embed-image-v1` (only option currently)

Image embeddings enable:
- Visual similarity search
- Multimodal retrieval
- Image-based queries

### AdminEmail

- **Type**: String
- **Required**: Yes
- **Description**: Email for Cognito admin user
- **Format**: Valid email address

This email receives:
- Temporary password on first deployment
- Password reset links
- Administrative notifications

**Configure**:

```bash
python publish.py --project-name <project-name> --admin-email <email> --region <region> --admin-email admin@example.com
```

### AlertEmail

- **Type**: String
- **Description**: Email for CloudWatch alarms and budget alerts
- **Format**: Valid email address

Receives notifications for:
- Lambda errors exceeding threshold
- DLQ message accumulation
- Budget warnings
- Step Function failures

**Configure**:

```bash
python publish.py --project-name <project-name> --admin-email <email> --region <region> \
  --admin-email admin@example.com \
  --alert-email alerts@example.com
```

---

## Project-Based Configuration

Deploy multiple independent projects with different configurations:

### Development Project Example

Optimized for rapid iteration:

```bash
python publish.py \
  --project-name myapp-dev \
  --admin-email dev@example.com \
  --region us-east-1
```

Resources created:
- Stack: `RAGStack-myapp-dev`
- Buckets: `ragstack-myapp-dev-input-<account-id>`, etc.
- Functions: `RAGStack-myapp-dev-ProcessDocument`, etc.

### Production Project Example

Optimized for reliability:

```bash
python publish.py \
  --project-name myapp-prod \
  --admin-email admin@example.com \
  --region us-east-1
```

Resources created:
- Stack: `RAGStack-myapp-prod`
- Buckets: `ragstack-myapp-prod-input-<account-id>`, etc.
- Functions: `RAGStack-myapp-prod-ProcessDocument`, etc.

### Multi-Project Deployments

You can deploy as many independent projects as needed:

```bash
# Customer service documents
python publish.py --project-name customer-docs --admin-email cs@example.com --region us-east-1

# Legal archive
python publish.py --project-name legal-archive --admin-email legal@example.com --region us-east-1

# HR records
python publish.py --project-name hr-records --admin-email hr@example.com --region us-west-2
```

Each project is completely isolated with its own resources.

**Best practices**:
- Use descriptive project names (e.g., `myapp-prod`, not just `prod`)
- Keep project names consistent across team members
- Document which project serves which purpose
- Consider regional deployment for compliance/latency requirements

---

## Lambda Configuration

Lambda functions use global settings defined in `template.yaml`:

### Global Function Settings

```yaml
Globals:
  Function:
    Runtime: python3.13
    Timeout: 900  # 15 minutes
    MemorySize: 2048
    Environment:
      Variables:
        LOG_LEVEL: INFO
```

### Runtime Configuration

| Setting | Value | Reason |
|---------|-------|--------|
| Runtime | `python3.13` | Latest Python, better performance |
| Timeout | `900s` (15 min) | Large documents need time |
| Memory | `2048 MB` | OCR and embeddings are memory-intensive |
| Log Level | `INFO` | Balance between verbosity and noise |

### Adjusting Lambda Settings

To change timeout or memory for all functions, edit `template.yaml`:

```yaml
Globals:
  Function:
    Timeout: 600  # 10 minutes
    MemorySize: 3008  # 3 GB
```

To change for a specific function:

```yaml
ProcessDocumentFunction:
  Type: AWS::Serverless::Function
  Properties:
    Timeout: 900
    MemorySize: 4096  # Override global setting
```

### Log Levels

Available levels (set via `LOG_LEVEL` environment variable):

| Level | Use Case |
|-------|----------|
| `DEBUG` | Development, troubleshooting |
| `INFO` | Production (recommended) |
| `WARNING` | Minimal logging |
| `ERROR` | Only errors |

**Change log level**:

```bash
aws lambda update-function-configuration \
  --function-name RAGStack-<project-name>-ProcessDocument \
  --environment "Variables={LOG_LEVEL=DEBUG}"
```

---

## OCR Configuration

### Choosing an OCR Backend

| Feature | Textract | Bedrock |
|---------|----------|---------|
| **Cost** | $1.50/1000 pages | $25-75/1000 pages |
| **Speed** | Fast (~2s/page) | Slower (~5s/page) |
| **Accuracy** | Excellent | Excellent |
| **Tables** | Native support | Via prompting |
| **Handwriting** | Good | Very good |
| **Complex layouts** | Good | Excellent |

### Textract Configuration

Default configuration uses Textract's `DetectDocumentText` API:

```python
# In lib/ragstack_common/ocr.py
response = textract.detect_document_text(
    Document={'S3Object': {'Bucket': bucket, 'Key': key}}
)
```

**For documents with tables**, the code automatically uses `AnalyzeDocument`:

```python
if has_tables:
    response = textract.analyze_document(
        Document={'S3Object': {'Bucket': bucket, 'Key': key}},
        FeatureTypes=['TABLES', 'FORMS']
    )
```

### Bedrock OCR Configuration

When using Bedrock OCR, the system uses vision-enabled Claude models:

```python
# Automatically encodes images and sends to Bedrock
response = bedrock.invoke_model(
    modelId='anthropic.claude-3-5-haiku-20241022-v1:0',
    body={
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64', 'data': image_b64}},
                {'type': 'text', 'text': 'Extract all text from this image...'}
            ]
        }]
    }
)
```

---

## Embedding Models

### Text Embeddings

**Titan Embed Text v2** (recommended):
- **Dimensions**: 1024
- **Max input**: 8,192 tokens
- **Cost**: $0.0002 per 1K tokens
- **Use case**: Document text embeddings

**Titan Embed Text v1** (legacy):
- **Dimensions**: 512
- **Max input**: 512 tokens
- **Cost**: $0.0002 per 1K tokens
- **Use case**: Older deployments

### Image Embeddings

**Titan Embed Image v1**:
- **Dimensions**: 1024
- **Max size**: 2048x2048 pixels
- **Cost**: $0.00006 per image
- **Use case**: Visual similarity, multimodal search

### Embedding Generation Strategy

The system generates embeddings in batches to avoid Lambda timeouts:

```python
BATCH_SIZE = 20  # Pages per batch
DELAY_BETWEEN_BATCHES = 2  # seconds

for i in range(0, len(pages), BATCH_SIZE):
    batch = pages[i:i+BATCH_SIZE]
    process_batch(batch)
    time.sleep(DELAY_BETWEEN_BATCHES)
```

For documents >20 pages, processing is automatically batched.

---

## UI Configuration

The React UI is configured in `src/ui/src/config.js`:

```javascript
export const awsConfig = {
  region: process.env.REACT_APP_AWS_REGION || 'us-east-1',
  userPoolId: process.env.REACT_APP_USER_POOL_ID,
  userPoolWebClientId: process.env.REACT_APP_USER_POOL_CLIENT_ID,
  apiUrl: process.env.REACT_APP_API_URL
};
```

### Building the UI

Configuration is injected during build:

```bash
cd src/ui

# Build with production config
npm run build

# Build with custom config
REACT_APP_AWS_REGION=us-west-2 \
REACT_APP_USER_POOL_ID=us-west-2_ABC123 \
npm run build
```

### Environment Variables

The `publish.py` script automatically configures these during deployment:

```bash
# Extracted from CloudFormation outputs
export REACT_APP_AWS_REGION="us-east-1"
export REACT_APP_USER_POOL_ID="us-east-1_ABC123DEF"
export REACT_APP_USER_POOL_CLIENT_ID="abcdef123456"
export REACT_APP_API_URL="https://xyz.appsync-api.us-east-1.amazonaws.com/graphql"
```

---

## Cost Optimization

### Reduce OCR Costs

1. **Use Textract instead of Bedrock**:
   ```toml
   parameter_overrides = ["OcrBackend=textract"]
   ```
   Saves ~$20-60/month for 1000 documents

2. **Optimize image quality**:
   - Documents are resized to optimal dimensions in `lib/ragstack_common/image.py`
   - Textract: 150 DPI
   - Bedrock: 1024x1024 max

### Reduce Lambda Costs

1. **Adjust memory** (cost scales with memory):
   ```yaml
   MemorySize: 1769  # Sweet spot for CPU/memory ratio
   ```

2. **Reduce timeout** (if documents are small):
   ```yaml
   Timeout: 300  # 5 minutes for <10 page docs
   ```

3. **Use ARM Graviton** (not yet supported in SAM for Python 3.13)

### Reduce Storage Costs

1. **S3 Lifecycle policies** (already configured):
   - Incomplete uploads deleted after 7 days
   - Consider adding transition to Glacier after 90 days

2. **DynamoDB on-demand** (already configured):
   - Only pay for actual reads/writes
   - No capacity planning needed

### Monitoring Costs

Enable budget alerts:

```bash
aws budgets create-budget \
  --account-id 123456789012 \
  --budget file://budget.json
```

---

## Next Steps

- **Deploy** - See [Deployment Guide](DEPLOYMENT.md)
- **Use the system** - See [User Guide](USER_GUIDE.md)
- **Monitor performance** - See [Architecture Guide](ARCHITECTURE.md)
- **Troubleshoot** - See [Troubleshooting Guide](TROUBLESHOOTING.md)
