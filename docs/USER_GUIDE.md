# RAGStack-Lambda User Guide

This guide explains how to use the RAGStack-Lambda web interface to upload, monitor, and search documents.

## Table of Contents

- [Accessing the Web UI](#accessing-the-web-ui)
- [Signing In](#signing-in)
- [Dashboard Overview](#dashboard-overview)
- [Uploading Documents](#uploading-documents)
- [Monitoring Document Processing](#monitoring-document-processing)
- [Searching Documents](#searching-documents)
- [Managing Settings](#managing-settings)
- [Understanding Document Status](#understanding-document-status)
- [Tips and Best Practices](#tips-and-best-practices)

---

## Accessing the Web UI

After deployment, you'll receive a CloudFront URL where the web interface is hosted.

### Finding Your URL

The URL is provided in CloudFormation stack outputs:

```bash
# Get URL from AWS CLI
aws cloudformation describe-stacks \
  --stack-name RAGStack-<project-name> \
  --query 'Stacks[0].Outputs[?OutputKey==`WebUIUrl`].OutputValue' \
  --output text

# Example output:
# https://d1234567890abc.cloudfront.net
```

Or find it in AWS Console:
1. Go to **CloudFormation** → **Stacks**
2. Select your stack (e.g., `RAGStack-<project-name>`)
3. Go to **Outputs** tab
4. Copy the `WebUIUrl` value

### Browser Requirements

The UI works best with modern browsers:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

---

## Signing In

On first deployment, you'll receive an email with a temporary password.

### First Login

1. Open the **WebUIUrl** in your browser
2. You'll see the **Login** page
3. Enter your credentials:
   - **Username**: Email address you specified during deployment
   - **Password**: Temporary password from email

4. Click **Sign In**

### Setting a New Password

On first login, you'll be prompted to create a permanent password:

1. Enter the **temporary password** (from email)
2. Create a **new password**:
   - Minimum 8 characters
   - At least one uppercase letter (A-Z)
   - At least one lowercase letter (a-z)
   - At least one number (0-9)
   - At least one special character (!@#$%^&*)

3. Click **Change Password**

### Resetting Your Password

If you forget your password:

1. Click **Forgot Password?** on the login page
2. Enter your email address
3. Click **Send Code**
4. Check your email for a verification code
5. Enter the code and your new password
6. Click **Reset Password**

### Session Duration

Your session lasts for 1 hour of activity. After that, you'll be automatically logged out and need to sign in again.

---

## Dashboard Overview

After signing in, you'll land on the **Dashboard** page.

### What You'll See

The Dashboard displays all documents you've uploaded:

| Column | Description |
|--------|-------------|
| **Document Name** | Original filename |
| **Status** | Current processing state |
| **Uploaded** | Date and time of upload |
| **Pages** | Number of pages detected |
| **Actions** | View details, download results |

### Navigation

The top navigation bar provides access to:

- **Dashboard** - View all documents (you're here)
- **Upload** - Upload new documents
- **Search** - Query the Knowledge Base
- **Sign Out** - Log out of the application

### Viewing Document Details

To see detailed information about a document:

1. Click on a document name in the table
2. A detail panel opens showing:
   - Document metadata (filename, size, pages)
   - Processing status for each step
   - OCR text extracted
   - Error messages (if any)
   - Download links for results

---

## Uploading Documents

The **Upload** page lets you add documents to the processing pipeline.

### Supported Formats

RAGStack-Lambda supports these document types:

| Format | Extensions | Notes |
|--------|------------|-------|
| **PDF** | `.pdf` | Most common, best results |
| **Images** | `.jpg`, `.jpeg`, `.png`, `.tiff` | Converted to PDF internally |
| **Office Documents** | `.docx`, `.pptx`, `.xlsx` | Converted to PDF |
| **Text Files** | `.txt`, `.md` | No OCR needed |
| **eBooks** | `.epub`, `.mobi` | Converted to PDF |

**File size limits**:
- Maximum size: 100 MB per file
- Maximum pages: 200 pages per document
- For larger documents, split them first

### How to Upload

#### Method 1: Drag and Drop

1. Go to the **Upload** page
2. Drag files from your computer
3. Drop them onto the upload zone
4. Files are automatically queued and uploaded

#### Method 2: Browse Files

1. Go to the **Upload** page
2. Click **Browse Files** in the upload zone
3. Select one or more files
4. Click **Open**
5. Files are automatically queued and uploaded

### Upload Queue

The upload queue shows real-time progress:

| Column | Description |
|--------|-------------|
| **Filename** | Name of the file being uploaded |
| **Size** | File size in MB |
| **Progress** | Upload percentage (0-100%) |
| **Status** | `Uploading`, `Processing`, `Complete`, `Failed` |

### What Happens After Upload

Once uploaded, documents go through this pipeline:

1. **Uploaded to S3** - File stored in InputBucket
2. **OCR Processing** - Text extracted from pages (2-5 min)
3. **Embedding Generation** - Vector embeddings created (1-3 min)
4. **Knowledge Base Sync** - Indexed for search (2-10 min)
5. **Complete** - Ready to search

**Total time**: 5-20 minutes depending on document size and OCR backend.

---

## Monitoring Document Processing

Track your document's progress through the pipeline.

### Status Indicators

Documents show different statuses:

#### UPLOADED
- ✅ Document successfully uploaded to S3
- ⏳ Waiting for OCR processing to start

#### PROCESSING
- 🔄 OCR is extracting text from pages
- This is the longest step (2-5 minutes per document)

#### GENERATING_EMBEDDINGS
- 🔄 Creating vector embeddings from extracted text
- Usually takes 1-3 minutes

#### SYNCING_KB
- 🔄 Adding embeddings to Knowledge Base
- Takes 2-10 minutes for first sync
- Subsequent syncs are faster (automatic in background)

#### COMPLETED
- ✅ Document fully processed and searchable
- You can now search for content from this document

#### FAILED
- ❌ Processing error occurred
- Click document name to view error details
- See [Troubleshooting Guide](TROUBLESHOOTING.md)

### Real-Time Updates

The Dashboard automatically refreshes every 10 seconds to show latest status.

To manually refresh:
- Click the **Refresh** button (top right)
- Or reload the page in your browser

### Viewing Processing Details

For detailed status:

1. Click on a document name
2. The detail panel shows:
   - **Processing Steps**: OCR → Embeddings → KB Sync
   - **Completed Steps**: ✅ Green checkmarks
   - **In Progress**: 🔄 Spinning indicator
   - **Failed Steps**: ❌ Red X with error message

3. **OCR Text** tab shows extracted text
4. **Metadata** tab shows document properties
5. **Download** button downloads results as JSON

---

## Searching Documents

Once documents are processed, search them using the **Search** page.

### How to Search

1. Go to the **Search** page
2. Enter your query in the search box
   - Example: "What is the total revenue?"
   - Example: "Describe the key findings"
3. Click **Search** or press Enter
4. Results appear below

### Search Interface

The search page has:

- **Search Box** - Enter natural language queries
- **Results Section** - Shows matching passages
- **Filters** (if available) - Filter by document, date, etc.

### Understanding Results

Each search result shows:

| Field | Description |
|-------|-------------|
| **Document Name** | Which document this passage came from |
| **Excerpt** | Relevant text snippet (with highlights) |
| **Confidence Score** | How relevant this result is (0-1) |
| **Page Number** | Which page the text appears on |

Results are ranked by relevance (highest first).

### Search Tips

#### Be Specific
- ❌ "revenue"
- ✅ "What was the total revenue in Q4 2024?"

#### Use Natural Language
- ✅ "How many employees does the company have?"
- ✅ "List all product names mentioned"

#### Ask Questions
- ✅ "What are the key risks identified?"
- ✅ "Who is the CEO?"

#### Search Across Documents
- Queries automatically search ALL processed documents
- Filter by document name if needed

### Advanced Search Features

#### Semantic Search
The system uses **semantic search**, meaning it understands meaning, not just keywords:

- Query: "How much money did they make?"
- Matches: "revenue", "income", "profit", "earnings"

#### Multimodal Search
If your documents have images, the system can:
- Find visually similar images
- Search based on image content
- Match text to related images

---

## Managing Settings

The Settings page allows you to modify runtime configuration without redeploying the stack. This includes changing OCR backends, embedding models, and response models.

### Accessing Settings

1. Click **Settings** in the navigation menu
2. The Settings page displays all configurable parameters with their current values

### Configuration Parameters

The Settings page shows the following configurable parameters:

#### OCR Backend
Choose how document text extraction is performed:
- **textract** (default): Uses AWS Textract for OCR - faster and cost-effective ($1.50/1000 pages)
- **bedrock**: Uses Bedrock Claude models for OCR - better for complex layouts ($25-75/1000 pages depending on model)

#### Bedrock OCR Model
*Only visible when OCR Backend = "bedrock"*

Select which Claude model to use for OCR:
- **claude-3-5-haiku**: Fastest and most cost-effective
- **claude-3-5-sonnet**: Balanced speed and accuracy
- **claude-3-opus**: Most accurate, best for complex documents

#### Text Embedding Model
Select the model for generating text embeddings:
- **amazon.titan-embed-text-v1**: Titan Text v1 (768 dimensions)
- **amazon.titan-embed-text-v2:0**: Titan Text v2 (1024 dimensions, better quality)
- **cohere.embed-english-v3**: Cohere English v3 (1024 dimensions)
- **cohere.embed-multilingual-v3**: Cohere Multilingual v3 (1024 dimensions, supports multiple languages)

#### Image Embedding Model
Select the model for generating image embeddings:
- **amazon.titan-embed-image-v1**: Titan Image v1 (1024 dimensions)

#### Response Model
Select the Bedrock model for Knowledge Base query responses:
- **anthropic.claude-3-5-haiku**: Fastest responses, cost-effective
- **anthropic.claude-3-5-sonnet-v2**: Balanced speed and quality
- **anthropic.claude-3-opus**: Most detailed responses

### Saving Configuration

1. Modify any parameters using the dropdown menus
2. Click **Save changes** button
3. A success message appears when saved: "Configuration saved successfully"
4. Changes take effect **immediately** on the next document processing or query

**Note**: The Settings page shows which fields have been customized from their default values with a "Customized from default" indicator.

### Resetting Configuration

To revert unsaved changes:
1. Click the **Reset** button
2. Form fields revert to the last saved state
3. No confirmation required

### Changing Embedding Models

Changing the text or image embedding model when you have existing documents requires special attention:

#### Embedding Change Detection

When you change an embedding model and click "Save changes", the system:
1. Checks if you have any completed documents (status = COMPLETED)
2. If documents exist, shows a modal with three options

#### Option 1: Continue with Mixed Embeddings
- **What happens**: Saves the configuration change immediately
- **Effect**: New documents use the new embedding model; existing documents keep their old embeddings
- **Pros**: Fast, no processing required
- **Cons**: Search quality may be inconsistent when comparing old and new documents
- **When to use**: Testing new models, or when documents are independent

#### Option 2: Re-embed All Documents
- **What happens**: Saves configuration and triggers a background job to regenerate all embeddings
- **Effect**: All documents are reprocessed with the new embedding model
- **Pros**: Ensures consistent search quality across all documents
- **Cons**: Takes time (approximately 1 minute per 10 documents)
- **When to use**: Production environments where consistency matters

#### Option 3: Cancel
- **What happens**: Closes the modal without saving
- **Effect**: Embedding model change is discarded; returns to previous value
- **When to use**: Changed your mind about the model switch

### Re-embedding Job Progress

When you choose "Re-embed all documents":

1. **Progress Banner Appears**
   - Shows at the top of the Settings page
   - Displays: "Re-embedding documents: X / Y completed (Z%)"
   - Updates automatically every 5 seconds

2. **Job Details**
   - Total documents being processed
   - Number of documents completed so far
   - Percentage progress

3. **What's Happening**
   - The system triggers the processing pipeline for each document
   - OCR results are reused (not regenerated)
   - Only embeddings are regenerated with the new model
   - Documents are processed in parallel

4. **Job Completion**
   - Banner changes to: "Re-embedding completed! All N documents have been processed."
   - Green success alert appears
   - You can dismiss the alert by clicking the X

5. **During Processing**
   - You can navigate away from the Settings page
   - The job continues in the background
   - When you return, progress is updated
   - You can continue using other parts of the application

**Estimated Time**: Approximately 1 minute per 10 documents (varies by document size and complexity)

### Knowledge Base Compatibility

**⚠️ IMPORTANT**: Changing embedding models has implications for your Bedrock Knowledge Base.

#### Understanding Knowledge Base Configuration

Your Knowledge Base is configured at creation time with a specific embedding model. The KB expects all documents to use embeddings from that model.

#### Safe Changes (Same Model Family)

Changing within the same model family is **safe**:
- ✅ `amazon.titan-embed-text-v1` → `amazon.titan-embed-text-v2:0`
- ✅ `cohere.embed-english-v3` → `cohere.embed-multilingual-v3`

These changes work because the embedding dimensions and format are compatible.

#### Breaking Changes (Different Model Families)

Changing between different model families will **break search**:
- ❌ `amazon.titan-embed-text-v2:0` → `cohere.embed-english-v3`
- ❌ `cohere.embed-english-v3` → `amazon.titan-embed-text-v1`

**Why it breaks**: Different model families produce embeddings in different formats and dimensions. The Knowledge Base cannot compare them.

#### What Happens When Search Breaks

If you switch to an incompatible embedding model:
- New documents generate embeddings in the new format
- Knowledge Base expects embeddings in the old format
- Search queries return no results or incorrect results
- No error messages (it fails silently)

#### How to Safely Change Model Families

If you need to switch to a different model family:

1. **Check your current Knowledge Base model**:
   ```bash
   aws bedrock-agent get-knowledge-base --knowledge-base-id <your-kb-id>
   ```
   Look for the `embeddingModelArn` field in the output

2. **Create a new Knowledge Base** with the new embedding model:
   - Go to AWS Console → Bedrock → Knowledge bases
   - Create new KB with desired embedding model
   - Point data source to your Vector S3 bucket
   - Note the new KB ID

3. **Update your configuration**:
   ```bash
   aws lambda update-function-configuration \
     --function-name RAGStack-<project>-QueryKB \
     --environment Variables={KNOWLEDGE_BASE_ID=<new-kb-id>}
   ```

4. **Change embedding model in Settings**:
   - Go to Settings page
   - Change embedding model
   - Choose "Re-embed all documents"

5. **Wait for re-embedding to complete**

6. **Sync the new Knowledge Base**:
   - Go to AWS Console → Bedrock → Knowledge bases → Data sources
   - Click "Sync" to index the new embeddings

**Alternative**: If recreating the Knowledge Base is not feasible, stay within the same model family.

#### Verifying Knowledge Base Compatibility

To verify your setup before changing embedding models:

```bash
# Get Knowledge Base embedding model
aws bedrock-agent get-knowledge-base \
  --knowledge-base-id <kb-id> \
  --query 'knowledgeBase.embeddingModelConfiguration.bedrockEmbeddingModelConfiguration.embeddingModelArn'

# Get current text embedding model from configuration
aws dynamodb get-item \
  --table-name RAGStack-<project>-Configuration \
  --key '{"Configuration": {"S": "Default"}}' \
  --query 'Item.text_embed_model_id.S'

# Compare the models - they should be from the same family
```

### Configuration Best Practices

#### For Cost Optimization
- **OCR Backend**: Use Textract for most documents
- **Bedrock OCR**: Only use for complex layouts or multilingual documents
- **Response Model**: Use Haiku for general queries, Sonnet/Opus for complex questions

#### For Production Workloads
- **Text Embeddings**: Use Titan Text v2 or Cohere English v3 for best quality
- **Re-embedding**: Always re-embed when changing models in production
- **KB Compatibility**: Verify Knowledge Base model before making changes

#### For Multilingual Content
- **Text Embeddings**: Use Cohere Multilingual v3
- **Bedrock OCR**: Use Sonnet or Opus models for non-English text
- **Response Model**: Sonnet handles multiple languages well

#### For Complex Documents
- **OCR Backend**: Switch to Bedrock with Sonnet or Opus
- **Response Model**: Use Sonnet or Opus for detailed answers

### Troubleshooting Settings

#### Settings Page Won't Load
- Check browser console for errors (F12 → Console tab)
- Verify you're signed in (session may have expired)
- Try refreshing the page

#### Configuration Not Saving
- Check for error messages in red alert boxes
- Verify you have network connectivity
- Check CloudWatch logs for ConfigurationResolver Lambda errors

#### Changes Not Taking Effect
- Configuration changes are immediate (no cache)
- Verify the Custom configuration was saved in DynamoDB:
  ```bash
  aws dynamodb get-item \
    --table-name RAGStack-<project>-Configuration \
    --key '{"Configuration": {"S": "Custom"}}'
  ```
- Check Lambda logs to confirm new configuration is being read

#### Re-embedding Job Stuck
- Check Step Functions console for execution status
- Review GenerateEmbeddings Lambda logs
- Job progress is tracked in ConfigurationTable with key `ReEmbedJob_Latest`

For more troubleshooting help, see [Troubleshooting Guide](TROUBLESHOOTING.md).

---

## Understanding Document Status

### Normal Processing Flow

```
UPLOADED → PROCESSING → GENERATING_EMBEDDINGS → SYNCING_KB → COMPLETED
```

**Typical timeline**:
- UPLOADED: Instant
- PROCESSING: 2-5 minutes (OCR)
- GENERATING_EMBEDDINGS: 1-3 minutes
- SYNCING_KB: 2-10 minutes (first time)
- Total: 5-20 minutes

### When Things Take Longer

Some documents may take longer:

**Large Documents (>20 pages)**:
- PROCESSING: 10-20 minutes
- GENERATING_EMBEDDINGS: 5-10 minutes (batched)

**Complex Layouts**:
- PROCESSING: 5-15 minutes (OCR needs more time)

**First Knowledge Base Sync**:
- SYNCING_KB: Up to 15 minutes (creates index)

### Stuck Documents

If a document is stuck in PROCESSING for >30 minutes:

1. Check the document details for errors
2. Review CloudWatch logs (see [Troubleshooting](TROUBLESHOOTING.md))
3. Try uploading the document again
4. Contact support if issue persists

---

## Tips and Best Practices

### Optimize Upload Performance

1. **Use PDF when possible**
   - PDFs process faster than images
   - Text-based PDFs skip OCR

2. **Upload in batches**
   - Upload 10-20 documents at a time
   - Wait for batch to complete before next batch

3. **Check file quality**
   - Use high-resolution scans (300 DPI)
   - Ensure text is readable
   - Remove blank pages

### Improve Search Accuracy

1. **Use complete sentences**
   - Better: "What is the refund policy?"
   - Worse: "refund"

2. **Be specific with context**
   - Better: "What was the revenue in Q4 2024?"
   - Worse: "revenue"

3. **Try different phrasings**
   - If first search doesn't work, rephrase
   - Use synonyms

### Manage Documents

1. **Use descriptive filenames**
   - Good: `2024-Q4-Financial-Report.pdf`
   - Bad: `doc1.pdf`

2. **Delete old documents**
   - Remove outdated documents from Dashboard
   - Reduces storage costs
   - Improves search relevance

3. **Monitor processing**
   - Check Dashboard regularly
   - Address failed documents quickly

### Security Best Practices

1. **Use strong passwords**
   - Mix uppercase, lowercase, numbers, symbols
   - Use a password manager

2. **Sign out when done**
   - Especially on shared computers
   - Sessions expire after 1 hour anyway

3. **Don't share credentials**
   - Each user should have their own account
   - Contact admin to create new users

### Cost Management

1. **Delete processed documents**
   - Once indexed, you can delete original files
   - Embeddings remain in Knowledge Base

2. **Use Textract backend**
   - Cheaper than Bedrock for most documents
   - Configure in [CONFIGURATION.md](CONFIGURATION.md)

3. **Batch uploads during off-hours**
   - Reduces concurrency costs
   - Faster processing with less contention

---

## Common Tasks

### Downloading Results

To download OCR results:

1. Go to **Dashboard**
2. Click on document name
3. Click **Download** button
4. Saves JSON file with:
   - Extracted text
   - Page boundaries
   - Metadata

### Deleting Documents

To delete a document:

1. Go to **Dashboard**
2. Click the **Delete** icon (🗑️) next to document
3. Confirm deletion
4. Document removed from system

**Note**: This deletes from S3 and DynamoDB, but embeddings remain in Knowledge Base until next sync.

### Viewing Processing Logs

For troubleshooting:

1. Click on document name in Dashboard
2. Scroll to **Logs** section (if available)
3. View processing logs and errors

For detailed logs:
- See [Troubleshooting Guide](TROUBLESHOOTING.md)
- Access CloudWatch logs (requires AWS Console access)

---

## Getting Help

### In-App Help

- Hover over **?** icons for tooltips
- Check status messages for guidance

### Documentation

- [Deployment Guide](DEPLOYMENT.md) - Setup and deployment
- [Configuration Guide](CONFIGURATION.md) - Customization options
- [Architecture Guide](ARCHITECTURE.md) - How it works
- [Testing Guide](TESTING.md) - Validation procedures
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues

### Support

For issues or questions:
1. Check [Troubleshooting Guide](TROUBLESHOOTING.md) first
2. Review CloudWatch logs (ask your admin)
3. Open a GitHub issue with:
   - Document name and status
   - Error messages
   - Screenshots (if applicable)

---

## What's Next?

Now that you know how to use the system:

- **Upload documents** and monitor their progress
- **Search your documents** using natural language
- **Explore search results** and refine your queries
- **Share feedback** to help improve the system
