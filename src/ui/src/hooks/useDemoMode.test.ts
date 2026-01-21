import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';

// Mock graphql function - must be declared before vi.mock
const mockGraphql = vi.fn();

// Mock Amplify API
vi.mock('aws-amplify/api', () => {
  return {
    generateClient: () => ({
      graphql: (...args: unknown[]) => mockGraphql(...args),
    }),
  };
});

// Import after mock is set up
import { useDemoMode } from './useDemoMode';

describe('useDemoMode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes with loading state', () => {
    mockGraphql.mockReturnValue(new Promise(() => {})); // Never resolves

    const { result } = renderHook(() => useDemoMode());

    expect(result.current.loading).toBe(true);
    expect(result.current.isEnabled).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('returns demo mode enabled when config says true', async () => {
    mockGraphql.mockResolvedValueOnce({
      data: {
        getConfiguration: {
          Schema: '{}',
          Default: JSON.stringify({ demo_mode_enabled: true }),
          Custom: '{}',
        },
      },
    });

    const { result } = renderHook(() => useDemoMode());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.isEnabled).toBe(true);
    expect(result.current.uploadLimit).toBe(5); // Default
    expect(result.current.chatLimit).toBe(30); // Default
  });

  it('returns demo mode disabled when not in config', async () => {
    mockGraphql.mockResolvedValueOnce({
      data: {
        getConfiguration: {
          Schema: '{}',
          Default: '{}',
          Custom: '{}',
        },
      },
    });

    const { result } = renderHook(() => useDemoMode());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.isEnabled).toBe(false);
  });

  it('uses custom quota values from config', async () => {
    mockGraphql.mockResolvedValueOnce({
      data: {
        getConfiguration: {
          Schema: '{}',
          Default: JSON.stringify({
            demo_mode_enabled: true,
            demo_upload_quota_daily: 10,
            demo_chat_quota_daily: 50,
          }),
          Custom: '{}',
        },
      },
    });

    const { result } = renderHook(() => useDemoMode());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.isEnabled).toBe(true);
    expect(result.current.uploadLimit).toBe(10);
    expect(result.current.chatLimit).toBe(50);
  });

  it('custom config overrides default config', async () => {
    mockGraphql.mockResolvedValueOnce({
      data: {
        getConfiguration: {
          Schema: '{}',
          Default: JSON.stringify({
            demo_mode_enabled: false,
            demo_upload_quota_daily: 5,
          }),
          Custom: JSON.stringify({
            demo_upload_quota_daily: 20,
          }),
        },
      },
    });

    const { result } = renderHook(() => useDemoMode());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Custom overrides default for upload limit
    expect(result.current.uploadLimit).toBe(20);
  });

  it('handles API error gracefully', async () => {
    mockGraphql.mockRejectedValueOnce(new Error('API error'));

    const { result } = renderHook(() => useDemoMode());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('API error');
    expect(result.current.isEnabled).toBe(false);
  });

  it('handles missing getConfiguration response', async () => {
    mockGraphql.mockResolvedValueOnce({
      data: {
        getConfiguration: null,
      },
    });

    const { result } = renderHook(() => useDemoMode());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Failed to load configuration');
  });

  it('provides refresh function', async () => {
    mockGraphql
      .mockResolvedValueOnce({
        data: {
          getConfiguration: {
            Schema: '{}',
            Default: JSON.stringify({ demo_mode_enabled: false }),
            Custom: '{}',
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          getConfiguration: {
            Schema: '{}',
            Default: JSON.stringify({ demo_mode_enabled: true }),
            Custom: '{}',
          },
        },
      });

    const { result } = renderHook(() => useDemoMode());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.isEnabled).toBe(false);

    // Refresh to get updated value
    await result.current.refresh();

    await waitFor(() => {
      expect(result.current.isEnabled).toBe(true);
    });
  });
});
