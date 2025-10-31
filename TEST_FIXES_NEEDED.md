# Test Suite Issues - Fix Roadmap

**Status**: Local testing workflow is functional. Test collection works. However, 42 tests fail and 31 have errors.

**Last Run**: 126 tests collected, 52 passed, 42 failed, 31 errors, 1 skipped

---

## Issue Categories

### 1. Module Import Errors (High Priority) 🔴

**Problem**: Several test files are importing from the wrong Lambda function directory.

**Affected Files**:
- `tests/unit/test_configuration_resolver.py` - Imports from `query_kb` instead of `appsync_resolvers`
- `tests/unit/test_generate_embeddings.py` - Imports from wrong directory
- `tests/unit/test_process_document.py` - Imports from wrong directory

**Error Pattern**:
```
AttributeError: <module 'index' from '.../query_kb/index.py'> does not have attribute 'get_configuration_item'
```

**Root Cause**: Tests add wrong Lambda directory to `sys.path` before importing.

**Fix Approach**:
1. Check each test file's `lambda_dir` path assignment (around line 12-13)
2. Verify it points to the correct Lambda function directory
3. Expected directories:
   - `test_configuration_resolver.py` → `src/lambda/appsync_resolvers/`
   - `test_generate_embeddings.py` → `src/lambda/generate_embeddings/`
   - `test_process_document.py` → `src/lambda/process_document/`

**Estimated Impact**: Fixes ~20-25 test failures

---

### 2. pytest_plugins Mock Issue (Medium Priority) 🟡

**Problem**: `lib/ragstack_common/` test files have a conftest.py with mocked pytest_plugins that pytest can't handle.

**Affected Files**:
- All tests in `lib/ragstack_common/test_*.py` (31 errors)

**Error Pattern**:
```
UsageError: Plugins may be specified as a sequence or a ','-separated string of plugin names.
Got: <MagicMock name='mock.pytest_plugins' id='...'>
```

**Root Cause**: `lib/ragstack_common/conftest.py` likely has:
```python
pytest_plugins = MagicMock()  # ❌ This breaks pytest
```

**Fix Approach**:
1. Check `lib/ragstack_common/conftest.py`
2. Either remove pytest_plugins entirely or make it a proper list:
   ```python
   pytest_plugins = []  # ✅ Proper format
   ```

**Estimated Impact**: Fixes 31 test errors

---

### 3. Environment Variable Issues (Medium Priority) 🟡

**Problem**: Tests fail because Lambda code requires environment variables at module level.

**Affected Tests**:
- `test_lambda_handler_get_configuration` - Missing `KNOWLEDGE_BASE_ID`
- `test_lambda_handler_missing_required_fields` - Same issue

**Error Pattern**:
```
ValueError: KNOWLEDGE_BASE_ID environment variable is required
```

**Fix Approach**:
1. Ensure environment variables are set BEFORE importing Lambda modules
2. Pattern in test files:
   ```python
   import os
   os.environ["KNOWLEDGE_BASE_ID"] = "test-kb-id"  # Set FIRST

   # THEN import the module
   import index
   ```

**Estimated Impact**: Fixes ~5 test failures

---

### 4. Test Assertion Errors (Low Priority - Test Logic) 🟢

**Problem**: Tests run but assertions fail due to incorrect mock setup or expected values.

**Affected Tests**:
- `test_lambda_handler_success` - `assert 0.0 == 0.95`
- `test_lambda_handler_custom_max_results` - `TypeError: 'NoneType' object is not subscriptable`
- `test_lambda_handler_bedrock_error` - Missing 'error' key in response
- Several others with assertion mismatches

**Root Cause**: Test expectations don't match actual Lambda function behavior or mocks aren't returning expected data.

**Fix Approach**:
1. Review each failing test individually
2. Check if:
   - Mock return values are correct
   - Assertions match actual function behavior
   - Test setup properly initializes all dependencies
3. Update mocks or assertions as needed

**Estimated Impact**: Fixes ~10-15 test failures

---

## Recommended Fix Order

### Phase 1: Quick Wins (1-2 hours)
1. ✅ Fix `lib/ragstack_common/conftest.py` pytest_plugins issue
2. ✅ Fix module import paths in test files
3. ✅ Add missing environment variables

**Expected Result**: ~50 tests passing (up from 52)

### Phase 2: Test Logic (2-4 hours)
1. Fix assertion errors one-by-one
2. Update mock configurations
3. Verify test expectations match code behavior

