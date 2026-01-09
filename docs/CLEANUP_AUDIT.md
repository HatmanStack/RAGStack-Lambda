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
| *To be populated as code is removed* | | | | |

---

## TypeScript Dead Code Removed

| File | Export Name | Type | Reason | Phase |
|------|-------------|------|--------|-------|
| *To be populated during Phase 2* | | | | |

---

## Console/Print Statements Removed

| Language | File | Lines Removed | Phase |
|----------|------|---------------|-------|
| *To be populated during Phases 1-2* | | | |

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
