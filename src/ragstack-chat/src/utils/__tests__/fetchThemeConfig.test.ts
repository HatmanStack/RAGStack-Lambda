/**
 * Tests for fetchThemeConfig utility
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock iamFetch before importing the module
vi.mock('../iamAuth', () => ({
  iamFetch: vi.fn(),
}));

import { fetchThemeConfig, fetchCDNConfig } from '../fetchThemeConfig';
import { iamFetch } from '../iamAuth';

const mockIamFetch = vi.mocked(iamFetch);

describe('fetchThemeConfig', () => {
  const mockFetch = vi.fn();
  const originalFetch = global.fetch;
  const originalDocument = global.document;

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
    mockIamFetch.mockReset();

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
        identityPoolId: 'us-east-1:test-pool',
        region: 'us-east-1',
      }),
    });

    // iamFetch returns GraphQL response
    mockIamFetch.mockResolvedValueOnce({
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
    } as Response);

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
        identityPoolId: 'us-east-1:test-pool',
        region: 'us-east-1',
      }),
    });

    // iamFetch returns error
    mockIamFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    } as Response);

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
        identityPoolId: 'us-east-1:test-pool',
        region: 'us-east-1',
      }),
    });

    // iamFetch returns GraphQL errors
    mockIamFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        errors: [{ message: 'Unauthorized' }],
      }),
    } as Response);

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
        identityPoolId: 'us-east-1:test-pool',
        region: 'us-east-1',
      }),
    });

    // iamFetch returns only preset
    mockIamFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          getThemeConfig: {
            themePreset: 'light',
          },
        },
      }),
    } as Response);

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
        identityPoolId: 'us-east-1:test-pool',
        region: 'us-east-1',
      }),
    });

    // iamFetch returns empty theme
    mockIamFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          getThemeConfig: {},
        },
      }),
    } as Response);

    const { fetchThemeConfig: freshFetch } = await import('../fetchThemeConfig');
    const result = await freshFetch();

    expect(result).toEqual({
      themePreset: 'light',
      themeOverrides: undefined,
    });
  });

  it('returns null when config is missing identityPoolId', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        apiEndpoint: 'https://test-api.example.com/graphql',
        // Missing identityPoolId and region
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
        identityPoolId: 'us-east-1:test-pool',
        region: 'us-east-1',
      }),
    });

    // iamFetch
    mockIamFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          getThemeConfig: {
            themePreset: 'light',
          },
        },
      }),
    } as Response);

    const { fetchThemeConfig: freshFetch } = await import('../fetchThemeConfig');
    await freshFetch();

    // Should have called fetch with the config URL derived from script src
    expect(mockFetch).toHaveBeenCalledWith(
      'https://cdn.example.com/config.json',
      expect.any(Object)
    );
  });
});

describe('fetchCDNConfig', () => {
  const mockFetch = vi.fn();
  const originalFetch = global.fetch;
  const originalDocument = global.document;

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();

    const mockScript = { src: 'https://cdn.example.com/ragstack-chat.js' };
    global.document = {
      ...originalDocument,
      querySelectorAll: vi.fn().mockReturnValue([mockScript]),
    } as unknown as Document;

    vi.resetModules();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    global.document = originalDocument;
  });

  it('returns config with identityPoolId and region', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        apiEndpoint: 'https://api.example.com/graphql',
        identityPoolId: 'us-west-2:abc123',
        region: 'us-west-2',
      }),
    });

    const { fetchCDNConfig: freshFetch } = await import('../fetchThemeConfig');
    const result = await freshFetch();

    expect(result).toEqual({
      apiEndpoint: 'https://api.example.com/graphql',
      identityPoolId: 'us-west-2:abc123',
      region: 'us-west-2',
    });
  });
});
