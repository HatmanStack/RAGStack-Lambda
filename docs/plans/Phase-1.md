# Phase 1: Implementation

## Phase Goal

Implement Cohere Rerank 3.5 for filtered queries and remove the score boost workaround. After this phase, filtered queries will automatically be reranked for improved relevancy.

**Success Criteria:**
- Filtered queries call Bedrock Rerank API with 3x oversampled results
- Reranked results are returned in relevance order
- Unfiltered queries work unchanged (no rerank call)
- All existing tests pass, new rerank tests added
- UI no longer shows boost slider

**Estimated tokens:** ~18,000

---

## Prerequisites

- [ ] Read and understand [Phase-0.md](./Phase-0.md) completely
- [ ] Verify `uv` is installed: `uv --version`
- [ ] Verify tests pass before starting: `npm run test:backend`

---

## Task 1: Add Rerank Constants and Helper Methods

**Goal:** Add the foundational constants and helper methods for preparing rerank sources, including metadata synthesis for visual embeddings.

**Files to Modify:**
- `lib/ragstack_common/multislice_retriever.py` - Add constants and helper methods

**Prerequisites:**
- None (first task)

**Implementation Steps:**

1. Open `lib/ragstack_common/multislice_retriever.py`

2. After the existing constants (line ~27), add new rerank constants:
   ```python
   # Rerank configuration
   RERANK_MODEL_ARN = "arn:aws:bedrock:us-east-1::foundation-model/cohere.rerank-v3-5:0"
   RERANK_OVERSAMPLE_FACTOR = 3
   RERANK_MAX_CHARS = 2000  # ~512 tokens at 4 chars/token (Cohere limit)

   # Rich metadata keys that can be synthesized into text for reranking
   RICH_METADATA_KEYS = ("ai_caption", "people_mentioned", "surnames", "topic", "document_type")
   ```

3. Add helper methods to the `MultiSliceRetriever` class (after `_convert_filter_format` method, around line 496):

   ```python
   def _has_rich_metadata(self, metadata: dict) -> bool:
       """Check if metadata has fields that can be synthesized into text."""
       return any(metadata.get(key) for key in RICH_METADATA_KEYS)

   def _synthesize_text_from_metadata(self, metadata: dict) -> str:
       """
       Synthesize searchable text from metadata for visual embeddings.

       Formats metadata as YAML-style text that Cohere Rerank can evaluate.

       Args:
           metadata: Metadata dictionary from retrieval result.

       Returns:
           Synthesized text string, or empty string if no rich metadata.
       """
       parts = []

       # Use AI caption if available (most descriptive)
       if metadata.get("ai_caption"):
           parts.append(metadata["ai_caption"])

       # Add people mentioned
       if metadata.get("people_mentioned"):
           people = metadata["people_mentioned"]
           if isinstance(people, list):
               parts.append(f"people: {', '.join(people[:5])}")
           else:
               parts.append(f"people: {people}")

       # Add surnames
       if metadata.get("surnames"):
           surnames = metadata["surnames"]
           if isinstance(surnames, list):
               parts.append(f"surnames: {', '.join(surnames[:5])}")
           else:
               parts.append(f"surnames: {surnames}")

       # Add topic
       if metadata.get("topic"):
           parts.append(f"topic: {metadata['topic']}")

       # Add document type
       if metadata.get("document_type"):
           parts.append(f"type: {metadata['document_type']}")

       return "\n".join(parts)

   def _prepare_source_for_rerank(self, result: dict) -> dict | None:
       """
       Prepare a retrieval result for the Bedrock Rerank API.

       Handles three cases:
       1. Text content available → use directly
       2. No text but rich metadata → synthesize text from metadata
       3. No text and no rich metadata → return None (un-rerankable)

       Args:
           result: A KB retrieval result dictionary.

       Returns:
           Source dict for rerank API, or None if result cannot be reranked.
       """
       text = result.get("content", {}).get("text", "")
       metadata = result.get("metadata", {})

       # If no text, try to synthesize from rich metadata
       if not text:
           text = self._synthesize_text_from_metadata(metadata)

       if not text:
           return None  # Un-rerankable: no text and no rich metadata

       # Prepend metadata header for text results (adds context)
       if result.get("content", {}).get("text") and self._has_rich_metadata(metadata):
           header = self._synthesize_text_from_metadata(metadata)
           if header:
               text = f"{header}\n\n{text}"

       truncated = text[:RERANK_MAX_CHARS]
       return {
           "type": "INLINE",
           "inlineDocumentSource": {
               "type": "TEXT",
               "textDocument": {"text": truncated}
           }
       }

   def _interpolate_score(self, original_position: int, reranked_results: list[dict]) -> float:
       """
       Assign score to un-rerankable result to maintain its relative position.

       Used for filtered results that cannot be reranked (visual with baseline
       metadata only). Slots them into the same position they held originally.

       Args:
           original_position: Original position (0-indexed) in filtered results.
           reranked_results: List of reranked results with scores.

       Returns:
           Interpolated score that maintains original position.
       """
       if not reranked_results:
           return 0.5

       n = len(reranked_results)
       pos = min(original_position, n)

       if pos == 0:
           # Was first - score just above new first
           return reranked_results[0]["score"] + 0.001
       elif pos >= n:
           # Beyond reranked list - score just below last
           return reranked_results[-1]["score"] - 0.001
       else:
           # Slot between position (pos-1) and (pos)
           score_above = reranked_results[pos - 1]["score"]
           score_below = reranked_results[pos]["score"]
           return (score_above + score_below) / 2
   ```

