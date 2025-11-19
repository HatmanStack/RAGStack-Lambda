# Phase 2: Frontend Implementation

## Phase Goal

Implement user-facing components for collapsible sources and document access. This includes creating a new `SourcesToggle` component that wraps sources in an expandable/collapsible container, updating individual source items to display document links when available, adding admin UI controls for the configuration toggle, and ensuring full accessibility compliance.

**Success Criteria:**
- ✅ Sources are collapsed by default in chat interface
- ✅ Users can expand/collapse sources with smooth animation
- ✅ Document links appear when `documentUrl` is present
- ✅ Clicking document link opens original file in new tab
- ✅ Admin can toggle `chat_allow_document_access` via web UI
- ✅ All UI is keyboard accessible and screen reader compatible

**Estimated tokens:** ~70,000

---

## Prerequisites

**Completed:**
- Phase 0 (Foundation) read and understood
- Phase 1 (Backend) complete and deployed to test environment

**Backend API Contract Verified:**
- Conversation query returns sources with `documentUrl` and `documentAccessAllowed` fields
- Configuration can be read and updated via GraphQL
- Presigned URLs successfully generated and downloadable

**Environment Requirements:**
- React 19 development environment
- Access to test deployment with backend changes
- Ability to test with screen readers (NVDA, VoiceOver, or JAWS)

---

## Tasks

### Task 1: Create SourcesToggle Component

**Goal:** Build collapsible wrapper component that shows/hides sources on user interaction

**Files to Create:**
- `src/amplify-chat/src/components/SourcesToggle.tsx` - Main component
- `src/amplify-chat/src/components/SourcesToggle.test.tsx` - Component tests
- `src/amplify-chat/src/components/SourcesToggle.module.css` - Component styles

**Prerequisites:**
- Read existing `SourcesDisplay.tsx` to understand current pattern
- Understand React hooks (`useState`, `useEffect`)
- Review sessionStorage API for persistence

**Implementation Steps:**

1. **Create Component File Structure**
   - Create new component file with TypeScript interface for props
   - Props should include:
     - `sources: Source[]` (array of source objects)
     - `defaultExpanded?: boolean` (optional, defaults to false)
     - `onToggle?: (expanded: boolean) => void` (optional callback)

2. **Implement State Management**
   - Use `useState` to track collapsed/expanded state
   - Initialize from `defaultExpanded` prop OR sessionStorage
   - Storage key should be namespaced: `'amplify-chat-sources-expanded'`

3. **Implement SessionStorage Persistence**
   - On mount: try to read from sessionStorage, fall back to `defaultExpanded`
   - On state change: save to sessionStorage (wrap in try/catch for errors)
   - Handle environments without sessionStorage (SSR, private browsing)

4. **Implement Toggle Handler**
   - On button click: toggle state
   - Save to sessionStorage
   - Call `onToggle` callback if provided
   - Log toggle event at debug level

5. **Render Collapsed State**
   - Show button with icon and source count
   - Format: `📄 Sources (N) [Show ▶]`
   - Button should be semantic HTML `<button>` element
   - Include ARIA attributes: `aria-expanded={false}`

6. **Render Expanded State**
   - Show same button with different text: `📄 Sources (N) [Hide ▼]`
   - Below button: render list of sources using existing `SourcesDisplay` component
   - Include ARIA attributes: `aria-expanded={true}`

