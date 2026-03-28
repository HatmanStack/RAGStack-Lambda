# Phase 0: Foundation

## Phase Goal

Establish architectural decisions, design rationale, and testing patterns that will guide the implementation in Phase 1.

**This phase is documentation-only** - no code changes. Read this entire document before starting Phase 1.

**Estimated tokens:** ~5,000

---

## Architecture Decisions

### ADR-1: Rerank Location in Flow

**Decision:** Rerank filtered slice results immediately after retrieval, before merging with unfiltered results.

**Context:** The MultiSliceRetriever runs two parallel queries:
- Unfiltered slice: Pure vector similarity (high relevancy)
- Filtered slice: Vector similarity + metadata filter (lower relevancy due to S3 Vectors limitations)

**Options Considered:**
1. Rerank filtered slice results before merge
2. Rerank all results after merge
3. Rerank only the final output

**Rationale:** Option 1 chosen because:
- The relevancy problem is specific to filtered results
- Unfiltered results already have high relevancy from pure vector similarity
- Reranking only filtered results minimizes API calls and latency
- The current merge logic already separates filtered vs unfiltered slices

**Consequences:**
- Rerank API called once per filtered query
- Unfiltered queries bypass reranking entirely
- Clear separation of concerns in code

---

### ADR-2: Oversample Factor

**Decision:** Fixed 3x oversample for filtered slice.

**Context:** To get better reranking results, we need more candidates than the final requested count.

**Options Considered:**
1. Fixed 3x oversample
2. Fixed 5x oversample
3. Configurable oversample factor
4. Adaptive based on result quality

**Rationale:** Option 1 chosen because:
- 3x provides good candidate pool without excessive API costs
- Rerank API charges per query (up to 100 docs = 1 query), so 3x fits within single query billing
- Simpler implementation with predictable behavior
- Blog post research suggested 3-5x; 3x is conservative starting point

**Consequences:**
- For `num_results=10`, filtered slice requests 30 results
- Rerank API receives up to 30 documents
- Final output contains requested `num_results`

---

### ADR-3: Error Handling Strategy

**Decision:** Retry once, then fall back to un-reranked results.

**Context:** Rerank API can fail due to transient errors, rate limits, or service issues.

**Options Considered:**
1. Fail the entire query
2. Retry once, then fall back
3. Exponential backoff with multiple retries

**Rationale:** Option 2 chosen because:
- Search functionality should be resilient
- Single retry catches momentary service hiccups
- Un-reranked results still work (just suboptimal relevancy)
- Excessive retries add unacceptable latency

**Consequences:**
- Maximum 2 rerank API calls per filtered query (1 initial + 1 retry)
- Fallback logs warning for monitoring
- Users may occasionally see lower-quality filtered results

---

### ADR-4: Boost Removal Strategy

**Decision:** Remove boost infrastructure entirely rather than deprecate.

**Context:** The 1.25x score boost was a workaround. With reranking, it's no longer needed.

**Options Considered:**
1. Keep boost as optional feature
2. Keep config but default to 1.0
3. Remove entirely

**Rationale:** Option 3 chosen because:
- Boost and reranking solve the same problem differently
- Keeping both adds confusion and maintenance burden
- YAGNI - no use case for both simultaneously
- Clean removal simplifies codebase

**Consequences:**
- `multislice_filtered_boost` config removed from schema
- UI settings control removed
- Lambda code simplified (no boost parameter passing)
- Existing user configs with boost values are ignored (harmless)

---

### ADR-5: Text Extraction and Metadata Handling for Rerank API

**Decision:** Use layered approach based on available content:
1. Text content → use directly
2. Rich metadata (captions, people, topics) → synthesize text
3. Baseline metadata only → interpolate score to maintain position

**Context:** KB retrieval results vary in content:
- Text documents have `content.text`
- Visual embeddings may have rich metadata (`ai_caption`, `people_mentioned`, `topic`)
- Some visual embeddings have only baseline metadata (`content_type`, `document_id`)

**Rationale:**
- Maximize reranking coverage by synthesizing text from metadata when possible
- Visual results with rich metadata can be meaningfully reranked
- Visual results with only baseline metadata cannot be reranked, but passed the filter + had strong visual match
- Score interpolation maintains their relative position without arbitrary boost factors