**Verification Checklist:**
- [ ] Constants defined at module level (including `RICH_METADATA_KEYS`)
- [ ] `_has_rich_metadata` method correctly identifies rich metadata
- [ ] `_synthesize_text_from_metadata` creates YAML-style text
- [ ] `_prepare_source_for_rerank` handles all three cases (text, rich metadata, none)
- [ ] `_interpolate_score` maintains original position
- [ ] Tests still pass: `uv run pytest tests/unit/python/test_multislice_retriever.py -v`

**Testing Instructions:**

Add unit tests for the helper methods:

```python
def test_prepare_source_with_text(retriever):
    """Test source preparation with text content."""
    result = {"content": {"text": "Sample document text"}, "metadata": {}, "score": 0.9}
    source = retriever._prepare_source_for_rerank(result)
    assert source is not None
    assert "Sample document text" in source["inlineDocumentSource"]["textDocument"]["text"]

def test_prepare_source_with_rich_metadata(retriever):
    """Test source preparation with rich metadata (no text)."""
    result = {
        "content": {},
        "metadata": {"people_mentioned": ["judy wilson"], "topic": "family_photos"},
        "score": 0.9
    }
    source = retriever._prepare_source_for_rerank(result)
    assert source is not None
    assert "judy wilson" in source["inlineDocumentSource"]["textDocument"]["text"]
    assert "family_photos" in source["inlineDocumentSource"]["textDocument"]["text"]

def test_prepare_source_baseline_metadata_only(retriever):
    """Test source preparation with only baseline metadata returns None."""
    result = {
        "content": {},
        "metadata": {"content_type": "image", "document_id": "doc123"},
        "score": 0.9
    }
    source = retriever._prepare_source_for_rerank(result)
    assert source is None

def test_interpolate_score_maintains_position(retriever):
    """Test that interpolate_score maintains original position."""
    reranked = [
        {"score": 0.95},
        {"score": 0.88},
        {"score": 0.82},
        {"score": 0.75},
    ]
    # Original position 2 should get score between 0.88 and 0.82
    score = retriever._interpolate_score(2, reranked)
    assert 0.82 < score < 0.88
    assert score == (0.88 + 0.82) / 2
```

**Commit Message Template:**
```
feat(retriever): add rerank constants and helper methods

- Add RERANK_MODEL_ARN, RERANK_OVERSAMPLE_FACTOR, RERANK_MAX_CHARS
- Add RICH_METADATA_KEYS for identifying rerankable visual embeddings
- Add _synthesize_text_from_metadata for visual embedding reranking
- Add _prepare_source_for_rerank handling text, rich metadata, and baseline
- Add _interpolate_score to maintain position for un-rerankable results
```

---

## Task 2: Implement Core Rerank Method

**Goal:** Add the main `_rerank_results` method that handles three categories of results:
1. Rerankable (text or rich metadata) → send to Rerank API
2. Un-rerankable filtered (baseline metadata only) → interpolate score to maintain position
3. Proper retry and fallback logic

**Files to Modify:**
- `lib/ragstack_common/multislice_retriever.py` - Add `_rerank_results` method

**Prerequisites:**
- Task 1 complete

**Implementation Steps:**

1. Add the `_rerank_results` method after `_interpolate_score`:

```python
def _rerank_results(
    self,
    query: str,
    results: list[dict],
    num_results: int,
) -> list[dict]:
    """
    Rerank filtered results using Cohere Rerank 3.5.

    Handles three categories:
    1. Rerankable (has text or rich metadata) → rerank via API
    2. Un-rerankable (baseline metadata only) → interpolate score to maintain position
    3. On API failure → retry once, then fall back to original order

    Args:
        query: The search query text.
        results: List of KB retrieval results to rerank.
        num_results: Number of results to return after reranking.

    Returns:
        Reranked results with scores adjusted appropriately.
    """
    if not results:
        return results

    # Categorize results by rerankability
    rerankable = []          # Has text or rich metadata - can be reranked
    rerankable_indices = []  # Track original positions
    unrerankable = []        # Baseline metadata only - interpolate score
    unrerankable_positions = []  # Track original positions for interpolation

    for i, result in enumerate(results):
        source = self._prepare_source_for_rerank(result)
        if source:
            rerankable.append((result, source))
            rerankable_indices.append(i)
        else:
            unrerankable.append(result)
            unrerankable_positions.append(i)
            logger.debug(f"Un-rerankable result at position {i}: {_get_uri(result)}")

    if not rerankable:
        logger.info("No rerankable content, returning original results")
        return results[:num_results]

    # Prepare sources for rerank API
    sources = [source for _, source in rerankable]
    rerankable_results = [result for result, _ in rerankable]

    # Call rerank API with retry
    reranked = None
    for attempt in range(2):
        try:
            logger.info(
                f"[RERANK] Attempt {attempt + 1}: query='{query[:50]}...', "
                f"rerankable={len(sources)}, unrerankable={len(unrerankable)}, target={num_results}"
            )

            response = self.bedrock_agent.rerank(
                queries=[{"type": "TEXT", "textQuery": {"text": query}}],
                sources=sources,
                rerankingConfiguration={
                    "type": "BEDROCK_RERANKING_MODEL",
                    "bedrockRerankingConfiguration": {
                        "modelConfiguration": {
                            "modelArn": RERANK_MODEL_ARN,
                        },
                        "numberOfResults": min(num_results, len(sources)),
                    }
                }
            )

            # Map reranked results back to original results
            reranked = []
            for rerank_result in response.get("results", []):
                idx = rerank_result.get("index", 0)
                if 0 <= idx < len(rerankable_results):
                    result = rerankable_results[idx].copy()
                    result["score"] = rerank_result.get("relevanceScore", result.get("score", 0))
                    result["_reranked"] = True
                    reranked.append(result)
                    logger.debug(
                        f"[RERANK RESULT] idx={idx}, score={result['score']:.4f}, "
                        f"uri={_get_uri(result)}"
                    )

            logger.info(f"[RERANK] Success: {len(rerankable_results)} -> {len(reranked)} results")
            break  # Success - exit retry loop

        except Exception as e:
            if attempt == 0:
                logger.warning(f"[RERANK] Attempt 1 failed, retrying: {e}")
                continue
            logger.error(f"[RERANK] Failed after retry, using original order: {e}")
            # Fall back: return original results sorted by score
            sorted_results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)
            return sorted_results[:num_results]

    # Handle un-rerankable results: interpolate scores to maintain original position
    if unrerankable and reranked:
        for result, original_pos in zip(unrerankable, unrerankable_positions):
            interpolated_score = self._interpolate_score(original_pos, reranked)
            result_copy = result.copy()
            result_copy["score"] = interpolated_score
            result_copy["_interpolated"] = True
            reranked.append(result_copy)
            logger.debug(
                f"[INTERPOLATED] original_pos={original_pos}, score={interpolated_score:.4f}, "
                f"uri={_get_uri(result)}"
            )

        # Re-sort by score after adding interpolated results
        reranked.sort(key=lambda x: x.get("score", 0), reverse=True)

    return reranked[:num_results] if reranked else results[:num_results]
```

