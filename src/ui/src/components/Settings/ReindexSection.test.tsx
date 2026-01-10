import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// Store original confirm to restore later
const originalConfirm = window.confirm;

// Mock useReindex hook
const mockStartReindex = vi.fn();
const mockClearState = vi.fn();
let mockHookState = {
  status: null as string | null,
  progress: null as { totalDocuments: number; processedCount: number; percentComplete: number; currentDocument: string | null; errorCount: number; errorMessages: string[] } | null,
  error: null as string | null,
  isStarting: false,
  isInProgress: false,
  newKnowledgeBaseId: null as string | null,
  startReindex: mockStartReindex,
  clearState: mockClearState,
};

vi.mock('../../hooks/useReindex', () => ({
  useReindex: () => mockHookState,
}));

// Import after mock is set up
import { ReindexSection } from './ReindexSection';

describe('ReindexSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mock state to defaults
    mockHookState = {
      status: null,
      progress: null,
      error: null,
      isStarting: false,
      isInProgress: false,
      newKnowledgeBaseId: null,
      startReindex: mockStartReindex,
      clearState: mockClearState,
    };
    // Reset window.confirm to a mock function
    window.confirm = vi.fn();
  });

  afterEach(() => {
    // Restore original confirm
    window.confirm = originalConfirm;
  });

  it('renders start button when idle', () => {
    render(<ReindexSection />);
    expect(screen.getByText('Reindex All Documents')).toBeInTheDocument();
  });

  it('renders warning alert with explanation', () => {
    render(<ReindexSection />);
    expect(screen.getByText(/This will regenerate metadata/)).toBeInTheDocument();
  });

  it('shows confirmation before starting', async () => {
    (window.confirm as ReturnType<typeof vi.fn>).mockReturnValue(true);
    mockStartReindex.mockResolvedValue({ executionArn: 'test-arn' });

    render(<ReindexSection />);
    fireEvent.click(screen.getByText('Reindex All Documents'));

    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringContaining('regenerate metadata')
    );
  });

  it('does not start if confirmation is cancelled', async () => {
    (window.confirm as ReturnType<typeof vi.fn>).mockReturnValue(false);

    render(<ReindexSection />);
    fireEvent.click(screen.getByText('Reindex All Documents'));

    expect(mockStartReindex).not.toHaveBeenCalled();
  });

  it('calls startReindex when confirmed', async () => {
    (window.confirm as ReturnType<typeof vi.fn>).mockReturnValue(true);
    mockStartReindex.mockResolvedValue({ executionArn: 'test-arn' });

    render(<ReindexSection />);
    fireEvent.click(screen.getByText('Reindex All Documents'));

    await waitFor(() => {
      expect(mockStartReindex).toHaveBeenCalled();
    });
  });

  it('shows loading state when starting', () => {
    mockHookState = {
      ...mockHookState,
      isStarting: true,
    };

    render(<ReindexSection />);
    // Button should be in loading state
    const button = screen.getByRole('button', { name: /Reindex All Documents/i });
    expect(button).toBeDisabled();
  });

  it('shows progress during reindex', () => {
    mockHookState = {
      ...mockHookState,
      status: 'PROCESSING',
      isInProgress: true,
      progress: {
        totalDocuments: 100,
        processedCount: 45,
        percentComplete: 45,
        currentDocument: 'document-123.pdf',
        errorCount: 0,
        errorMessages: [],
      },
    };

    render(<ReindexSection />);
    expect(screen.getByText(/45 of 100 documents/)).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows button as disabled during reindex', () => {
    mockHookState = {
      ...mockHookState,
      status: 'PROCESSING',
      isInProgress: true,
      progress: {
        totalDocuments: 100,
        processedCount: 45,
        percentComplete: 45,
        currentDocument: null,
        errorCount: 0,
        errorMessages: [],
      },
    };

    render(<ReindexSection />);
    const button = screen.getByRole('button', { name: /Reindexing/i });
    expect(button).toBeDisabled();
  });

  it('shows success message on completion', () => {
    mockHookState = {
      ...mockHookState,
      status: 'COMPLETED',
      isInProgress: false,
      newKnowledgeBaseId: 'kb-new-123',
      progress: {
        totalDocuments: 100,
        processedCount: 100,
        percentComplete: 100,
        currentDocument: null,
        errorCount: 0,
        errorMessages: [],
      },
    };

    render(<ReindexSection />);
    expect(screen.getByText(/Reindex completed successfully/)).toBeInTheDocument();
  });

  it('shows error message on failure', () => {
    mockHookState = {
      ...mockHookState,
      status: 'FAILED',
      isInProgress: false,
      error: 'Something went wrong',
    };

    render(<ReindexSection />);
    expect(screen.getByText(/Something went wrong/)).toBeInTheDocument();
  });

  it('shows status-specific messages', () => {
    // Test CREATING_KB status
    mockHookState = {
      ...mockHookState,
      status: 'CREATING_KB',
      isInProgress: true,
      progress: {
        totalDocuments: 0,
        processedCount: 0,
        percentComplete: 0,
        currentDocument: null,
        errorCount: 0,
        errorMessages: [],
      },
    };

    render(<ReindexSection />);
    expect(screen.getByText(/Creating new Knowledge Base/)).toBeInTheDocument();
  });

  it('shows error count during processing', () => {
    mockHookState = {
      ...mockHookState,
      status: 'PROCESSING',
      isInProgress: true,
      progress: {
        totalDocuments: 100,
        processedCount: 50,
        percentComplete: 50,
        currentDocument: null,
        errorCount: 3,
        errorMessages: ['Error 1', 'Error 2', 'Error 3'],
      },
    };

    render(<ReindexSection />);
    expect(screen.getByText(/3 errors/)).toBeInTheDocument();
  });
});
