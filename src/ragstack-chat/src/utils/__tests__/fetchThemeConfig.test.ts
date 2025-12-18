/**
 * Tests for fetchThemeConfig utility
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchThemeConfig } from '../fetchThemeConfig';

describe('fetchThemeConfig', () => {
  const mockFetch = vi.fn();
  const originalFetch = global.fetch;
  const originalDocument = global.document;

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();

    // Mock document.querySelectorAll to return a script element
    const mockScript = { src: 'https://cdn.example.com/ragstack-chat.js' };
    global.document = {
      ...originalDocument,
      querySelectorAll: vi.fn().mockReturnValue([mockScript]),
    } as unknown as Document;

    // Clear the cached config between tests
    vi.resetModules();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    global.document = originalDocument;
    vi.restoreAllMocks();
  });

  it('returns theme config on successful fetch', async () => {
    // First call: config.json
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        apiEndpoint: 'https://test-api.example.com/graphql',
        apiKey: 'test-api-key',
      }),
    });

    // Second call: GraphQL API
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

    const { fetchThemeConfig: freshFetch } = await import('../fetchThemeConfig');
    const result = await freshFetch();

    expect(result).toEqual({
      themePreset: 'dark',
      themeOverrides: {
        primaryColor: '#ff9900',
        fontFamily: 'Arial',
        spacing: 'comfortable',
      },
    });
  });

  it('returns null when config.json fetch fails', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    const { fetchThemeConfig: freshFetch } = await import('../fetchThemeConfig');
    const result = await freshFetch();

    expect(result).toBeNull();
  });

  it('returns null when API returns error status', async () => {
    // First call: config.json
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        apiEndpoint: 'https://test-api.example.com/graphql',
        apiKey: 'test-api-key',
      }),
    });

    // Second call: GraphQL API fails
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    const { fetchThemeConfig: freshFetch } = await import('../fetchThemeConfig');
    const result = await freshFetch();

    expect(result).toBeNull();
  });

  it('returns null when GraphQL returns errors', async () => {
    // First call: config.json
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        apiEndpoint: 'https://test-api.example.com/graphql',
        apiKey: 'test-api-key',
      }),
    });

    // Second call: GraphQL returns errors
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        errors: [{ message: 'Some GraphQL error' }],
      }),
    });

    const { fetchThemeConfig: freshFetch } = await import('../fetchThemeConfig');
    const result = await freshFetch();

    expect(result).toBeNull();
  });

  it('returns null on network error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const { fetchThemeConfig: freshFetch } = await import('../fetchThemeConfig');
    const result = await freshFetch();

    expect(result).toBeNull();
  });

  it('returns theme with only themePreset when no overrides', async () => {
    // First call: config.json
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        apiEndpoint: 'https://test-api.example.com/graphql',
        apiKey: 'test-api-key',
      }),
    });

    // Second call: GraphQL API
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

    const { fetchThemeConfig: freshFetch } = await import('../fetchThemeConfig');
    const result = await freshFetch();

    expect(result).toEqual({
      themePreset: 'light',
      themeOverrides: undefined,
    });
  });

  it('defaults to light theme when themePreset is missing', async () => {
    // First call: config.json
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        apiEndpoint: 'https://test-api.example.com/graphql',
        apiKey: 'test-api-key',
      }),
    });

    // Second call: GraphQL API with null themePreset
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

    const { fetchThemeConfig: freshFetch } = await import('../fetchThemeConfig');
    const result = await freshFetch();

    expect(result?.themePreset).toBe('light');
  });

  it('returns null when config has no apiEndpoint', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        apiEndpoint: '',
        apiKey: 'test-api-key',
      }),
    });

    const { fetchThemeConfig: freshFetch } = await import('../fetchThemeConfig');
    const result = await freshFetch();

    expect(result).toBeNull();
  });

  it('constructs config URL from script src', async () => {
    // First call: config.json
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        apiEndpoint: 'https://test-api.example.com/graphql',
        apiKey: 'test-api-key',
      }),
    });

    // Second call: GraphQL API
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          getThemeConfig: {
            themePreset: 'brand',
          },
        },
      }),
    });

    const { fetchThemeConfig: freshFetch } = await import('../fetchThemeConfig');
    await freshFetch();

    // Should have called fetch with the config URL derived from script src
    expect(mockFetch).toHaveBeenCalledWith(
      'https://cdn.example.com/config.json',
      expect.any(Object)
    );
  });
});
