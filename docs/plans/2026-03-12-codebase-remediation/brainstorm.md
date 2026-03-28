# Feature: Codebase Remediation to 9/10 Across All Pillars

## Overview

RAGStack-Lambda is a serverless document processing pipeline with AI chat on AWS. A code audit evaluated the codebase across four pillars — Pragmatism, Defensiveness, Performance, and Type Rigor — scoring 7-8/10 in each. This remediation targets 9/10 across all four pillars.

The work is structured in three phases: (1) comprehensive test coverage for all 14 untested Lambda handlers to create a safety net, (2) TypedDict introduction and mypy strict enforcement plus splitting the 1,824-line `query_kb/index.py` monolith into a package, and (3) defensive infrastructure including a DLQ replay Lambda, S3 size guards, React error boundaries, and replacing `window.alert()` with Cloudscape Flashbar notifications.

The remediation is intentionally conservative — no logic changes, no new AWS services, no architectural rewrites. Every change is testable, reversible, and builds on existing patterns.

## Decisions

1. **Phase ordering: Tests → Types → Defense.** Tests first creates a safety net for the refactoring and infrastructure changes that follow. Type rigor second because TypedDicts define the contracts used in the query_kb refactor. Defensive infrastructure last because it benefits from both the test coverage and the cleaner module boundaries.

2. **query_kb refactor: Package split only.** Turn `query_kb/` into a Python package with separate modules. Move functions, keep signatures identical. No logic changes. Existing tests catch import breakage.

3. **TypedDict scope: Critical path only.** ~8-10 TypedDicts for structures crossing module boundaries (Bedrock responses, KB queries, document metadata, DynamoDB tracking items). Internal helper dicts stay as `dict[str, Any]`.

4. **mypy: Full strict mode in CI.** All Python code must pass `mypy --strict`. Added to the CI pipeline alongside ruff. Existing untyped code gets properly annotated, not `# type: ignore`-ed.

5. **DLQ strategy: Replay Lambda.** DLQs already exist for all 5 SQS queues. Add a replay Lambda that moves messages from a DLQ back to its source queue. Manual trigger via console/CLI. CloudWatch alarm on DLQ message count > 0.

6. **Observability: Consistent document_id in logs.** No X-Ray or Powertools (cost). The `document_id` already flows through the entire pipeline. Audit and fix log statements for consistent inclusion while writing tests. No new infrastructure.

7. **S3 size guard: HEAD check before read.** `read_s3_binary()` gets a configurable max size parameter. HEAD the object first, raise if over limit. Only 2 call sites (ocr.py, detect_file_type). Consistent with existing media upload size gating.

8. **React error boundaries: Route-level + critical components.** Wrap each route (Dashboard, Upload, Chat, Search, Settings) plus ChatInterface and DocumentTable independently. ~7 boundaries total.

9. **Replace window.alert() with Cloudscape Flashbar.** Flashbar is part of the existing Cloudscape Design System (40+ files already import Cloudscape components). Non-blocking notifications with dismiss/retry actions.

10. **Skip unified retry abstraction.** Both existing implementations (bedrock.py recursive, ingestion.py iterative) work, have tests, and aren't causing problems. YAGNI.

## Scope: In

- Unit tests for all 14 untested Lambda handlers (admin_user_provisioner, api_key_resolver, batch_processor, budget_sync, combine_pages, configuration_resolver, enqueue_batches, initial_sync, kb_custom_resource, process_document, process_media, queue_processor, reindex_kb, start_codebuild)
- Unit tests for `logging_utils.py`
- Audit all Lambda log statements for consistent `document_id` / `image_id` / `scrape_id` inclusion
- TypedDicts for critical-path cross-module contracts (~8-10 types)
- mypy strict mode across all Python code, added to CI
- `query_kb/index.py` split into package: `handler.py`, `retrieval.py`, `conversation.py`, `sources.py`, `filters.py`, `media.py`
- DLQ replay Lambda with CloudWatch alarm
- Size guard on `read_s3_binary()` (HEAD check, configurable max)
- React error boundaries (route-level + ChatInterface + DocumentTable)
- Replace `window.alert()` with Cloudscape Flashbar notifications

## Scope: Out

- Unified retry abstraction (YAGNI — both implementations work)
- X-Ray / Lambda Powertools (cost)
- Streaming S3 reads (downstream APIs need full bytes, only 2 call sites)
- TypedDicts for internal/helper dicts (critical path only)
- Per-chunk metadata extraction (backlogged from v2.3.8, separate feature)
- reindex_kb refactor (1,483 lines — flagged but separate effort, not blocking 9/10)
- Frontend test coverage increase (current 29% UI, 41% ragstack-chat — not blocking backend pillar scores)
- Integration test expansion (mocked unit tests sufficient for pillar scores)

## Open Questions

