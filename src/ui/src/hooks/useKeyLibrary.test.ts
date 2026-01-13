import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';

// Mock must be hoisted - define fn inside
vi.mock('aws-amplify/api', () => {
  const mockGraphql = vi.fn();
  return {
    generateClient: () => ({
      graphql: mockGraphql,
    }),
    __mockGraphql: mockGraphql,
  };
});

// Get reference to mock after module load
import * as amplifyApi from 'aws-amplify/api';
const mockGraphql = (amplifyApi as unknown as { __mockGraphql: ReturnType<typeof vi.fn> }).__mockGraphql;

import { useKeyLibrary } from './useKeyLibrary';

describe('useKeyLibrary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('fetches keys on mount', async () => {
    mockGraphql.mockResolvedValueOnce({
      data: {
        getKeyLibrary: [
          {
            keyName: 'topic',
            dataType: 'string',
            sampleValues: ['technology', 'health'],
            occurrenceCount: 10,
            status: 'active',
          },
        ],
      },
    });

    const { result } = renderHook(() => useKeyLibrary());

    // Initially loading
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockGraphql).toHaveBeenCalledTimes(1);
    expect(result.current.keys).toHaveLength(1);
    expect(result.current.keys[0].keyName).toBe('topic');
  });

  it('returns loading state during fetch', async () => {
    let resolvePromise: (value: unknown) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    mockGraphql.mockReturnValueOnce(promise);

    const { result } = renderHook(() => useKeyLibrary());

    // Should be loading initially
    expect(result.current.loading).toBe(true);
    expect(result.current.keys).toEqual([]);

    // Resolve the promise
    resolvePromise!({
      data: { getKeyLibrary: [] },
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
  });

  it('returns error on failure', async () => {
    mockGraphql.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useKeyLibrary());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Network error');
    expect(result.current.keys).toEqual([]);
  });

  it('refetch triggers new request', async () => {
    mockGraphql.mockResolvedValue({
      data: {
        getKeyLibrary: [
          { keyName: 'topic', dataType: 'string', sampleValues: [], occurrenceCount: 5, status: 'active' },
        ],
      },
    });

    const { result } = renderHook(() => useKeyLibrary());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockGraphql).toHaveBeenCalledTimes(1);

    // Call refetch
    await act(async () => {
      await result.current.refetch();
    });

    expect(mockGraphql).toHaveBeenCalledTimes(2);
  });

  it('transforms response to typed interface', async () => {
    mockGraphql.mockResolvedValueOnce({
      data: {
        getKeyLibrary: [
          {
            keyName: 'document_type',
            dataType: 'string',
            sampleValues: ['invoice', 'report', 'memo'],
            occurrenceCount: 25,
            status: 'active',
          },
        ],
      },
    });

    const { result } = renderHook(() => useKeyLibrary());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    const key = result.current.keys[0];
    expect(key.keyName).toBe('document_type');
    expect(key.dataType).toBe('string');
    expect(key.sampleValues).toEqual(['invoice', 'report', 'memo']);
    expect(key.occurrenceCount).toBe(25);
  });
});
