# Manual Testing Plan for v2.5.1 Audit Remediation

Deploy to a test stack first. Do not deploy to production until every section passes.

## Prerequisites

- A deployed test stack (e.g., `ragstack-test`)
- At least 2 documents already uploaded (1 PDF, 1 image)
- At least 1 scraped web page
- Admin credentials for the dashboard

## 1. Smoke Test (Do This First)

These verify the resolver split didn't break basic routing.

- [ ] Open the dashboard, confirm it loads without errors
- [ ] Document list loads and shows existing documents
- [ ] Image list loads and shows existing images
- [ ] Scrape jobs list loads (even if empty)
- [ ] Settings page loads and shows current configuration
- [ ] Metadata stats page loads

If any of these fail, stop here. The resolver split has a routing bug.

## 2. Document Upload and Processing

Tests the full pipeline: upload, OCR, ingest, query.

- [ ] Upload a small PDF (< 10 pages) via dashboard
- [ ] Verify status progresses: UPLOADED -> PROCESSING -> INDEXED
- [ ] Upload a large PDF (> 10 pages) to test batching path
- [ ] Verify it processes through batch flow and reaches INDEXED
- [ ] Upload a non-PDF file (DOCX, XLSX, or plain text)
- [ ] Verify it processes correctly

**What this validates:** Step Functions payload (documents.py:1251), env var access (os.environ.get), S3 size guard (won't block normal uploads)

## 3. Chat (Query KB)

Tests the refactored query_kb with exception narrowing and _compat.py changes.

- [ ] Send a chat message about an uploaded document
- [ ] Verify you get a response with source citations
- [ ] Verify source links are clickable and download the document
- [ ] Send a follow-up message in the same conversation
- [ ] Verify conversation history is maintained
- [ ] Open a new conversation and verify it starts fresh
- [ ] Send a very long message (> 500 chars) and verify it works
- [ ] Send an empty message and verify you get a validation error, not a crash

**What this validates:** KB retrieval error handling (handler.py), _compat.py imports, parse_s3_uri guarding, visual enrichment, ConfigurationManager caching

## 4. Image Upload and Caption

Tests the images.py resolver split.

- [ ] Upload an image via the image upload flow
- [ ] Verify it appears in the images list
- [ ] Generate a caption for the image
- [ ] Verify the caption appears and is reasonable
- [ ] Delete an image
- [ ] Verify it disappears from the list

**What this validates:** images.py resolver routing, pagination token fix (LastEvaluatedKey), config_manager initialization

## 5. Image Pagination

Tests the pagination fix specifically.

- [ ] If you have > 20 images, scroll/page through the list
- [ ] Verify the second page loads correctly (not duplicating or missing items)
- [ ] If you have < 20 images, upload enough to exceed one page and test

**What this validates:** images.py pagination using LastEvaluatedKey instead of document_id

## 6. Web Scraping

Tests the scrape.py resolver split and pagination fix.

- [ ] Start a scrape job for a small site (set max pages to 5)
- [ ] Verify the job appears in the list with DISCOVERING status
- [ ] Wait for it to progress through PROCESSING to COMPLETED
- [ ] Verify all pages are listed (not truncated at 100)
- [ ] Cancel a scrape job while it's in progress
- [ ] Verify it moves to CANCELLED status
- [ ] Try to cancel an already-completed job
- [ ] Verify you get an error message, not a crash

**What this validates:** scrape.py query pagination, atomic cancel with ConditionExpression, exception propagation

## 7. Reindex

Tests the metadata.py resolver and execution name uniqueness.

- [ ] Go to Settings and trigger a reindex
- [ ] Verify Step Functions execution starts (check status in dashboard)
- [ ] Verify the execution name in CloudWatch/Step Functions console has a UUID suffix
- [ ] If feasible, try triggering two reindexes rapidly
- [ ] Verify the second gets a "reindex already in progress" error, not a collision

**What this validates:** execution_name UUID suffix (metadata.py), reindex lock check using module-level constant (shared.py)

## 8. Document Reprocess

Tests documents.py reprocess path.

- [ ] Select a document and trigger reprocess
- [ ] Verify it goes back to PROCESSING and re-processes
- [ ] Reprocess a scraped document specifically
- [ ] Verify it re-ingests and returns to INDEXED (not stuck in PROCESSING)

**What this validates:** Step Functions payload, scraped content conditional INDEXED status

## 9. Document Delete

Tests the full delete flow across resolver modules.

- [ ] Delete a single document
- [ ] Verify it disappears from the list
- [ ] Verify the S3 content is cleaned up (check CloudWatch logs for delete operations)
- [ ] Delete multiple documents at once
- [ ] Verify all are removed

**What this validates:** documents.py delete flow, S3 content folder cleanup

## 10. Settings / Configuration

Tests ConfigurationManager caching.

- [ ] Change a setting (e.g., chat model) in the Settings UI
- [ ] Send a chat message
- [ ] Verify the new setting takes effect (check CloudWatch logs for model used)
- [ ] Change the setting back

**What this validates:** request-scoped caching with clear_cache() at handler entry

## 11. Error Handling Spot Checks

These verify narrowed exceptions don't hide failures.

- [ ] Check CloudWatch logs after all the above tests
- [ ] Search for "Unexpected error" log entries (from the safety net catch-all)
- [ ] If any exist, investigate -- they indicate an exception type we didn't anticipate
- [ ] Search for "Traceback" in logs -- any stack traces indicate unhandled errors
- [ ] Verify no Lambda invocation errors in CloudWatch metrics

## 12. Frontend Console Check

Tests the no-console rule and error logging.

- [ ] Open browser DevTools console before loading the dashboard
- [ ] Navigate through all pages
- [ ] Verify NO console.log output (those were removed)
- [ ] Intentionally disconnect network and try an action
- [ ] Verify console.error output appears (those were added for real failures)

## 13. Pre-commit Hooks

Tests Phase 4 guardrails locally.

- [ ] Run `pre-commit install` in the repo
- [ ] Make a small Python change and commit
- [ ] Verify ruff check and ruff format hooks run automatically
- [ ] Intentionally introduce a lint error and commit
- [ ] Verify the hook blocks the commit

## Pass Criteria

All checkboxes above must be checked. Any failure in sections 1-10 is a blocker. Section 11-13 failures are warnings that should be investigated but don't block deployment if the root cause is understood.

After all tests pass on the test stack, deploy to production.