**Result Categories:**

| Category | Has Text | Has Rich Metadata | Action |
|----------|----------|-------------------|--------|
| Text document | Yes | Maybe | Rerank using text |
| Visual with caption | No | Yes | Synthesize text → Rerank |
| Visual baseline only | No | No | Interpolate score |

**Edge Case - Unfiltered Visual Results:**
- Visual-only results in unfiltered slice are dropped
- Rationale: No filter validation = just random visual similarity, not trustworthy
- Text results from unfiltered slice are kept for merge

---

### ADR-6: Score Interpolation for Un-rerankable Results

**Decision:** Interpolate scores based on original position relative to reranked results.

**Context:** Visual results with only baseline metadata cannot be reranked (no text to evaluate), but they passed the metadata filter and had strong visual similarity. They still suffer from the ~10% S3 Vectors penalty.

**Options Considered:**
1. Apply fixed 1.25x boost (original workaround)
2. Score interpolation based on position
3. Percentile mapping across score range

**Rationale:** Option 2 chosen because:
- Adapts to actual query context and score distribution
- Doesn't use arbitrary multiplier that may not fit different KB sizes
- Maintains the relative ordering that vector similarity established
- Keeps results at their original position rather than artificially inflating

**Implementation:**
```python
def _interpolate_score(self, original_position: int, reranked_results: list[dict]) -> float:
    """Assign score to maintain original position among reranked results."""
    if not reranked_results:
        return 0.5

    n = len(reranked_results)
    pos = min(original_position, n)

    if pos == 0:
        return reranked_results[0]["score"] + 0.001
    elif pos >= n:
        return reranked_results[-1]["score"] - 0.001
    else:
        score_above = reranked_results[pos - 1]["score"]
        score_below = reranked_results[pos]["score"]
        return (score_above + score_below) / 2
```

**Example:**
- Original filtered: `[A, B, IMAGE, D, E]` (IMAGE at position 2)
- Reranked: `[D(0.95), A(0.88), B(0.82), E(0.75)]`
- IMAGE gets: `(0.88 + 0.82) / 2 = 0.85`
- Final: `[D(0.95), A(0.88), IMAGE(0.85), B(0.82), E(0.75)]`

---

## Design Patterns

### Pattern 1: Rerank Method Structure

```python
def _rerank_results(self, query: str, results: list[dict], num_results: int) -> list[dict]:
    """
    Rerank filtered results using Cohere Rerank 3.5.

    Flow:
    1. Separate text vs visual-only results
    2. Prepare sources for rerank API
    3. Call rerank with retry
    4. Map reranked results back to originals
    5. Combine with visual-only results
    6. Return top num_results

    On error: Return original results sorted by score (fallback)
    """
```

### Pattern 2: Retry Logic

```python
for attempt in range(2):  # Max 2 attempts
    try:
        return self._call_rerank_api(...)
    except Exception as e:
        if attempt == 0:
            logger.warning(f"Rerank attempt 1 failed, retrying: {e}")
            continue
        logger.error(f"Rerank failed after retry, falling back: {e}")
        return fallback_results
```

### Pattern 3: Source Preparation

```python
def _prepare_source_for_rerank(self, result: dict) -> dict | None:
    """Return None for visual-only results (no text to rerank)."""
    text = result.get("content", {}).get("text", "")
    if not text:
        return None
    return {
        "type": "INLINE",
        "inlineDocumentSource": {
            "type": "TEXT",
            "textDocument": {"text": text[:RERANK_MAX_CHARS]}
        }
    }
```

---

## Tech Stack

### Rerank API

- **Model:** Cohere Rerank 3.5
- **ARN:** `arn:aws:bedrock:us-east-1::foundation-model/cohere.rerank-v3-5:0`
- **Client:** `boto3.client("bedrock-agent-runtime")` (already used for retrieve)
- **Method:** `client.rerank()`

### API Request Format

```python
response = bedrock_agent.rerank(
    queries=[{"type": "TEXT", "textQuery": {"text": query}}],
    sources=[
        {
            "type": "INLINE",
            "inlineDocumentSource": {
                "type": "TEXT",
                "textDocument": {"text": "document text here"}
            }
        }
        # ... more sources
    ],
    rerankingConfiguration={
        "type": "BEDROCK_RERANKING_MODEL",
        "bedrockRerankingConfiguration": {
            "modelConfiguration": {
                "modelArn": "arn:aws:bedrock:us-east-1::foundation-model/cohere.rerank-v3-5:0"
            },
            "numberOfResults": 10  # How many to return
        }
    }
)
```

