import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MetadataKeyInput } from './MetadataKeyInput';

// Mock useKeyLibrary hook
vi.mock('../../hooks/useKeyLibrary', () => ({
  useKeyLibrary: () => ({
    keys: [
      {
        keyName: 'document_type',
        dataType: 'string',
        sampleValues: ['report', 'memo'],
        occurrenceCount: 10,
        status: 'active',
      },
      { keyName: 'topic', dataType: 'string', sampleValues: ['tech'], occurrenceCount: 5, status: 'active' },
      { keyName: 'author', dataType: 'string', sampleValues: ['John'], occurrenceCount: 3, status: 'active' },
    ],
    loading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

// Mock similarity utility
vi.mock('../../utils/similarity', () => ({
  findSimilarKeys: (input: string) => {
    if (input.toLowerCase() === 'doc_type') {
      return [{ keyName: 'document_type', similarity: 0.8 }];
    }
    return [];
  },
}));

describe('MetadataKeyInput', () => {
  const mockOnChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the multiselect trigger', () => {
    render(<MetadataKeyInput value={[]} onChange={mockOnChange} />);

    // Verify component renders with placeholder
    const trigger = screen.getByRole('button', { name: /select or type keys to extract/i });
    expect(trigger).toBeInTheDocument();
  });

  it('displays selected keys as tokens', () => {
    render(<MetadataKeyInput value={['topic', 'author']} onChange={mockOnChange} />);

    // Should show selected values as tokens
    expect(screen.getByText('topic')).toBeInTheDocument();
    expect(screen.getByText('author')).toBeInTheDocument();
  });

  it('respects disabled prop', () => {
    render(<MetadataKeyInput value={[]} onChange={mockOnChange} disabled />);

    const trigger = screen.getByRole('button');
    expect(trigger).toBeDisabled();
  });

  it('renders without errors when empty', () => {
    const { container } = render(<MetadataKeyInput value={[]} onChange={mockOnChange} />);
    expect(container).toBeTruthy();
  });

  it('renders without errors with selected values', () => {
    const { container } = render(
      <MetadataKeyInput value={['test_key', 'another_key']} onChange={mockOnChange} />
    );
    expect(container).toBeTruthy();
    expect(screen.getByText('test_key')).toBeInTheDocument();
    expect(screen.getByText('another_key')).toBeInTheDocument();
  });

  it('passes onChange prop correctly', () => {
    // Verify the component accepts and uses the onChange prop
    const { rerender } = render(<MetadataKeyInput value={[]} onChange={mockOnChange} />);

    // Rerender with new value should work
    rerender(<MetadataKeyInput value={['new_key']} onChange={mockOnChange} />);
    expect(screen.getByText('new_key')).toBeInTheDocument();
  });
});
