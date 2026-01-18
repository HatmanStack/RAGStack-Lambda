# Migration Guide: v1.x to v2.0

This guide covers migrating RAGStack deployments from v1.x (deployed after December 24, 2025) to v2.0.

## Breaking Changes in v2.0

### Architecture Changes

| Component | v1.x | v2.0 |
|-----------|------|------|
| **S3 Prefixes** | `output/` (docs), `images/` (images) | `content/` (unified) |
| **Data Sources** | 2 (TextDataSource + ImageDataSource) | 1 (DataSource) |
| **Env Vars** | `TEXT_DATA_SOURCE_ID`, `IMAGE_DATA_SOURCE_ID` | `DATA_SOURCE_ID` |
| **Image Metadata** | `IN_LINE_ATTRIBUTE` | `S3_LOCATION` (.metadata.json files) |
| **CloudFormation Outputs** | `DataSourceId`, `TextDataSourceId`, `ImageDataSourceId` | `DataSourceId` only |

### Why Migrate?

- **Simplified architecture**: Single data source reduces complexity
- **Unified content handling**: All content types use consistent metadata format
- **Improved metadata extraction**: New LLM-based metadata extraction for all content
- **Better filtering**: `content_type` field enables filtering by document/image/web_page

## Prerequisites

- Python 3.13+ with `boto3` installed
- AWS CLI configured with appropriate permissions
- Access to the deployed stack

## Migration Process

### Step 1: Run the Migration Script (Dry Run)

First, preview what changes will be made:

```bash
python scripts/migrate_v1_to_v2.py --stack-name <your-stack-name> --dry-run
```

This will show:
- Files that will be copied from `output/` and `images/` to `content/`
- DynamoDB tracking records that will be updated

### Step 2: Run the Actual Migration

Once satisfied with the dry run output:

```bash
python scripts/migrate_v1_to_v2.py --stack-name <your-stack-name>
```

The script will:
1. Copy all files from `output/` to `content/`
2. Copy all files from `images/` to `content/`
3. Update tracking table records with new S3 URIs

**Note:** The script is idempotent - it skips files that already exist in `content/` and records that are already updated.

### Step 3: Deploy v2.0 Stack

Pull the latest code and deploy:

```bash
git pull origin main
sam build
sam deploy --stack-name <your-stack-name>
```

This updates:
- Lambda functions with new single data source logic
- Knowledge Base custom resource to create unified data source
- EventBridge rules to watch `content/` prefix

### Step 4: Trigger Reindex

Open the RAGStack dashboard and navigate to **Settings**:

1. Scroll to the **Knowledge Base Reindex** section
2. Click **Start Reindex**
3. Wait for the reindex to complete

The reindex will:
- Create a new Knowledge Base with the unified `content/` data source
- Re-extract metadata for all content using the new extraction system
- Ingest all documents, images, and scraped pages with fresh embeddings
- Delete the old Knowledge Base

### Step 5: Verify Migration

After reindex completes:

1. **Test chat**: Query the Knowledge Base and verify responses
2. **Check sources**: Ensure source attribution shows correct paths
3. **Test image search**: Verify image captions are searchable
4. **Test filters**: Use content_type filter to search specific content types

## Migration Script Details

### What the Script Does

```text
migrate_v1_to_v2.py
├── Get stack outputs (bucket name, table name)
├── Step 1: Copy output/* → content/*
├── Step 2: Copy images/* → content/*
└── Step 3: Update DynamoDB tracking records
    ├── output_s3_uri: output/ → content/
    ├── input_s3_uri: images/ → content/ (for images)
    └── caption_s3_uri: images/ → content/ (for images)
```

### What the Script Does NOT Do

- Does NOT delete old files (output/, images/ remain intact)
- Does NOT modify the Knowledge Base (reindex handles this)
- Does NOT generate metadata files (reindex handles this)

### Options

```bash
python scripts/migrate_v1_to_v2.py --help

Options:
  --stack-name   CloudFormation stack name (required)
  --region       AWS region (default: us-east-1)
  --dry-run      Preview changes without making them
  --verbose, -v  Enable debug logging
```

## Reindex Details

The reindex process handles all content types with type-specific logic:

| Type | Text Source | Metadata Extraction | Ingestion |
|------|-------------|---------------------|-----------|
| Documents | `output_s3_uri` | LLM extracts from text | 1 document |
| Images | `caption_s3_uri` | LLM extracts from caption | 2 documents (image + caption) |
| Scraped | `output_s3_uri` | Job-aware (see below) | 1 document |

