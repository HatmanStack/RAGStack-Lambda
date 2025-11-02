import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
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
});
