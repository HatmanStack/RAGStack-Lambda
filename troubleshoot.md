# Troubleshooting - Active Issues

This document tracks issues currently being investigated/worked on.

---

## 1. Sources Not Showing Correct Relevance Score

**Status:** In Progress

**Symptoms:**
- Sources in ragstack-chat show 0% relevance or no score
- Score badge not appearing for some sources

**Root Cause Analysis:**
- KB returns `score` in retrieval results but it may be 0 or null for some content types
- The `extract_kb_scalar` function handles KB's list-wrapped values but score extraction may fail silently

**Files Involved:**
- `src/lambda/query_kb/index.py` - `extract_sources()` function, line ~833
- `src/lambda/search_kb/index.py` - score extraction in results parsing
- `src/ragstack-chat/src/components/SourcesDisplay.tsx` - score display logic

**Current Fix:**
- Only display score badge if `score > 0` (hide 0% relevant)
- Need to investigate why KB returns 0 scores for certain content

**Next Steps:**
- [ ] Check KB retrieval response to verify score is being returned
- [ ] Add logging to capture raw score values from KB
- [ ] Verify score is being correctly passed through GraphQL

---

## 2. Video Segment Links Not Pointing to Correct Timestamps

**Status:** In Progress

**Symptoms:**
- Clicking segment links gives S3 AccessDenied errors
- Links work for some videos but not others
- Error mentions `s3:ListBucket` permission denied

**Root Cause Analysis:**
- Video files uploaded to `input/` folder but tracking record says `content/`
- Presigned URL generated for `content/` path but file doesn't exist there
- Mismatch between where files are uploaded and where tracking records point

**Specific Case:**
- Document ID: `533b9462-75b2-4c50-aae8-49f044c900e0`
- Tracking record `input_s3_uri`: `s3://bucket/content/533b9462.../video.mp4`
- Actual file location: `s3://bucket/input/533b9462.../video.mp4`

**Files Involved:**
- `src/lambda/appsync_resolvers/index.py` - `create_upload_url()` function
- `src/lambda/process_media/index.py` - EventBridge event handling
- `template.yaml` - EventBridge rules for media processing

**Investigation:**
- Presigned URL was generated for `content/` path at 19:32:27
- File was uploaded to `input/` at 19:32:31
- S3UploadTrigger EventBridge rule still watching `input/` triggered processing
- Frontend may not be using presigned POST fields correctly

**Next Steps:**
- [ ] Verify frontend is using presigned POST `key` field correctly
- [ ] Check if S3UploadTrigger rule should be disabled for media files
- [ ] Add logging to track upload path vs tracking record path
- [ ] Consider adding validation that file exists before creating tracking record

---

## 3. Image Extracted Metadata Not Displaying in Dashboard

**Status:** Blocked - Needs Deployment

**Symptoms:**
- ImageDetail shows "Load Full Caption" button but no Extracted Metadata section
- Data exists in DynamoDB but not shown in UI

**Root Cause:**
- GraphQL schema changes are **uncommitted** and not deployed
- Fields `extractedText`, `extractedMetadata`, `captionUrl` added to Image type in local code
- AppSync filters out fields not in deployed schema

**Files Involved:**
- `src/api/schema.graphql` - Image type definition (uncommitted changes)
- `src/lambda/appsync_resolvers/index.py` - `format_image()` function
- `src/ui/src/components/Dashboard/ImageDetail.tsx` - display logic
- `src/ui/src/graphql/queries/getImage.ts` - query includes the fields

**Resolution:**
- Deploy stack to update AppSync schema
- Schema changes are now committed in commit `684215a`

**Next Steps:**
- [ ] Deploy stack: `python publish.py --project-name ragstack-test-2 ...`
- [ ] Verify fields appear in AppSync console
- [ ] Test ImageDetail displays extractedMetadata

---

## 4. MP4 Files Not Showing Up in Correct Location

**Status:** In Progress

**Symptoms:**
- Videos uploaded via UI end up in `input/` instead of `content/`
- EventBridge MediaContentTrigger watches `content/` but files go to `input/`
- Processing happens via legacy S3UploadTrigger path instead of new direct path

**Root Cause Analysis:**
- `create_upload_url()` generates presigned URL for `content/` path
- But actual upload goes to `input/` (frontend issue or presigned POST misconfiguration)
- Tracking record created with `content/` path, file uploaded to `input/`

**Timeline for Document 533b9462:**
1. 19:32:27 - `create_upload_url` generated presigned POST for `content/533b9462.../video.mp4`
2. 19:32:27 - Tracking record created with `input_s3_uri = content/...`
3. 19:32:31 - File uploaded to `input/533b9462.../video.mp4` (WRONG LOCATION)
4. 19:32:31 - S3UploadTrigger fired (watches `input/`)
5. 19:32:37 - ProcessMedia received Step Functions event with `input/` path

**Files Involved:**
- `src/ui/src/hooks/useDocuments.ts` or similar - frontend upload logic
- `src/lambda/appsync_resolvers/index.py` - `create_upload_url()` presigned POST generation
- `template.yaml` - S3UploadTrigger rule (still active for `input/`)

**Next Steps:**
- [ ] Check frontend code that handles presigned POST upload
- [ ] Verify presigned POST `fields` are being sent correctly in form data
- [ ] Consider disabling S3UploadTrigger for media files
- [ ] Add validation/logging at upload time to catch path mismatches

---

## Quick Reference: Relevant EventBridge Rules

| Rule Name | Watches | Target | Purpose |
|-----------|---------|--------|---------|
| S3UploadTrigger | `input/` | SQS → Step Functions | Legacy document processing |
| MediaContentTrigger | `content/*.mp4` | ProcessMedia Lambda | Direct video processing |
| MediaContentWebm | `content/*.webm` | ProcessMedia Lambda | Direct video processing |
| MediaContentMp3 | `content/*.mp3` | ProcessMedia Lambda | Direct audio processing |
| MediaContentWav | `content/*.wav` | ProcessMedia Lambda | Direct audio processing |
| ImageAutoProcess | `content/*.jpeg/jpg/png/gif/webp` | ProcessImage Lambda | Image processing |

---

## Commands for Debugging

```bash
# Check tracking record for a document
aws dynamodb get-item --table-name ragstack-test-2-tracking \
  --key '{"document_id": {"S": "DOC_ID"}}' --region us-east-1

# Check S3 locations
aws s3 ls s3://ragstack-test-2-data-631094035453/content/DOC_ID/ --region us-east-1
aws s3 ls s3://ragstack-test-2-data-631094035453/input/DOC_ID/ --region us-east-1

# Check Lambda logs
aws logs tail /aws/lambda/ragstack-test-2-appsync --since 30m --region us-east-1 --format short
aws logs tail /aws/lambda/ragstack-test-2-process-media --since 30m --region us-east-1 --format short
aws logs tail /aws/lambda/ragstack-test-2-query --since 30m --region us-east-1 --format short

# Copy file to correct location (temporary fix)
aws s3 cp s3://bucket/input/DOC_ID/file.mp4 s3://bucket/content/DOC_ID/file.mp4 --region us-east-1
```

---

*Last updated: 2026-01-15*
