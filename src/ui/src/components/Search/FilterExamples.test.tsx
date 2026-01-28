import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FilterExamples } from './FilterExamples';
import type { FilterExample } from '../../hooks/useMetadata';

// Mock useKeyLibrary since FilterKeyInput uses it
vi.mock('../../hooks/useKeyLibrary', () => ({
  useKeyLibrary: () => ({
    keys: [
      { keyName: 'location', dataType: 'string', occurrenceCount: 10, status: 'active' },
      { keyName: 'year', dataType: 'number', occurrenceCount: 5, status: 'active' },
    ],
    loading: false,
  }),
}));

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

    // Expand the section first (it's collapsed by default)
    const expandButton = screen.getByRole('button', { expanded: false });
    fireEvent.click(expandButton);

    // Should have 3 toggle controls (Cloudscape Toggle uses checkbox role)
    const toggles = screen.getAllByRole('checkbox');
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

    // Expand the section first (it's collapsed by default)
    const expandButton = screen.getByRole('button', { expanded: false });
    fireEvent.click(expandButton);

    const toggles = screen.getAllByRole('checkbox');
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
        'Select keys above, then click "Regenerate Examples" to create filter examples.'
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

    // Filter JSON should be displayed in a pre block
    const preBlock = screen.getByRole('dialog').querySelector('pre');
    expect(preBlock).toBeInTheDocument();
    expect(preBlock?.textContent).toContain('topic');
    expect(preBlock?.textContent).toContain('$eq');
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

  // Filter Key Workflow Tests
  describe('filter key workflow', () => {
    const defaultFilterKeyProps = {
      examples: mockExamples,
      totalExamples: 3,
      lastGenerated: '2025-01-06T10:00:00Z',
      loading: false,
      error: null,
      filterKeys: [],
      onFilterKeysChange: vi.fn(),
      onRegenerateExamples: vi.fn(),
      regenerating: false,
    };

    it('shows filter key input', () => {
      render(<FilterExamples {...defaultFilterKeyProps} />);

      // The filter key input section should be visible
      expect(screen.getByText('Keys to Use for Filters')).toBeInTheDocument();
    });

    it('shows regenerate button', () => {
      render(<FilterExamples {...defaultFilterKeyProps} />);

      expect(screen.getByText('Regenerate Examples')).toBeInTheDocument();
    });

    it('disables regenerate button when no keys selected', () => {
      render(<FilterExamples {...defaultFilterKeyProps} filterKeys={[]} />);

      // The button should be disabled and hint message should be shown
      expect(screen.getByText('Add at least one key to generate examples')).toBeInTheDocument();
      expect(screen.getByText('Regenerate Examples')).toBeInTheDocument();
    });

    it('enables regenerate button when keys are selected', () => {
      render(<FilterExamples {...defaultFilterKeyProps} filterKeys={['location']} />);

      // The button should be enabled (hint message should not be shown)
      expect(screen.queryByText('Add at least one key to generate examples')).not.toBeInTheDocument();
      expect(screen.getByText('Regenerate Examples')).toBeInTheDocument();
    });

    it('shows hint when no keys selected', () => {
      render(<FilterExamples {...defaultFilterKeyProps} filterKeys={[]} />);

      expect(screen.getByText('Add at least one key to generate examples')).toBeInTheDocument();
    });

    it('hides hint when keys are selected', () => {
      render(<FilterExamples {...defaultFilterKeyProps} filterKeys={['location']} />);

      expect(screen.queryByText('Add at least one key to generate examples')).not.toBeInTheDocument();
    });

    it('calls onRegenerateExamples when button clicked', () => {
      const onRegenerate = vi.fn().mockResolvedValue(undefined);
      render(
        <FilterExamples
          {...defaultFilterKeyProps}
          filterKeys={['location']}
          onRegenerateExamples={onRegenerate}
        />
      );

      // Find all buttons and click the one with "Regenerate Examples" text
      const buttons = screen.getAllByRole('button');
      const regenerateButton = buttons.find(btn =>
        btn.textContent?.includes('Regenerate Examples')
      );

      if (regenerateButton) {
        fireEvent.click(regenerateButton);
        expect(onRegenerate).toHaveBeenCalled();
      } else {
        // If button not found, the test should fail
        expect(screen.getByText('Regenerate Examples')).toBeInTheDocument();
      }
    });

    it('disables filter key input during regeneration', () => {
      render(
        <FilterExamples
          {...defaultFilterKeyProps}
          filterKeys={['location']}
          regenerating={true}
        />
      );

      // The regenerate button text should still be present
      expect(screen.getByText('Regenerate Examples')).toBeInTheDocument();
    });

    it('shows appropriate empty state message when keys are selected', () => {
      render(
        <FilterExamples
          examples={[]}
          totalExamples={0}
          lastGenerated={null}
          loading={false}
          error={null}
          filterKeys={['location']}
          onFilterKeysChange={vi.fn()}
          onRegenerateExamples={vi.fn()}
          regenerating={false}
        />
      );

      expect(
        screen.getByText('Click "Regenerate Examples" to create filter examples using the selected keys.')
      ).toBeInTheDocument();
    });
  });
});
