/**
 * Frontend Performance Benchmarks for SourcesToggle Component
 *
 * Tests rendering performance and interaction speed.
 * Target: < 16ms per frame (60 FPS)
 *
 * Run with:
 *   cd src/amplify-chat && npm run bench
 */

import { describe, bench, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { fireEvent } from '@testing-library/dom';
import { SourcesToggle } from '../../SourcesToggle';
import type { Source } from '../../../types';

// Generate test data
const generateSources = (count: number): Source[] =>
  Array.from({ length: count }, (_, i) => ({
    title: `Document ${i + 1}.pdf`,
    location: `chunk-${String(i + 1).padStart(3, '0')}`,
    snippet: `This is sample content from document ${i + 1}. `.repeat(10).substring(0, 200),
    documentUrl: `https://s3.amazonaws.com/bucket/doc-${i + 1}.pdf?presigned=xyz`,
    documentAccessAllowed: true,
  }));

describe('SourcesToggle Rendering Performance', () => {
  bench('Render with 3 sources (typical)', () => {
    const sources = generateSources(3);
    render(<SourcesToggle sources={sources} />);
  });

  bench('Render with 10 sources (large)', () => {
    const sources = generateSources(10);
    render(<SourcesToggle sources={sources} />);
  });

  bench('Render with 20 sources (stress test)', () => {
    const sources = generateSources(20);
    render(<SourcesToggle sources={sources} />);
  });

  bench('Render collapsed (default)', () => {
    const sources = generateSources(5);
    render(<SourcesToggle sources={sources} />);
  });

  bench('Render expanded', () => {
    const sources = generateSources(5);
    render(<SourcesToggle sources={sources} defaultExpanded={true} />);
  });
});

describe('SourcesToggle Interaction Performance', () => {
  bench('Toggle expand', () => {
    const sources = generateSources(5);
    const { getByRole } = render(<SourcesToggle sources={sources} />);

    const button = getByRole('button');
    fireEvent.click(button);
  });

  bench('Toggle expand and collapse', () => {
    const sources = generateSources(5);
    const { getByRole } = render(<SourcesToggle sources={sources} />);

    const button = getByRole('button');
    fireEvent.click(button); // Expand
    fireEvent.click(button); // Collapse
  });

  bench('Multiple rapid toggles (10x)', () => {
    const sources = generateSources(5);
    const { getByRole } = render(<SourcesToggle sources={sources} />);

    const button = getByRole('button');
    for (let i = 0; i < 10; i++) {
      fireEvent.click(button);
    }
  });
});

describe('SessionStorage Performance', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  bench('Read from sessionStorage', () => {
    sessionStorage.setItem('amplify-chat-sources-expanded', 'true');
    const sources = generateSources(5);
    render(<SourcesToggle sources={sources} />);
  });

  bench('Write to sessionStorage on toggle', () => {
    const sources = generateSources(5);
    const { getByRole } = render(<SourcesToggle sources={sources} />);

    const button = getByRole('button');
    fireEvent.click(button); // Triggers sessionStorage.setItem
  });
});

describe('Memoization Performance', () => {
  bench('Re-render with same props (should be fast due to React.memo)', () => {
    const sources = generateSources(5);
    const { rerender } = render(<SourcesToggle sources={sources} />);

    // Re-render with same props
    rerender(<SourcesToggle sources={sources} />);
  });

  bench('Re-render with different props (should re-render)', () => {
    const sources1 = generateSources(5);
    const sources2 = generateSources(5);
    const { rerender } = render(<SourcesToggle sources={sources1} />);

    // Re-render with different sources array
    rerender(<SourcesToggle sources={sources2} />);
  });
});

/**
 * Performance Targets:
 *
 * - Render with 10 sources: < 16ms (60 FPS)
 * - Toggle expand/collapse: < 16ms (60 FPS)
 * - SessionStorage operations: < 5ms
 * - Re-render with same props (memoized): < 1ms
 *
 * If benchmarks fail to meet targets:
 * - Consider virtualization for large source lists
 * - Lazy load sources (render on expand)
 * - Optimize sessionStorage reads (debounce writes)
 */