**Verification Checklist:**
- [ ] Method categorizes results into rerankable vs un-rerankable
- [ ] Rerankable results sent to Rerank API
- [ ] Un-rerankable results get interpolated scores based on original position
- [ ] Interpolated results are merged and re-sorted with reranked results
- [ ] Retry logic triggers on first failure
- [ ] Fallback returns sorted original results
- [ ] Tests still pass: `uv run pytest tests/unit/python/test_multislice_retriever.py -v`

**Testing Instructions:**

Add unit tests for the rerank method:

```python
def test_rerank_results_calls_api(retriever, mock_bedrock_agent):
    """Test that _rerank_results calls the rerank API for rerankable results."""
    results = [
        {"content": {"text": "Document 1"}, "metadata": {}, "score": 0.7, "location": {"s3Location": {"uri": "s3://b/1"}}},
        {"content": {"text": "Document 2"}, "metadata": {}, "score": 0.8, "location": {"s3Location": {"uri": "s3://b/2"}}},
    ]
    mock_bedrock_agent.rerank.return_value = {
        "results": [
            {"index": 1, "relevanceScore": 0.95},
            {"index": 0, "relevanceScore": 0.85},
        ]
    }

    reranked = retriever._rerank_results("test query", results, num_results=2)

    assert mock_bedrock_agent.rerank.call_count == 1
    assert len(reranked) == 2
    assert reranked[0]["score"] == 0.95
    assert reranked[1]["score"] == 0.85

def test_rerank_interpolates_unreankable_results(retriever, mock_bedrock_agent):
    """Test that un-rerankable results get interpolated scores."""
    results = [
        {"content": {"text": "Doc 1"}, "metadata": {}, "score": 0.9, "location": {"s3Location": {"uri": "s3://b/1"}}},
        {"content": {}, "metadata": {"content_type": "image"}, "score": 0.85, "location": {"s3Location": {"uri": "s3://b/2"}}},  # Un-rerankable
        {"content": {"text": "Doc 3"}, "metadata": {}, "score": 0.7, "location": {"s3Location": {"uri": "s3://b/3"}}},
    ]
    mock_bedrock_agent.rerank.return_value = {
        "results": [
            {"index": 0, "relevanceScore": 0.95},  # Doc 1
            {"index": 1, "relevanceScore": 0.75},  # Doc 3
        ]
    }

    reranked = retriever._rerank_results("test query", results, num_results=3)

    # Un-rerankable result (originally at position 1) should have interpolated score
    # between position 0 (0.95) and position 1 (0.75) in reranked results
    interpolated = [r for r in reranked if r.get("_interpolated")]
    assert len(interpolated) == 1
    assert 0.75 < interpolated[0]["score"] < 0.95

def test_rerank_with_rich_metadata_visual(retriever, mock_bedrock_agent):
    """Test that visual results with rich metadata are reranked."""
    results = [
        {"content": {}, "metadata": {"people_mentioned": ["judy wilson"], "topic": "family_photos"}, "score": 0.8, "location": {"s3Location": {"uri": "s3://b/1"}}},
    ]
    mock_bedrock_agent.rerank.return_value = {
        "results": [{"index": 0, "relevanceScore": 0.92}]
    }

    reranked = retriever._rerank_results("photos of judy", results, num_results=1)

    # Should have been reranked (not interpolated)
    assert mock_bedrock_agent.rerank.call_count == 1
    assert reranked[0].get("_reranked") is True
    assert reranked[0]["score"] == 0.92
```