### Job-Aware Scraped Content Reindex

Scraped content uses a special two-level metadata extraction:

1. **Job-level metadata**: Extracted from the **seed document** (first page scraped)
   - Applied to ALL pages in the scrape job
   - Provides semantic context (e.g., "AWS Lambda documentation")

2. **Page-level metadata**: Deterministic fields for each page
   - `source_url`, `source_domain`, `scraped_date`, `job_id`

**How it works:**
```text
Scraped Page → S3 metadata → job_id
                               ↓
                          ScrapeJobs table → base_url
                               ↓
                          Find seed document (source_url == base_url)
                               ↓
                          Re-extract job metadata from seed (using NEW settings)
                               ↓
                          Merge job metadata + page metadata
```

This ensures:
- All pages in a job share semantic metadata from the seed
- Metadata uses the NEW extraction settings (not preserved from original scrape)
- Job metadata is cached per-batch to avoid redundant LLM calls

### Common Metadata

All content gets:
- Fresh metadata extraction using configured LLM model
- `content_type` field for filtering ("document", "image", "web_page")
- Base metadata (document_id, filename, file_type)

## Rollback

If issues occur after migration:

1. **Before stack deploy**: Old files still exist in `output/` and `images/` - no rollback needed
2. **After stack deploy but before reindex**: Re-deploy old code version
3. **After reindex**: The old KB is deleted; you'd need to re-upload content

## Troubleshooting

### Migration Script Errors

**"Stack not found"**
- Verify stack name is correct
- Check you're using the right AWS region

**"Access Denied" errors**
- Ensure AWS credentials have S3 read/write and DynamoDB permissions
- Check the IAM user/role has access to the stack's resources

### Reindex Errors

**"Failed to read text"**
- Check the `output_s3_uri` or `caption_s3_uri` paths are correct
- Verify files were copied to `content/` prefix

**"Metadata extraction failed"**
- Check Bedrock model access (ensure your region supports the configured model)
- Review CloudWatch logs for the ReindexKB Lambda

### Post-Migration Issues

**Chat returns no results**
- Wait for reindex to fully complete
- Check Knowledge Base status in AWS console
- Verify data source has correct `content/` prefix

**Images not searchable**
- Ensure caption files exist at `content/{imageId}/caption.txt`
- Check the image's tracking record has `caption_s3_uri` field

### SAM Layer Caching Issue

**Symptoms:**
- Lambda functions fail with `No module named 'ragstack_common'` or `No module named 'crhelper'`
- CloudFormation update gets stuck on `CodeBuildRun` or `WCCodeBuildRun` custom resources
- Stack enters `UPDATE_ROLLBACK_FAILED` state

**Cause:**
SAM uses content hashing to skip S3 uploads. After a reindex creates a new Knowledge Base, if you redeploy, SAM may reuse a stale/corrupted layer artifact from S3 instead of uploading the freshly built layer. The local build shows ~121MB but S3 only has ~120KB.

**Diagnosis:**
```bash
# Check local build size (should be ~121MB)
du -sh .aws-sam/build/RagstackCommonLayer/

# Check deployed layer size (should match, not 120KB)
aws lambda get-function-configuration --function-name <stack>-sync-status-checker \
  --query "Layers[0].CodeSize" --output text
```

**Fix:**

1. If stack is stuck in `UPDATE_IN_PROGRESS`, cancel and wait for rollback:
   ```bash
   aws cloudformation cancel-update-stack --stack-name <stack> --region us-east-1
   ```

2. If stack is in `UPDATE_ROLLBACK_FAILED`, continue rollback skipping failed resources:
   ```bash
   aws cloudformation continue-update-rollback --stack-name <stack> --region us-east-1 \
     --resources-to-skip CodeBuildRun WCCodeBuildRun BatchProcessorFunction \
       AppSyncResolverFunction ConfigurationResolverFunction
   ```

3. Once stack is in `UPDATE_ROLLBACK_COMPLETE`, clear caches and redeploy:
   ```bash
   # Delete SAM build cache
   rm -rf .aws-sam/

   # Delete stale S3 artifacts (keep UI source zips)
   aws s3 rm s3://<stack>-artifacts-<account-id>/ --recursive --exclude "*.zip"

   # Fresh build and deploy
   sam build --parallel
   python publish.py --stack-name <stack> --admin-email <email>
   ```

**Prevention:**
After running reindex, always clear the SAM cache before redeploying:
```bash
rm -rf .aws-sam/
```

## Support

For issues:
- Check [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
