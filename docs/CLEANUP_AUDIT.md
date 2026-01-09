# Codebase Cleanup Audit Report

## Pre-Cleanup Baseline (Captured: 2026-01-09)

### Test Counts

| Suite | Total | Passed | Failed | Skipped |
|-------|-------|--------|--------|---------|
| Python Backend | 703 | 696 | 7 | 0 |
| UI Frontend | 187 | 183 | 2 | 2 |
| ragstack-chat | TBD | TBD | TBD | TBD |

**Note:** Pre-existing test failures in baseline (not introduced by cleanup).

### Bundle Sizes

| Package | Asset | Size | Gzip |
|---------|-------|------|------|
| src/ui | index.js | 1,814.74 kB | 520.02 kB |
| src/ui | index.css | 1,278.29 kB | 241.95 kB |
| src/ragstack-chat | wc.js (IIFE) | 207.77 kB | 65.35 kB |
| src/ragstack-chat | wc.esm.js | 318.24 kB | 77.65 kB |
| src/ragstack-chat | style.css | 13.49 kB | 2.82 kB |

### Static Analysis Baseline

#### Vulture (Python Dead Code)

**Command:** `uvx vulture lib/ src/lambda/ tests/ vulture_whitelist.py --min-confidence 80`

| Category | Count | Notes |
|----------|-------|-------|
| Unused variables | 28 | All in test files (fixture parameters) |
| Unused functions | 0 | - |
| Unused classes | 0 | - |

**Details:** All 28 findings are pytest fixture parameters that appear unused because they're injected by pytest. These are false positives and should be whitelisted.

#### Knip (TypeScript Dead Code)

**src/ui** (broken config - scanning .jsx instead of .tsx):
- Configuration hints: `src/main.jsx` and `src/**/*.{js,jsx}` patterns have no matches
- Reported 8 "unused dependencies" - false positives due to wrong file extensions

**src/ragstack-chat** (working config):

| Category | Count | Items |
|----------|-------|-------|
| Unused files | 2 | `amplify-config.generated.ts`, `amplify-config.template.ts` |
| Unused exports | 2 | `getCredentials`, `signRequest` in `iamAuth.ts` |
| Unused exported types | 2 | `SourcesToggleProps`, `CDNConfig` |

---

## Summary

This section will be updated after cleanup phases are complete.

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Python dead code items | 28 | - | - |
| TypeScript unused exports | 4+ | - | - |
| TypeScript unused files | 2 | - | - |
| UI bundle size (gzip) | 520.02 kB | - | - |
| Chat bundle size (gzip) | 65.35 kB | - | - |

---

## Phase 1 Analysis Findings (Task 1)

### Vulture Analysis at 60% Confidence

Running `uvx vulture lib/ src/lambda/ tests/ vulture_whitelist.py --min-confidence 60` identified the following candidates for removal:

#### lib/ragstack_common/ - Confirmed Dead Code (Auto-delete)

| File | Item | Type | Confidence |
|------|------|------|------------|
| `image.py:188` | `prepare_image` | function | 60% |
| `image.py:221` | `apply_adaptive_binarization` | function | 60% |
| `key_library.py:163` | `invalidate_cache` | method | 60% |
| `models.py:142` | `MeteringRecord` | class | 60% |
| `scraper/fetcher.py:331` | `fetch_with_http` | function | 60% |
| `scraper/fetcher.py:361` | `fetch_page` | function | 60% |
| `sources.py:186` | `parse_citation_uri` | function | 60% |
| `sources.py:268` | `extract_page_number` | function | 60% |
| `sources.py:294` | `lookup_document_metadata` | function | 60% |
| `sources.py:345` | `generate_document_url` | function | 60% |
| `sources.py:387` | `resolve_document_s3_uri` | function | 60% |
| `sources.py:432` | `build_source_object` | function | 60% |
| `storage.py:94` | `read_s3_json` | function | 60% |
| `storage.py:135` | `write_s3_json` | function | 60% |
| `storage.py:159` | `write_s3_binary` | function | 60% |
| `storage.py:183` | `s3_object_exists` | function | 60% |