**Commit Message Template:**
```
feat(retriever): add _rerank_results with interpolation for un-rerankable results

- Categorize results: rerankable (text/rich metadata) vs un-rerankable (baseline)
- Rerank rerankable results via Cohere Rerank 3.5 API
- Interpolate scores for un-rerankable to maintain original position
- Add retry-once on failure, fallback to original order
```

---

## Task 3: Integrate Rerank into Retrieve Flow

**Goal:** Modify the main `retrieve` method to call rerank for filtered results and update slice configs for 3x oversampling.

**Files to Modify:**
- `lib/ragstack_common/multislice_retriever.py` - Modify `retrieve` and `_build_slice_configs`

**Prerequisites:**
- Task 2 complete

**Implementation Steps:**

1. **Update `_build_slice_configs`** (around line 290) to oversample filtered slice:

```python
def _build_slice_configs(
    self,
    metadata_filter: dict | None,
    num_results: int,
) -> list[SliceConfig]:
    """
    Build slice configurations based on filter availability.

    For filtered queries, the filtered slice requests 3x results
    to provide better candidates for reranking.

    Args:
        metadata_filter: The LLM-generated filter (if any).
        num_results: Number of final results requested.

    Returns:
        List of SliceConfig objects.
    """
    slices = [
        # Slice 1: Unfiltered (baseline recall)
        SliceConfig(
            name="unfiltered",
            use_filter=False,
            num_results=num_results,
            description="Baseline vector similarity",
        ),
    ]

    if metadata_filter:
        # Slice 2: With filter (precision) - oversample for reranking
        slices.append(
            SliceConfig(
                name="filtered",
                use_filter=True,
                num_results=num_results * RERANK_OVERSAMPLE_FACTOR,
                description="LLM-generated metadata filter (reranked)",
            )
        )

    return slices
```

2. **Update `retrieve` method** (around line 275, after slice results collected, before merge):

Insert reranking step and unfiltered visual-only filtering after the `except Exception` block:

```python
        except Exception as e:
            logger.error(f"Multi-slice retrieval error: {e}")
            # Return whatever we collected

        # Drop visual-only results from unfiltered slice (no filter validation = untrustworthy)
        if "unfiltered" in slice_results:
            original_unfiltered = len(slice_results["unfiltered"])
            slice_results["unfiltered"] = [
                r for r in slice_results["unfiltered"]
                if r.get("content", {}).get("text")  # Keep only results with text
            ]
            dropped = original_unfiltered - len(slice_results["unfiltered"])
            if dropped > 0:
                logger.info(f"Dropped {dropped} visual-only results from unfiltered slice")

        # Rerank filtered results if present
        if "filtered" in slice_results and slice_results["filtered"]:
            original_count = len(slice_results["filtered"])
            slice_results["filtered"] = self._rerank_results(
                query=query,
                results=slice_results["filtered"],
                num_results=num_results,
            )
            logger.info(
                f"Reranked filtered slice: {original_count} -> {len(slice_results['filtered'])}"
            )

        # Merge results (no boost needed - reranking handles relevancy)
        total = sum(len(r) for r in slice_results.values())
        merged = merge_slices_with_guaranteed_minimum(
            slice_results,
            min_per_slice=min(3, num_results),
            total_results=num_results * 2,
            filtered_score_boost=1.0,  # No boost - reranking replaces it
        )
```

3. **Update the log message** at the end of `retrieve` to reflect no boost:

```python
        logger.info(
            f"Multi-slice retrieval complete: {total} total, {len(merged)} after merge"
        )
```

**Verification Checklist:**
- [ ] Filtered slice requests `num_results * 3` results
- [ ] Visual-only results dropped from unfiltered slice before merge
- [ ] `_rerank_results` called after slice execution, before merge
- [ ] Merge called with `filtered_score_boost=1.0`
- [ ] Log messages updated to reflect reranking
- [ ] Tests still pass: `uv run pytest tests/unit/python/test_multislice_retriever.py -v`

**Testing Instructions:**

Add integration test for full flow:

```python
def test_retrieve_with_filter_calls_rerank(retriever, mock_bedrock_agent, sample_kb_results):
    """Test that retrieve calls rerank for filtered queries."""
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}
    mock_bedrock_agent.rerank.return_value = {
        "results": [{"index": 0, "relevanceScore": 0.95}]
    }

    result = retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id=None,
        metadata_filter={"topic": {"$eq": "genealogy"}},
        num_results=5,
    )

    # Rerank should be called for filtered results
    assert mock_bedrock_agent.rerank.call_count == 1

def test_retrieve_without_filter_no_rerank(retriever, mock_bedrock_agent, sample_kb_results):
    """Test that retrieve does NOT call rerank without filter."""
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}

    result = retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id=None,
        metadata_filter=None,  # No filter
        num_results=5,
    )

    # Rerank should NOT be called
    assert mock_bedrock_agent.rerank.call_count == 0

def test_retrieve_drops_visual_only_from_unfiltered(retriever, mock_bedrock_agent):
    """Test that visual-only results are dropped from unfiltered slice."""
    # Mix of text and visual-only results
    mixed_results = [
        {"content": {"text": "Text doc"}, "metadata": {}, "score": 0.9, "location": {"s3Location": {"uri": "s3://b/1"}}},
        {"content": {}, "metadata": {"content_type": "image"}, "score": 0.95, "location": {"s3Location": {"uri": "s3://b/2"}}},  # Visual-only - should be dropped
    ]
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": mixed_results}

    result = retriever.retrieve(
        query="test query",
        knowledge_base_id="kb-123",
        data_source_id=None,
        metadata_filter=None,  # No filter = unfiltered only
        num_results=5,
    )

    # Visual-only result should be dropped (even though it had higher score)
    assert len(result) == 1
    assert result[0]["content"]["text"] == "Text doc"
```

