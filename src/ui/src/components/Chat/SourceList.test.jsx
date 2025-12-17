import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SourceList } from './SourceList';

describe('SourceList', () => {
  it('renders nothing when sources array is empty', () => {
    const { container } = render(<SourceList sources={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when sources is null', () => {
    const { container } = render(<SourceList sources={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders expandable section with source count', () => {
    const sources = [
      { documentId: 'doc1.pdf', pageNumber: 1, s3Uri: 's3://...', snippet: 'Text 1' },
      { documentId: 'doc2.pdf', pageNumber: 2, s3Uri: 's3://...', snippet: 'Text 2' }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText(/Sources \(2\)/i)).toBeInTheDocument();
  });

  it('displays document names', () => {
    const sources = [
      { documentId: 'invoice-jan.pdf', pageNumber: 1, s3Uri: 's3://...', snippet: 'Invoice' },
      { documentId: 'receipt-feb.pdf', pageNumber: 3, s3Uri: 's3://...', snippet: 'Receipt' }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText('invoice-jan.pdf')).toBeInTheDocument();
    expect(screen.getByText('receipt-feb.pdf')).toBeInTheDocument();
  });

  it('displays page numbers when available', () => {
    const sources = [
      { documentId: 'doc.pdf', pageNumber: 5, s3Uri: 's3://...', snippet: 'Text' }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText(/Page 5/i)).toBeInTheDocument();
  });

  it('handles missing page numbers gracefully', () => {
    const sources = [
      { documentId: 'doc.pdf', pageNumber: null, s3Uri: 's3://...', snippet: 'Text' }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText('doc.pdf')).toBeInTheDocument();
    expect(screen.queryByText(/Page/i)).not.toBeInTheDocument();
  });

  it('displays snippets when available', () => {
    const sources = [
      { documentId: 'doc.pdf', pageNumber: 1, s3Uri: 's3://...', snippet: 'This is a snippet from the document' }
    ];

    const { container } = render(<SourceList sources={sources} />);

    // Component displays snippet in quotes with ellipsis
    const text = container.textContent;
    expect(text).toContain('"This is a snippet from the document"...');
  });

  it('handles multiple sources correctly', () => {
    const sources = [
      { documentId: 'doc1.pdf', pageNumber: 1, s3Uri: 's3://1', snippet: 'Snippet 1' },
      { documentId: 'doc2.pdf', pageNumber: 2, s3Uri: 's3://2', snippet: 'Snippet 2' },
      { documentId: 'doc3.pdf', pageNumber: 3, s3Uri: 's3://3', snippet: 'Snippet 3' }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText(/Sources \(3\)/i)).toBeInTheDocument();
    expect(screen.getByText('doc1.pdf')).toBeInTheDocument();
    expect(screen.getByText('doc2.pdf')).toBeInTheDocument();
    expect(screen.getByText('doc3.pdf')).toBeInTheDocument();
  });

  it('handles sources with missing snippets', () => {
    const sources = [
      { documentId: 'doc.pdf', pageNumber: 1, s3Uri: 's3://...', snippet: null }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText('doc.pdf')).toBeInTheDocument();
    expect(screen.getByText(/Page 1/i)).toBeInTheDocument();
  });

  it('displays source URL as external link for scraped content', () => {
    const sources = [
      {
        documentId: 'abc123',
        isScraped: true,
        sourceUrl: 'https://docs.example.com/page1',
        snippet: 'Some content from scraped page',
        documentUrl: 'https://s3.example.com/abc123.scraped.md'
      }
    ];

    render(<SourceList sources={sources} />);

    // Should show the source URL as text
    expect(screen.getByText(/docs\.example\.com\/page1/i)).toBeInTheDocument();
  });

  it('shows download markdown link for scraped content', () => {
    const sources = [
      {
        documentId: 'abc123',
        isScraped: true,
        sourceUrl: 'https://docs.example.com/page1',
        snippet: 'Content',
        documentUrl: 'https://s3.example.com/abc123.scraped.md'
      }
    ];

    render(<SourceList sources={sources} />);

    expect(screen.getByText('Download markdown')).toBeInTheDocument();
  });

  it('does not show page number for scraped content', () => {
    const sources = [
      {
        documentId: 'abc123',
        pageNumber: 1,
        isScraped: true,
        sourceUrl: 'https://docs.example.com/page1',
        snippet: 'Content'
      }
    ];

    render(<SourceList sources={sources} />);

    // Page number should not be shown for scraped content
    expect(screen.queryByText(/Page 1/i)).not.toBeInTheDocument();
  });

  it('falls back to documentId when scraped source has no sourceUrl', () => {
    const sources = [
      {
        documentId: 'abc123',
        isScraped: true,
        sourceUrl: null,
        snippet: 'Content'
      }
    ];

    render(<SourceList sources={sources} />);

    // Should show documentId when sourceUrl is missing
    expect(screen.getByText('abc123')).toBeInTheDocument();
  });

  it('renders image source with thumbnail', () => {
    const sources = [
      {
        documentId: 'img-123',
        isImage: true,
        caption: 'A beautiful image',
        thumbnailUrl: 'https://example.com/thumb.png',
        documentUrl: 'https://example.com/full.png'
      }
    ];

    render(<SourceList sources={sources} />);

    // Should show the image source count
    expect(screen.getByText(/Sources \(1\)/i)).toBeInTheDocument();

    // Expand the section to access the content
    const expandButton = screen.getByRole('button', { name: /Sources \(1\)/i });
    fireEvent.click(expandButton);

    // Should show the image element after expanding
    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('src', 'https://example.com/thumb.png');
  });

  it('renders image source caption', () => {
    const sources = [
      {
        documentId: 'img-123',
        isImage: true,
        caption: 'A beautiful landscape photograph',
        thumbnailUrl: 'https://example.com/thumb.png'
      }
    ];

    render(<SourceList sources={sources} />);

    // Caption may appear multiple times (preview and modal)
    const captionElements = screen.getAllByText('A beautiful landscape photograph');
    expect(captionElements.length).toBeGreaterThanOrEqual(1);
  });
});
