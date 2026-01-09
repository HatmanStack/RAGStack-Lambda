import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FilterExamples } from './FilterExamples';
import type { FilterExample } from '../../hooks/useMetadata';

const mockExamples: FilterExample[] = [
  {
    name: 'Genealogy Documents',
    description: 'Filter for genealogy-related content',
    useCase: 'Finding family history documents',
    filter: JSON.stringify({ topic: { $eq: 'genealogy' } }),
  },
  {
    name: 'PDF Documents',
    description: 'Filter for PDF document type',
    useCase: 'Finding PDF documents only',
    filter: JSON.stringify({ document_type: { $eq: 'pdf' } }),
  },
  {
    name: 'Recent Documents',
    description: 'Filter for documents from 2020 onwards',
    useCase: 'Finding recent content',
    filter: JSON.stringify({ year: { $gte: 2020 } }),
  },
];

describe('FilterExamples', () => {
  it('renders with mock examples', () => {
    render(
      <FilterExamples
        examples={mockExamples}
        totalExamples={3}
        lastGenerated="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('Filter Examples')).toBeInTheDocument();
  });

  it('displays example names', () => {
    render(
      <FilterExamples
        examples={mockExamples}
        totalExamples={3}
        lastGenerated="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('Genealogy Documents')).toBeInTheDocument();
    expect(screen.getByText('PDF Documents')).toBeInTheDocument();
    expect(screen.getByText('Recent Documents')).toBeInTheDocument();
  });

  it('displays example descriptions', () => {
    render(
      <FilterExamples
        examples={mockExamples}
        totalExamples={3}
        lastGenerated="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('Filter for genealogy-related content')).toBeInTheDocument();
    expect(screen.getByText('Filter for PDF document type')).toBeInTheDocument();
  });

  it('displays use case column', () => {
    render(
      <FilterExamples
        examples={mockExamples}
        totalExamples={3}
        lastGenerated="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('Finding family history documents')).toBeInTheDocument();
    expect(screen.getByText('Finding PDF documents only')).toBeInTheDocument();
    expect(screen.getByText('Finding recent content')).toBeInTheDocument();
  });

  it('shows View buttons', () => {
    render(
      <FilterExamples
        examples={mockExamples}
        totalExamples={3}
        lastGenerated="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    const viewButtons = screen.getAllByText('View');
    expect(viewButtons.length).toBe(3);
  });

  it('opens modal when View is clicked', () => {
    render(
      <FilterExamples
        examples={mockExamples}
        totalExamples={3}
        lastGenerated="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    const viewButtons = screen.getAllByText('View');
    fireEvent.click(viewButtons[0]);

    // Modal should be open with the example name as header
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    // The example name appears twice - once in table, once in modal
    const genealogyTexts = screen.getAllByText('Genealogy Documents');
    expect(genealogyTexts.length).toBe(2);
  });

  it('shows toggle controls', () => {
    render(
      <FilterExamples
        examples={mockExamples}
        totalExamples={3}
        lastGenerated="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
        enabledExamples={['Genealogy Documents', 'PDF Documents', 'Recent Documents']}
        onToggleExample={vi.fn()}
      />
    );

    // Should have 3 toggle controls
    const toggles = screen.getAllByRole('switch');
    expect(toggles.length).toBe(3);
  });

  it('calls onToggleExample when toggle is clicked', () => {
    const onToggleExample = vi.fn();

    render(
      <FilterExamples
        examples={mockExamples}
        totalExamples={3}
        lastGenerated="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
        enabledExamples={['Genealogy Documents', 'PDF Documents', 'Recent Documents']}
        onToggleExample={onToggleExample}
      />
    );

    const toggles = screen.getAllByRole('switch');
    fireEvent.click(toggles[0]);

    expect(onToggleExample).toHaveBeenCalledWith('Genealogy Documents', false);
  });

  it('shows loading state', () => {
    render(
      <FilterExamples
        examples={[]}
        totalExamples={0}
        lastGenerated={null}
        loading={true}
        error={null}
      />
    );

    expect(screen.getByText('Loading filter examples...')).toBeInTheDocument();
  });

  it('shows error state', () => {
    render(
      <FilterExamples
        examples={[]}
        totalExamples={0}
        lastGenerated={null}
        loading={false}
        error="Failed to load filter examples"
      />
    );

    expect(screen.getByText('Failed to load filter examples')).toBeInTheDocument();
  });

  it('shows empty state when no examples', () => {
    render(
      <FilterExamples
        examples={[]}
        totalExamples={0}
        lastGenerated={null}
        loading={false}
        error={null}
      />
    );

    expect(screen.getByText('No filter examples')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Run the metadata analyzer to generate filter examples based on your documents.'
      )
    ).toBeInTheDocument();
  });

  it('displays filter JSON in modal', () => {
    render(
      <FilterExamples
        examples={mockExamples}
        totalExamples={3}
        lastGenerated="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    const viewButtons = screen.getAllByText('View');
    fireEvent.click(viewButtons[0]);

    // Filter JSON should be displayed in a code block
    const codeBlock = screen.getByRole('dialog').querySelector('code');
    expect(codeBlock).toBeInTheDocument();
    expect(codeBlock?.textContent).toContain('topic');
    expect(codeBlock?.textContent).toContain('$eq');
  });

  it('closes modal when Close is clicked', () => {
    render(
      <FilterExamples
        examples={mockExamples}
        totalExamples={3}
        lastGenerated="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
      />
    );

    // Open modal
    const viewButtons = screen.getAllByText('View');
    fireEvent.click(viewButtons[0]);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Close modal
    const closeButton = screen.getByText('Close');
    fireEvent.click(closeButton);

    // Modal should be closed
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('displays enabled count in header', () => {
    render(
      <FilterExamples
        examples={mockExamples}
        totalExamples={3}
        lastGenerated="2025-01-06T10:00:00Z"
        loading={false}
        error={null}
        enabledExamples={['Genealogy Documents']}
      />
    );

    // Should show "1/3 enabled"
    expect(screen.getByText(/1\/3 enabled/)).toBeInTheDocument();
  });
});