**Commit Message Template:**
```
feat(retriever): integrate reranking into retrieve flow

- Oversample filtered slice by 3x for better rerank candidates
- Drop visual-only results from unfiltered slice (no filter validation)
- Call _rerank_results after filtered slice returns
- Pass filtered_score_boost=1.0 to merge (reranking replaces boost)
```

---

## Task 4: Add IAM Permissions for Rerank

**Goal:** Grant Lambda functions permission to use the Bedrock Rerank API.

**Files to Modify:**
- `template.yaml` - Add IAM policy statement

**Prerequisites:**
- None (independent of code changes)

**Important:** Per [AWS documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/rerank-prereq.html), the Rerank API requires **both** `bedrock:Rerank` and `bedrock:InvokeModel` actions. The template already has wildcard `bedrock:InvokeModel` for foundation models, so we only need to add `bedrock:Rerank`.

**Implementation Steps:**

1. Open `template.yaml`

2. Find `QueryKBFunction` policies section (around line 1612-1666). Add a new statement for the Rerank action:

```yaml
Policies:
  - Statement:
      - Effect: Allow
        Action:
          - bedrock:Retrieve
          # ... existing actions
```

Add a new statement in the same Policies list:

```yaml
      - Effect: Allow
        Action:
          - bedrock:Rerank
        Resource: '*'
```

3. Find `SearchKBFunction` policies section (around line 1668-1722). Add the same statement:

```yaml
      - Effect: Allow
        Action:
          - bedrock:Rerank
        Resource: '*'
```

**Note:** The `bedrock:InvokeModel` permission for the Cohere Rerank model is already covered by the existing wildcard permission for foundation models in both functions.

**Verification Checklist:**
- [ ] QueryKBFunction has `bedrock:Rerank` with Resource: '*'
- [ ] SearchKBFunction has `bedrock:Rerank` with Resource: '*'
- [ ] Existing `bedrock:InvokeModel` wildcard for foundation models is preserved
- [ ] YAML syntax is valid: `sam validate`

**Testing Instructions:**

Validate the template:

```bash
sam validate
```

No unit tests needed for IAM changes - will be validated at deploy time.

**Commit Message Template:**
```
chore(iam): add bedrock:Rerank permission for Rerank API

- Add bedrock:Rerank to QueryKBFunction
- Add bedrock:Rerank to SearchKBFunction
- bedrock:InvokeModel already covered by existing wildcard
```

---

## Task 5: Remove Boost from MultiSliceRetriever

**Goal:** Remove the `filtered_score_boost` parameter from the retriever class.

**Files to Modify:**
- `lib/ragstack_common/multislice_retriever.py` - Remove boost parameter

**Prerequisites:**
- Task 3 complete (reranking integrated)

**Implementation Steps:**

1. **Update `__init__`** to remove boost parameter (around line 175):

Before:
```python
def __init__(
    self,
    bedrock_agent_client=None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_slices: int = DEFAULT_MAX_SLICES,
    enabled: bool = True,
    filtered_score_boost: float = DEFAULT_FILTERED_SCORE_BOOST,
):
```

After:
```python
def __init__(
    self,
    bedrock_agent_client=None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_slices: int = DEFAULT_MAX_SLICES,
    enabled: bool = True,
):
```

2. **Remove boost storage and logging** in `__init__`:

Remove:
```python
self.filtered_score_boost = filtered_score_boost
```

Update log message:
```python
logger.info(
    f"Initialized MultiSliceRetriever: timeout={timeout_seconds}s, "
    f"max_slices={max_slices}, enabled={enabled}"
)
```

3. **Remove the constant** `DEFAULT_FILTERED_SCORE_BOOST` (line ~27)

4. **Update docstring** to remove boost mention

**Verification Checklist:**
- [ ] `filtered_score_boost` parameter removed from `__init__`
- [ ] `self.filtered_score_boost` removed
- [ ] `DEFAULT_FILTERED_SCORE_BOOST` constant removed
- [ ] Log message updated
- [ ] `merge_slices_with_guaranteed_minimum` still called with `1.0` (from Task 3)

**Testing Instructions:**

Run tests - some existing tests may fail if they pass boost parameter:

```bash
uv run pytest tests/unit/python/test_multislice_retriever.py -v
```

Fix any tests that pass `filtered_score_boost` to the constructor.

**Commit Message Template:**
```
refactor(retriever): remove filtered_score_boost parameter

- Remove boost parameter from __init__
- Remove DEFAULT_FILTERED_SCORE_BOOST constant
- Reranking now handles filtered result relevancy
```

---

## Task 6: Remove Boost from Lambda Functions

**Goal:** Remove boost configuration reading and parameter passing from query_kb and search_kb.

**Files to Modify:**
- `src/lambda/query_kb/index.py` - Remove boost config and parameter
- `src/lambda/search_kb/index.py` - Remove boost config and parameter

**Prerequisites:**
- Task 5 complete (boost removed from retriever)

**Implementation Steps:**

### query_kb/index.py

1. **Update `_get_filter_components` function** (around line 171):

Remove the `filtered_score_boost` parameter:

Before:
```python
def _get_filter_components(filtered_score_boost: float = 1.25):
```

