# Visual Embeddings Ingestion Architecture Discussion

**Date:** January 2025
**Context:** Planning visual embeddings for video semantic search
**Decision:** Try incremental sync first, with fallback options documented

---

## The Problem

We want to add visual embeddings for video files using Bedrock KB's native video chunking (Nova Multimodal Embeddings). The challenge is that:

1. **IngestDocuments API** (what we use for text) does **NOT support video** - only text/PDF/Office
2. **StartIngestionJob** (data source sync) **does support video** but syncs the entire data source prefix
3. Our single data source has prefix `content/` which contains ALL content (text transcripts, images, video)

**Core question:** How do we ingest video without re-processing text that was already ingested via IngestDocuments API?

---

## Options Considered

### Option 1: Trust Incremental Sync (CHOSEN)

Put video in `content/`, call `StartIngestionJob`, trust KB to skip already-indexed files.

**How it should work:**
- Text was indexed via `IngestDocuments` API → stored in vector store
- `StartIngestionJob` scans `content/`, sees text files
- KB checks vector store, finds text already indexed → skips
- KB finds new video file → processes and indexes

**Evidence from docs:**
> "Syncing is incremental, so Amazon Bedrock only processes added, modified, or deleted documents since the last sync"
> "Amazon Bedrock Knowledge Bases scans each document and verifies whether it has already been indexed into the vector store"

**Risk:** Uncertain if cross-API indexing is tracked correctly (IngestDocuments vs StartIngestionJob use same vector store index?)

**Why we're trying this first:**
- Simplest implementation
- No infrastructure changes needed
- If it works, we're done

---

### Option 2: Second Data Source (FALLBACK)

Create separate data source for video with isolated prefix.

```
DS1: prefix "content/"              → Text only (IngestDocuments API)
DS2: prefix "content/visual_segments/" → Video only (StartIngestionJob)
```

**Pros:**
- Guaranteed isolation
- Zero risk of text re-processing
- Each data source has single ingestion method

**Cons:**
- Requires KB custom resource changes
- Need to store/manage second DATA_SOURCE_ID
- More complex infrastructure

**Implementation if needed:**
1. Modify `src/lambda/kb_custom_resource/index.py` to create second data source
2. Add `VISUAL_DATA_SOURCE_ID` environment variable
3. IngestVisual Lambda calls StartIngestionJob on DS2 only

---

### Option 3: Unified StartIngestionJob for Everything

Switch ALL ingestion (text + video) to use `StartIngestionJob` instead of `IngestDocuments` API.

**How it would work:**
- `IngestToKB` and `IngestMedia` just write files to S3 (no API calls)
- Single EventBridge trigger calls `StartIngestionJob` when processing completes
- KB handles all ingestion uniformly

**Pros:**
- Single ingestion method
- No cross-API tracking concerns
- KB manages everything

**Cons:**
- Breaking change to existing architecture
- `StartIngestionJob` is async (longer time to searchable)
- Lose per-document control of `IngestDocuments`

**When to consider:**
- If Option 1 fails AND Option 2 is too complex
- Future simplification effort

---

### Option 4: Clean Slate Per-Batch (REJECTED)

Copy content out, delete, add new batch, re-ingest.

**Why it doesn't work:**
KB tracks deletions. When files are removed from `content/`, next sync REMOVES their embeddings from vector store.

> "Syncing is incremental, so Amazon Bedrock only processes added, modified, or **deleted** documents"

This would destroy existing text search capability.

---

### Option 5: Direct Nova API + Manual Vector Insertion (NOT EXPLORED)

Call Nova Multimodal Embeddings API directly, insert vectors into S3 Vectors manually.

**Pros:**
- Full control
- No KB sync concerns

**Cons:**
- Complex implementation
- Manual vector management
- Bypass KB entirely for video

**When to consider:**
- If KB-based approaches all fail
- Need custom chunking logic

---

## Key Technical Findings

### Metadata Inheritance
Metadata.json attributes ARE inherited by all chunks KB creates:
> "Metadata fields are treated as string values associated with each chunk"

So `{docId}.mp4.metadata.json` with `content_type: visual` applies to every video segment.

### Storage Behavior
- **Data bucket (`content/`)**: Original source files only
- **S3 Vectors bucket**: Vector embeddings + metadata
- **Multimodal storage** (optional): Copy of originals for retrieval

KB does NOT write processed segments back to data bucket.

### Video Chunking
KB handles video chunking natively:
- Duration: 1-30 seconds (configurable, default 5s)
- Configured at embedding model level
- Returns timestamps in metadata for each chunk

### Cross-API Indexing (UNCERTAIN)
The critical unknown: Does KB's vector store track documents indexed via `IngestDocuments` API the same way as `StartIngestionJob`?

Both should write to the same vector store, so incremental sync SHOULD recognize already-indexed documents. But this is the risk we're accepting with Option 1.

---

## Decision Record

**Chosen approach:** Option 1 (Trust Incremental Sync)

**Rationale:**
- Simplest implementation path
- No infrastructure changes
- Documented fallback (Option 2) if it fails

**Success criteria:**
- Video files indexed without re-processing text
- Text search still works after video ingestion
- No duplicate embeddings in vector store

**Failure indicators:**
- Text files re-processed (visible in ingestion job stats)
- Duplicate search results
- Significantly longer ingestion times

**If Option 1 fails:**
- Implement Option 2 (second data source)
- Update KB custom resource
- Minimal code changes to IngestVisual Lambda

---

## Implementation Notes

### Current Architecture
```
Upload → ProcessMedia (transcript) → IngestMedia (IngestDocuments API)
```

### New Architecture (Option 1)
```
Upload → ProcessMedia (transcript) → IngestMedia (IngestDocuments API for text)
                                          ↓
                                   Copy video to content/{docId}/
                                          ↓
                              EventBridge → StartIngestionJob
```

### File Structure
```
content/{docId}/
├── transcript_full.txt
├── transcript_full.txt.metadata.json
├── segment-000.txt
├── segment-000.txt.metadata.json
├── video.mp4                          # NEW: Video for visual embeddings
└── video.mp4.metadata.json            # NEW: content_type=visual
```

### Why NOT `visual_segments/` Subfolder?
Originally planned `content/visual_segments/` for video, but this provides **zero isolation** because:
- Data source prefix is `content/`
- `StartIngestionJob` scans entire prefix regardless of subfolders
- Subfolder only helps Lambda code parse results, not KB ingestion

Keeping video in `content/{docId}/` is simpler and equally (in)effective for isolation.

---

## Future Considerations

1. **Monitor ingestion job statistics** - Track if text files are being re-processed
2. **Consider Option 3** (unified StartIngestionJob) for architectural simplification
3. **Evaluate Option 2** (second data source) if incremental sync proves unreliable
4. **Test with small dataset first** before large-scale video ingestion
