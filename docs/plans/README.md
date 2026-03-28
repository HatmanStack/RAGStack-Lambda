# Filtered Query Re-ranking Implementation Plan

## Feature Overview

RAGStack-Lambda uses S3 Vectors for document retrieval, which achieves 90% cost savings through aggressive 4-bit quantization. However, filtered queries (e.g., "photos of Judy" with a person name filter) suffer from ~10% lower relevancy due to quantization noise and HNSW graph disconnection when nodes are filtered out.

The current workaround applies a 1.25x score boost to filtered results, which normalizes scores but doesn't actually improve result quality. This plan implements the proper fix: **re-ranking filtered results using Bedrock Cohere Rerank 3.5**. The reranker uses a cross-encoder to evaluate query-document relevance directly, overcoming the limitations of the quantized vector similarity scores.

The implementation handles three categories of results:
1. **Text content or rich metadata** (captions, people, topics) → Rerank via API
2. **Visual with baseline metadata only** → Interpolate score to maintain position
3. **Visual-only in unfiltered slice** → Drop (no filter validation = untrustworthy)

Uses a 3x oversample strategy for filtered queries, completely replacing the score boost workaround.

## Prerequisites

- **AWS Account** with Bedrock access enabled
- **Cohere Rerank 3.5** model access in your region (us-east-1 supported)
- **Python 3.13+** with `uv` for package management
- **Node.js 24+** for UI changes
- **Docker** for Lambda layer builds (if testing locally)
- **SAM CLI** for deployment

## Phase Summary

| Phase | Goal | Estimated Tokens |
|-------|------|------------------|
| [Phase-0](./Phase-0.md) | Foundation: Architecture decisions, patterns, testing strategy | ~5,000 |
| [Phase-1](./Phase-1.md) | Implementation: Add reranking, remove boost, update tests, changelog | ~20,000 |

**Total Estimated Tokens:** ~25,000

## Important Notes

- **Commit messages should NOT include Co-Authored-By or Generated-By attribution lines**
- Follow conventional commits format: `type(scope): description`
- All tests must pass locally before committing
- Do not deploy to AWS during implementation - owner handles deployment

## Quick Links

- [Phase 0: Foundation](./Phase-0.md)
- [Phase 1: Implementation](./Phase-1.md)
