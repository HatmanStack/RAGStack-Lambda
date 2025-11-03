# User Guide

How to use the RAGStack-Lambda web interface.

## Getting Started

### Find Your URL

After deployment, get the CloudFront URL:
```bash
aws cloudformation describe-stacks \
  --stack-name RAGStack-<project-name> \
  --query 'Stacks[0].Outputs[?OutputKey==`WebUIUrl`].OutputValue' \
  --output text
```

Or in AWS Console: CloudFormation → Stacks → Outputs → WebUIUrl

### Sign In

1. Open the URL in a modern browser (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
2. Enter email and temporary password (from deployment email)
3. Set a new password (min 8 chars: uppercase, lowercase, number, special char)
4. Session expires after 1 hour of inactivity

**Forgot password?** Click "Forgot Password?" on login page

## Dashboard

After login, you're on the Dashboard. See:
- Document list with name, status, upload date, file size
- Status indicators: UPLOADED, PROCESSING, GENERATING_EMBEDDINGS, SYNCING_KB, COMPLETED, FAILED
- Real-time updates every 30 seconds
- Filter by status or search by filename
- Click document name for details

## Upload Documents

### Supported Formats
- PDF (text-native or scanned)
- Images (JPG, PNG, TIFF)
- Office (DOCX, XLSX, PPTX)
- Text (TXT, MD)
- eBooks (EPUB)

### How to Upload

**Method 1 (Drag & Drop):**
1. Go to Upload page
2. Drag files onto the drop zone
3. Files upload immediately

**Method 2 (Browse):**
1. Go to Upload page
2. Click "Browse Files" button
3. Select files
4. Confirm upload

### After Upload

1. Document appears on Dashboard with status UPLOADED
2. EventBridge triggers processing automatically
3. Stages: UPLOADED → PROCESSING → GENERATING_EMBEDDINGS → SYNCING_KB → COMPLETED
4. Takes 2-15 minutes depending on file size
5. Once INDEXED, searchable

**Note**: Text-native PDFs process fastest (~2-5 min). Scanned PDFs slower (~15 min+).

## Search Documents

1. Go to Search page
2. Enter a question or search term
3. Press Enter or click Search
4. Results show:
   - Relevance score
   - Document name and source
   - Matching excerpt
   - Expandable full content

**Tips:**
- Be specific ("What is the return policy?") vs vague ("stuff")
- Search requires documents to be INDEXED status
- Results show top 10 matches

## Monitor Processing

Watch documents progress through stages:

| Status | Meaning | Duration |
|--------|---------|----------|
| UPLOADED | File uploaded, waiting to process | <1 min |
| PROCESSING | OCR extracting text | 2-15 min |
| GENERATING_EMBEDDINGS | Creating embeddings | 1-5 min |
| SYNCING_KB | Indexing in Knowledge Base | 1-10 min |
| COMPLETED | Ready to search | - |
| FAILED | Error processing (check logs) | - |

**If stuck:** Check CloudWatch logs:
```bash
aws logs tail /aws/lambda/RAGStack-<project>-ProcessDocument --follow
```

## Settings

Configure OCR and chat models (no redeployment needed):

1. Go to Settings page
2. Modify:
   - **OCR Backend**: "textract" (cheaper) or "bedrock" (multimodal)
   - **Bedrock OCR Model**: Claude model for document OCR
   - **Chat Model ID**: Claude model for Knowledge Base queries
3. Click Save
4. Changes apply immediately

**Cost Impact:**
- Textract: ~$1.50 per 1000 pages
- Bedrock OCR: ~$0.75 per 1000 pages
- Haiku: 90% cheaper than Opus per token

See [Configuration Guide](CONFIGURATION.md) for details.

## Tips & Best Practices

**Upload:**
- Smaller files process faster
- Text-native PDFs skip OCR (fastest, free)
- Avoid huge documents (>50MB or 500+ pages)
- Use good document quality (OCR works better with clear scans)

**Search:**
- Be specific: "What is the cancellation policy?" not "stuff"
- Try different phrasings if first search misses docs
- Results sorted by relevance score (higher = better match)

**Cost Savings:**
- Use Textract OCR (default) for documents
- Use Haiku model for chat (still very capable)
- Delete old extracted text you don't need

**Performance:**
- Search is instant (vectors already indexed)
- Processing takes time (depends on file size and type)
- Check status every 30 seconds (automatic refresh)

## Troubleshooting

**UI not loading?**
- Check URL is correct
- Invalidate CloudFront cache:
  ```bash
  aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"
  ```

**Login fails?**
- Verify email format is correct
- Check temporary password email hasn't expired
- Try password reset

**Upload fails?**
- File format supported?
- File size <10MB?
- Check browser console for errors

**Search returns nothing?**
- Documents must be COMPLETED status
- Try rephrasing query (be more specific)
- Check at least one document is INDEXED

**Processing stuck?**
- Check CloudWatch logs (see Monitor Processing above)
- Large documents timeout after 15 min
- Check Bedrock model access (AWS Console → Bedrock → Model access)

For more help: See [Troubleshooting Guide](TROUBLESHOOTING.md)

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter | Search documents |
| Ctrl+K | Focus search |
| ? | Show help |

## Related Documentation

- [Configuration Guide](CONFIGURATION.md) - Adjust settings
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
- [Architecture](ARCHITECTURE.md) - How it works