### API Response Format

```python
{
    "results": [
        {"index": 2, "relevanceScore": 0.95},  # index refers to sources array
        {"index": 0, "relevanceScore": 0.87},
        {"index": 5, "relevanceScore": 0.72},
        # ... ordered by relevanceScore descending
    ]
}
```

---

## Testing Strategy

### Unit Test Mocking

All unit tests mock the `bedrock_agent` client. The existing pattern in `test_multislice_retriever.py`:

```python
@pytest.fixture
def mock_bedrock_agent():
    return MagicMock()

@pytest.fixture
def retriever(mock_bedrock_agent):
    return MultiSliceRetriever(bedrock_agent_client=mock_bedrock_agent)
```

**Extend for rerank:**

```python
def test_rerank_called_for_filtered(retriever, mock_bedrock_agent):
    mock_bedrock_agent.retrieve.return_value = {"retrievalResults": [...]}
    mock_bedrock_agent.rerank.return_value = {
        "results": [{"index": 0, "relevanceScore": 0.95}]
    }

    result = retriever.retrieve(
        query="test",
        knowledge_base_id="kb-123",
        data_source_id=None,
        metadata_filter={"key": {"$eq": "value"}},  # Filter present = rerank
        num_results=5
    )

    assert mock_bedrock_agent.rerank.call_count == 1
```

### Test Categories

1. **Happy Path Tests**
   - Rerank called when filter present
   - Rerank not called when no filter
   - Correct oversample factor (3x)
   - Results properly reordered by relevance score

2. **Error Handling Tests**
   - Single failure triggers retry
   - Double failure falls back to original results
   - Fallback results are sorted by original score

3. **Edge Case Tests**
   - Visual-only results (no text) pass through
   - Empty results handled gracefully
   - Mixed text/visual results handled correctly

### Running Tests

```bash
# All tests
npm run test:backend

# Just multislice retriever tests
uv run pytest tests/unit/python/test_multislice_retriever.py -v

# Single test
uv run pytest tests/unit/python/test_multislice_retriever.py::test_rerank_called_for_filtered -v
```

---

## Commit Message Format

Use conventional commits. Examples for this feature:

```
feat(retriever): add Cohere Rerank 3.5 for filtered results

- Add _rerank_results method with retry logic
- Oversample filtered slice by 3x
- Fall back to original results on error
```

```
refactor(retriever): remove filtered_score_boost parameter

- Remove boost from MultiSliceRetriever.__init__
- Update merge to always use boost=1.0
- Simplify _get_filter_components in Lambdas
```

```
chore(iam): add bedrock:InvokeModel for Cohere Rerank model

- Add permission to QueryKBFunction
- Add permission to SearchKBFunction
```

```
test(retriever): replace boost tests with rerank tests

- Remove test_filtered_score_boost_* tests
- Add test_rerank_* tests for new behavior
```

**Important:** Do NOT include Co-Authored-By or Generated-By lines.

---

## File Overview

Files to modify in Phase 1:

| File | Purpose | Changes |
|------|---------|---------|
| `lib/ragstack_common/multislice_retriever.py` | Core retrieval logic | Add rerank, remove boost |
| `template.yaml` | IAM permissions | Add Cohere Rerank permission |
| `src/lambda/query_kb/index.py` | Chat API | Remove boost parameter |
| `src/lambda/search_kb/index.py` | Search API | Remove boost parameter |
| `src/ui/src/components/Settings/index.tsx` | Settings UI | Remove boost control |
| `tests/unit/python/test_multislice_retriever.py` | Unit tests | Replace boost tests with rerank tests |

---

## Verification Checklist (Phase 0)

Before proceeding to Phase 1, verify you understand:

- [ ] Where reranking fits in the retrieve flow (after filtered slice, before merge)
- [ ] The 3x oversample strategy
- [ ] Retry + fallback error handling
- [ ] How to mock rerank API in tests
- [ ] Commit message format (no attribution lines)