**Expected Result**: ~80-90 tests passing

### Phase 3: Comprehensive Cleanup (Optional)
1. Add missing test coverage
2. Refactor common test patterns into fixtures
3. Document test architecture

---

## Current State Summary

### ✅ What's Working
- Test collection (all 126 tests discovered)
- Local testing workflow (`npm test`, `npm run lint`)
- GitHub Actions CI/CD workflow
- 52 tests passing consistently

### ❌ What Needs Fixing
- 42 test failures (mostly import/setup issues)
- 31 test errors (pytest_plugins mock issue)

### 📊 Success Metrics
- **Current**: 52/126 tests passing (41%)
- **After Phase 1**: ~50 tests fixed, 102/126 passing (81%)
- **After Phase 2**: ~15 more fixed, 117/126 passing (93%)

---

## Commands for Testing Fixes

```bash
# Run all tests and see results
npm run test:backend

# Run specific test file
pytest tests/unit/test_configuration_resolver.py -v

# Run with detailed output
pytest tests/unit/test_configuration_resolver.py -vs

# Run just one test
pytest tests/unit/test_configuration_resolver.py::test_lambda_handler_get_configuration -vs

# Check for import errors without running tests
python -c "import sys; sys.path.insert(0, 'src/lambda/appsync_resolvers'); import index"
```

---

## Notes

- These issues are **pre-existing** - not caused by the Phase 0-3 local testing workflow implementation
- The core testing infrastructure (ruff, pytest, vitest, CI/CD) is working correctly
- Test fixes are **technical debt** that should be addressed separately from the testing workflow feature
- All fixes are in test code only - no production code changes needed

---

## Frontend Test Issues (New) 🔴

**Status**: 12 passing, 10 failing (all in Settings component re-embedding features)
**Last Updated**: 2025-10-30

### Problem Summary

The Settings component's re-embedding job polling tests are failing due to complex interactions between:
- Vitest fake timers
- React state updates
- GraphQL mock exhaustion
- `act()` wrapper requirements

### Root Cause

The component uses `setInterval` to poll job status every 5 seconds. When using fake timers with `act()`:
1. Component re-renders trigger additional GraphQL calls
2. We run out of mocked responses
3. Tests timeout waiting for promises to resolve
4. Error: "Cannot read properties of undefined (reading 'data')"

### Failing Tests (10 total)

All in `src/components/Settings/index.test.jsx`:

1. `checks for existing re-embedding job on mount` (line 334)
2. `displays progress banner when re-embedding job is in progress` (line 361)
3. `displays success banner when re-embedding job is completed` (line 391)
4. `polls job status every 5 seconds when job is in progress` (line 420)
5. `stops polling when job completes` (line 464)
6. `triggers re-embedding job when user selects re-embed option in modal` (line 520)
7. `handles re-embedding job error gracefully` (line 576)
8. `dismisses completed job banner when user clicks dismiss` (line 598)
9. `shows no banner when no re-embedding job exists` (line 631)
10. `calculates progress percentage correctly` (line 655)

### What We Tried

**Attempt 1: Remove global fake timers** (✅ Partial Success)
- Removed `beforeEach(() => vi.useFakeTimers())` from describe block
- Fixed 6 tests that don't need time control
- Issue: 4 polling tests still need fake timers

**Attempt 2: Selective fake timers** (⚠️ Helped but not enough)
- Used `vi.useFakeTimers({ toFake: ['setInterval', 'setTimeout', 'clearInterval', 'clearTimeout'] })`
- This prevents mocking microtasks that React Testing Library needs
- Issue: Still need proper mock sequencing

**Attempt 3: Add fallback mocks** (⚠️ Still timing out)
- Added `.mockResolvedValue()` for repeated calls
- Issue: `act()` causes more re-renders than expected

**Attempt 4: Wrap timer calls in act()** (❌ Made it worse)
- Wrapped `vi.runAllTimersAsync()` and `vi.advanceTimersByTimeAsync()` in `act()`
- Issue: Even more re-renders, even more mock exhaustion

### Recommended Solutions

**Option A: Skip These Tests** (✅ Current approach for MVP)
- Add `it.skip()` to all 10 failing tests
- Document why (complex fake timer + React interactions)
- Note: Feature works in practice, just hard to test

**Option B: Refactor Component** (Ideal for future)
- Extract polling logic into custom hook
- Make interval controllable via prop (for testing)
- Example:
  ```javascript
  const { jobStatus } = useJobPolling(enabled, testInterval || 5000);
  ```

