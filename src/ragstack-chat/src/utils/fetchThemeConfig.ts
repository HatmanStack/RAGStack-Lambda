/**
 * Fetch theme configuration from the SAM AppSync API
 *
 * This utility fetches theme settings from the public getThemeConfig endpoint.
 * It uses the SAM stack's GraphQL API because theme config is stored in
 * the SAM stack's DynamoDB table.
 *
 * At runtime, the web component fetches config.json from the same CDN origin
 * to discover the API endpoint and Identity Pool ID. This enables real-time
 * theme updates without rebuilding the web component.
 */

import { iamFetch } from './iamAuth';

export interface ThemeConfig {
  themePreset: 'light' | 'dark' | 'brand';
  themeOverrides?: {
    primaryColor?: string;
    fontFamily?: string;
    spacing?: 'compact' | 'comfortable' | 'spacious';
  };
}

export interface CDNConfig {
  apiEndpoint: string;
  identityPoolId: string;
  region: string;
}

// Cache the CDN config to avoid refetching on every request
let cachedCDNConfig: CDNConfig | null = null;

const GET_THEME_CONFIG_QUERY = `
  query GetThemeConfig {
    getThemeConfig {
      themePreset
      primaryColor
      fontFamily
      spacing
    }
  }
`;

/**
 * Fetch CDN config.json to get API endpoint and Identity Pool ID
 * Uses the script's origin to construct the config URL
 * Exported for use by ChatInterface as well
 */
export async function fetchCDNConfig(): Promise<CDNConfig | null> {
  if (cachedCDNConfig) {
    return cachedCDNConfig;
  }

  try {
    // Get the base URL from the current script's location
    const scripts = document.querySelectorAll('script[src*="ragstack-chat"]');
    let baseUrl = '';

    if (scripts.length > 0) {
      const scriptSrc = (scripts[0] as HTMLScriptElement).src;
      baseUrl = scriptSrc.substring(0, scriptSrc.lastIndexOf('/'));
    }

    const configUrl = baseUrl ? `${baseUrl}/config.json` : '/config.json';

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    const response = await fetch(configUrl, {
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      return null;
    }

    const config = await response.json();
    cachedCDNConfig = config;
    return config;
  } catch {
    return null;
  }
}

/**
 * Fetch theme configuration from the SAM GraphQL API
 *
 * @returns Promise<ThemeConfig | null> - Theme config or null if fetch fails
 */
export async function fetchThemeConfig(): Promise<ThemeConfig | null> {
  try {
    // Fetch CDN config to get API endpoint
    const cdnConfig = await fetchCDNConfig();

    if (!cdnConfig?.apiEndpoint || !cdnConfig?.identityPoolId || !cdnConfig?.region) {
      return null;
    }

    // Set up timeout to prevent hanging in poor network conditions
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const body = JSON.stringify({
      query: GET_THEME_CONFIG_QUERY,
    });

    // Use IAM auth for the request
    const response = await iamFetch(
      cdnConfig.apiEndpoint,
      body,
      cdnConfig.identityPoolId,
      cdnConfig.region,
      controller.signal
    );

    clearTimeout(timeoutId);

    if (!response.ok) {
      return null;
    }

    const result = await response.json();

    if (result.errors) {
      return null;
    }

    const themeData = result.data?.getThemeConfig;
    if (!themeData) {
      return null;
    }

    // Build theme config with overrides
    const themeOverrides: ThemeConfig['themeOverrides'] = {};
    if (themeData.primaryColor) themeOverrides.primaryColor = themeData.primaryColor;
    if (themeData.fontFamily) themeOverrides.fontFamily = themeData.fontFamily;
    if (themeData.spacing) themeOverrides.spacing = themeData.spacing;

    return {
      themePreset: themeData.themePreset || 'light',
      themeOverrides: Object.keys(themeOverrides).length > 0 ? themeOverrides : undefined,
    };
  } catch {
    return null;
  }
}