None — all scope decisions resolved.

## Relevant Codebase Context

### Backend Structure
- `lib/ragstack_common/` — Shared Python library (Lambda layer): bedrock.py, storage.py, ocr.py, config.py, ingestion.py, logging_utils.py, exceptions.py, metadata_normalizer.py, metadata_extractor.py, key_library.py, multislice_retriever.py
- `src/lambda/*/index.py` — 31 Lambda handlers
- `src/lambda/query_kb/index.py` — 1,824-line monolith (handler, retrieval, conversation, sources, filters, media all in one file)
- `tests/unit/python/` — 64 test files, pytest with parallel execution (`-n auto`)
- `tests/conftest.py` — Shared fixtures: `reset_config_singleton` (autouse), `mock_dynamodb_key_library_table`, `mock_key_library`, `mock_bedrock_client`
- `tests/unit/conftest.py` — `sys.modules['index']` cleanup (known Lambda handler caching issue)

### Frontend Structure
- `src/ui/` — React 19 + Vite + Cloudscape Design System (40+ Cloudscape component imports)
- `src/ragstack-chat/` — Reusable chat component (React + web component wrapper)
- No Flashbar usage currently — needs introduction
- No error boundaries currently — needs introduction
- `window.alert()` used for error display

### Infrastructure
- `template.yaml` — SAM template, all infrastructure as code
- 5 SQS queues with DLQs already configured (14-day retention, maxReceiveCount: 3)
- `read_s3_binary()` — 2 actual call sites: `ocr.py:85`, `detect_file_type/index.py:199`
- `.github/workflows/ci.yml` — 8 CI jobs (lint + test for backend, frontend, ragstack-chat)

### Exception Hierarchy
```
MediaProcessingError (base)
├─ TranscriptionError
├─ UnsupportedMediaFormatError
├─ MediaDurationExceededError
├─ MediaFileSizeExceededError
├─ AudioExtractionError
└─ SegmentationError
```

### query_kb Function Groupings (for package split)
- **media.py** (~350 lines): fetch_image_for_converse, generate_media_url, extract_source_url_from_content, extract_image_caption_from_content
- **filters.py** (~220 lines): extract_kb_scalar, get_config_manager, _get_filter_components, _get_filter_examples
- **conversation.py** (~100 lines): get_conversation_history, store_conversation_turn
- **retrieval.py** (~270 lines): _extract_id_pattern, _augment_with_id_lookup, build_retrieval_query, _rewrite_query_with_llm, build_conversation_messages, format_timestamp
- **sources.py** (~500 lines): extract_sources (full citation parsing)
- **handler.py** (~500 lines): lambda_handler (orchestration)

### 14 Untested Lambda Handlers (by size)
| Handler | Lines | Complexity |
|:---|:---|:---|
| reindex_kb | 1,483 | High — KB reindex orchestration |
| process_media | 444 | High — media processing pipeline |
| process_document | 384 | High — OCR extraction orchestration |
| batch_processor | 352 | High — batch processing orchestration |
| kb_custom_resource | 339 | High — CloudFormation custom resource |
| budget_sync | 319 | Medium — budget synchronization |
| configuration_resolver | 302 | Medium — config management |
| combine_pages | 247 | Medium — page combination logic |
| start_codebuild | 158 | Low — CodeBuild trigger |
| enqueue_batches | 148 | Low — SQS batch enqueue |
| api_key_resolver | 147 | Low — API key management |
| admin_user_provisioner | 142 | Low — Cognito user provisioning |
| initial_sync | 107 | Low — initial KB sync |
| queue_processor | 102 | Low — SQS message processor |

### Test Patterns
- Pytest with `conftest.py` fixtures for AWS service mocking
- `MagicMock` for DynamoDB tables, Bedrock clients
- `@patch` decorators for boto3 service clients
- `sys.modules['index']` cleanup between Lambda handler tests
- CI runs `pytest -n auto` (parallel execution)

## Technical Constraints

- **Lambda layer packaging:** `lib/ragstack_common/` is packaged as a Lambda layer (Docker required for build). New files in `ragstack_common/` are automatically included.
- **sys.modules caching:** Lambda handler tests must clear `sys.modules['index']` between test files to avoid cross-contamination. The existing `tests/unit/conftest.py` handles this.
- **mypy + boto3:** Requires `boto3-stubs` package with service-specific type stubs for full type checking of AWS SDK calls.
- **Cloudscape Flashbar:** Requires a notification state manager (typically `useState` array of flash items) at the layout level, passed down via context or props.
- **SAM template changes:** DLQ replay Lambda and CloudWatch alarms require additions to `template.yaml`. Size guard is code-only.
- **Python 3.13:** All type annotations should use modern syntax (`str | None` not `Optional[str]`, `dict[str, Any]` not `Dict[str, Any]`).