After:
```python
def _get_filter_components():
```

2. **Remove boost change detection** (around line 184-187):

Remove this block:
```python
boost_changed = (
    _multislice_retriever is not None
    and _multislice_retriever.filtered_score_boost != filtered_score_boost
)
if _multislice_retriever is None or boost_changed:
```

Replace with:
```python
if _multislice_retriever is None:
```

3. **Remove boost from retriever initialization** (around line 189-192):

Before:
```python
_multislice_retriever = MultiSliceRetriever(
    bedrock_agent_client=bedrock_agent,
    filtered_score_boost=filtered_score_boost,
)
```

After:
```python
_multislice_retriever = MultiSliceRetriever(
    bedrock_agent_client=bedrock_agent,
)
```

4. **Remove boost config reading** (around line 1468-1471):

Delete these lines:
```python
filtered_score_boost = float(
    get_config_manager().get_parameter("multislice_filtered_boost", default=1.25)
)
```

5. **Update function calls** (around line 1476 and 1503):

Change:
```python
_, filter_generator, _ = _get_filter_components(filtered_score_boost)
```

To:
```python
_, filter_generator, _ = _get_filter_components()
```

### search_kb/index.py

Apply the same changes to `_get_filter_components` and its calls:

1. **Function definition** (around line 99-120): Remove `filtered_score_boost` parameter from signature
2. **Boost change detection** (around line 110-113): Remove boost change detection logic
3. **Retriever initialization** (around line 115-118): Remove boost from retriever initialization
4. **Config reading** (around line 269-272): Remove boost config reading
5. **Function calls** (around line 275, 297): Update all `_get_filter_components()` calls to take no arguments

**Verification Checklist:**
- [ ] `_get_filter_components()` takes no parameters in both files
- [ ] No references to `multislice_filtered_boost` config
- [ ] MultiSliceRetriever created without boost parameter
- [ ] All tests pass: `npm run test:backend`

**Testing Instructions:**

```bash
npm run test:backend
```

Specific files:
```bash
uv run pytest tests/unit/python/test_query_kb.py -v
uv run pytest tests/unit/python/test_search_kb.py -v
```

**Commit Message Template:**
```
refactor(lambda): remove filtered_score_boost from query_kb and search_kb

- Remove boost parameter from _get_filter_components
- Remove multislice_filtered_boost config reads
- Simplify retriever initialization
```

---

## Task 7: Remove Boost from UI

**Goal:** Remove the "Filtered Results Boost" slider from the Settings page.

**Files to Modify:**
- `src/ui/src/components/Settings/index.tsx` - Remove boost form field

**Prerequisites:**
- None (can be done in parallel with other tasks)

**Implementation Steps:**

1. Open `src/ui/src/components/Settings/index.tsx`

2. Find the "Filtered Results Boost" FormField (around line 914-941). It looks like:

```tsx
{formValues.multislice_enabled === true && formValues.filter_generation_enabled === true && (
  <>
    <FormField
      label="Filtered Results Boost"
      description="Score multiplier for results matching metadata filters (1.0 = no boost, 2.0 = double)"
    >
      <Input
        type="number"
        step={0.05}
        value={String(formValues.multislice_filtered_boost ?? 1.25)}
        onChange={({ detail }) => {
          const val = parseFloat(detail.value) || 1.25;
          setFormValues({ ...formValues, multislice_filtered_boost: Math.min(2.0, Math.max(1.0, val)) });
        }}
      />
    </FormField>
  </>
)}
```

3. Delete the entire conditional block (from `{formValues.multislice_enabled...` through the closing `)}`)

**Verification Checklist:**
- [ ] "Filtered Results Boost" field removed from Settings
- [ ] No TypeScript errors: `npm run lint:frontend`
- [ ] UI tests pass: `npm run test:frontend`

**Testing Instructions:**

```bash
cd src/ui
npm run lint
npm run test
```

**Commit Message Template:**
```
chore(ui): remove filtered results boost control from Settings

- Remove FormField for multislice_filtered_boost
- Reranking now handles filtered result relevancy automatically
```

---

## Task 8: Remove Boost from Config Schema

**Goal:** Remove the `multislice_filtered_boost` field from the configuration schema.

**Files to Modify:**
- `template.yaml` - Remove from config schema

