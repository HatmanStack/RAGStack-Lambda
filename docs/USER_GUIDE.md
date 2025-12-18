# User Guide

## Access UI

Get CloudFront URL from deployment outputs or:
```bash
aws cloudformation describe-stacks \
  --stack-name RAGStack-<project> \
  --query 'Stacks[0].Outputs[?OutputKey==`WebUIUrl`].OutputValue' \
  --output text
```

## Sign In

1. Open URL, enter email + temporary password (from email)
2. Set new password (8+ chars: upper, lower, number, special)

Reset password: Click "Forgot Password?" on login

## Upload Documents

**Supported:** PDF, JPG, PNG, TIFF, DOCX, XLSX, TXT, MD, EPUB

1. Upload page → Drag files or click "Browse"
2. Files upload immediately
3. Processing: UPLOADED → PROCESSING → GENERATING_EMBEDDINGS → SYNCING_KB → COMPLETED (2-15 min)

## Chat

Use the Chat page to ask questions about your documents:

1. Chat page → Enter question
2. AI responds with answer + sources
3. Follow-up questions in same conversation

**Tip:** Be specific ("What is the return policy?") not vague ("stuff")

## Monitor Processing

| Status | Duration |
|--------|----------|
| UPLOADED | <1 min |
| PROCESSING | 2-15 min |
| GENERATING_EMBEDDINGS | 1-5 min |
| SYNCING_KB | 1-10 min |
| COMPLETED | Ready |
| FAILED | Check logs |

Stuck? Check logs: `aws logs tail /aws/lambda/RAGStack-<project>-ProcessDocument --follow`

## Settings

Configure OCR and models (no redeployment):

1. Settings page
2. Change OCR backend (textract/bedrock) or model
3. Save → applies immediately

**Cost:** Textract cheaper, Haiku cheapest model

## Tips

- Text-native PDFs process fastest (no OCR)
- Avoid huge files (>50MB)
- Chat requires documents in COMPLETED status

## Troubleshooting

**UI not loading?** Invalidate CloudFront cache
**Upload fails?** Check file format/size (<10MB)
**Chat not working?** Documents must be COMPLETED status

See [Troubleshooting](TROUBLESHOOTING.md)
