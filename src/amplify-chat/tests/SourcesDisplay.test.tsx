/**
 * Tests for SourcesDisplay component
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SourcesDisplay } from '../src/components/SourcesDisplay';
import { Source } from '../src/types';

describe('SourcesDisplay Component', () => {
  it('renders nothing when sources array is empty', () => {
    const { container } = render(<SourcesDisplay sources={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when sources is undefined', () => {
    const { container } = render(
      <SourcesDisplay sources={undefined as any} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders sources header with correct count', () => {
    const sources: Source[] = [
      {
        title: 'document1.pdf',
        location: 'Page 1',
        snippet: 'This is a snippet',
      },
      {
        title: 'document2.pdf',
        location: 'Page 2',
        snippet: 'Another snippet',
      },
    ];

    render(<SourcesDisplay sources={sources} />);

    expect(screen.getByText(/Sources/i)).toBeInTheDocument();
    expect(screen.getByText('(2)')).toBeInTheDocument();
  });

  it('displays source title for each source', () => {
    const sources: Source[] = [
      {
        title: 'README.md',
        location: 'Page 1',
        snippet: 'Documentation content',
      },
      {
        title: 'API.md',
        location: 'Page 5',
        snippet: 'API documentation',
      },
    ];

    render(<SourcesDisplay sources={sources} />);

    expect(screen.getByText('README.md')).toBeInTheDocument();
    expect(screen.getByText('API.md')).toBeInTheDocument();
  });

  it('displays source location when provided', () => {
    const sources: Source[] = [
      {
        title: 'doc.pdf',
        location: 'Page 3',
        snippet: 'Some text',
      },
    ];

    render(<SourcesDisplay sources={sources} />);

    expect(screen.getByText(/Page 3/)).toBeInTheDocument();
  });

  it('displays source snippet when provided', () => {
    const sources: Source[] = [
      {
        title: 'doc.pdf',
        location: 'Page 1',
        snippet: 'This is the actual snippet from the document',
      },
    ];

    render(<SourcesDisplay sources={sources} />);

    expect(
      screen.getByText(/This is the actual snippet from the document/)
    ).toBeInTheDocument();
  });

  it('handles multiple sources correctly', () => {
    const sources: Source[] = [
      {
        title: 'file1.txt',
        location: 'Location 1',
        snippet: 'Snippet 1',
      },
      {
        title: 'file2.txt',
        location: 'Location 2',
        snippet: 'Snippet 2',
      },
      {
        title: 'file3.txt',
        location: 'Location 3',
        snippet: 'Snippet 3',
      },
    ];

    render(<SourcesDisplay sources={sources} />);

    expect(screen.getByText('(3)')).toBeInTheDocument();
    expect(screen.getByText('file1.txt')).toBeInTheDocument();
    expect(screen.getByText('file2.txt')).toBeInTheDocument();
    expect(screen.getByText('file3.txt')).toBeInTheDocument();
  });

  it('applies custom className when provided', () => {
    const sources: Source[] = [
      {
        title: 'doc.pdf',
        location: 'Page 1',
        snippet: 'Text',
      },
    ];

    const { container } = render(
      <SourcesDisplay sources={sources} className="custom-class" />
    );

    const sourcesContainer = container.querySelector('.custom-class');
    expect(sourcesContainer).toBeInTheDocument();
  });

  it('renders source items with proper structure', () => {
    const sources: Source[] = [
      {
        title: 'document.pdf',
        location: 'Page 5',
        snippet: 'Example content here',
      },
    ];

    const { container } = render(<SourcesDisplay sources={sources} />);

    const sourceItems = container.querySelectorAll('[class*="sourceItem"]');
    expect(sourceItems.length).toBeGreaterThan(0);
  });

  it('handles sources with empty snippets', () => {
    const sources: Source[] = [
      {
        title: 'doc.pdf',
        location: 'Page 1',
        snippet: '',
      },
    ];

    render(<SourcesDisplay sources={sources} />);

    expect(screen.getByText('doc.pdf')).toBeInTheDocument();
    expect(screen.getByText(/Page 1/)).toBeInTheDocument();
  });
});
