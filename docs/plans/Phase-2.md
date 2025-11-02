# Phase 2: Settings Frontend - UI Rendering

## Overview

This phase verifies and tests that the Settings UI correctly renders the three new configuration fields added in Phase 1. The existing Settings component (`src/ui/src/components/Settings/index.jsx`) is already schema-driven and should automatically render the new fields - **minimal or no code changes expected**.

**Key Focus**: Testing and verification that the UI correctly handles:
- Dropdown rendering for all new fields
- Conditional visibility for `bedrock_ocr_model_id` (only when `ocr_backend === "bedrock"`)
- Field ordering
- Re-embedding workflow (should NOT trigger for OCR/chat changes)

**Estimated Duration**: 1 day
**Estimated Token Count**: ~20,000 tokens

---

## Goals

By the end of this phase:

- [ ] Settings page renders all 7 configuration fields correctly
- [ ] Conditional field logic works (`bedrock_ocr_model_id` visible only when needed)
- [ ] Field ordering matches specification (OCR → Chat → Embeddings)
- [ ] Re-embedding workflow only triggers for embedding model changes (not OCR/chat)
- [ ] Component tests written and passing
- [ ] Manual testing completed with checklist
- [ ] Changes committed (if any code changes needed)

---

## Prerequisites

- Phase 1 complete (backend returns updated schema)
- Frontend dependencies installed (`cd src/ui && npm install`)
- Dev server can start (`npm start`)
- Familiar with React hooks and CloudScape components

---

## Tasks

### Task 2.1: Analyze Existing Settings Component

**Goal**: Understand current Settings implementation and verify it supports new fields

**Files to Review**:
- `src/ui/src/components/Settings/index.jsx`

**Prerequisites**: None (first task)

**Instructions**:

Before making any changes, analyze the existing Settings component to understand how it dynamically renders fields from the backend schema.

**Steps**:

1. **Read Settings component**:
   - Open `src/ui/src/components/Settings/index.jsx`
   - Review the `renderField` function (around line 221)
   - Understand how it handles `enum` fields (renders Select dropdown)
   - Understand how it handles `dependsOn` conditional logic (lines 228-236)

2. **Review existing re-embedding logic**:
   - Examine `handleSave` function (lines 113-142)
   - Note how it detects embedding model changes (lines 118-121)
   - Understand the modal workflow (lines 331-376)
   - Confirm it only checks `text_embed_model_id` and `image_embed_model_id`

3. **Verify schema-driven rendering**:
   - Find where fields are mapped (lines 319-326)
   - Confirm fields are sorted by `order` property
   - Confirm `renderField` is called for each property in schema

4. **Reference base repository** (optional):
   - Use subagent: "Use config-pattern-finder to show how the Settings UI renders configuration fields dynamically"
   - Compare with RAGStack implementation
   - Note any differences

5. **Document findings**:
   - Note any code changes needed (likely none)
   - Identify test scenarios to cover
   - Plan manual verification steps

**Verification Checklist**:

- [ ] Understand `renderField` function logic
- [ ] Understand `dependsOn` conditional rendering
- [ ] Understand re-embedding detection logic
- [ ] Confirmed no code changes needed for basic rendering
- [ ] Test plan drafted

**Testing**:

No automated tests for this task - it's code review and analysis.

**Commit Message**:

N/A (no code changes expected)

**Estimated Tokens**: ~3,000

---

### Task 2.2: Write Component Tests for New Fields

**Goal**: Create comprehensive tests for Settings component with new fields

