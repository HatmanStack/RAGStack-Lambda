/**
 * Fetch theme configuration from the SAM AppSync API
 *
 * This utility fetches theme settings from the public getThemeConfig endpoint.
 * It uses the SAM stack's GraphQL API (not the Amplify API) because theme
 * config is stored in the SAM stack's DynamoDB table.
 *
 * The API endpoint and key are embedded at build time via inject-amplify-config.js
 */

import { THEME_API_CONFIG } from '../amplify-config.generated';

export interface ThemeConfig {
  themePreset: 'light' | 'dark' | 'brand';
  themeOverrides?: {
    primaryColor?: string;
    fontFamily?: string;
    spacing?: 'compact' | 'comfortable' | 'spacious';
  };
}

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
 * Fetch theme configuration from the SAM GraphQL API
 *
 * @returns Promise<ThemeConfig | null> - Theme config or null if fetch fails
 */
export async function fetchThemeConfig(): Promise<ThemeConfig | null> {
  try {
    console.log('[ThemeConfig] Fetching theme from SAM API...');

    // Check if theme API config is available
    if (!THEME_API_CONFIG?.endpoint || !THEME_API_CONFIG?.apiKey) {
      console.warn('[ThemeConfig] Theme API config not available, using defaults');
      return null;
    }

    // Set up timeout to prevent hanging in poor network conditions
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(THEME_API_CONFIG.endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': THEME_API_CONFIG.apiKey,
      },
      body: JSON.stringify({
        query: GET_THEME_CONFIG_QUERY,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      console.warn(`[ThemeConfig] API returned ${response.status}`);
      return null;
    }

    const result = await response.json();

    if (result.errors) {
      console.warn('[ThemeConfig] GraphQL errors:', result.errors);
      return null;
    }

    const themeData = result.data?.getThemeConfig;
    if (!themeData) {
      console.warn('[ThemeConfig] No theme data in response');
      return null;
    }

    console.log('[ThemeConfig] Theme loaded:', themeData);

    // Build theme config with overrides
    const themeOverrides: ThemeConfig['themeOverrides'] = {};
    if (themeData.primaryColor) themeOverrides.primaryColor = themeData.primaryColor;
    if (themeData.fontFamily) themeOverrides.fontFamily = themeData.fontFamily;
    if (themeData.spacing) themeOverrides.spacing = themeData.spacing;

    return {
      themePreset: themeData.themePreset || 'light',
      themeOverrides: Object.keys(themeOverrides).length > 0 ? themeOverrides : undefined,
    };
  } catch (err) {
    console.warn('[ThemeConfig] Failed to fetch theme configuration:', err);
    console.warn('[ThemeConfig] Falling back to default theme');
    return null;
  }
}
