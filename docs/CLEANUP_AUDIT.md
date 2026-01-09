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

## Python Dead Code Removed

| File | Function/Class | Line | Reason | Phase |
|------|---------------|------|--------|-------|
| *To be populated during Phase 1* | | | | |

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
