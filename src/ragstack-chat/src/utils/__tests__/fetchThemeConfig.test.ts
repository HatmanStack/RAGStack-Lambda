/**
 * Tests for fetchThemeConfig utility
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock the generated config before importing the module
vi.mock('../../amplify-config.generated', () => ({
  THEME_API_CONFIG: {
    endpoint: 'https://test-api.example.com/graphql',
    apiKey: 'test-api-key',
  },
}));

import { fetchThemeConfig } from '../fetchThemeConfig';

describe('fetchThemeConfig', () => {
  const mockFetch = vi.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('returns theme config on successful fetch', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          getThemeConfig: {
            themePreset: 'dark',
            primaryColor: '#ff9900',
            fontFamily: 'Arial',
            spacing: 'comfortable',
          },
        },
      }),
    });

    const result = await fetchThemeConfig();

    expect(result).toEqual({
      themePreset: 'dark',
      themeOverrides: {
        primaryColor: '#ff9900',
        fontFamily: 'Arial',
        spacing: 'comfortable',
      },
    });
  });

  it('returns null when API returns error status', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    const result = await fetchThemeConfig();

    expect(result).toBeNull();
  });

  it('returns null when GraphQL returns errors', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        errors: [{ message: 'Some GraphQL error' }],
      }),
    });

    const result = await fetchThemeConfig();

    expect(result).toBeNull();
  });

  it('returns null and logs warning on network error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const result = await fetchThemeConfig();

    expect(result).toBeNull();
    expect(console.warn).toHaveBeenCalled();
  });

  it('returns theme with only themePreset when no overrides', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          getThemeConfig: {
            themePreset: 'light',
            primaryColor: null,
            fontFamily: null,
            spacing: null,
          },
        },
      }),
    });

    const result = await fetchThemeConfig();

    expect(result).toEqual({
      themePreset: 'light',
      themeOverrides: undefined,
    });
  });

  it('defaults to light theme when themePreset is missing', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          getThemeConfig: {
            themePreset: null,
          },
        },
      }),
    });

    const result = await fetchThemeConfig();

    expect(result?.themePreset).toBe('light');
  });

  it('aborts fetch after timeout', async () => {
    // Simulate a slow response that exceeds timeout
    mockFetch.mockImplementationOnce(
      () => new Promise((resolve) => setTimeout(resolve, 10000))
    );

    const result = await fetchThemeConfig();

    // Should return null due to abort
    expect(result).toBeNull();
  }, 10000);
});

describe('fetchThemeConfig without API config', () => {
  it('returns null when THEME_API_CONFIG is not set', async () => {
    // Re-mock with null config
    vi.doMock('../../amplify-config.generated', () => ({
      THEME_API_CONFIG: {
        endpoint: null,
        apiKey: null,
      },
    }));

    // Need to re-import to get the new mock
    const { fetchThemeConfig: fetchWithoutConfig } = await import('../fetchThemeConfig');

    const result = await fetchWithoutConfig();
    expect(result).toBeNull();
  });
});