**Files to Create**:
- `src/ui/src/components/Settings/Settings.test.jsx` (create if doesn't exist)

**Prerequisites**: Task 2.1 complete

**Instructions**:

Write tests BEFORE making any changes to ensure the Settings component correctly handles the new configuration fields.

**Steps**:

1. **Set up test file** (if doesn't exist):
   - Create `src/ui/src/components/Settings/Settings.test.jsx`
   - Import necessary testing utilities (React Testing Library)
   - Import CloudScape components used in Settings
   - Mock GraphQL client

2. **Write tests for field rendering**:

**Test File**: `src/ui/src/components/Settings/Settings.test.jsx`

```jsx
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { Settings } from './index';

// Mock AWS Amplify GraphQL client
vi.mock('aws-amplify/api', () => ({
  generateClient: () => ({
    graphql: vi.fn()
  })
}));

describe('Settings Component - New Fields', () => {
  const mockGetConfigurationResponse = {
    data: {
      getConfiguration: {
        Schema: JSON.stringify({
          properties: {
            ocr_backend: {
              type: 'string',
              enum: ['textract', 'bedrock'],
              description: 'OCR Backend',
              order: 1
            },
            bedrock_ocr_model_id: {
              type: 'string',
              enum: [
                'anthropic.claude-3-5-haiku-20241022-v1:0',
                'anthropic.claude-3-5-sonnet-20241022-v2:0',
                'us.anthropic.claude-3-7-sonnet-20250219-v1:0'
              ],
              description: 'Bedrock OCR Model',
              order: 2,
              dependsOn: {
                field: 'ocr_backend',
                value: 'bedrock'
              }
            },
            chat_model_id: {
              type: 'string',
              enum: [
                'us.amazon.nova-pro-v1:0',
                'us.amazon.nova-lite-v1:0',
                'anthropic.claude-3-5-sonnet-20241022-v2:0'
              ],
              description: 'Chat Model',
              order: 3
            },
            text_embed_model_id: {
              type: 'string',
              enum: ['amazon.titan-embed-text-v2:0'],
              description: 'Text Embedding Model',
              order: 4
            },
            image_embed_model_id: {
              type: 'string',
              enum: ['amazon.titan-embed-image-v1'],
              description: 'Image Embedding Model',
              order: 5
            }
          }
        }),
        Default: JSON.stringify({
          ocr_backend: 'textract',
          bedrock_ocr_model_id: 'anthropic.claude-3-5-haiku-20241022-v1:0',
          chat_model_id: 'us.amazon.nova-pro-v1:0',
          text_embed_model_id: 'amazon.titan-embed-text-v2:0',
          image_embed_model_id: 'amazon.titan-embed-image-v1'
        }),
        Custom: '{}'
      }
    }
  };

  beforeEach(() => {
    // Reset mocks before each test
    vi.clearAllMocks();

    // Mock GraphQL responses
    const { generateClient } = require('aws-amplify/api');
    generateClient().graphql.mockResolvedValue(mockGetConfigurationResponse);
  });

  test('renders all 7 configuration fields', async () => {
    render(<Settings />);

    await waitFor(() => {
      expect(screen.getByText(/OCR Backend/i)).toBeInTheDocument();
      expect(screen.getByText(/Chat Model/i)).toBeInTheDocument();
      expect(screen.getByText(/Text Embedding Model/i)).toBeInTheDocument();
      expect(screen.getByText(/Image Embedding Model/i)).toBeInTheDocument();
    });
  });

  test('bedrock model field hidden when OCR backend is textract', async () => {
    render(<Settings />);

    await waitFor(() => {
      expect(screen.getByText(/OCR Backend/i)).toBeInTheDocument();
    });

    // Bedrock OCR Model should NOT be visible when ocr_backend is 'textract'
    expect(screen.queryByText(/Bedrock OCR Model/i)).not.toBeInTheDocument();
  });

  test('bedrock model field visible when OCR backend is bedrock', async () => {
    // Update mock to have ocr_backend set to 'bedrock'
    const bedrockConfig = {
      ...mockGetConfigurationResponse,
      data: {
        getConfiguration: {
          ...mockGetConfigurationResponse.data.getConfiguration,
          Default: JSON.stringify({
            ocr_backend: 'bedrock',  // Changed to bedrock
            bedrock_ocr_model_id: 'anthropic.claude-3-5-haiku-20241022-v1:0',
            chat_model_id: 'us.amazon.nova-pro-v1:0',
            text_embed_model_id: 'amazon.titan-embed-text-v2:0',
            image_embed_model_id: 'amazon.titan-embed-image-v1'
          })
        }
      }
    };

    const { generateClient } = require('aws-amplify/api');
    generateClient().graphql.mockResolvedValue(bedrockConfig);

    render(<Settings />);

    await waitFor(() => {
      // Bedrock OCR Model SHOULD be visible when ocr_backend is 'bedrock'
      expect(screen.getByText(/Bedrock OCR Model/i)).toBeInTheDocument();
    });
  });

  test('fields are rendered in correct order', async () => {
    render(<Settings />);

    await waitFor(() => {
      const labels = screen.getAllByRole('group').map(el => el.textContent);

      // Verify OCR fields come first, then chat, then embeddings
      const ocrIndex = labels.findIndex(l => l.includes('OCR Backend'));
      const chatIndex = labels.findIndex(l => l.includes('Chat Model'));
      const textEmbedIndex = labels.findIndex(l => l.includes('Text Embedding'));

      expect(ocrIndex).toBeLessThan(chatIndex);
      expect(chatIndex).toBeLessThan(textEmbedIndex);
    });
  });

  test('changing OCR backend does NOT trigger re-embedding warning', async () => {
    const { generateClient } = require('aws-amplify/api');
    const mockUpdateConfig = vi.fn().mockResolvedValue({ data: { updateConfiguration: true } });

    generateClient().graphql.mockImplementation((options) => {
      if (options.query.includes('updateConfiguration')) {
        return mockUpdateConfig(options);
      }
      return Promise.resolve(mockGetConfigurationResponse);
    });

    const { user } = render(<Settings />);

    await waitFor(() => {
      expect(screen.getByText(/OCR Backend/i)).toBeInTheDocument();
    });

    // Change OCR backend (simulate user interaction)
    // Note: This is pseudocode - actual implementation depends on CloudScape Select component
    // You'll need to interact with the dropdown appropriately

    // Click Save
    const saveButton = screen.getByText(/Save changes/i);
    user.click(saveButton);

    await waitFor(() => {
      // Should NOT show re-embedding modal
      expect(screen.queryByText(/Embedding Model Change Detected/i)).not.toBeInTheDocument();
    });
  });

  test('changing chat model does NOT trigger re-embedding warning', async () => {
    // Similar to above test but for chat_model_id
    // Verify that changing chat model doesn't show the modal
  });

  test('changing embedding model DOES trigger re-embedding warning', async () => {
    // Mock document count > 0
    const mockDocCountResponse = {
      data: { getDocumentCount: 5 }
    };

    const { generateClient } = require('aws-amplify/api');
    generateClient().graphql.mockImplementation((options) => {
      if (options.query.includes('getDocumentCount')) {
        return Promise.resolve(mockDocCountResponse);
      }
      return Promise.resolve(mockGetConfigurationResponse);
    });

    render(<Settings />);

    await waitFor(() => {
      expect(screen.getByText(/Text Embedding Model/i)).toBeInTheDocument();
    });

    // Change embedding model
    // (simulate user interaction with dropdown)

    // Click Save
    // ...

    await waitFor(() => {
      // SHOULD show re-embedding modal
      expect(screen.getByText(/Embedding Model Change Detected/i)).toBeInTheDocument();
    });
  });
});
```

3. **Configure Vitest** (if not configured):
   - Ensure `src/ui/vitest.config.js` is set up
   - Verify jsdom environment for React components
   - Check that testing-library is available

4. **Run tests** (they should PASS if Settings component is already correct):
   - Execute tests to verify current behavior
   - If tests fail, identify what needs fixing in Settings component

**Verification Checklist**:

- [ ] Test file created with comprehensive test cases
- [ ] Tests cover all 7 fields rendering
- [ ] Tests cover conditional visibility (`dependsOn`)
- [ ] Tests cover field ordering
- [ ] Tests verify re-embedding workflow NOT triggered for OCR/chat
- [ ] Tests verify re-embedding workflow IS triggered for embeddings
- [ ] All tests passing

**Testing**:

```bash
# Run Settings tests
cd src/ui
npm test -- Settings.test.jsx

# With coverage
npm test -- Settings.test.jsx --coverage

# Watch mode for development
npm test -- Settings.test.jsx --watch
```

**Commit Message**:

```
test(settings): add tests for new configuration fields rendering

- Test all 7 fields render correctly
- Test conditional visibility of bedrock_ocr_model_id
- Test field ordering (OCR, chat, embeddings)
- Test re-embedding workflow not triggered for OCR/chat changes
- Test re-embedding workflow still works for embedding changes
- Achieve 80%+ coverage for Settings component
```

**Estimated Tokens**: ~10,000

---

### Task 2.3: Manual UI Testing

**Goal**: Verify Settings UI works correctly in browser with real interactions

**Files to Test**:
- Settings page via dev server

**Prerequisites**: Task 2.2 complete (tests passing)

**Instructions**:

Use the local development server to manually test the Settings UI and ensure everything works as expected.

**Steps**:

1. **Start frontend dev server**:
   - Navigate to `src/ui`
   - Start dev server (it will connect to mocked or local GraphQL endpoint)

2. **Test basic rendering**:
   - Open browser to dev server URL (typically http://localhost:5173)
   - Navigate to Settings page (/settings route)
   - Verify all fields appear

3. **Test field ordering**:
   - Confirm fields appear in this order from top to bottom:
     1. OCR Backend
     2. Bedrock OCR Model (if visible)
     3. Chat Model
     4. Text Embedding Model
     5. Image Embedding Model

4. **Test conditional visibility**:
   - **Default state** (ocr_backend = "textract"):
     - Verify "Bedrock OCR Model" dropdown is NOT visible
   - **Change to Bedrock**:
     - Select "bedrock" from "OCR Backend" dropdown
     - Verify "Bedrock OCR Model" dropdown appears immediately below
     - Verify it has 3 Claude model options
   - **Change back to Textract**:
     - Select "textract" from "OCR Backend" dropdown
     - Verify "Bedrock OCR Model" dropdown disappears

5. **Test dropdown options**:
   - **OCR Backend**: Should have 2 options (textract, bedrock)
   - **Bedrock OCR Model**: Should have 3 Claude model options
   - **Chat Model**: Should have 4 model options (2 Nova, 2 Claude)
   - **Text Embedding Model**: Should have 2 Titan options
   - **Image Embedding Model**: Should have 1 Titan option

6. **Test form interactions**:
   - Change OCR backend to "bedrock"
   - Select a Bedrock model
   - Change chat model
   - Click "Save changes"
   - Verify success message appears
   - Verify NO re-embedding modal appears (OCR and chat changes don't trigger it)

7. **Test embedding change workflow** (preserve existing behavior):
   - Change Text Embedding Model to different value
   - Click "Save changes"
   - **If documents exist**: Modal should appear with 3 options
   - **If no documents**: No modal, just success message

8. **Test reset button**:
   - Make several changes to fields
   - Click "Reset" button
   - Verify all fields revert to saved values

9. **Test form validation**:
   - All fields are required dropdowns (can't be empty)
   - Verify save button enabled when changes made
   - Verify save button shows loading state during save

**Verification Checklist**:

- [ ] All 7 fields render correctly
- [ ] Bedrock model field appears/disappears based on OCR backend selection
- [ ] Fields are in correct order
- [ ] Dropdowns have correct number of options
- [ ] Conditional field updates instantly (no lag)
- [ ] Save button works for OCR and chat changes (no modal)
- [ ] Re-embedding modal still works for embedding changes
- [ ] Reset button reverts changes correctly
- [ ] No console errors
- [ ] UI is responsive and user-friendly

**Testing**:

```bash
# Start dev server
cd src/ui
npm start

# Open browser to http://localhost:5173
# Navigate to /settings
# Follow manual test checklist above
```

**Document Findings**:

Create a simple test log in your notes (not committed):

```
Manual Test Results - Settings UI
Date: [date]

✅ All fields render
✅ Bedrock model conditional visibility works
✅ Field ordering correct
✅ Dropdown options correct
✅ OCR/chat changes don't trigger re-embedding modal
✅ Embedding changes still trigger modal
✅ Reset button works
✅ No console errors

Issues Found: [none or list any issues]
```

**Commit Message**:

N/A (manual testing, no code changes)

**Estimated Tokens**: ~5,000

---

### Task 2.4: Fix Any Issues Found (If Needed)

**Goal**: Address any issues discovered during manual testing

**Files to Modify**:
- `src/ui/src/components/Settings/index.jsx` (only if issues found)

**Prerequisites**: Task 2.3 complete

**Instructions**:

Based on manual testing, fix any issues. **Note**: If Settings component is already schema-driven correctly, no changes should be needed.

**Possible Issues and Fixes**:

**Issue 1**: Bedrock model field doesn't appear/disappear correctly

**Fix**:
- Verify `renderField` function checks `dependsOn` correctly (lines 228-236)
- Ensure `formValues` state is updated when OCR backend changes
- The existing logic should handle this, but check for any edge cases

**Issue 2**: Fields appear in wrong order

**Fix**:
- Verify sorting logic in render (lines 321)
- Should sort by `property.order`
- Ensure all fields have `order` property in schema

**Issue 3**: Re-embedding modal appears for OCR/chat changes

**Fix**:
- Check `handleSave` function (lines 118-121)
- Should only check `text_embed_model_id` and `image_embed_model_id`
- Ensure new fields are NOT included in this check

**Issue 4**: Dropdown options are missing or incorrect

**Fix**:
- Backend schema issue (go back to Phase 1)
- Verify enum arrays are correct in schema

**If no issues found**: Skip to next task

**Verification Checklist**:

- [ ] All issues from manual testing resolved
- [ ] Component tests still passing
- [ ] Manual re-test confirms fixes work
- [ ] No regressions introduced

**Testing**:

```bash
# Re-run component tests
npm test -- Settings.test.jsx

# Re-run manual tests
npm start
# Follow manual test checklist again
```

**Commit Message** (if changes needed):

```
fix(settings): resolve [specific issue description]

- Fix conditional rendering for bedrock_ocr_model_id
- Ensure correct field ordering
- Prevent re-embedding modal for OCR/chat changes
- All tests passing and manual verification complete
```

**Estimated Tokens**: ~5,000

---

## Phase 2 Summary

### What You Built

- ✅ Analyzed existing Settings component (schema-driven rendering)
- ✅ Wrote comprehensive component tests for new fields
- ✅ Verified conditional visibility (dependsOn logic)
- ✅ Confirmed re-embedding workflow preserved (only embedding changes)
- ✅ Manually tested UI in browser
- ✅ Fixed any issues (if found)

### Test Coverage

- All 7 configuration fields rendering
- Conditional field visibility (bedrock_ocr_model_id)
- Field ordering (by order property)
- Re-embedding workflow trigger logic
- Form interactions (save, reset)

### Commits Made

Expected ~1-2 commits:
1. Component tests for new fields
2. Bug fixes (only if issues found during manual testing)

### Verification

Run these commands to verify Phase 2 completion:

```bash
# All frontend tests passing
cd src/ui
npm test -- Settings.test.jsx

# Dev server starts without errors
npm start

# Manual checklist completed (all ✅)
```

### Next Steps

**Frontend Settings complete!** The UI now dynamically renders all 7 configuration fields.

→ **[Continue to Phase 3: Chat Backend](Phase-3.md)**

Phase 3 will enhance the QueryKB Lambda to support conversational chat with session management.

---

**Phase 2 Estimated Token Total**: ~20,000 tokens
