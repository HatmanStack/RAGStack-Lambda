import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

// Mock subscription object
const mockSubscription = {
  unsubscribe: vi.fn(),
};

// Mock graphql function - must be declared before vi.mock
const mockGraphql = vi.fn();

// Mock Amplify API - must use function reference, not inline arrow
vi.mock('aws-amplify/api', () => {
  return {
    generateClient: () => ({
      graphql: (...args: unknown[]) => mockGraphql(...args),
    }),
  };
});

// Import after mock is set up
import { useReindex } from './useReindex';

describe('useReindex', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock for subscription setup
    mockGraphql.mockReturnValue({
      subscribe: vi.fn(() => mockSubscription),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes with null status and no progress', () => {
    const { result } = renderHook(() => useReindex());

    expect(result.current.status).toBeNull();
    expect(result.current.progress).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.isStarting).toBe(false);
    expect(result.current.isInProgress).toBe(false);
  });

  it('starts reindex and returns execution ARN', async () => {
    const mockExecutionArn = 'arn:aws:states:us-east-1:123456789:execution:test';

    // First call is subscription setup, second is mutation
    mockGraphql
      .mockReturnValueOnce({ subscribe: vi.fn(() => mockSubscription) })
      .mockResolvedValueOnce({
        data: {
          startReindex: {
            executionArn: mockExecutionArn,
            status: 'PENDING',
            startedAt: new Date().toISOString(),
          },
        },
      });

    const { result } = renderHook(() => useReindex());

    await act(async () => {
      const response = await result.current.startReindex();
      expect(response?.executionArn).toBe(mockExecutionArn);
    });

    expect(result.current.status).toBe('PENDING');
  });

  it('updates progress on subscription events', async () => {
    let subscriptionCallback: ((data: unknown) => void) | null = null;

    mockGraphql.mockReturnValue({
      subscribe: vi.fn(({ next }) => {
        subscriptionCallback = next;
        return mockSubscription;
      }),
    });

    const { result } = renderHook(() => useReindex());

    // Simulate subscription event
    act(() => {
      if (subscriptionCallback) {
        subscriptionCallback({
          data: {
            onReindexUpdate: {
              status: 'PROCESSING',
              totalDocuments: 100,
              processedCount: 45,
              currentDocument: 'document-123.pdf',
              errorCount: 2,
              errorMessages: ['Error 1'],
              newKnowledgeBaseId: null,
              updatedAt: new Date().toISOString(),
            },
          },
        });
      }
    });

    await waitFor(() => {
      expect(result.current.status).toBe('PROCESSING');
      expect(result.current.progress?.totalDocuments).toBe(100);
      expect(result.current.progress?.processedCount).toBe(45);
      expect(result.current.progress?.percentComplete).toBe(45);
      expect(result.current.isInProgress).toBe(true);
    });
  });

  it('handles completion status', async () => {
    let subscriptionCallback: ((data: unknown) => void) | null = null;

    mockGraphql.mockReturnValue({
      subscribe: vi.fn(({ next }) => {
        subscriptionCallback = next;
        return mockSubscription;
      }),
    });

    const { result } = renderHook(() => useReindex());

    act(() => {
      if (subscriptionCallback) {
        subscriptionCallback({
          data: {
            onReindexUpdate: {
              status: 'COMPLETED',
              totalDocuments: 100,
              processedCount: 100,
              currentDocument: null,
              errorCount: 0,
              errorMessages: [],
              newKnowledgeBaseId: 'kb-new-123',
              updatedAt: new Date().toISOString(),
            },
          },
        });
      }
    });

    await waitFor(() => {
      expect(result.current.status).toBe('COMPLETED');
      expect(result.current.isInProgress).toBe(false);
    });
  });

  it('handles error status', async () => {
    let subscriptionCallback: ((data: unknown) => void) | null = null;

    mockGraphql.mockReturnValue({
      subscribe: vi.fn(({ next }) => {
        subscriptionCallback = next;
        return mockSubscription;
      }),
    });

    const { result } = renderHook(() => useReindex());

    act(() => {
      if (subscriptionCallback) {
        subscriptionCallback({
          data: {
            onReindexUpdate: {
              status: 'FAILED',
              totalDocuments: 100,
              processedCount: 50,
              currentDocument: null,
              errorCount: 1,
              errorMessages: ['Critical failure'],
              newKnowledgeBaseId: null,
              updatedAt: new Date().toISOString(),
            },
          },
        });
      }
    });

    await waitFor(() => {
      expect(result.current.status).toBe('FAILED');
      expect(result.current.error).toBe('Critical failure');
      expect(result.current.isInProgress).toBe(false);
    });
  });

  it('cleans up subscription on unmount', () => {
    mockGraphql.mockReturnValue({
      subscribe: vi.fn(() => mockSubscription),
    });

    const { unmount } = renderHook(() => useReindex());

    unmount();

    expect(mockSubscription.unsubscribe).toHaveBeenCalled();
  });

  it('handles mutation errors gracefully', async () => {
    mockGraphql
      .mockReturnValueOnce({ subscribe: vi.fn(() => mockSubscription) })
      .mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useReindex());

    await act(async () => {
      const response = await result.current.startReindex();
      expect(response).toBeNull();
    });

    expect(result.current.error).toBe('Network error');
    expect(result.current.isStarting).toBe(false);
  });
});