7. **Handle Empty Sources**
   - If `sources.length === 0`, return `null` (don't render anything)
   - This matches existing `SourcesDisplay` behavior

**Verification Checklist:**
- [ ] Component renders correctly with sources
- [ ] Default state is collapsed
- [ ] Clicking button toggles state
- [ ] State persists across component re-renders
- [ ] sessionStorage errors don't crash component
- [ ] Empty sources array returns null
- [ ] Component is exported and importable

**Testing Instructions:**

Create comprehensive test suite:

```typescript
describe('SourcesToggle', () => {
  it('renders collapsed by default', () => {
    // Render component
    // Verify "Show" text visible
    // Verify sources not rendered
  });

  it('expands when button clicked', async () => {
    // Render component
    // Click button
    // Verify "Hide" text visible
    // Verify sources rendered
  });

  it('persists state to sessionStorage', async () => {
    // Render component
    // Click button (expand)
    // Verify sessionStorage.setItem called
  });

  it('restores state from sessionStorage', () => {
    // Mock sessionStorage with expanded=true
    // Render component
    // Verify component starts expanded
  });

  it('handles sessionStorage errors gracefully', () => {
    // Mock sessionStorage.setItem to throw error
    // Click button
    // Verify component doesn't crash
  });

  it('returns null when sources empty', () => {
    // Render with sources=[]
    // Verify nothing rendered
  });
});
```

Run tests:
```bash
cd src/amplify-chat && npm test -- SourcesToggle.test.tsx
```

**Commit Message Template:**
```
feat(frontend): add collapsible SourcesToggle component

- Create wrapper component for expandable/collapsible sources
- Default to collapsed state (cleaner UI)
- Persist expand/collapse state in sessionStorage
- Render sources using existing SourcesDisplay component
- Handle empty sources and storage errors gracefully
- Add comprehensive test coverage
```

**Estimated tokens:** ~18,000

---

### Task 2: Update SourceItem to Display Document Links

**Goal:** Modify individual source items to show "View Document" link when `documentUrl` is present

**Files to Modify:**
- `src/amplify-chat/src/components/SourcesDisplay.tsx` - Update source rendering
- `src/amplify-chat/src/types.ts` - Update `Source` interface

**Prerequisites:**
- Task 1 complete (SourcesToggle exists)
- Backend returns sources with `documentUrl` and `documentAccessAllowed` fields

**Implementation Steps:**

1. **Update Source Interface**
   - Open `src/amplify-chat/src/types.ts`
   - Locate `Source` interface
   - Add two optional fields:
     ```typescript
     documentUrl?: string | null;
     documentAccessAllowed?: boolean;
     ```

2. **Update Source Item Rendering**
   - Locate source item map in `SourcesDisplay.tsx`
   - After snippet rendering, add conditional document link

3. **Render Document Link (When Available)**
   - Check if `source.documentUrl` exists and is not null
   - Render link as:
     ```tsx
     <a
       href={source.documentUrl}
       target="_blank"
       rel="noopener noreferrer"
       className={styles.documentLink}
     >
       View Document →
     </a>
     ```
   - `target="_blank"`: Opens in new tab
   - `rel="noopener noreferrer"`: Security best practice

4. **Render Disabled State (When Not Available)**
   - Check if `source.documentAccessAllowed === false`
   - Render disabled state:
     ```tsx
     <span className={styles.documentLinkDisabled}>
       Document access disabled
     </span>
     ```
   - Only show this if admin has explicitly disabled access
   - Don't show anything if feature not configured

5. **Add Visual Affordances**
   - Document link should have distinct styling (underline, color, hover state)
   - Disabled state should appear greyed out
   - Include icon or arrow to indicate external link

**Verification Checklist:**
- [ ] `Source` interface includes new optional fields
- [ ] Document link appears when `documentUrl` present
- [ ] Link opens in new tab with security attributes
- [ ] Disabled state appears when access explicitly disabled
- [ ] No errors when fields are undefined
- [ ] Link is keyboard accessible (Tab, Enter)

**Testing Instructions:**

Update existing `SourcesDisplay.test.tsx`:

```typescript
describe('SourcesDisplay with document links', () => {
  it('renders document link when URL present', () => {
    const sources = [{
      title: 'test.pdf',
      location: 'Page 1',
      snippet: 'Test snippet',
      documentUrl: 'https://example.com/test.pdf',
      documentAccessAllowed: true
    }];

    render(<SourcesDisplay sources={sources} />);

    const link = screen.getByText('View Document →');
    expect(link).toHaveAttribute('href', 'https://example.com/test.pdf');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('shows disabled state when access disabled', () => {
    const sources = [{
      title: 'test.pdf',
      location: 'Page 1',
      snippet: 'Test snippet',
      documentUrl: null,
      documentAccessAllowed: false
    }];

    render(<SourcesDisplay sources={sources} />);

    expect(screen.getByText('Document access disabled')).toBeInTheDocument();
  });

  it('handles missing documentUrl gracefully', () => {
    const sources = [{
      title: 'test.pdf',
      location: 'Page 1',
      snippet: 'Test snippet'
      // documentUrl and documentAccessAllowed not present
    }];

    render(<SourcesDisplay sources={sources} />);

    // Should not crash, should not show link or disabled state
    expect(screen.queryByText('View Document')).not.toBeInTheDocument();
  });
});
```

**Commit Message Template:**
```
feat(frontend): add document download links to source items

- Update Source interface with documentUrl and documentAccessAllowed
- Render "View Document" link when URL is available
- Open links in new tab with security attributes
- Show disabled state when access explicitly disabled
- Handle missing fields gracefully (backward compatibility)
```

**Estimated tokens:** ~15,000

---

### Task 3: Add CSS Styling and Animations

**Goal:** Style the collapsible sources toggle and document links with smooth animations

**Files to Create/Modify:**
- `src/amplify-chat/src/components/SourcesToggle.module.css` - New styles
- `src/amplify-chat/src/styles/ChatWithSources.module.css` - Update existing styles

**Prerequisites:**
- Tasks 1-2 complete (components render)
- Understanding of CSS transitions and animations
- Awareness of `prefers-reduced-motion` media query

**Implementation Steps:**

1. **Style Toggle Button**
   - Create button styles in `SourcesToggle.module.css`
   - Button should be full-width or left-aligned
   - Include hover, focus, and active states
   - Use existing CSS custom properties for colors
   - Ensure focus indicator is visible (accessibility)

2. **Style Collapsible Content**
   - Create container styles for sources list
   - Add CSS transition for smooth expand/collapse:
     ```css
     .sourcesList {
       overflow: hidden;
       transition: max-height 0.3s ease-out, opacity 0.2s ease-out;
     }
     ```
   - Use `max-height` trick for animating height of dynamic content

3. **Add Animation States**
   - Collapsed state: `max-height: 0; opacity: 0;`
   - Expanded state: `max-height: 2000px; opacity: 1;` (generous max-height)
   - Transition properties: `max-height 0.3s ease-out, opacity 0.2s ease-out`

4. **Style Document Link**
   - Add styles in `ChatWithSources.module.css`
   - Link should be clearly clickable (color, underline, hover state)
   - Include right arrow icon (→) or external link icon
   - Hover state should be visually distinct
   - Example:
     ```css
     .documentLink {
       color: var(--chat-color-source-accent);
       text-decoration: underline;
       font-size: 0.9rem;
       display: inline-block;
       margin-top: 8px;
     }
     .documentLink:hover {
       color: var(--chat-color-user-bg);
       text-decoration: none;
     }
     ```

5. **Style Disabled State**
   - Greyed out appearance
   - No pointer cursor
   - Clearly indicates unavailability
   - Example:
     ```css
     .documentLinkDisabled {
       color: var(--chat-color-text-secondary);
       font-size: 0.85rem;
       font-style: italic;
       margin-top: 8px;
     }
     ```

6. **Respect Reduced Motion Preference**
   - Add media query to disable animations for users who prefer reduced motion:
     ```css
     @media (prefers-reduced-motion: reduce) {
       .sourcesList {
         transition: none;
       }
     }
     ```

7. **Test Responsiveness**
   - Ensure styles work on mobile (touch targets ≥ 44px)
   - Test on tablet and desktop
   - Verify no horizontal overflow

**Verification Checklist:**
- [ ] Toggle button has clear visual states (normal, hover, focus, active)
- [ ] Expand/collapse animation is smooth (0.3s transition)
- [ ] Document link is clearly clickable
- [ ] Disabled state is visually distinct
- [ ] Animations respect `prefers-reduced-motion`
- [ ] Responsive on all screen sizes
- [ ] Focus indicators are visible

**Testing Instructions:**

Manual testing checklist:
1. Click toggle button → verify smooth animation
2. Hover over document link → verify hover state
3. Click document link → verify new tab opens
4. Enable "Reduce motion" in OS settings → verify animations disabled
5. Test on mobile device → verify touch targets ≥ 44px
6. Use keyboard Tab → verify focus indicators visible

**Commit Message Template:**
```
style(frontend): add styling and animations for collapsible sources

- Style toggle button with hover, focus, and active states
- Add smooth expand/collapse animation (0.3s ease-out)
- Style document links with clear clickable appearance
- Add disabled state styling for unavailable documents
- Respect prefers-reduced-motion accessibility setting
- Ensure responsive design on all screen sizes
```

**Estimated tokens:** ~12,000

---

### Task 4: Add Admin UI Configuration Toggle

**Goal:** Add toggle control in admin web UI to enable/disable document access

**Files to Modify:**
- `src/ui/src/pages/Configuration.tsx` - Add new toggle control
- `src/ui/src/graphql/mutations.ts` - May need update (verify mutation supports new field)

**Prerequisites:**
- Admin UI currently supports configuration management
- GraphQL mutation `updateConfiguration` exists
- Backend accepts `chat_allow_document_access` in configuration

**Implementation Steps:**

1. **Locate Configuration Component**
   - Open `src/ui/src/pages/Configuration.tsx`
   - Find where chat configuration options are rendered
   - Identify pattern used by existing toggles (e.g., `chat_require_auth`)

2. **Add Toggle Control**
   - Add new toggle in the chat configuration section
   - Use same UI component as existing chat toggles
   - Label: "Allow Document Access"
   - Description: "Enable users to download original source documents via presigned URLs"
   - Bind to `config.chat_allow_document_access` value

3. **Implement Toggle Handler**
   - On toggle change: call GraphQL mutation to update configuration
   - Mutation should update `chat_allow_document_access` field
   - Show loading state during mutation
   - Show success/error notification after mutation completes

4. **Add Help Text**
   - Include informative description below toggle
   - Explain: "When enabled, chat users can download the original documents that were used as sources for AI responses. Presigned URLs expire after 1 hour."
   - Add security note: "Only enable if users should have access to source documents."

5. **Test Configuration Flow**
   - Verify toggle reflects current value from backend
   - Verify toggling sends correct mutation
   - Verify changes propagate to chat (within 60s due to cache)
   - Test both enabling and disabling

**Verification Checklist:**
- [ ] Toggle appears in admin UI configuration page
- [ ] Toggle reflects current backend configuration
- [ ] Clicking toggle updates backend via GraphQL mutation
- [ ] Loading state shows during update
- [ ] Success notification appears on successful update
- [ ] Error notification appears on failed update
- [ ] Help text clearly explains feature and security implications

**Testing Instructions:**

Manual testing flow:
1. Open admin UI → Configuration page
2. Locate "Allow Document Access" toggle
3. Toggle ON → verify mutation sent, success shown
4. Open chat → send query → verify document links appear
5. Toggle OFF → verify mutation sent
6. Open chat → send query → verify document links hidden
7. Test error case (disconnect network) → verify error shown

**Commit Message Template:**
```
feat(admin-ui): add configuration toggle for document access

- Add "Allow Document Access" toggle in Configuration page
- Wire up to chat_allow_document_access GraphQL field
- Show loading state during mutation
- Display success/error notifications
- Include help text explaining feature and security
```

**Estimated tokens:** ~15,000

---

### Task 5: Accessibility and Keyboard Navigation

**Goal:** Ensure all new UI components are fully accessible to keyboard users and screen readers

**Files to Modify:**
- `src/amplify-chat/src/components/SourcesToggle.tsx` - Add ARIA attributes
- `src/amplify-chat/src/components/SourcesDisplay.tsx` - Update link accessibility

**Prerequisites:**
- Tasks 1-4 complete (all components exist)
- Access to screen reader for testing (NVDA, VoiceOver, or JAWS)
- Understanding of ARIA attributes and keyboard navigation

**Implementation Steps:**

1. **Toggle Button Accessibility**
   - Ensure button is semantic `<button>` element (not div)
   - Add `aria-expanded` attribute reflecting current state
   - Add `aria-label` with descriptive text including count
   - Example:
     ```tsx
     <button
       onClick={handleToggle}
       aria-expanded={expanded}
       aria-label={`${expanded ? 'Hide' : 'Show'} ${sources.length} source${sources.length === 1 ? '' : 's'}`}
     >
       {/* Visual content */}
     </button>
     ```

2. **Keyboard Navigation**
   - Verify button is focusable via Tab key
   - Verify button activates with Enter or Space key
   - Verify focus indicator is visible (from CSS)
   - Test Tab order flows logically through sources

3. **Document Link Accessibility**
   - Links should be semantic `<a>` elements
   - Add `aria-label` if text isn't self-describing
   - Example:
     ```tsx
     <a
       href={source.documentUrl}
       target="_blank"
       rel="noopener noreferrer"
       aria-label={`View source document: ${source.title}`}
     >
       View Document →
     </a>
     ```

4. **Screen Reader Announcements**
   - When sources expand/collapse, consider adding `aria-live` region
   - Announce state changes to screen reader users
   - Example:
     ```tsx
     <div
       aria-live="polite"
       aria-atomic="true"
       className="sr-only"
     >
       {expanded ? 'Sources expanded' : 'Sources collapsed'}
     </div>
     ```

5. **Focus Management**
   - When expanding sources, consider moving focus to first source
   - When collapsing, return focus to toggle button
   - Use `useRef` and `.focus()` method

6. **Color Contrast**
   - Verify all text meets WCAG AA standards (4.5:1 for normal text)
   - Use contrast checker tool
   - Test in dark mode if applicable

**Verification Checklist:**
- [ ] All interactive elements are keyboard accessible
- [ ] Tab order is logical
- [ ] Focus indicators are visible
- [ ] Screen reader announces state changes
- [ ] ARIA attributes are correct
- [ ] Color contrast meets WCAG AA
- [ ] Works with screen reader (NVDA/VoiceOver/JAWS)

**Testing Instructions:**

**Keyboard Testing:**
1. Use only keyboard (no mouse)
2. Tab to toggle button → verify focus visible
3. Press Enter → verify sources expand
4. Tab through sources → verify can reach document links
5. Press Enter on document link → verify opens in new tab
6. Shift+Tab back through elements → verify reverse order works

**Screen Reader Testing:**
1. Enable screen reader (NVDA on Windows, VoiceOver on Mac)
2. Navigate to chat component
3. Locate toggle button → verify announces correctly
4. Activate toggle → verify state change announced
5. Navigate to document link → verify title announced
6. Activate link → verify new tab opened

**Commit Message Template:**
```
a11y(frontend): ensure collapsible sources are fully accessible

- Add aria-expanded attribute to toggle button
- Add aria-labels with descriptive text
- Implement keyboard navigation (Enter, Space)
- Add screen reader announcements for state changes
- Verify color contrast meets WCAG AA
- Test with screen readers (NVDA, VoiceOver)
```

**Estimated tokens:** ~10,000

---

## Phase Verification

**Before proceeding to Phase 3, verify:**

### Functional Requirements
- [ ] Sources are collapsed by default in chat interface
- [ ] Users can expand/collapse sources with button click
- [ ] Expand/collapse state persists across re-renders (sessionStorage)
- [ ] Document links appear when backend provides `documentUrl`
- [ ] Clicking document link downloads original file
- [ ] Admin can toggle document access in web UI
- [ ] Configuration changes propagate to chat (within 60s)

### Code Quality
- [ ] All React components use TypeScript with proper interfaces
- [ ] All components have unit tests with > 80% coverage
- [ ] CSS uses existing custom properties (no hardcoded colors)
- [ ] No console errors or warnings
- [ ] Components are properly memoized where needed
- [ ] Code follows existing patterns in codebase

### Accessibility
- [ ] All interactive elements are keyboard accessible
- [ ] Tab order is logical
- [ ] Focus indicators are visible
- [ ] Screen reader announces all important state changes
- [ ] Color contrast meets WCAG AA
- [ ] Works with NVDA, VoiceOver, or JAWS

### Visual Design
- [ ] Expand/collapse animation is smooth (0.3s)
- [ ] Animation respects `prefers-reduced-motion`
- [ ] Document links have clear hover states
- [ ] Disabled state is visually distinct
- [ ] Responsive on mobile, tablet, desktop
- [ ] Consistent with existing chat UI design

### Browser Compatibility
- [ ] Works in Chrome
- [ ] Works in Firefox
- [ ] Works in Safari
- [ ] Works in Edge
- [ ] No IE11 support required (modern browsers only)

---

## Integration Points for Phase 3

**Phase 3 (Testing) will verify:**

1. **End-to-End User Flows:**
   - User uploads document → asks question → sees sources → downloads document
   - Admin toggles configuration → user sees/doesn't see document links
   - Document URL expires → user sees error (expected behavior)

2. **Edge Cases:**
   - Empty sources array
   - Missing documentUrl field
   - Malformed presigned URL
   - SessionStorage disabled/full
   - Network errors during configuration update

3. **Performance:**
   - Rendering 10+ sources doesn't lag
   - Expand/collapse animation is smooth
   - No memory leaks on repeated toggle

---

## Known Limitations & Future Enhancements

**Current Limitations:**
- No inline document preview (opens in new tab)
- No page-level highlighting in PDFs
- Session state lost if user clears browsing data
- Animation disabled for users with `prefers-reduced-motion`

**Future Enhancements:**
- PDF preview modal with inline viewer
- Deep linking to specific pages (#page=N)
- Recent documents cache to avoid re-downloading
- Analytics on document access patterns
- Custom animation timing preferences

---

**Estimated tokens for Phase 2:** ~70,000

**Next:** [Phase 3: Testing & Integration](./Phase-3.md)
