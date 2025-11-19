/**
 * SourcesToggle Component Tests
 *
 * Comprehensive test suite covering:
 * - Default collapsed state
 * - Expand/collapse interaction
 * - SessionStorage persistence
 * - Error handling
 * - Empty sources
 * - Keyboard accessibility
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SourcesToggle } from '../SourcesToggle';
import type { Source } from '../../types';

// Mock SourcesDisplay component
vi.mock('../SourcesDisplay', () => ({
  SourcesDisplay: ({ sources }: { sources: Source[] }) => (
    <div data-testid="sources-display">
      {sources.map((source, idx) => (
        <div key={idx}>{source.title}</div>
      ))}
    </div>
  ),
}));

describe('SourcesToggle', () => {
  const mockSources: Source[] = [
    {
      title: 'Document 1.pdf',
      location: 'Page 1',
      snippet: 'Test snippet 1',
    },
    {
      title: 'Document 2.pdf',
      location: 'Page 2',
      snippet: 'Test snippet 2',
    },
  ];

  beforeEach(() => {
    // Clear sessionStorage before each test
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders collapsed by default', () => {
      render(<SourcesToggle sources={mockSources} />);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-expanded', 'false');
      expect(button).toHaveTextContent('Show');
      expect(screen.queryByTestId('sources-display')).not.toBeInTheDocument();
    });

    it('renders with correct source count', () => {
      render(<SourcesToggle sources={mockSources} />);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('Sources (2)');
    });

    it('renders expanded when defaultExpanded is true', () => {
      render(<SourcesToggle sources={mockSources} defaultExpanded={true} />);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-expanded', 'true');
      expect(button).toHaveTextContent('Hide');
      expect(screen.getByTestId('sources-display')).toBeInTheDocument();
    });

    it('returns null when sources array is empty', () => {
      const { container } = render(<SourcesToggle sources={[]} />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null when sources is undefined', () => {
      const { container } = render(<SourcesToggle sources={undefined as any} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('Interaction', () => {
    it('expands when button clicked', () => {
      render(<SourcesToggle sources={mockSources} />);

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(button).toHaveAttribute('aria-expanded', 'true');
      expect(button).toHaveTextContent('Hide');
      expect(screen.getByTestId('sources-display')).toBeInTheDocument();
    });

    it('collapses when button clicked twice', () => {
      render(<SourcesToggle sources={mockSources} />);

      const button = screen.getByRole('button');

      // Expand
      fireEvent.click(button);
      expect(screen.getByTestId('sources-display')).toBeInTheDocument();

      // Collapse
      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-expanded', 'false');
      expect(screen.queryByTestId('sources-display')).not.toBeInTheDocument();
    });

    it('calls onToggle callback when toggled', () => {
      const onToggle = vi.fn();
      render(<SourcesToggle sources={mockSources} onToggle={onToggle} />);

      const button = screen.getByRole('button');

      // Expand
      fireEvent.click(button);
      expect(onToggle).toHaveBeenCalledWith(true);

      // Collapse
      fireEvent.click(button);
      expect(onToggle).toHaveBeenCalledWith(false);
    });
  });

  describe('SessionStorage Persistence', () => {
    it('persists expanded state to sessionStorage', () => {
      render(<SourcesToggle sources={mockSources} />);

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(sessionStorage.getItem('amplify-chat-sources-expanded')).toBe('true');
    });

    it('persists collapsed state to sessionStorage', () => {
      render(<SourcesToggle sources={mockSources} defaultExpanded={true} />);

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(sessionStorage.getItem('amplify-chat-sources-expanded')).toBe('false');
    });

    it('restores state from sessionStorage', () => {
      sessionStorage.setItem('amplify-chat-sources-expanded', 'true');

      render(<SourcesToggle sources={mockSources} />);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-expanded', 'true');
      expect(screen.getByTestId('sources-display')).toBeInTheDocument();
    });

    it('handles sessionStorage errors gracefully when reading', () => {
      // Mock sessionStorage.getItem to throw error
      const originalGetItem = sessionStorage.getItem;

      try {
        sessionStorage.getItem = vi.fn(() => {
          throw new Error('Storage error');
        });

        // Should not crash, should use defaultExpanded
        const { container } = render(<SourcesToggle sources={mockSources} defaultExpanded={true} />);
        expect(container.firstChild).toBeTruthy();
      } finally {
        // Always restore, even if assertions fail
        sessionStorage.getItem = originalGetItem;
      }
    });

    it('handles sessionStorage errors gracefully when writing', () => {
      // Mock sessionStorage.setItem to throw error
      const originalSetItem = sessionStorage.setItem;

      try {
        sessionStorage.setItem = vi.fn(() => {
          throw new Error('Quota exceeded');
        });

        render(<SourcesToggle sources={mockSources} />);

        const button = screen.getByRole('button');

        // Should not crash when clicking
        expect(() => fireEvent.click(button)).not.toThrow();
        expect(button).toHaveAttribute('aria-expanded', 'true');
      } finally {
        // Always restore, even if assertions fail
        sessionStorage.setItem = originalSetItem;
      }
    });
  });

  describe('Accessibility', () => {
    it('has correct aria-label for collapsed state', () => {
      render(<SourcesToggle sources={mockSources} />);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Show 2 sources');
    });

    it('has correct aria-label for expanded state', () => {
      render(<SourcesToggle sources={mockSources} defaultExpanded={true} />);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Hide 2 sources');
    });

    it('has correct aria-label for single source', () => {
      const singleSource: Source[] = [mockSources[0]];
      render(<SourcesToggle sources={singleSource} />);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Show 1 source');
    });

    it('updates aria-label when toggled', () => {
      render(<SourcesToggle sources={mockSources} />);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Show 2 sources');

      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-label', 'Hide 2 sources');
    });

    it('is keyboard accessible with Enter key', () => {
      render(<SourcesToggle sources={mockSources} />);

      const button = screen.getByRole('button');
      fireEvent.keyDown(button, { key: 'Enter', code: 'Enter' });

      // Button click should be triggered by Enter (browser default behavior)
      // We're just verifying the button is focusable and semantic
      expect(button.tagName).toBe('BUTTON');
      expect(button).toHaveAttribute('type', 'button');
    });
  });

  // Note: Memoization behavior is tested implicitly through observable behavior tests.
  // DOM node identity tests don't prove React.memo works since React preserves
  // nodes even without memoization in many cases.
});