**Prerequisites:**
- Task 6 complete (Lambdas don't read boost config)

**Implementation Steps:**

1. Open `template.yaml`

2. Find the configuration schema (around line 4293-4298). Look for:

```yaml
'multislice_filtered_boost': {
    'type': 'number',
    'order': 21,
    'description': 'Score multiplier for filtered results (1.0-2.0)',
    'default': 1.25
}
```

3. Delete this entire block

4. If there's a trailing comma on the previous field, ensure proper YAML formatting

**Verification Checklist:**
- [ ] `multislice_filtered_boost` removed from schema
- [ ] YAML syntax valid: `sam validate`
- [ ] No other references to this config field

**Testing Instructions:**

```bash
sam validate
```

**Commit Message Template:**
```
chore(config): remove multislice_filtered_boost from schema

- Remove deprecated boost config field
- Reranking replaces boost functionality
```

---

## Task 9: Update Unit Tests

**Goal:** Remove boost-related tests and add comprehensive rerank tests.

**Files to Modify:**
- `tests/unit/python/test_multislice_retriever.py` - Replace boost tests with rerank tests

**Prerequisites:**
- Tasks 1-5 complete (rerank implemented, boost removed)

**Implementation Steps:**

1. **Remove boost-related tests** (around lines 459-545):
   - Delete `test_filtered_score_boost_reorders_results`
   - Delete `test_filtered_score_boost_returns_boosted_score`
   - Delete `test_multislice_retriever_accepts_boost_parameter`
   - Delete `test_multislice_retriever_default_boost`

2. **Update any tests that pass `filtered_score_boost` to the retriever**

3. **Add new rerank tests**:

```python
# === Rerank Tests ===

class TestRerankResults:
    """Tests for the _rerank_results method."""

    def test_rerank_calls_api_with_correct_format(self, retriever, mock_bedrock_agent):
        """Test that rerank API is called with correct request format."""
        results = [
            {"content": {"text": "Doc 1 text"}, "score": 0.7, "location": {"s3Location": {"uri": "s3://b/1"}}},
            {"content": {"text": "Doc 2 text"}, "score": 0.8, "location": {"s3Location": {"uri": "s3://b/2"}}},
        ]
        mock_bedrock_agent.rerank.return_value = {
            "results": [{"index": 1, "relevanceScore": 0.95}, {"index": 0, "relevanceScore": 0.85}]
        }

        retriever._rerank_results("test query", results, num_results=2)

        mock_bedrock_agent.rerank.assert_called_once()
        call_kwargs = mock_bedrock_agent.rerank.call_args.kwargs
        assert call_kwargs["queries"][0]["textQuery"]["text"] == "test query"
        assert len(call_kwargs["sources"]) == 2
        assert "bedrockRerankingConfiguration" in call_kwargs["rerankingConfiguration"]

    def test_rerank_reorders_by_relevance_score(self, retriever, mock_bedrock_agent):
        """Test that results are reordered by rerank relevance score."""
        results = [
            {"content": {"text": "Low relevance"}, "score": 0.9, "location": {"s3Location": {"uri": "s3://b/1"}}},
            {"content": {"text": "High relevance"}, "score": 0.5, "location": {"s3Location": {"uri": "s3://b/2"}}},
        ]
        mock_bedrock_agent.rerank.return_value = {
            "results": [{"index": 1, "relevanceScore": 0.95}, {"index": 0, "relevanceScore": 0.60}]
        }

        reranked = retriever._rerank_results("query", results, num_results=2)

        # High relevance doc (originally idx 1) should be first
        assert reranked[0]["score"] == 0.95
        assert reranked[1]["score"] == 0.60

    def test_rerank_retries_on_failure(self, retriever, mock_bedrock_agent):
        """Test that rerank retries once on failure."""
        results = [{"content": {"text": "Doc"}, "score": 0.8, "location": {"s3Location": {"uri": "s3://b/1"}}}]
        mock_bedrock_agent.rerank.side_effect = [
            Exception("First failure"),
            {"results": [{"index": 0, "relevanceScore": 0.9}]}
        ]

        reranked = retriever._rerank_results("query", results, num_results=1)

        assert mock_bedrock_agent.rerank.call_count == 2
        assert reranked[0]["score"] == 0.9

    def test_rerank_falls_back_after_two_failures(self, retriever, mock_bedrock_agent):
        """Test fallback to original results after retry exhausted."""
        results = [
            {"content": {"text": "Doc 1"}, "score": 0.9, "location": {"s3Location": {"uri": "s3://b/1"}}},
            {"content": {"text": "Doc 2"}, "score": 0.7, "location": {"s3Location": {"uri": "s3://b/2"}}},
        ]
        mock_bedrock_agent.rerank.side_effect = Exception("Persistent failure")

        reranked = retriever._rerank_results("query", results, num_results=2)

        assert mock_bedrock_agent.rerank.call_count == 2
        # Should return original results sorted by score
        assert reranked[0]["score"] == 0.9
        assert reranked[1]["score"] == 0.7

    def test_rerank_skips_visual_only_results(self, retriever, mock_bedrock_agent):
        """Test that visual-only results (no text) are not sent to rerank."""
        results = [
            {"content": {"text": "Has text"}, "score": 0.8, "location": {"s3Location": {"uri": "s3://b/1"}}},
            {"content": {}, "score": 0.9, "location": {"s3Location": {"uri": "s3://b/2"}}},  # Visual only
        ]
        mock_bedrock_agent.rerank.return_value = {
            "results": [{"index": 0, "relevanceScore": 0.95}]
        }

        reranked = retriever._rerank_results("query", results, num_results=2)

        # Only text result sent to rerank
        call_kwargs = mock_bedrock_agent.rerank.call_args.kwargs
        assert len(call_kwargs["sources"]) == 1
        # Both results should be in output
        assert len(reranked) == 2

    def test_rerank_returns_empty_for_no_text_results(self, retriever, mock_bedrock_agent):
        """Test handling when all results are visual-only."""
        results = [
            {"content": {}, "score": 0.9, "location": {"s3Location": {"uri": "s3://b/1"}}},
        ]

        reranked = retriever._rerank_results("query", results, num_results=1)

        # Rerank should not be called
        assert mock_bedrock_agent.rerank.call_count == 0
        assert len(reranked) == 1


class TestRetrieveWithRerank:
    """Tests for retrieve method with reranking integration."""

    def test_retrieve_calls_rerank_for_filtered_query(self, retriever, mock_bedrock_agent, sample_kb_results):
        """Test that retrieve calls rerank when filter is provided."""
        mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}
        mock_bedrock_agent.rerank.return_value = {
            "results": [{"index": 0, "relevanceScore": 0.95}]
        }

        retriever.retrieve(
            query="test",
            knowledge_base_id="kb-123",
            data_source_id=None,
            metadata_filter={"topic": {"$eq": "genealogy"}},
            num_results=5,
        )

        assert mock_bedrock_agent.rerank.call_count == 1

    def test_retrieve_no_rerank_without_filter(self, retriever, mock_bedrock_agent, sample_kb_results):
        """Test that retrieve does NOT call rerank without filter."""
        mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}

        retriever.retrieve(
            query="test",
            knowledge_base_id="kb-123",
            data_source_id=None,
            metadata_filter=None,
            num_results=5,
        )

        assert mock_bedrock_agent.rerank.call_count == 0

    def test_retrieve_oversamples_filtered_slice(self, retriever, mock_bedrock_agent, sample_kb_results):
        """Test that filtered slice requests 3x results for oversampling."""
        mock_bedrock_agent.retrieve.return_value = {"retrievalResults": sample_kb_results}
        mock_bedrock_agent.rerank.return_value = {"results": []}

        retriever.retrieve(
            query="test",
            knowledge_base_id="kb-123",
            data_source_id=None,
            metadata_filter={"topic": {"$eq": "genealogy"}},
            num_results=5,
        )

        # Check retrieve calls
        calls = mock_bedrock_agent.retrieve.call_args_list
        # Find the filtered call (has filter in config)
        for call in calls:
            config = call.kwargs.get("retrievalConfiguration", {}).get("vectorSearchConfiguration", {})
            if "filter" in config:
                # Filtered slice should request 3x = 15 results
                assert config["numberOfResults"] == 15
                break
        else:
            pytest.fail("No filtered retrieve call found")
```

**Verification Checklist:**
- [ ] All boost tests removed
- [ ] New rerank tests added and passing
- [ ] Tests cover: API format, reordering, retry, fallback, visual-only, integration
- [ ] All tests pass: `npm run test:backend`

**Testing Instructions:**

```bash
uv run pytest tests/unit/python/test_multislice_retriever.py -v
```

**Commit Message Template:**
```
test(retriever): replace boost tests with rerank tests

- Remove test_filtered_score_boost_* tests
- Add TestRerankResults class with comprehensive tests
- Add TestRetrieveWithRerank integration tests
- Test retry, fallback, visual-only handling
```

---

## Task 10: Update CHANGELOG

**Goal:** Document the reranking feature and boost removal in the CHANGELOG.

**Files to Modify:**
- `CHANGELOG.md` - Add new version entry

**Prerequisites:**
- All other tasks complete

**Implementation Steps:**

1. Open `CHANGELOG.md`

2. Add a new version entry at the top (below any existing header). Use the next minor version:

```markdown
## [v2.3.0] - YYYY-MM-DD

### Added
- **Filtered query reranking**: Automatically rerank filtered results using Cohere Rerank 3.5 for improved relevancy
  - 3x oversampling for filtered queries
  - Visual embeddings with rich metadata (captions, people, topics) are reranked via synthesized text
  - Visual embeddings with only baseline metadata retain their position via score interpolation
- Visual-only results in unfiltered slices are now dropped (no filter validation = untrustworthy)

### Removed
- **Filtered score boost**: The `multislice_filtered_boost` config and UI control have been removed
  - Reranking now handles relevancy directly instead of artificial score boosting
  - Existing config values are ignored (no migration needed)

### Changed
- `MultiSliceRetriever` no longer accepts `filtered_score_boost` parameter
- Filtered slice now requests 3x results to provide better candidates for reranking
```

3. Update the date to the actual release date when merging.

**Verification Checklist:**
- [ ] New version entry added with correct format
- [ ] Added section describes reranking feature
- [ ] Removed section documents boost removal
- [ ] Changed section notes API changes
- [ ] Date placeholder present (will be set at release)

**Testing Instructions:**

No tests - manual review of CHANGELOG format.

**Commit Message Template:**
```
docs(changelog): add v2.3.0 entry for reranking feature

- Document filtered query reranking with Cohere Rerank 3.5
- Document removal of multislice_filtered_boost
- Note visual embedding handling changes
```

---

## Phase Verification

After completing all tasks, verify the entire phase:

### Automated Checks

```bash
# All backend tests pass
npm run test:backend

# All frontend tests pass
npm run test:frontend

# Lint passes
npm run lint
npm run lint:frontend

# Template valid
sam validate
```

### Manual Verification

- [ ] Search `multislice_filtered_boost` in codebase - should only appear in CHANGELOG or docs
- [ ] Search `filtered_score_boost` in codebase - should not appear except in tests (if any legacy)
- [ ] Review `git diff` to ensure all changes are intentional

### Integration Points

- [ ] `MultiSliceRetriever` works with filter (calls rerank)
- [ ] `MultiSliceRetriever` works without filter (no rerank call)
- [ ] Error path tested (rerank failure falls back gracefully)

### Known Limitations

- Rerank adds ~200-500ms latency to filtered queries
- Visual-only results (images without text) are not reranked
- Cohere Rerank 3.5 has 512 token limit per document (text truncated)

---

## Rollback Plan

If issues arise after deployment:

1. Revert commits in reverse order
2. The boost infrastructure can be re-added if needed
3. IAM permissions can remain (harmless if not used)

---

`PLAN_COMPLETE`