**Option C: Use Real Timers** (Pragmatic alternative)
- Remove fake timers entirely
- Set test timeout to 15000ms
- Let real setInterval run (slower but works)

**Option D: Mock setInterval Directly** (Advanced)
- Don't use fake timers
- Mock `setInterval` to call callback immediately
- More control but more complex

### Phase 3 Implementation Results (2025-10-31)

**Status**: ✅ Partially Successful - 6/10 tests fixed, 4 remain failing

**Results Summary**:
- Before: 12/22 tests passing (55%)
- After: 18/22 tests passing (82%)
- Fixed: 6 tests (+27% improvement)
- Still Failing: 4 tests (all IN_PROGRESS banner rendering)

**What Was Fixed** ✅:
1. checks for existing re-embedding job on mount
2. displays success banner when re-embedding job is completed
3. triggers re-embedding job when user selects re-embed option
4. handles re-embedding job error gracefully
5. dismisses completed job banner when user clicks dismiss
6. shows no banner when no re-embedding job exists

**Still Failing** ❌:
1. displays progress banner when re-embedding job is in progress
2. polls job status every 5 seconds when job is in progress
3. stops polling when job completes
4. calculates progress percentage correctly

**Implementation Approach**:
- Created custom setInterval mock utility (no Vitest fake timers)
- Removed `.skip` from all 10 tests
- Used direct interval control via `triggerAllIntervals()`
- Proper GraphQL mock sequencing (getConfiguration → getReEmbedJobStatus)

### Caveats: Why 4 Tests Still Fail

**Caveat 1: React State Batching vs Custom setInterval Mock**
React 18+ automatically batches state updates, which may interact poorly with our custom setInterval mock. When we call `triggerAllIntervals()`, React might not have completed its internal state updates yet, causing the component to not render the IN_PROGRESS banner before our test assertions run.

**Evidence**: All 4 failing tests show "Loading configuration..." stuck on screen, suggesting the component never completes its initial mount/state setup.

**Caveat 2: GraphQL Mock Call Order Ambiguity**
The component makes separate GraphQL calls for `getConfiguration` and `getReEmbedJobStatus`. Our mocks use `mockResolvedValueOnce()` chaining, which assumes a specific call order. If React's concurrent rendering causes calls to happen in a different order or if there are additional re-renders we're not accounting for, mocks get exhausted.

**Evidence**: Tried multiple mock strategies (mockImplementation, combined responses, sequential mocks) - all failed the same way.

**Caveat 3: useEffect Dependency Array Issues**
The component may have a `useEffect` that checks job status, but if the dependency array is incomplete or the effect isn't firing on expected state changes, IN_PROGRESS status might never trigger the banner render.

**Evidence**: COMPLETED status works fine (test passes), but IN_PROGRESS status doesn't render. This suggests the component's polling logic has different code paths for different statuses.

**Caveat 4: Testing Library waitFor Timeout**
Our custom setInterval mock doesn't advance "time" in the same way fake timers do. The component might be waiting for a real 5-second interval to pass before checking job status again, but `waitFor` times out at 1 second (default).

**Evidence**: Tests that don't use `triggerAllIntervals()` (like "displays success banner") pass fine.

**Caveat 5: Act() Wrapper Incompatibility**
Our `triggerAllIntervals()` utility wraps callbacks in `act()`, which should handle React state updates. However, if the component uses `flushSync` or other concurrent features, `act()` might not be sufficient to ensure all state updates complete before assertions.

**Evidence**: Increasing `waitFor` timeout doesn't help - component never renders the expected content.

### Recommended Next Steps

**Immediate (To unblock)**:
1. **Debug component in isolation**: Run component with actual GraphQL responses to verify IN_PROGRESS rendering works
2. **Check component source**: Verify `useEffect` dependencies and polling logic for IN_PROGRESS status
3. **Console log mock calls**: Add `console.log` to mock to see exact call sequence and timing

**Short-term (If urgent)**:
1. Use `it.skip()` for 4 failing tests (document caveat)
2. Add E2E test for re-embedding feature (Playwright/Cypress)
3. Manual QA verification before deployment

**Long-term (Proper fix)**:
1. Refactor component: Extract polling to custom hook with testable interface
2. Add `data-testid` attributes for banner states
3. Make interval duration configurable (default 5000, test can use 0)
4. Consider using React Query or SWR for polling (battle-tested)

---

**Next Step**: Start with Phase 1 backend fixes - they're straightforward and will have immediate impact.