**Total: 16 items in lib/**

#### lib/ragstack_common/constants.py - Unused Constants (Review)

| Constant | Line | Notes |
|----------|------|-------|
| `MAX_QUERY_LENGTH` | 13 | Never imported |
| `SNIPPET_LENGTH` | 16 | Never imported |
| `MESSAGE_LIMIT` | 19 | Never imported |
| `MAX_SEARCH_RESULTS` | 22 | Never imported |
| `DEFAULT_SEARCH_RESULTS` | 23 | Never imported |
| `PRESIGNED_URL_EXPIRY` | 31 | Never imported |
| `LAMBDA_TIMEOUT` | 34 | Never imported |
| `INGEST_TIMEOUT` | 37 | Never imported |
| `QUERY_TIMEOUT` | 40 | Never imported |
| `DEFAULT_PAGE_SIZE` | 48 | Never imported |
| `MAX_PAGE_SIZE` | 51 | Never imported |
| `MAX_IMAGE_DIMENSION` | 62 | Never imported |
| `DEFAULT_GLOBAL_QUOTA_DAILY` | 70 | Never imported |
| `DEFAULT_PER_USER_QUOTA_DAILY` | 73 | Never imported |

**Note:** Constants file is exported via `__init__.py` but individual constants are not used. Consider removing unused constants.

#### src/lambda/ - Confirmed Dead Code (Auto-delete)

| File | Item | Type | Confidence |
|------|------|------|------------|
| `detect_file_type/index.py:41` | `OCR_TYPES` | variable | 60% |
| `kb_custom_resource/index.py:25` | `generate_random_suffix` | function | 60% |
| `metadata_analyzer/index.py:53` | `DEFAULT_MIN_OCCURRENCE_RATE` | variable | 60% |

**Total: 3 items in src/lambda/**

#### Whitelisted Items (False Positives)

Added to `vulture_whitelist.py`:
- `create_or_update`, `poll_create_or_update`, `delete` - crhelper decorator-registered functions
- pytest fixtures from `tests/conftest.py`: `pytest_configure`, `sample_key_library_entries`, `sample_immigration_text`, `sample_census_text`, `sample_genealogy_text`, `sample_image_caption`, `immigration_metadata`
- `side_effect` - mock attribute set dynamically in tests

---

## Python Dead Code Removed

| File | Function/Class | Line | Reason | Phase |
|------|---------------|------|--------|-------|
| `lib/ragstack_common/image.py` | `prepare_image` | 188 | Never called (60% confidence) | 1 |
| `lib/ragstack_common/image.py` | `apply_adaptive_binarization` | 221 | Never called (60% confidence) | 1 |
| `lib/ragstack_common/key_library.py` | `invalidate_cache` | 163 | Never called (60% confidence) | 1 |
| `lib/ragstack_common/models.py` | `MeteringRecord` | 142 | Never used (60% confidence) | 1 |
| `lib/ragstack_common/scraper/fetcher.py` | `fetch_with_http` | 331 | Async variant never used | 1 |
| `lib/ragstack_common/scraper/fetcher.py` | `fetch_page` | 361 | Async variant never used | 1 |
| `lib/ragstack_common/sources.py` | `ParsedURI` | 174 | Only used by dead functions | 1 |
| `lib/ragstack_common/sources.py` | `parse_citation_uri` | 186 | Never called | 1 |
| `lib/ragstack_common/sources.py` | `extract_page_number` | 268 | Never called | 1 |
| `lib/ragstack_common/sources.py` | `lookup_document_metadata` | 294 | Never called | 1 |
| `lib/ragstack_common/sources.py` | `generate_presigned_url` | 323 | Duplicated in Lambda handlers | 1 |
| `lib/ragstack_common/sources.py` | `generate_document_url` | 345 | Never called | 1 |
| `lib/ragstack_common/sources.py` | `resolve_document_s3_uri` | 387 | Never called | 1 |
| `lib/ragstack_common/sources.py` | `build_source_object` | 432 | Never called | 1 |
| `lib/ragstack_common/storage.py` | `read_s3_json` | 94 | Never called | 1 |
| `lib/ragstack_common/storage.py` | `write_s3_json` | 135 | Never called | 1 |
| `lib/ragstack_common/storage.py` | `write_s3_binary` | 159 | Never called | 1 |
| `lib/ragstack_common/storage.py` | `s3_object_exists` | 183 | Never called | 1 |

**Total: 18 items removed from lib/**

| File | Function/Class | Line | Reason | Phase |
|------|---------------|------|--------|-------|
| `src/lambda/detect_file_type/index.py` | `OCR_TYPES` | 41 | Never used (defaults to "ocr") | 1 |
| `src/lambda/kb_custom_resource/index.py` | `generate_random_suffix` | 25 | Never called | 1 |
| `src/lambda/metadata_analyzer/index.py` | `DEFAULT_MIN_OCCURRENCE_RATE` | 53 | Never used | 1 |

**Total: 3 items removed from src/lambda/**

---

## Phase 2 Analysis Findings (Task 1)

### Knip Analysis Results

**Command:** `cd src/ui && npx knip` and `cd src/ragstack-chat && npx knip`

#### src/ui - Findings

| Category | Count | Items |
|----------|-------|-------|
| Unused files | 3 | `setupTests.ts`*, `types/amplify.ts`, `types/index.ts` |
| Unused exports | 1 | `useKeySimilarity` in `hooks/useMetadata.ts` |
| Unused exported types | 7 | See table below |
| Unlisted dependencies | 1 | `@vitest/coverage-v8` (devDep) |
| Unresolved imports | 1 | `./src/setupTests.js` in vitest.config.js (should be `.ts`) |

*`setupTests.ts` is actually used but referenced incorrectly as `.js` in vitest.config.js

**Unused Exported Types (src/ui):**

| File | Type Name | Decision |
|------|-----------|----------|
| `components/Settings/MetadataKeyInput.tsx` | `MetadataKeyInputProps` | Auto-delete |
| `hooks/useKeyLibrary.ts` | `MetadataKey` | Auto-delete |
| `hooks/useKeyLibrary.ts` | `UseKeyLibraryReturn` | Auto-delete |
| `hooks/useMetadata.ts` | `SimilarKey` | Auto-delete |
| `hooks/useMetadata.ts` | `KeySimilarityResult` | Auto-delete |
| `types/graphql.ts` | `GraphQLQueryResponse` | Auto-delete (re-export of GqlResponse) |
| `utils/similarity.ts` | `SimilarKey` | Auto-delete (duplicate) |

#### src/ragstack-chat - Findings

| Category | Count | Items |
|----------|-------|-------|
| Unused files | 2 | `amplify-config.generated.ts`, `amplify-config.template.ts` |
| Unused exports | 2 | `getCredentials`, `signRequest` in `utils/iamAuth.ts` |
| Unused exported types | 2 | `SourcesToggleProps`, `CDNConfig` |

**Note:** The amplify-config files are generated by build scripts but never imported in source code. The IAM auth functions (`getCredentials`, `signRequest`) are only used internally via `iamFetch` export.

---

## TypeScript Dead Code Removed

| File | Export Name | Type | Reason | Phase |
|------|-------------|------|--------|-------|
| *To be populated after cleanup* | | | | |

---

## Console/Print Statements Removed

| Language | File | Lines Removed | Phase |
|----------|------|---------------|-------|
| Python | - | 0 | 1 |
| TypeScript | src/ui/src/components/Dashboard/index.tsx | 1 console.warn | 2 |
| TypeScript | src/ui/src/components/Dashboard/DocumentTable.tsx | 2 console.warn | 2 |
| TypeScript | src/ragstack-chat/src/components/ChatInterface.tsx | 1 console.warn, 1 console.error | 2 |

**Note:** No executable `print()` statements found in production code (`lib/`, `src/lambda/`). Three `print()` calls exist in docstring examples (`text_extractors/__init__.py`) and are preserved per ADR-001.

**console.error Retention:** Per ADR-002, console.error statements are retained in TypeScript for error boundaries and critical runtime errors. The retained console.error statements provide essential debugging information for production issues without a logging infrastructure.

---

## Potential Secrets Detected

| File | Line | Pattern | Status |
|------|------|---------|--------|
| *To be populated during cleanup* | | | |

---

## Uncertain Items (Manual Review Required)

| File | Item | Reason for Uncertainty | Resolution |
|------|------|----------------------|------------|
| *To be populated during cleanup* | | | |

---

## Performance Optimizations Applied

### Phase 1 Analysis Results

**✅ Verified Correct Patterns:**
- Lazy loading: ConfigurationManager, KeyLibrary, OcrProcessor use proper lazy init
- boto3 clients: Module-level initialization in Lambda handlers (warm start reuse)
- ContentSniffer: Cached at module level in detect_file_type handler

**📋 Future Optimization Opportunities (Low Priority):**
- `sniffer.py`: 12+ regex patterns could be pre-compiled at module level
- `email_extractor.py`, `epub_extractor.py`: regex patterns in `_strip_html_tags()` could be pre-compiled
- `kb_custom_resource/index.py`: `sts_client` and `s3vectors_client` created inside functions (low impact - runs rarely during CloudFormation operations)

**Conclusion:** No immediate changes required. Current patterns follow AWS Lambda best practices.

| File | Change Description | Impact | Phase |
|------|-------------------|--------|-------|
| *To be populated during cleanup* | | | |

---

## Verification

### Post-Cleanup Checklist

- [ ] All tests pass (`npm run check`)
- [ ] No new runtime errors
- [ ] Bundle sizes reduced or unchanged
- [ ] Vulture reports zero issues (with whitelist)
- [ ] Knip reports zero issues (or documented exceptions)
- [ ] No `console.log` or `print()` in production code
