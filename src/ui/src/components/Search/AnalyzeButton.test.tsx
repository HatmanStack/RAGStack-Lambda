import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AnalyzeButton } from './AnalyzeButton';
import * as useMetadataModule from '../../hooks/useMetadata';

const mockResult = {
  success: true,
  vectorsSampled: 500,
  keysAnalyzed: 8,
  examplesGenerated: 5,
  executionTimeMs: 15000,
  error: undefined,
};

const errorResult = {
  success: false,
  vectorsSampled: 0,
  keysAnalyzed: 0,
  examplesGenerated: 0,
  executionTimeMs: 1000,
  error: 'Knowledge Base not configured',
};

describe('AnalyzeButton', () => {
  let mockAnalyze: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockAnalyze = vi.fn();
    vi.spyOn(useMetadataModule, 'useMetadataAnalyzer').mockReturnValue({
      analyze: mockAnalyze,
      analyzing: false,
      result: null,
      error: null,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders analyze button', () => {
    render(<AnalyzeButton />);
    expect(screen.getByText('Analyze Metadata')).toBeInTheDocument();
  });

  it('triggers analyze on click', async () => {
    mockAnalyze.mockResolvedValue(mockResult);

    render(<AnalyzeButton />);

    const button = screen.getByText('Analyze Metadata');
    fireEvent.click(button);

    expect(mockAnalyze).toHaveBeenCalled();
  });

  it('calls onComplete callback after successful analysis', async () => {
    // Mock that updates result after analyze is called
    mockAnalyze.mockImplementation(async () => {
      return mockResult;
    });

    const onComplete = vi.fn();
    render(<AnalyzeButton onComplete={onComplete} />);

    const button = screen.getByText('Analyze Metadata');
    fireEvent.click(button);

    await waitFor(() => {
      expect(onComplete).toHaveBeenCalled();
    });
  });

  it('shows success modal after analysis completes', async () => {
    // Simulate the hook returning result after analyze
    let hookResult: useMetadataModule.MetadataAnalysisResult | null = null;

    vi.spyOn(useMetadataModule, 'useMetadataAnalyzer').mockImplementation(() => ({
      analyze: async () => {
        hookResult = mockResult;
        return mockResult;
      },
      analyzing: false,
      result: hookResult,
      error: null,
    }));

    const { rerender } = render(<AnalyzeButton />);

    const button = screen.getByText('Analyze Metadata');
    fireEvent.click(button);

    // After click, the component re-renders with showResult=true
    // and result should be set from the analyze() return value
    await waitFor(() => {
      expect(screen.getByText('Metadata Analysis Complete')).toBeInTheDocument();
    });
  });

  it('displays analysis stats in success modal', async () => {
    vi.spyOn(useMetadataModule, 'useMetadataAnalyzer').mockImplementation(() => ({
      analyze: async () => mockResult,
      analyzing: false,
      result: mockResult, // Pre-set result for rendering
      error: null,
    }));

    render(<AnalyzeButton />);

    const button = screen.getByText('Analyze Metadata');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText('Vectors Sampled')).toBeInTheDocument();
      expect(screen.getByText('500')).toBeInTheDocument();
      expect(screen.getByText('Keys Analyzed')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
      expect(screen.getByText('Examples Generated')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });

  it('shows error in modal when analysis returns error', async () => {
    vi.spyOn(useMetadataModule, 'useMetadataAnalyzer').mockImplementation(() => ({
      analyze: async () => errorResult,
      analyzing: false,
      result: errorResult, // Pre-set error result
      error: null,
    }));

    render(<AnalyzeButton />);

    const button = screen.getByText('Analyze Metadata');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText('Knowledge Base not configured')).toBeInTheDocument();
    });
  });

  it('closes modal when Done is clicked', async () => {
    vi.spyOn(useMetadataModule, 'useMetadataAnalyzer').mockImplementation(() => ({
      analyze: async () => mockResult,
      analyzing: false,
      result: mockResult,
      error: null,
    }));

    render(<AnalyzeButton />);

    const button = screen.getByText('Analyze Metadata');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText('Metadata Analysis Complete')).toBeInTheDocument();
    });

    const doneButton = screen.getByText('Done');
    fireEvent.click(doneButton);

    // Modal visibility is controlled by showResult state
    // After clicking Done, the modal's visible prop becomes false
    // The modal header should no longer be displayed (modal closes)
    // Note: The Modal component may still be in DOM but with visible=false
    await waitFor(
      () => {
        // Check that the modal dialog is no longer in the document
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      },
      { timeout: 2000 }
    );
  });

  it('shows execution time in success modal', async () => {
    vi.spyOn(useMetadataModule, 'useMetadataAnalyzer').mockImplementation(() => ({
      analyze: async () => mockResult,
      analyzing: false,
      result: mockResult,
      error: null,
    }));

    render(<AnalyzeButton />);

    const button = screen.getByText('Analyze Metadata');
    fireEvent.click(button);

    await waitFor(() => {
      // 15000ms = 15.0s
      expect(screen.getByText(/Analysis completed successfully in 15\.0s/)).toBeInTheDocument();
    });
  });
});
